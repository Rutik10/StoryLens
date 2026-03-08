import { useState, useCallback } from "react";
import Upload from "./components/Upload";
import Pipeline from "./components/Pipeline";
import VideoPlayer from "./components/VideoPlayer";
import LiveVoice from "./components/LiveVoice";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

const STEPS = [
  { id: "identify", label: "Identifying object..." },
  { id: "facts", label: "Fetching surprising facts..." },
  { id: "script", label: "Writing script + generating video (this takes 5–10 min)..." },
  { id: "veo", label: "Generating scenes with Veo 3.1..." },
  { id: "stitch", label: "Stitching final video..." },
];

export default function App() {
  const [screen, setScreen] = useState("upload"); // upload | pipeline | video
  const [stepStatus, setStepStatus] = useState({});
  const [veoProgress, setVeoProgress] = useState(0); // 0-5
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const setStep = useCallback((stepId, status) => {
    setStepStatus((prev) => ({ ...prev, [stepId]: status }));
  }, []);

  const handleUpload = useCallback(
    async (file) => {
      setError(null);
      setStepStatus({});
      setVeoProgress(0);
      setScreen("pipeline");

      try {
        // Step 1+2: Analyze
        setStep("identify", "running");
        const formData = new FormData();
        formData.append("image", file);

        const analyzeRes = await fetch(`${API_BASE}/analyze`, {
          method: "POST",
          body: formData,
        });

        if (!analyzeRes.ok) {
          const err = await analyzeRes.json().catch(() => ({ detail: analyzeRes.statusText }));
          throw new Error(err.detail || "Analysis failed");
        }

        const analyzeData = await analyzeRes.json();
        setStep("identify", "done");
        setStep("facts", "done");

        // Step 3-5: Generate
        setStep("script", "running");

        const genForm = new FormData();
        genForm.append("object_json", JSON.stringify(analyzeData.object));
        genForm.append("facts", analyzeData.facts);

        // Simulate Veo progress during generation (steps 4-5 are slow)
        let veoTick = 0;
        const veoInterval = setInterval(() => {
          veoTick++;
          if (veoTick <= 5) setVeoProgress(veoTick);
        }, 8000); // roughly 8s per scene

        const genRes = await fetch(`${API_BASE}/generate`, {
          method: "POST",
          body: genForm,
        });

        clearInterval(veoInterval);

        if (!genRes.ok) {
          const err = await genRes.json().catch(() => ({ detail: genRes.statusText }));
          throw new Error(err.detail || "Generation failed");
        }

        const genData = await genRes.json();

        setStep("script", "done");

        if (genData.veo_available) {
          setVeoProgress(5);
          setStep("veo", "done");
          setStep("stitch", "done");
        } else {
          setStep("veo", "skipped");
          setStep("stitch", "skipped");
        }

        setResult({
          object: analyzeData.object,
          facts: analyzeData.facts,
          script: genData.script,
          videoUrl: genData.video_url ? `${API_BASE}${genData.video_url}` : null,
          veoAvailable: genData.veo_available,
          message: genData.message,
        });

        setScreen("video");
      } catch (err) {
        console.error(err);
        setError(err.message || "Something went wrong");
        setScreen("upload");
      }
    },
    [setStep]
  );

  const handleSave = useCallback(async () => {
    if (!result) return;
    try {
      const form = new FormData();
      form.append("object_json", JSON.stringify(result.object));
      form.append("facts", result.facts);
      form.append("script_json", JSON.stringify(result.script));
      form.append("video_url", result.videoUrl || "");

      const res = await fetch(`${API_BASE}/save`, { method: "POST", body: form });
      const data = await res.json();
      if (data.notion_url) {
        window.open(data.notion_url, "_blank");
      } else {
        alert("Saved to Notion!");
      }
    } catch (err) {
      alert(`Save failed: ${err.message}`);
    }
  }, [result]);

  const handleReset = useCallback(() => {
    setScreen("upload");
    setResult(null);
    setError(null);
    setStepStatus({});
    setVeoProgress(0);
  }, []);

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 font-sans">
      {/* Header */}
      <header className="border-b border-zinc-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-amber-400 to-orange-600" />
          <span className="text-xl font-bold tracking-tight">OrdinaryEpic</span>
        </div>
        {screen !== "upload" && (
          <button
            onClick={handleReset}
            className="text-sm text-zinc-400 hover:text-zinc-200 transition-colors"
          >
            New story
          </button>
        )}
      </header>

      <main className="max-w-4xl mx-auto px-4 py-10">
        {error && (
          <div className="mb-6 rounded-lg bg-red-900/30 border border-red-700 px-4 py-3 text-red-300 text-sm">
            {error}
          </div>
        )}

        {screen === "upload" && <Upload onUpload={handleUpload} />}
        {screen === "pipeline" && (
          <Pipeline steps={STEPS} stepStatus={stepStatus} veoProgress={veoProgress} />
        )}
        {screen === "video" && result && (
          <div className="space-y-8">
            {/* Object title */}
            <div>
              <p className="text-xs uppercase tracking-widest text-amber-400 mb-1">
                OrdinaryEpic
              </p>
              <h1 className="text-4xl font-bold leading-tight">
                {result.object.object_name}
              </h1>
              <p className="text-zinc-400 mt-1 text-sm">
                {result.object.material} &middot; {result.object.estimated_age}
              </p>
            </div>

            {/* Video or Script fallback */}
            {result.videoUrl ? (
              <VideoPlayer src={result.videoUrl} />
            ) : (
              <ScriptFallback script={result.script} message={result.message} />
            )}

            {/* Facts */}
            <div className="bg-zinc-900 rounded-xl p-6 border border-zinc-800">
              <h2 className="text-lg font-semibold mb-4 text-amber-400">
                5 Verified Surprising Facts
              </h2>
              <div className="space-y-3 text-sm text-zinc-300 leading-relaxed whitespace-pre-line">
                {result.facts}
              </div>
            </div>

            {/* Script */}
            <div className="bg-zinc-900 rounded-xl p-6 border border-zinc-800">
              <h2 className="text-lg font-semibold mb-4 text-amber-400">
                Cinematic Script — Myth-Bust-Blow Arc
              </h2>
              <div className="space-y-4">
                {result.script.map((scene) => (
                  <div key={scene.scene_number} className="flex gap-4">
                    <div className="flex-none">
                      <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-amber-500/10 text-amber-400 text-xs font-bold">
                        {scene.scene_number}
                      </span>
                    </div>
                    <div>
                      <p className="text-xs text-zinc-500 uppercase tracking-wider mb-1">
                        {scene.emotional_beat.replace(/_/g, " ")}
                      </p>
                      <p className="text-sm text-zinc-200 italic leading-relaxed">
                        "{scene.narration}"
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Live Voice */}
            <LiveVoice
              apiBase={API_BASE}
              objectName={result.object.object_name}
              facts={result.facts}
            />

            {/* Save to Notion */}
            <div className="flex justify-end">
              <button
                onClick={handleSave}
                className="flex items-center gap-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 px-5 py-2.5 rounded-lg text-sm font-medium transition-colors border border-zinc-700"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M4.459 4.208c.746.606 1.026.56 2.428.466l13.215-.793c.28 0 .047-.28-.046-.326L17.86 1.968c-.42-.326-.981-.7-2.055-.607L3.01 2.295c-.466.046-.56.28-.374.466zm.793 3.08v13.904c0 .747.373 1.027 1.214.98l14.523-.84c.841-.046.935-.56.935-1.167V6.354c0-.606-.233-.933-.748-.887l-15.177.887c-.56.047-.747.327-.747.933zm14.337.745c.093.42 0 .84-.42.888l-.7.14v10.264c-.608.327-1.168.514-1.635.514-.748 0-.935-.234-1.495-.933l-4.577-7.186v6.952L12.21 19s0 .84-1.168.84l-3.222.186c-.093-.186 0-.653.327-.746l.84-.233V9.854L7.822 9.76c-.094-.42.14-1.026.793-1.073l3.456-.233 4.764 7.279v-6.44l-1.215-.14c-.093-.514.28-.887.747-.933zM1.936 1.035l13.31-.98c1.634-.14 2.055-.047 3.082.7l4.249 2.986c.7.513.934.653.934 1.213v16.378c0 1.026-.373 1.634-1.68 1.726l-15.458.934c-.98.047-1.448-.093-1.962-.747l-3.129-4.06c-.56-.747-.793-1.306-.793-1.96V2.667c0-.839.374-1.54 1.447-1.632z"/>
                </svg>
                Save to Notion
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

function ScriptFallback({ script, message }) {
  return (
    <div className="bg-zinc-900 rounded-xl p-6 border border-amber-700/40">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-2 h-2 rounded-full bg-amber-400" />
        <p className="text-amber-400 text-sm">{message}</p>
      </div>
      <div className="space-y-6">
        {script.map((scene) => (
          <div key={scene.scene_number} className="border-l-2 border-zinc-700 pl-4">
            <p className="text-xs text-zinc-500 uppercase tracking-wider mb-1">
              Scene {scene.scene_number} — {scene.emotional_beat.replace(/_/g, " ")}
            </p>
            <p className="text-zinc-200 italic mb-2">"{scene.narration}"</p>
            <p className="text-zinc-500 text-xs">
              Shot: {scene.veo_json.shot.type} &middot; {scene.veo_json.shot.camera}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

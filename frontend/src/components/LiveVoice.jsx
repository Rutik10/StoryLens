import { useState, useRef, useEffect, useCallback } from "react";

const WS_BASE = (import.meta.env.VITE_API_BASE || "http://localhost:8000")
  .replace(/^http/, "ws");

// Audio config: 16-bit PCM, 16kHz mono
const SAMPLE_RATE = 16000;
const CHUNK_DURATION_MS = 100;

export default function LiveVoice({ apiBase, objectName, facts }) {
  const [state, setState] = useState("idle"); // idle | connecting | active | error
  const [transcript, setTranscript] = useState([]);
  const [error, setError] = useState("");

  const wsRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioContextRef = useRef(null);
  const audioQueueRef = useRef([]);
  const isPlayingRef = useRef(false);

  // ----------------------------------------------------------------
  // Audio playback helpers
  // ----------------------------------------------------------------
  const playNextChunk = useCallback(() => {
    if (audioQueueRef.current.length === 0) {
      isPlayingRef.current = false;
      return;
    }
    isPlayingRef.current = true;
    const ctx = audioContextRef.current;
    if (!ctx) return;

    const pcmData = audioQueueRef.current.shift();
    // Convert 16-bit PCM bytes to float32
    const int16 = new Int16Array(pcmData.buffer, pcmData.byteOffset, pcmData.byteLength / 2);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) {
      float32[i] = int16[i] / 32768;
    }
    const audioBuffer = ctx.createBuffer(1, float32.length, SAMPLE_RATE);
    audioBuffer.getChannelData(0).set(float32);
    const source = ctx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(ctx.destination);
    source.onended = playNextChunk;
    source.start();
  }, []);

  const enqueueAudio = useCallback(
    (base64Data) => {
      const binary = atob(base64Data);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
      audioQueueRef.current.push(bytes);
      if (!isPlayingRef.current) playNextChunk();
    },
    [playNextChunk]
  );

  // ----------------------------------------------------------------
  // WebSocket + mic
  // ----------------------------------------------------------------
  const start = useCallback(async () => {
    setState("connecting");
    setTranscript([]);
    setError("");

    try {
      // Init AudioContext for playback
      audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)({
        sampleRate: SAMPLE_RATE,
      });

      // Connect WebSocket
      const ws = new WebSocket(`${WS_BASE}/live`);
      wsRef.current = ws;

      await new Promise((resolve, reject) => {
        ws.onopen = () => {
          // Send init payload
          ws.send(JSON.stringify({ object_name: objectName, facts }));
        };
        ws.onerror = (e) => reject(new Error("WebSocket connection failed"));

        ws.onmessage = (event) => {
          const msg = JSON.parse(event.data);
          if (msg.type === "ready") resolve();
          else if (msg.type === "error") reject(new Error(msg.message));
        };
      });

      setState("active");

      // Re-attach main message handler
      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === "audio") {
          enqueueAudio(msg.data);
        } else if (msg.type === "text") {
          setTranscript((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role === "assistant") {
              return [...prev.slice(0, -1), { role: "assistant", text: last.text + msg.data }];
            }
            return [...prev, { role: "assistant", text: msg.data }];
          });
        } else if (msg.type === "done") {
          // Response complete
        } else if (msg.type === "error") {
          setError(msg.message);
          setState("error");
        }
      };

      ws.onclose = () => {
        setState("idle");
      };

      // Start mic capture
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      const mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      mediaRecorderRef.current = mediaRecorder;

      // We'll convert audio chunks and send as PCM
      const audioCtx = new AudioContext({ sampleRate: SAMPLE_RATE });
      const source = audioCtx.createMediaStreamSource(stream);
      const processor = audioCtx.createScriptProcessor(4096, 1, 1);

      source.connect(processor);
      processor.connect(audioCtx.destination);

      processor.onaudioprocess = (e) => {
        if (ws.readyState !== WebSocket.OPEN) return;
        const float32 = e.inputBuffer.getChannelData(0);
        // Convert to 16-bit PCM
        const int16 = new Int16Array(float32.length);
        for (let i = 0; i < float32.length; i++) {
          const s = Math.max(-1, Math.min(1, float32[i]));
          int16[i] = s < 0 ? s * 32768 : s * 32767;
        }
        const b64 = btoa(String.fromCharCode(...new Uint8Array(int16.buffer)));
        ws.send(JSON.stringify({ type: "audio", data: b64 }));
      };

    } catch (err) {
      console.error("Live voice error:", err);
      setError(err.message || "Failed to start voice session");
      setState("error");
    }
  }, [objectName, facts, enqueueAudio]);

  const stop = useCallback(() => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "end" }));
      ws.close();
    }
    mediaRecorderRef.current?.stop();
    audioContextRef.current?.close();
    audioQueueRef.current = [];
    isPlayingRef.current = false;
    setState("idle");
  }, []);

  useEffect(() => {
    return () => stop();
  }, [stop]);

  const sendTextMessage = useCallback(
    (text) => {
      const ws = wsRef.current;
      if (ws && ws.readyState === WebSocket.OPEN) {
        setTranscript((prev) => [...prev, { role: "user", text }]);
        ws.send(JSON.stringify({ type: "text", data: text }));
      }
    },
    []
  );

  const [textInput, setTextInput] = useState("");

  const handleSendText = (e) => {
    e.preventDefault();
    if (textInput.trim() && state === "active") {
      sendTextMessage(textInput.trim());
      setTextInput("");
    }
  };

  return (
    <div className="bg-zinc-900 rounded-xl border border-zinc-800 overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-zinc-800 flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-zinc-100">Live Voice Q&amp;A</h3>
          <p className="text-xs text-zinc-500 mt-0.5">
            Ask the narrator anything about {objectName}
          </p>
        </div>

        {/* Status indicator */}
        <div className="flex items-center gap-2">
          {state === "active" && (
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-xs text-emerald-400">Live</span>
            </div>
          )}
          {state === "connecting" && (
            <div className="flex items-center gap-1.5">
              <svg className="w-3 h-3 animate-spin text-amber-400" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              <span className="text-xs text-amber-400">Connecting...</span>
            </div>
          )}
        </div>
      </div>

      <div className="p-6 space-y-4">
        {/* Error */}
        {error && (
          <div className="text-sm text-red-400 bg-red-900/20 border border-red-800 rounded-lg px-3 py-2">
            {error}
          </div>
        )}

        {/* Transcript */}
        {transcript.length > 0 && (
          <div className="space-y-3 max-h-48 overflow-y-auto pr-1">
            {transcript.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[85%] rounded-xl px-3 py-2 text-sm leading-relaxed
                    ${msg.role === "user"
                      ? "bg-amber-500/10 text-amber-100 border border-amber-500/20"
                      : "bg-zinc-800 text-zinc-200"
                    }
                  `}
                >
                  {msg.text}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Controls */}
        <div className="space-y-3">
          {/* Voice button */}
          <button
            onClick={state === "active" ? stop : start}
            disabled={state === "connecting"}
            className={`w-full py-3 rounded-xl font-medium text-sm transition-all active:scale-[0.98]
              ${state === "active"
                ? "bg-red-900/30 border border-red-700 text-red-400 hover:bg-red-900/50"
                : state === "connecting"
                ? "bg-zinc-800 text-zinc-500 cursor-not-allowed"
                : "bg-gradient-to-r from-amber-500 to-orange-600 text-white hover:from-amber-400 hover:to-orange-500 shadow-lg shadow-orange-900/20"
              }
            `}
          >
            {state === "active" ? (
              <span className="flex items-center justify-center gap-2">
                <span className="w-2 h-2 rounded-full bg-red-400 animate-pulse" />
                Stop voice session
              </span>
            ) : state === "connecting" ? (
              "Connecting to Gemini Live..."
            ) : (
              <span className="flex items-center justify-center gap-2">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                </svg>
                Start voice conversation
              </span>
            )}
          </button>

          {/* Text input (works in active state) */}
          {state === "active" && (
            <form onSubmit={handleSendText} className="flex gap-2">
              <input
                type="text"
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                placeholder="Or type a question..."
                className="flex-1 bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm
                  text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-amber-500/50"
              />
              <button
                type="submit"
                disabled={!textInput.trim()}
                className="px-4 py-2 bg-zinc-700 hover:bg-zinc-600 text-zinc-200 rounded-lg text-sm
                  transition-colors disabled:opacity-40"
              >
                Send
              </button>
            </form>
          )}

          {state === "idle" && (
            <p className="text-xs text-zinc-600 text-center">
              Talk to the documentary narrator using your microphone.
              Gemini Live responds in real time with voice.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

import { useEffect, useState } from "react";

const STATUS_CONFIG = {
  pending: { color: "text-zinc-600", bg: "bg-zinc-800", icon: null },
  running: { color: "text-amber-400", bg: "bg-amber-400/10", icon: "spinner" },
  done: { color: "text-emerald-400", bg: "bg-emerald-400/10", icon: "check" },
  skipped: { color: "text-zinc-500", bg: "bg-zinc-800", icon: "dash" },
};

function Spinner() {
  return (
    <svg
      className="w-4 h-4 animate-spin text-amber-400"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  );
}

function StepIcon({ icon }) {
  if (icon === "spinner") return <Spinner />;
  if (icon === "check")
    return (
      <svg className="w-4 h-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
      </svg>
    );
  if (icon === "dash")
    return <div className="w-3 h-0.5 bg-zinc-600 rounded" />;
  return <div className="w-2 h-2 rounded-full bg-zinc-700" />;
}

export default function Pipeline({ steps, stepStatus, veoProgress }) {
  const [dots, setDots] = useState("");
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const iv = setInterval(() => setDots((d) => (d.length >= 3 ? "" : d + ".")), 500);
    return () => clearInterval(iv);
  }, []);

  useEffect(() => {
    const iv = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(iv);
  }, []);

  const currentStep = steps.find(
    (s) => stepStatus[s.id] === "running"
  );

  return (
    <div className="flex flex-col items-center gap-10">
      {/* Animated headline */}
      <div className="text-center space-y-2">
        <h2 className="text-3xl font-bold">
          {currentStep
            ? currentStep.label.replace("...", dots)
            : "Processing your epic story"}
        </h2>
        <p className="text-zinc-500 text-sm">{elapsed}s elapsed</p>
      </div>

      {/* Pulsing orb */}
      <div className="relative flex items-center justify-center">
        <div className="absolute w-36 h-36 rounded-full bg-amber-500/10 animate-ping" />
        <div className="absolute w-24 h-24 rounded-full bg-amber-500/20 animate-pulse" />
        <div className="w-16 h-16 rounded-full bg-gradient-to-br from-amber-400 to-orange-600 shadow-xl shadow-orange-900/50" />
      </div>

      {/* Steps */}
      <div className="w-full max-w-md space-y-3">
        {steps.map((step) => {
          const status = stepStatus[step.id] || "pending";
          const config = STATUS_CONFIG[status];

          return (
            <div
              key={step.id}
              className={`flex items-center gap-3 rounded-xl px-4 py-3 border transition-all duration-500
                ${status === "running" ? "border-amber-500/30 bg-amber-500/5" : "border-zinc-800 bg-zinc-900"}
              `}
            >
              <div className={`flex-none w-6 h-6 rounded-full ${config.bg} flex items-center justify-center`}>
                <StepIcon icon={config.icon} />
              </div>
              <div className="flex-1">
                <p className={`text-sm font-medium ${config.color}`}>
                  {step.id === "veo" && status === "running"
                    ? `Generating scenes with Veo 3.1... (${veoProgress}/5)`
                    : step.label}
                </p>
              </div>
              {step.id === "veo" && (status === "running" || status === "done") && (
                <div className="flex-none flex gap-1">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <div
                      key={i}
                      className={`w-2 h-2 rounded-full transition-all duration-300 ${
                        i < (status === "done" ? 5 : veoProgress)
                          ? "bg-amber-400"
                          : "bg-zinc-700"
                      }`}
                    />
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <p className="text-zinc-600 text-xs text-center max-w-xs">
        Veo 3.1 generates 10-second cinematic clips in parallel.
        This typically takes 2–3 minutes for all 5 scenes.
      </p>
    </div>
  );
}

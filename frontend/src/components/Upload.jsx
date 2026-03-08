import { useState, useRef, useCallback } from "react";

const DEMO_HINTS = [
  { label: "Stapler", emoji: "📎", hint: "Try: stapler.jpg" },
  { label: "Coffee Cup", emoji: "☕", hint: "Try: coffee_cup.jpg" },
  { label: "Paper Clip", emoji: "🖇️", hint: "Try: paper_clip.jpg" },
];

export default function Upload({ onUpload }) {
  const [dragging, setDragging] = useState(false);
  const [preview, setPreview] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const inputRef = useRef(null);

  const handleFile = useCallback((file) => {
    if (!file || !file.type.startsWith("image/")) return;
    setSelectedFile(file);
    const url = URL.createObjectURL(file);
    setPreview(url);
  }, []);

  const handleDrop = useCallback(
    (e) => {
      e.preventDefault();
      setDragging(false);
      const file = e.dataTransfer.files?.[0];
      handleFile(file);
    },
    [handleFile]
  );

  const handleDragOver = (e) => {
    e.preventDefault();
    setDragging(true);
  };

  const handleDragLeave = () => setDragging(false);

  const handleChange = (e) => {
    handleFile(e.target.files?.[0]);
  };

  const handleSubmit = () => {
    if (selectedFile) onUpload(selectedFile);
  };

  return (
    <div className="flex flex-col items-center gap-10">
      {/* Hero text */}
      <div className="text-center space-y-3 max-w-xl">
        <h2 className="text-5xl font-bold leading-tight tracking-tight">
          Every object has a{" "}
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-amber-400 to-orange-500">
            secret story.
          </span>
        </h2>
        <p className="text-zinc-400 text-lg">
          Upload a photo of any everyday object. We'll find the facts that will change
          how you see it — forever.
        </p>
      </div>

      {/* Drop zone */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => !preview && inputRef.current?.click()}
        className={`relative w-full max-w-lg rounded-2xl border-2 border-dashed transition-all cursor-pointer
          ${dragging
            ? "border-amber-400 bg-amber-400/5"
            : preview
            ? "border-zinc-700 cursor-default"
            : "border-zinc-700 hover:border-zinc-500 hover:bg-zinc-900/50"
          }
        `}
        style={{ minHeight: 280 }}
      >
        {preview ? (
          <div className="relative">
            <img
              src={preview}
              alt="Preview"
              className="w-full rounded-xl object-cover max-h-72"
            />
            <button
              onClick={(e) => {
                e.stopPropagation();
                setPreview(null);
                setSelectedFile(null);
              }}
              className="absolute top-2 right-2 w-7 h-7 rounded-full bg-zinc-900/80 flex items-center justify-center text-zinc-300 hover:text-white"
            >
              ×
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center gap-3 p-12 text-center">
            <div className="w-14 h-14 rounded-full bg-zinc-800 flex items-center justify-center">
              <svg
                className="w-7 h-7 text-zinc-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                />
              </svg>
            </div>
            <div>
              <p className="text-zinc-300 font-medium">Drop a photo here</p>
              <p className="text-zinc-500 text-sm mt-1">or click to browse</p>
            </div>
            <p className="text-zinc-600 text-xs">JPG, PNG, WEBP up to 20MB</p>
          </div>
        )}

        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          onChange={handleChange}
          className="hidden"
        />
      </div>

      {/* CTA */}
      {selectedFile && (
        <button
          onClick={handleSubmit}
          className="w-full max-w-lg py-3.5 rounded-xl bg-gradient-to-r from-amber-500 to-orange-600
            hover:from-amber-400 hover:to-orange-500 text-white font-semibold text-base
            transition-all shadow-lg shadow-orange-900/30 active:scale-[0.98]"
        >
          Reveal the epic story
        </button>
      )}

      {/* Demo hints */}
      <div className="w-full max-w-lg">
        <p className="text-xs text-zinc-600 text-center mb-3 uppercase tracking-widest">
          Instant demo objects
        </p>
        <div className="grid grid-cols-3 gap-3">
          {DEMO_HINTS.map((demo) => (
            <div
              key={demo.label}
              className="rounded-lg bg-zinc-900 border border-zinc-800 px-3 py-2.5 text-center"
            >
              <div className="text-2xl mb-1">{demo.emoji}</div>
              <p className="text-zinc-300 text-sm font-medium">{demo.label}</p>
              <p className="text-zinc-600 text-xs mt-0.5">{demo.hint}</p>
            </div>
          ))}
        </div>
        <p className="text-xs text-zinc-600 text-center mt-3">
          Name your file with the object name to get instant cached results
        </p>
      </div>
    </div>
  );
}

import { useRef, useState, useEffect } from "react";

export default function VideoPlayer({ src, audioSrc }) {
  const videoRef = useRef(null);
  const audioRef = useRef(null);
  const [playing, setPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [duration, setDuration] = useState(0);
  const [muted, setMuted] = useState(false);

  useEffect(() => {
    const video = videoRef.current;
    const audio = audioRef.current;
    if (!video) return;
    video.play().then(() => {
      if (audio) {
        audio.currentTime = video.currentTime;
        audio.play().catch(() => {});
      }
    }).catch(() => {});
  }, [src, audioSrc]);

  const syncAudioToVideo = () => {
    const video = videoRef.current;
    const audio = audioRef.current;
    if (!video || !audio) return;
    if (Math.abs(audio.currentTime - video.currentTime) > 0.35) {
      audio.currentTime = video.currentTime;
    }
  };

  const toggle = () => {
    const video = videoRef.current;
    const audio = audioRef.current;
    if (!video) return;
    if (video.paused) {
      video.play();
      if (audio) {
        audio.currentTime = video.currentTime;
        audio.play().catch(() => {});
      }
      setPlaying(true);
    } else {
      video.pause();
      if (audio) audio.pause();
      setPlaying(false);
    }
  };

  const handleTimeUpdate = () => {
    const video = videoRef.current;
    if (!video || !video.duration) return;
    syncAudioToVideo();
    setProgress((video.currentTime / video.duration) * 100);
  };

  const handleLoadedMetadata = () => {
    const video = videoRef.current;
    if (video) setDuration(video.duration);
  };

  const handlePlay = () => {
    const video = videoRef.current;
    const audio = audioRef.current;
    if (audio && video) {
      audio.currentTime = video.currentTime;
      audio.play().catch(() => {});
    }
    setPlaying(true);
  };

  const handlePause = () => {
    const audio = audioRef.current;
    if (audio) audio.pause();
    setPlaying(false);
  };

  const handleSeek = (e) => {
    const video = videoRef.current;
    const audio = audioRef.current;
    if (!video) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    video.currentTime = pct * video.duration;
    if (audio) audio.currentTime = video.currentTime;
  };

  const toggleMute = () => {
    const audio = audioRef.current;
    const nextMuted = !muted;
    if (audio) audio.muted = nextMuted;
    setMuted(nextMuted);
  };

  const formatTime = (s) => {
    if (!s || isNaN(s)) return "0:00";
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60).toString().padStart(2, "0");
    return `${m}:${sec}`;
  };

  return (
    <div className="rounded-2xl overflow-hidden bg-zinc-900 border border-zinc-800 shadow-2xl shadow-black/50">
      <audio ref={audioRef} src={audioSrc || undefined} preload="auto" />

      <div className="relative group cursor-pointer" onClick={toggle}>
        <video
          ref={videoRef}
          src={src}
          className="w-full max-h-[480px] object-contain bg-black"
          onTimeUpdate={handleTimeUpdate}
          onLoadedMetadata={handleLoadedMetadata}
          onPlay={handlePlay}
          onPause={handlePause}
          playsInline
        />

        <div
          className={`absolute inset-0 flex items-center justify-center transition-opacity duration-200
            ${playing ? "opacity-0 group-hover:opacity-100" : "opacity-100"}
          `}
        >
          <div className="w-16 h-16 rounded-full bg-black/50 backdrop-blur flex items-center justify-center">
            {playing ? (
              <svg className="w-7 h-7 text-white" fill="currentColor" viewBox="0 0 24 24">
                <path d="M6 19h4V5H6zm8-14v14h4V5z" />
              </svg>
            ) : (
              <svg className="w-7 h-7 text-white ml-1" fill="currentColor" viewBox="0 0 24 24">
                <path d="M8 5v14l11-7z" />
              </svg>
            )}
          </div>
        </div>
      </div>

      <div className="px-4 py-3 space-y-2">
        <div className="w-full h-1.5 bg-zinc-700 rounded-full cursor-pointer" onClick={handleSeek}>
          <div
            className="h-full bg-gradient-to-r from-amber-400 to-orange-500 rounded-full transition-all"
            style={{ width: `${progress}%` }}
          />
        </div>

        <div className="flex items-center justify-between text-xs text-zinc-500">
          <div className="flex items-center gap-3">
            <button onClick={toggle} className="text-zinc-300 hover:text-white transition-colors">
              {playing ? (
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M6 19h4V5H6zm8-14v14h4V5z" />
                </svg>
              ) : (
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M8 5v14l11-7z" />
                </svg>
              )}
            </button>

            <button onClick={toggleMute} className="text-zinc-300 hover:text-white transition-colors">
              {muted ? (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2" />
                </svg>
              ) : (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M15.536 8.464a5 5 0 010 7.072M12 6v12m0 0l-4-4m4 4l4-4M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
                </svg>
              )}
            </button>

            <span>{formatTime((progress / 100) * duration)}</span>
            <span>/</span>
            <span>{formatTime(duration)}</span>
          </div>

          <div className="flex items-center gap-2">
            {audioSrc && <span className="text-amber-400">Narration synced</span>}
            <a
              href={src}
              download="ordinaryepic_story.mp4"
              className="text-zinc-400 hover:text-zinc-200 transition-colors"
              title="Download video"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}

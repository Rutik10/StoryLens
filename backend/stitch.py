"""
stitch.py — FFmpeg video stitching
Concatenates scene_1.mp4 through scene_5.mp4 into final_video.mp4.
"""

import os
import asyncio
import logging
import tempfile
import time
from pathlib import Path

logger = logging.getLogger(__name__)


async def stitch_clips(clip_paths: list[str], output_dir: str) -> str:
    """
    Concatenate video clips into a single final video using FFmpeg.

    Args:
        clip_paths: Ordered list of mp4 file paths
        output_dir: Directory to write final_video.mp4

    Returns:
        Path to the final stitched video
    """
    if not clip_paths:
        raise ValueError("No clips provided for stitching")

    # Verify all clips exist
    for p in clip_paths:
        if not Path(p).exists():
            raise FileNotFoundError(f"Clip not found: {p}")

    timestamp = int(time.time())
    final_path = Path(output_dir) / f"final_video_{timestamp}.mp4"

    # Build FFmpeg concat list file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, dir=output_dir
    ) as concat_file:
        concat_path = concat_file.name
        for clip in clip_paths:
            # FFmpeg concat demuxer requires absolute or relative paths with proper escaping
            abs_clip = str(Path(clip).resolve())
            concat_file.write(f"file '{abs_clip}'\n")

    logger.info(f"Stitching {len(clip_paths)} clips → {final_path}")

    cmd = [
        "ffmpeg",
        "-y",                          # overwrite output
        "-f", "concat",
        "-safe", "0",
        "-i", concat_path,
        "-c", "copy",                  # stream copy — no re-encode for speed
        str(final_path),
    ]

    logger.info(f"FFmpeg command: {' '.join(cmd)}")

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    # Clean up concat list
    try:
        Path(concat_path).unlink()
    except Exception:
        pass

    if proc.returncode != 0:
        err_msg = stderr.decode("utf-8", errors="replace")
        logger.error(f"FFmpeg failed (code {proc.returncode}):\n{err_msg}")
        raise RuntimeError(f"FFmpeg stitching failed: {err_msg[-500:]}")

    if not final_path.exists():
        raise RuntimeError("FFmpeg completed but output file not found")

    file_size_mb = final_path.stat().st_size / (1024 * 1024)
    logger.info(f"Stitched video: {final_path} ({file_size_mb:.1f} MB)")
    return str(final_path)


async def get_video_duration(video_path: str) -> float:
    """Get video duration in seconds using ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    try:
        return float(stdout.decode().strip())
    except ValueError:
        return 0.0

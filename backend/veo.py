"""
veo.py — Veo 3.1 video generation via Vertex AI (google-genai SDK)
Generates a single 8-second video from a prompt string.
"""

import os
import time
import asyncio
import logging
from pathlib import Path

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

VEO_MODEL = "veo-3.1-generate-preview"


def _get_client() -> genai.Client:
    return genai.Client(
        vertexai=True,
        project=os.getenv("GOOGLE_CLOUD_PROJECT"),
        location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
    )


async def generate_video(prompt: str, output_dir: str,
                         poll_interval: int = 15, max_wait: int = 600) -> str:
    """
    Generate a single 8-second video from a prompt string.
    Returns the local path to the saved MP4.
    """
    client = _get_client()
    logger.info(f"Submitting to Veo (8s): {prompt[:100]}...")

    operation = client.models.generate_videos(
        model=VEO_MODEL,
        prompt=prompt,
        config=types.GenerateVideosConfig(
            aspect_ratio="16:9",
            duration_seconds=8,
            number_of_videos=1,
            generate_audio=True,
        ),
    )

    def _is_done(op) -> bool:
        done = getattr(op, "done", False)
        if callable(done):
            try:
                done = done()
            except TypeError:
                pass
        return bool(done)

    elapsed = 0
    operation_name = getattr(operation, "name", None)
    while not _is_done(operation):
        if elapsed >= max_wait:
            raise TimeoutError(f"Veo timed out after {max_wait}s")
        logger.info(f"Waiting for Veo... ({elapsed}s elapsed)")
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
        if operation_name:
            try:
                operation = client.operations.get(name=operation_name)
            except Exception:
                try:
                    operation = client.operations.get(operation_name)
                except Exception:
                    operation = client.operations.get(operation)
        else:
            operation = client.operations.get(operation)

    if operation.error:
        raise RuntimeError(f"Veo error: {operation.error}")

    result = getattr(operation, "result", None)
    if callable(result):
        try:
            result = result()
        except TypeError:
            pass
    if not result:
        result = getattr(operation, "response", None)

    generated = getattr(result, "generated_videos", None) or getattr(result, "videos", None)
    if not generated:
        logger.warning("Veo returned no video. operation=%r result=%r", operation, result)
        raise RuntimeError("Veo returned no video")

    first = generated[0]
    video = getattr(first, "video", None) or first
    video_uri = getattr(video, "uri", None)
    video_bytes = getattr(video, "video_bytes", None) or getattr(video, "bytes", None)

    if video_uri:
        # Large video written to GCS — download it
        from google.cloud import storage
        without_prefix = video_uri[len("gs://"):]
        bucket_name, blob_path = without_prefix.split("/", 1)
        gcs_client = storage.Client()
        blob = gcs_client.bucket(bucket_name).blob(blob_path)
        output_path = Path(output_dir) / f"video_{int(time.time())}.mp4"
        blob.download_to_filename(str(output_path))
    elif video_bytes:
        output_path = Path(output_dir) / f"video_{int(time.time())}.mp4"
        output_path.write_bytes(video_bytes)
    else:
        raise RuntimeError("Veo returned empty video bytes and no URI")

    logger.info(f"Video saved → {output_path} ({output_path.stat().st_size // 1024}KB)")
    return str(output_path)

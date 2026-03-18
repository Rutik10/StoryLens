"""
veo.py - Veo 2 video generation and extension via Vertex AI.
"""

import asyncio
import logging
import os
import time
import uuid
from pathlib import Path

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

VEO_MODEL = os.getenv("VEO_MODEL", "veo-3.1-fast-generate-preview")
VEO_OUTPUT_GCS_URI = os.getenv("VEO_OUTPUT_GCS_URI", "").strip()
ANCHOR_DURATION_SECONDS = 8
EXTENSION_SEGMENTS = 3


def _get_client() -> genai.Client:
    return genai.Client(
        vertexai=True,
        project=os.getenv("GOOGLE_CLOUD_PROJECT"),
        location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
    )


def _require_output_gcs_uri() -> str:
    if not VEO_OUTPUT_GCS_URI.startswith("gs://"):
        raise RuntimeError("Set VEO_OUTPUT_GCS_URI to a writable gs:// bucket/prefix for Veo 2 generation.")
    return VEO_OUTPUT_GCS_URI.rstrip("/") + "/"


def _unique_gcs_prefix() -> str:
    return f"{_require_output_gcs_uri()}{int(time.time())}_{uuid.uuid4().hex[:8]}/"


def _is_done(op) -> bool:
    done = getattr(op, "done", False)
    if callable(done):
        try:
            done = done()
        except TypeError:
            pass
    return bool(done)


async def _wait_for_operation(client: genai.Client, operation, poll_interval: int, max_wait: int):
    elapsed = 0
    operation_name = getattr(operation, "name", None)
    while not _is_done(operation):
        if elapsed >= max_wait:
            raise TimeoutError(f"Veo timed out after {max_wait}s")
        logger.info("Waiting for Veo... (%ss elapsed)", elapsed)
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
    return operation


def _extract_video_uri(result) -> str:
    generated = getattr(result, "generated_videos", None) or getattr(result, "videos", None)
    if not generated:
        raise RuntimeError("Veo returned no video")
    first = generated[0]
    video = getattr(first, "video", None) or first
    video_uri = getattr(video, "uri", None)
    if not video_uri:
        raise RuntimeError("Veo returned no GCS video URI")
    return video_uri


def _download_gcs_video(video_uri: str, output_dir: str) -> str:
    from google.cloud import storage

    without_prefix = video_uri[len("gs://"):]
    bucket_name, blob_path = without_prefix.split("/", 1)
    gcs_client = storage.Client()
    blob = gcs_client.bucket(bucket_name).blob(blob_path)
    output_path = Path(output_dir) / f"video_{int(time.time())}.mp4"
    blob.download_to_filename(str(output_path))
    logger.info("Video saved -> %s", output_path)
    return str(output_path)


async def _generate_anchor(
    client: genai.Client,
    prompt: str,
    poll_interval: int,
    max_wait: int,
) -> str:
    logger.info("Submitting anchor Veo clip (%ss)", ANCHOR_DURATION_SECONDS)
    operation = client.models.generate_videos(
        model=VEO_MODEL,
        prompt=prompt,
        config=types.GenerateVideosConfig(
            aspect_ratio="16:9",
            duration_seconds=ANCHOR_DURATION_SECONDS,
            number_of_videos=1,
            generate_audio=False,
            output_gcs_uri=_unique_gcs_prefix(),
        ),
    )
    operation = await _wait_for_operation(client, operation, poll_interval, max_wait)
    result = getattr(operation, "result", None)
    if callable(result):
        result = result()
    if not result:
        result = getattr(operation, "response", None)
    return _extract_video_uri(result)


async def _extend_video(
    client: genai.Client,
    video_uri: str,
    prompt: str,
    poll_interval: int,
    max_wait: int,
) -> str:
    logger.info("Extending Veo clip from %s", video_uri)
    operation = client.models.generate_videos(
        model=VEO_MODEL,
        prompt=prompt,
        video=types.Video(uri=video_uri, mime_type="video/mp4"),
        config=types.GenerateVideosConfig(
            aspect_ratio="16:9",
            number_of_videos=1,
            generate_audio=False,
            output_gcs_uri=_unique_gcs_prefix(),
        ),
    )
    operation = await _wait_for_operation(client, operation, poll_interval, max_wait)
    result = getattr(operation, "result", None)
    if callable(result):
        result = result()
    if not result:
        result = getattr(operation, "response", None)
    return _extract_video_uri(result)


async def generate_video(
    prompt: str,
    output_dir: str,
    extension_prompts: list[str] | None = None,
    poll_interval: int = 15,
    max_wait: int = 900,
) -> str:
    """
    Generate an anchor clip and extend it with Veo 2 to produce a continuous long video.
    """
    _require_output_gcs_uri()
    client = _get_client()

    current_video_uri = await _generate_anchor(client, prompt, poll_interval, max_wait)

    prompts = extension_prompts or []
    for index in range(min(len(prompts), EXTENSION_SEGMENTS)):
        current_video_uri = await _extend_video(
            client,
            current_video_uri,
            prompts[index],
            poll_interval,
            max_wait,
        )

    return _download_gcs_video(current_video_uri, output_dir)

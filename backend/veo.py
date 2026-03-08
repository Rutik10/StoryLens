"""
veo.py — Veo 3.0 video generation via Vertex AI (google-genai SDK)
Builds prompts and generates all 5 scenes in parallel.
"""

import os
import time
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

VEO_MODEL = "veo-3.0-generate-preview"

MOOD_MAP = {
    "false_familiarity": "calm and contemplative",
    "misconception": "slightly unsettling, questioning",
    "tension": "tense, suspenseful",
    "reveal": "dramatic, awe-inspiring",
    "reframe": "philosophical, quietly profound",
}


def _get_client() -> genai.Client:
    return genai.Client(
        vertexai=True,
        project=os.getenv("GOOGLE_CLOUD_PROJECT"),
        location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
    )


def build_veo_prompt(scene: dict, obj_data: dict) -> str:
    """Build a natural-language prompt for Veo from a scene dict."""
    object_name = obj_data.get("object_name", "object")
    emotional_beat = scene.get("emotional_beat", "reveal")
    mood = MOOD_MAP.get(emotional_beat, "cinematic")
    veo_json = scene.get("veo_json", {})
    shot = veo_json.get("shot", {})
    narration = scene.get("narration", "")

    return (
        f"Cinematic documentary. "
        f"{shot.get('type', 'close-up')} shot of a {object_name}. "
        f"{shot.get('framing', '')}. "
        f"Camera move: {shot.get('camera', 'slow push-in')}. "
        f"Action: {veo_json.get('action', '')}. "
        f"Setting: {veo_json.get('environment', '')}. "
        f"Lighting: {veo_json.get('lighting', 'dramatic side light')}. "
        f"Mood: {mood}. Color grade: desaturated with warm highlights. "
        f"Audio: {veo_json.get('audio', 'low cinematic drone')}. "
        f"Narration context: {narration}"
    ).strip()


def _generate_one_clip_sync(
    scene: dict,
    obj_data: dict,
    output_dir: str,
    scene_index: int,
    poll_interval: int = 15,
    max_wait: int = 600,
) -> str:
    """
    Generate a single video clip via Veo on Vertex AI (synchronous, polls until done).
    Returns path to saved mp4 file.
    """
    client = _get_client()
    prompt = build_veo_prompt(scene, obj_data)
    duration = 6  # Veo supported durations: 4, 6, 8 seconds

    logger.info(f"Scene {scene_index + 1}: submitting to Veo ({duration}s)...")

    operation = client.models.generate_videos(
        model=VEO_MODEL,
        prompt=prompt,
        config=types.GenerateVideosConfig(
            aspect_ratio="16:9",
            duration_seconds=duration,
            number_of_videos=1,
        ),
    )

    # Poll until the long-running operation completes
    elapsed = 0
    while not operation.done:
        if elapsed >= max_wait:
            raise TimeoutError(f"Scene {scene_index + 1} timed out after {max_wait}s")
        logger.info(f"Scene {scene_index + 1}: waiting... ({elapsed}s elapsed)")
        time.sleep(poll_interval)
        elapsed += poll_interval
        operation = client.operations.get(operation)

    if operation.error:
        raise RuntimeError(f"Scene {scene_index + 1} Veo error: {operation.error}")

    generated = operation.result.generated_videos
    if not generated:
        raise RuntimeError(f"Scene {scene_index + 1}: no video returned")

    video_bytes = generated[0].video.video_bytes
    if not video_bytes:
        raise RuntimeError(f"Scene {scene_index + 1}: empty video bytes")

    output_path = Path(output_dir) / f"scene_{scene_index + 1}.mp4"
    output_path.write_bytes(video_bytes)

    logger.info(f"Scene {scene_index + 1} saved → {output_path} ({len(video_bytes) // 1024}KB)")
    return str(output_path)


async def generate_all_scenes(
    scenes: list[dict],
    obj_data: dict,
    output_dir: str,
) -> list[str]:
    """
    Generate all 5 video clips in parallel using ThreadPoolExecutor.
    Returns ordered list of mp4 file paths.
    """
    results: dict[int, str] = {}
    errors: dict[int, Exception] = {}

    def generate_with_retry(scene, index, max_retries=2):
        for attempt in range(max_retries + 1):
            try:
                return index, _generate_one_clip_sync(scene, obj_data, output_dir, index)
            except Exception as e:
                if attempt < max_retries:
                    wait = 10 * (attempt + 1)
                    logger.warning(f"Scene {index + 1} attempt {attempt + 1} failed: {e}. Retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    return index, e

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(generate_with_retry, scene, i)
            for i, scene in enumerate(scenes)
        ]
        for future in as_completed(futures):
            index, result = future.result()
            if isinstance(result, Exception):
                errors[index] = result
                logger.error(f"Scene {index + 1} failed permanently: {result}")
            else:
                results[index] = result

    if errors:
        failed = [str(e) for e in errors.values()]
        raise RuntimeError(f"Failed to generate {len(errors)} scene(s): {'; '.join(failed)}")

    return [results[i] for i in sorted(results.keys())]

"""
veo.py — Veo 3.1 video generation via Vertex AI
Builds JSON prompts and generates all 5 scenes in parallel.
"""

import os
import json
import time
import logging
import asyncio
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

MOOD_MAP = {
    "false_familiarity": "calm and contemplative",
    "misconception": "slightly unsettling, questioning",
    "tension": "tense, suspenseful",
    "reveal": "dramatic, awe-inspiring",
    "reframe": "philosophical, quietly profound",
}


def build_veo_prompt(scene: dict, obj_data: dict) -> dict:
    """
    Build a full Veo 3.1 JSON prompt from a scene dict.

    Args:
        scene: Scene dict with veo_json and emotional_beat
        obj_data: Object metadata from vision.py

    Returns:
        Veo 3.1 prompt dict
    """
    object_name = obj_data.get("object_name", "object")
    emotional_beat = scene.get("emotional_beat", "reveal")
    mood = MOOD_MAP.get(emotional_beat, "cinematic")
    veo_json = scene.get("veo_json", {})

    return {
        "version": "veo-3.1",
        "output": {
            "duration_sec": int(veo_json.get("duration_sec", 10)),
            "fps": 24,
            "resolution": "1080p",
        },
        "global_style": {
            "look": "cinematic documentary",
            "color": "desaturated with warm highlights",
            "mood": mood,
            "safety": "safe",
        },
        "continuity": {
            "props": [object_name],
            "lighting": "dramatic side light throughout",
        },
        "narration": scene.get("narration", ""),
        "scenes": [veo_json],
    }


def _generate_one_clip_sync(
    scene: dict,
    obj_data: dict,
    output_dir: str,
    scene_index: int,
) -> str:
    """
    Generate a single video clip via Vertex AI Veo 3.1 (synchronous).
    Returns path to saved mp4 file.
    """
    import vertexai
    from vertexai.preview.vision_models import VideoGenerationModel

    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

    if not project:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT not set")

    vertexai.init(project=project, location=location)

    veo_prompt = build_veo_prompt(scene, obj_data)
    prompt_str = json.dumps(veo_prompt)

    logger.info(f"Generating scene {scene_index + 1} with Veo 3.1...")

    model = VideoGenerationModel.from_pretrained("veo-3.1-generate-preview")

    video = model.generate_video(
        prompt=prompt_str,
        duration_seconds=int(veo_prompt["output"]["duration_sec"]),
        aspect_ratio="16:9",
        output_resolution="1080p",
    )

    output_path = Path(output_dir) / f"scene_{scene_index + 1}.mp4"

    # Save the video — SDK returns bytes or a file-like object
    if hasattr(video, "video"):
        video_data = video.video
    else:
        video_data = video

    if hasattr(video_data, "save"):
        video_data.save(str(output_path))
    elif hasattr(video_data, "_video_bytes"):
        output_path.write_bytes(video_data._video_bytes)
    else:
        # Fallback: assume it's bytes-like
        output_path.write_bytes(bytes(video_data))

    logger.info(f"Scene {scene_index + 1} saved to {output_path}")
    return str(output_path)


async def generate_all_scenes(
    scenes: list[dict],
    obj_data: dict,
    output_dir: str,
) -> list[str]:
    """
    Generate all 5 video clips in parallel using ThreadPoolExecutor.

    Args:
        scenes: List of 5 scene dicts from script.py
        obj_data: Object metadata
        output_dir: Directory to save mp4 files

    Returns:
        Ordered list of mp4 file paths [scene_1.mp4 ... scene_5.mp4]
    """
    loop = asyncio.get_event_loop()
    results: dict[int, str] = {}
    errors: dict[int, Exception] = {}

    def generate_with_retry(scene, index, max_retries=2):
        for attempt in range(max_retries + 1):
            try:
                return index, _generate_one_clip_sync(scene, obj_data, output_dir, index)
            except Exception as e:
                if attempt < max_retries:
                    wait = 5 * (attempt + 1)
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
                logger.error(f"Scene {index + 1} failed: {result}")
            else:
                results[index] = result

    if errors:
        failed = [str(e) for e in errors.values()]
        raise RuntimeError(f"Failed to generate {len(errors)} scene(s): {'; '.join(failed)}")

    # Return in order
    return [results[i] for i in sorted(results.keys())]

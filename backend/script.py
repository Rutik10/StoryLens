"""
script.py — Cinematic script generation using Myth-Bust-Blow narrative arc.
Generates a 5-scene script as a structured JSON array.
"""

import os
import json
import re
import logging
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

SCRIPT_MODEL = "gemini-2.0-flash-exp"

SCRIPT_PROMPT_TEMPLATE = """You are a cinematic documentary scriptwriter.
Create a 5-scene script about: {object_name}

Object context:
{object_context}

Verified facts to weave in:
{facts}

Follow the Myth-Bust-Blow narrative arc EXACTLY:
- Scene 1: emotional_beat = "false_familiarity" (start with the ordinary, what everyone thinks they know)
- Scene 2: emotional_beat = "misconception" (expose the common misconception)
- Scene 3: emotional_beat = "tension" (build suspense, hint at the reveal)
- Scene 4: emotional_beat = "reveal" (THE most surprising fact, most dramatic moment)
- Scene 5: emotional_beat = "reframe" (change how we see the object forever; end with ONE unanswered question)

Return ONLY a valid JSON array (no markdown, no explanation):
[
  {{
    "scene_number": 1,
    "narration": "voiceover text, max 2 sentences, cinematic and specific",
    "emotional_beat": "false_familiarity",
    "veo_json": {{
      "shot": {{
        "type": "extreme close-up|close-up|medium|wide|aerial",
        "framing": "describe exact framing",
        "camera": "camera move e.g. slow push-in, pan left, static"
      }},
      "action": "what happens visually in this shot",
      "environment": "setting description",
      "lighting": "specific lighting description",
      "audio": "ambient sound + music tone",
      "duration_sec": 10
    }}
  }},
  ... (5 scenes total)
]

Make narration poetic, precise, and surprising. Each scene must feel like a different visual world."""


def _get_client() -> genai.Client:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY not set in environment")
    return genai.Client(api_key=api_key)


async def generate_script(obj_data: dict, facts: str) -> list[dict]:
    """
    Generate a 5-scene Myth-Bust-Blow script using Gemini.

    Args:
        obj_data: Structured object metadata from vision.py
        facts: Facts string from facts.py

    Returns:
        List of 5 scene dicts with narration, emotional_beat, and veo_json
    """
    client = _get_client()

    object_name = obj_data.get("object_name", "Object")
    object_context = json.dumps(obj_data, indent=2)

    prompt = SCRIPT_PROMPT_TEMPLATE.format(
        object_name=object_name,
        object_context=object_context,
        facts=facts,
    )

    logger.info(f"Generating script for: {object_name}")

    response = client.models.generate_content(
        model=SCRIPT_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.7,
            max_output_tokens=3000,
        ),
    )

    raw = response.text.strip()

    # Strip markdown fences
    raw = re.sub(r"^```(?:json)?\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)

    try:
        scenes = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse script JSON: {e}\nRaw: {raw[:500]}")
        # Build a minimal fallback script
        scenes = _fallback_script(object_name, facts)

    # Validate and normalize
    scenes = _normalize_scenes(scenes, object_name)

    logger.info(f"Script generated: {len(scenes)} scenes")
    return scenes


def _normalize_scenes(scenes: list, object_name: str) -> list:
    """Ensure all scenes have required fields."""
    emotional_beats = [
        "false_familiarity",
        "misconception",
        "tension",
        "reveal",
        "reframe",
    ]

    normalized = []
    for i, scene in enumerate(scenes[:5]):
        beat = emotional_beats[i] if i < len(emotional_beats) else "reveal"
        veo = scene.get("veo_json", {})
        shot = veo.get("shot", {})

        normalized.append({
            "scene_number": i + 1,
            "narration": scene.get("narration", f"Scene {i + 1} narration about {object_name}."),
            "emotional_beat": scene.get("emotional_beat", beat),
            "veo_json": {
                "shot": {
                    "type": shot.get("type", "close-up"),
                    "framing": shot.get("framing", f"Subject centered: {object_name}"),
                    "camera": shot.get("camera", "slow push-in"),
                },
                "action": veo.get("action", f"Camera slowly reveals the {object_name}"),
                "environment": veo.get("environment", "Studio with dark background"),
                "lighting": veo.get("lighting", "Dramatic side light"),
                "audio": veo.get("audio", "Low cinematic drone"),
                "duration_sec": int(veo.get("duration_sec", 10)),
            },
        })

    return normalized


def _fallback_script(object_name: str, facts: str) -> list:
    """Minimal fallback script if Gemini response is unparseable."""
    facts_lines = facts.strip().split("\n")
    fact1 = facts_lines[0] if facts_lines else f"surprising fact about {object_name}"
    fact4 = facts_lines[3] if len(facts_lines) > 3 else fact1

    return [
        {
            "scene_number": 1,
            "narration": f"You've seen a {object_name} a thousand times. You've never really looked at it.",
            "emotional_beat": "false_familiarity",
            "veo_json": {
                "shot": {"type": "wide", "framing": "Object on a table, full frame", "camera": "slow push-in"},
                "action": f"Camera drifts toward a lone {object_name} on an empty surface",
                "environment": "Minimalist studio, white surface",
                "lighting": "Soft overhead light",
                "audio": "Quiet ambient room tone",
                "duration_sec": 10,
            },
        },
        {
            "scene_number": 2,
            "narration": f"Everything you believe about the {object_name} is built on a story that was never quite true.",
            "emotional_beat": "misconception",
            "veo_json": {
                "shot": {"type": "close-up", "framing": "Tight on object surface", "camera": "slow pan"},
                "action": "Light shifts dramatically across the surface, revealing texture",
                "environment": "Dark studio",
                "lighting": "Raking side light",
                "audio": "Low tension string note",
                "duration_sec": 10,
            },
        },
        {
            "scene_number": 3,
            "narration": f"Something happened with this {object_name} that most history books left out.",
            "emotional_beat": "tension",
            "veo_json": {
                "shot": {"type": "extreme close-up", "framing": "Abstract detail", "camera": "static with rack focus"},
                "action": "Focus shifts slowly from blur to sharp on a specific detail",
                "environment": "Dark, moody studio",
                "lighting": "Single beam spotlight",
                "audio": "Rising orchestral tension",
                "duration_sec": 10,
            },
        },
        {
            "scene_number": 4,
            "narration": fact4[:200],
            "emotional_beat": "reveal",
            "veo_json": {
                "shot": {"type": "medium", "framing": "Object in dramatic context", "camera": "slow zoom out"},
                "action": "Dramatic reveal — object placed in historical context",
                "environment": "Evocative historical environment",
                "lighting": "Warm amber dramatic light",
                "audio": "Full cinematic score swell",
                "duration_sec": 10,
            },
        },
        {
            "scene_number": 5,
            "narration": f"The {object_name} sits unchanged on your desk. But now you have to ask: what else have you been holding without really knowing?",
            "emotional_beat": "reframe",
            "veo_json": {
                "shot": {"type": "wide", "framing": "Object small in vast space", "camera": "slow pull back"},
                "action": "Camera pulls back slowly, making the object appear small and significant at once",
                "environment": "Minimal infinity background",
                "lighting": "Fading light, contemplative",
                "audio": "Single piano note, fades to silence",
                "duration_sec": 10,
            },
        },
    ]

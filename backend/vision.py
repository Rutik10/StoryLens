"""
vision.py — Gemini Vision object analysis
Analyzes an uploaded image and returns structured object metadata.
"""

import os
import json
import re
import logging
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

VISION_MODEL = os.getenv("VISION_MODEL", "gemini-2.5-flash")

VISION_PROMPT = """Analyze this image and identify the main everyday object.
Return ONLY a valid JSON object with these exact keys (no markdown, no explanation):
{
  "object_name": "concise name of the object",
  "material": "primary material(s)",
  "estimated_age": "when it was invented or common period",
  "rarity_score": <integer 1-10, where 1=extremely common, 10=very rare>,
  "most_surprising_fact_angle": "one-sentence angle about the most surprising true thing about this object",
  "common_misconception": "one common misconception people have about this object"
}
Be specific and factually accurate."""


def _get_client() -> genai.Client:
    if os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").lower() == "true":
        return genai.Client(
            vertexai=True,
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
        )
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Set GOOGLE_API_KEY or GOOGLE_GENAI_USE_VERTEXAI=true")
    return genai.Client(api_key=api_key)


async def analyze_image(image_bytes: bytes, content_type: str = "image/jpeg") -> dict:
    """
    Send image bytes to Gemini Vision and return structured object metadata.

    Args:
        image_bytes: Raw image bytes
        content_type: MIME type of the image

    Returns:
        dict with object_name, material, estimated_age, rarity_score,
        most_surprising_fact_angle, common_misconception
    """
    client = _get_client()

    image_part = types.Part.from_bytes(data=image_bytes, mime_type=content_type)

    logger.info(f"Sending image ({len(image_bytes)} bytes) to Gemini Vision")

    response = client.models.generate_content(
        model=VISION_MODEL,
        contents=[image_part, VISION_PROMPT],
        config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=512,
        ),
    )

    raw = response.text.strip()
    logger.info(f"Vision raw response: {raw[:200]}")

    # Strip markdown code fences if present
    raw = re.sub(r"^```(?:json)?\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse vision response as JSON: {e}\nRaw: {raw}")
        # Fallback: extract what we can
        data = {
            "object_name": "Unknown Object",
            "material": "Unknown",
            "estimated_age": "Unknown",
            "rarity_score": 5,
            "most_surprising_fact_angle": raw[:200],
            "common_misconception": "No misconception identified",
        }

    # Ensure rarity_score is int
    try:
        data["rarity_score"] = int(data.get("rarity_score", 5))
    except (ValueError, TypeError):
        data["rarity_score"] = 5

    return data

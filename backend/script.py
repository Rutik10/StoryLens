"""
script.py — Generates a single Veo prompt for an 8-second funny short video.
"""

import os
import logging
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

SCRIPT_MODEL = "gemini-2.5-flash"

SCRIPT_PROMPT_TEMPLATE = """You are writing a prompt for an AI video generator called Veo.
The prompt must describe a funny 8-second video about a {object_name}, built around this fact:

FACT: {fact}

A Veo prompt is a single paragraph of plain prose that describes what is visible on screen.
It must include: what the subject is doing, the camera angle, the setting, the lighting, any sounds, and a clear narration line that speaks the fact.
Include the narration as a single inline sentence like: "Voiceover says: '{fact}'" (use the exact fact text verbatim).
It must NOT include: scene headers, screenplay format, character names, dialogue labels, markdown, or bullet points.

The video must be funny. The humour comes directly from the fact — the fact is either the setup or the punchline.
Keep it to ONE moment. 8 seconds is very short.
Now write one Veo prompt for the {object_name} fact above. One paragraph, plain prose only."""


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


def _extract_text(response) -> str | None:
    """Safely extract text from a Gemini response (handles 2.5 thinking responses)."""
    if response.text:
        return response.text
    if response.candidates:
        content = response.candidates[0].content
        parts = content.parts if content and content.parts else []
        text = " ".join(p.text for p in parts if hasattr(p, "text") and p.text)
        return text or None
    return None


def _pick_best_fact(client: genai.Client, object_name: str, facts: str) -> str:
    """Pick the single funniest/most surprising fact to build the video around."""
    response = client.models.generate_content(
        model=SCRIPT_MODEL,
        contents=(
            f"You are a comedy writer.\n"
            f"Below are facts about a {object_name}.\n\n"
            f"{facts}\n\n"
            f"Pick the ONE fact that has the most comedic or jaw-dropping potential for a funny 8-second video. "
            f"Return ONLY that fact, word for word, with no commentary."
        ),
        config=types.GenerateContentConfig(temperature=0.2, max_output_tokens=20000),
    )
    text = _extract_text(response)
    if not text:
        first_fact = next((line.strip() for line in facts.splitlines() if line.strip()), facts)
        logger.warning("_pick_best_fact got empty response, falling back to first fact")
        return first_fact
    return text.strip()


async def generate_script(obj_data: dict, facts: str) -> dict:
    """
    Generate a single Veo prompt for a funny 8-second video.
    Returns {"veo_prompt": "...", "fact": "..."}
    """
    client = _get_client()
    object_name = obj_data.get("object_name", "Object")

    best_fact = _pick_best_fact(client, object_name, facts)
    logger.info(f"Selected fact: {best_fact[:120]}...")

    prompt = SCRIPT_PROMPT_TEMPLATE.format(object_name=object_name, fact=best_fact)

    response = client.models.generate_content(
        model=SCRIPT_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.9, max_output_tokens=8000),
    )

    veo_prompt = (_extract_text(response) or "").strip()
    logger.info(f"Veo prompt: {veo_prompt[:120]}...")
    return {"veo_prompt": veo_prompt, "fact": best_fact}

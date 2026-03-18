"""
script.py - Generates a long-form Veo anchor prompt, continuation prompts, and narration.
"""

import json
import logging
import os
import re

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

SCRIPT_MODEL = "gemini-2.5-flash"

VIDEO_SCRIPT_PROMPT = """You are writing a funny mini-documentary video plan for Veo.
Create a 30-second video plan about a {object_name}.

Object metadata:
{object_json}

Available verified facts:
{facts}

Return ONLY valid JSON with this exact structure:
{{
  "fact": "the single best hero fact, copied exactly from the list",
  "anchor_prompt": "the first 8-second Veo prompt as one plain prose paragraph",
  "extension_prompts": [
    "the next continuation prompt",
    "the next continuation prompt",
    "the next continuation prompt"
  ],
  "narration_script": "a 25 to 30 second narration using 3 to 4 facts in a funny escalating documentary tone"
}}

Rules:
- The full video must have a complete arc with these beats:
  1. setup: introduce the object and the central absurd premise
  2. escalation: the object behaves in a more ridiculous way
  3. twist: a second surprising fact changes what we think is happening
  4. payoff ending: the final clip must end on a clear visual punchline, not an open continuation
- The video should escalate across the full 30 seconds and never reset, loop, or repeat the same action
- The extension prompts must clearly advance the action from the prior clip and mention what NEW thing happens next
- Use the same subject, location, style, and visual continuity throughout
- Make it funny, surprising, and visually specific
- Build the humor around exaggeration, contrast in scale, dead-serious documentary framing, or a ridiculous consequence of the fact
- The narration script must combine 3 to 4 different facts, not just one
- The narration should sound like a witty mini documentary with a strong final line
- Each prompt must mention camera movement, visible action, setting, lighting, and sound
- Each prompt must contain one inline narration sentence using this format: Voiceover says: '...'
- The last prompt must explicitly describe the final visual payoff and how the scene ends
- Do not use markdown
"""


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
    if response.text:
        return response.text
    if response.candidates:
        content = response.candidates[0].content
        parts = content.parts if content and content.parts else []
        text = " ".join(p.text for p in parts if hasattr(p, "text") and p.text)
        return text or None
    return None


def _clean_json_text(text: str) -> str:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _fact_lines(facts: str) -> list[str]:
    return [line.strip() for line in facts.splitlines() if line.strip()]


def _pick_best_fact(client: genai.Client, object_name: str, facts: str) -> str:
    response = client.models.generate_content(
        model=SCRIPT_MODEL,
        contents=(
            f"You are a comedy writer.\n"
            f"Below are facts about a {object_name}.\n\n"
            f"{facts}\n\n"
            "Pick the ONE fact with the strongest visual comedy potential. "
            "Return ONLY that fact, word for word, with no commentary."
        ),
        config=types.GenerateContentConfig(temperature=0.2, max_output_tokens=512),
    )
    text = (_extract_text(response) or "").strip()
    if text:
        return text
    return _fact_lines(facts)[0] if _fact_lines(facts) else facts.strip()


def _fallback_payload(object_name: str, facts: str, hero_fact: str) -> dict:
    fact_lines = _fact_lines(facts)[:4]
    narration_facts = fact_lines if fact_lines else [hero_fact]
    narration_script = (
        f"This looks like an ordinary {object_name}, but it hides deeply ridiculous history. "
        f"{narration_facts[0]} "
        f"Then it gets stranger. {narration_facts[min(1, len(narration_facts)-1)]} "
        f"And somehow it gets even more absurd. {narration_facts[min(2, len(narration_facts)-1)]} "
        f"Which means this humble {object_name} ends up feeling less like office equipment and more like a myth with paperwork."
    )
    anchor_prompt = (
        f"A cinematic opening shot of a {object_name} in an ordinary realistic setting, filmed like a dead-serious premium documentary "
        f"with a slow push-in camera move, crisp lighting, tactile ambient sound, and one visually absurd detail that quietly hints "
        f"something is very wrong. The object begins an impossible but believable action that sets up the joke with total sincerity. "
        f"Voiceover says: '{hero_fact}'"
    )
    extension_prompts = [
        f"Continue directly from the previous frame with the same {object_name}, setting, and style. Introduce a NEW comedic escalation: the object's impossible behavior becomes bigger, more inconvenient, and more ridiculous, while everyone in the scene still treats it like a perfectly normal documentary subject. Use a slightly faster tracking shot, busier room sound, and one clear visual gag that did not exist in the first clip. Voiceover says: '{narration_facts[min(1, len(narration_facts)-1)]}'",
        f"Continue from the exact ending frame again and reveal a NEW twist tied to another fact. The camera widens to show the larger consequence, the environment reacts, and the joke becomes more absurd in scale. Do not repeat any visual action from the previous clips; escalate into a second distinct set piece. Voiceover says: '{narration_facts[min(2, len(narration_facts)-1)]}'",
        f"Continue seamlessly into the final payoff ending. Deliver a clear visual punchline that resolves the whole 30-second mini story: the {object_name} ends in its most outrageous, funniest, fully revealed state, then lands on a final documentary-style ending image with no repetition and no cliffhanger. Voiceover says: '{narration_facts[min(3, len(narration_facts)-1)]}'",
    ]
    return {
        "fact": hero_fact,
        "anchor_prompt": anchor_prompt,
        "extension_prompts": extension_prompts,
        "narration_script": narration_script,
    }


async def generate_script(obj_data: dict, facts: str) -> dict:
    client = _get_client()
    object_name = obj_data.get("object_name", "Object")
    hero_fact = _pick_best_fact(client, object_name, facts)
    logger.info("Selected fact: %s...", hero_fact[:120])

    response = client.models.generate_content(
        model=SCRIPT_MODEL,
        contents=VIDEO_SCRIPT_PROMPT.format(
            object_name=object_name,
            object_json=json.dumps(obj_data, ensure_ascii=True),
            facts=facts,
        ),
        config=types.GenerateContentConfig(temperature=0.8, max_output_tokens=8000),
    )

    raw_text = (_extract_text(response) or "").strip()
    payload = _fallback_payload(object_name, facts, hero_fact)
    if raw_text:
        try:
            parsed = json.loads(_clean_json_text(raw_text))
            if isinstance(parsed, dict):
                payload["fact"] = (parsed.get("fact") or hero_fact).strip()
                payload["anchor_prompt"] = (parsed.get("anchor_prompt") or payload["anchor_prompt"]).strip()
                prompts = parsed.get("extension_prompts")
                if isinstance(prompts, list):
                    cleaned_prompts = [str(p).strip() for p in prompts if str(p).strip()]
                    if cleaned_prompts:
                        payload["extension_prompts"] = cleaned_prompts[:3]
                payload["narration_script"] = (
                    parsed.get("narration_script") or payload["narration_script"]
                ).strip()
        except Exception:
            logger.warning("Failed to parse structured video script JSON, using fallback payload")

    while len(payload["extension_prompts"]) < 3:
        payload["extension_prompts"].append(payload["anchor_prompt"])

    return {
        "veo_prompt": payload["anchor_prompt"],
        "fact": payload["fact"],
        "extension_prompts": payload["extension_prompts"][:3],
        "narration_script": payload["narration_script"],
    }

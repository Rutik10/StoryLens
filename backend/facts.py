"""
facts.py — Gemini + Google Search Grounding fact fetching
Finds 5 surprising, verified facts about an object with source citations.
"""

import os
import logging
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

FACTS_MODEL = os.getenv("FACTS_MODEL", "gemini-2.5-flash")


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


FACTS_PROMPT_TEMPLATE = """You are a research journalist with access to Google Search.
Find exactly 5 surprising, lesser-known, and verified facts about: {object_name}

Rules:
- Each fact must be genuinely surprising and non-obvious
- Each fact must be verified by at least 2 real, credible sources
- Cite each source in brackets at the end of the fact
- Facts should span different domains: history, science, culture, military, economics
- Be specific with numbers, dates, and names — no vague claims
- Do NOT use facts that are common knowledge

Format your response EXACTLY like this (numbered list):
1. [Surprising fact here]. [Source: Publication Name, Publication Name 2]
2. [Surprising fact here]. [Source: Publication Name, Publication Name 2]
3. [Surprising fact here]. [Source: Publication Name, Publication Name 2]
4. [Surprising fact here]. [Source: Publication Name, Publication Name 2]
5. [Surprising fact here]. [Source: Publication Name, Publication Name 2]"""


async def fetch_facts(object_name: str) -> str:
    """
    Use Gemini 2.0 Flash with Google Search Grounding to fetch 5 surprising facts.

    Args:
        object_name: Name of the object to research

    Returns:
        Numbered list string with facts and citations
    """
    client = _get_client()

    prompt = FACTS_PROMPT_TEMPLATE.format(object_name=object_name)

    logger.info(f"Fetching facts for: {object_name}")

    # Enable Google Search Grounding tool
    google_search_tool = types.Tool(google_search=types.GoogleSearch())

    response = client.models.generate_content(
        model=FACTS_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[google_search_tool],
            temperature=0.3,
            max_output_tokens=1024,
        ),
    )

    facts_text = response.text.strip()
    logger.info(f"Facts fetched ({len(facts_text)} chars)")

    # Log grounding metadata if available
    if hasattr(response, "candidates") and response.candidates:
        candidate = response.candidates[0]
        if hasattr(candidate, "grounding_metadata") and candidate.grounding_metadata:
            sources = getattr(candidate.grounding_metadata, "web_search_queries", [])
            logger.info(f"Search queries used: {sources}")

    return facts_text

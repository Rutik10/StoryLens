"""
notion.py — Notion MCP integration
Saves object analysis, facts, script, and video link to a Notion database.
"""

import os
import json
import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def _get_headers() -> dict:
    api_key = os.getenv("NOTION_API_KEY")
    if not api_key:
        raise RuntimeError("NOTION_API_KEY not set in environment")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }


def _text_block(content: str, heading: int = 0) -> dict:
    """Build a Notion block: paragraph or heading."""
    if heading == 1:
        return {"object": "block", "type": "heading_1", "heading_1": {"rich_text": [{"type": "text", "text": {"content": content[:2000]}}]}}
    if heading == 2:
        return {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"type": "text", "text": {"content": content[:2000]}}]}}
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": content[:2000]}}]}}


def _build_page_payload(
    obj_data: dict,
    facts: str,
    script_scenes: list,
    video_url: str,
    database_id: str,
) -> dict:
    object_name = obj_data.get("object_name", "Unknown Object")
    timestamp = datetime.now(timezone.utc).isoformat()

    # Build children blocks
    children = [
        _text_block("Object Analysis", heading=1),
        _text_block(f"Name: {object_name}"),
        _text_block(f"Material: {obj_data.get('material', 'Unknown')}"),
        _text_block(f"Estimated Age: {obj_data.get('estimated_age', 'Unknown')}"),
        _text_block(f"Rarity Score: {obj_data.get('rarity_score', '?')} / 10"),
        _text_block(f"Surprising angle: {obj_data.get('most_surprising_fact_angle', '')}"),
        _text_block(f"Common misconception: {obj_data.get('common_misconception', '')}"),
        _text_block("Verified Facts", heading=1),
    ]

    # Add each fact line as its own paragraph
    for line in facts.strip().split("\n"):
        if line.strip():
            children.append(_text_block(line.strip()))

    children.append(_text_block("Cinematic Script (Myth-Bust-Blow)", heading=1))
    for scene in script_scenes:
        children.append(
            _text_block(
                f"Scene {scene.get('scene_number', '?')} — {scene.get('emotional_beat', '').upper()}",
                heading=2,
            )
        )
        children.append(_text_block(f"Narration: {scene.get('narration', '')}"))

    if video_url:
        children.append(_text_block("Final Video", heading=1))
        children.append(_text_block(f"Video URL: {video_url}"))

    children.append(_text_block(f"Generated at: {timestamp}"))

    return {
        "parent": {"database_id": database_id},
        "properties": {
            "Name": {
                "title": [
                    {"text": {"content": f"OrdinaryEpic: {object_name}"}}
                ]
            },
            "Object": {
                "rich_text": [{"text": {"content": object_name}}]
            },
            "Created": {
                "date": {"start": timestamp}
            },
        },
        "children": children,
    }


async def save_to_notion(
    obj_data: dict,
    facts: str,
    script_scenes: list,
    video_url: str,
) -> dict:
    """
    Create a new Notion page in the configured database.

    Args:
        obj_data: Object metadata from vision.py
        facts: Facts string from facts.py
        script_scenes: List of scene dicts from script.py
        video_url: URL of the final video (may be empty)

    Returns:
        dict with 'url' key pointing to the created Notion page
    """
    database_id = os.getenv("NOTION_DATABASE_ID")
    if not database_id:
        raise RuntimeError("NOTION_DATABASE_ID not set in environment")

    headers = _get_headers()
    payload = _build_page_payload(obj_data, facts, script_scenes, video_url, database_id)

    logger.info(f"Saving to Notion database: {database_id}")

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{NOTION_API_BASE}/pages",
            headers=headers,
            json=payload,
        )

    if response.status_code not in (200, 201):
        logger.error(f"Notion API error {response.status_code}: {response.text[:500]}")
        response.raise_for_status()

    result = response.json()
    page_url = result.get("url", "")
    logger.info(f"Notion page created: {page_url}")
    return {"url": page_url, "id": result.get("id", "")}

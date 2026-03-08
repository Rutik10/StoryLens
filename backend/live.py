"""
live.py — Gemini Live API voice WebSocket handler
Provides real-time voice Q&A about the generated story.
"""

import os
import json
import base64
import asyncio
import logging
from typing import AsyncGenerator

from fastapi import WebSocket

logger = logging.getLogger(__name__)

LIVE_MODEL = "gemini-2.0-flash-live-001"


SYSTEM_PROMPT_TEMPLATE = """You are a documentary narrator who just created an extraordinary story about {object_name}.

You know these verified facts:
{facts}

Your personality:
- Speak in the same tone as the video: surprising, specific, and cinematic
- Never be vague. Use exact numbers, dates, and names
- If asked something you don't know, say so — but pivot to something equally surprising that you DO know
- Keep responses under 3 sentences unless the user asks for more detail
- Start responses with the most surprising part first

You are in a live voice conversation. The user is watching the video you created and has questions."""


async def run_live_session(websocket: WebSocket, object_name: str, facts: str) -> None:
    """
    Run a Gemini Live API voice session over a WebSocket connection.

    Protocol:
      Client → Server: JSON {"type": "audio", "data": "<base64 PCM>"}
                     | JSON {"type": "text", "data": "user message"}
                     | JSON {"type": "end"}
      Server → Client: JSON {"type": "audio", "data": "<base64 PCM>"}
                     | JSON {"type": "text", "data": "transcript chunk"}
                     | JSON {"type": "done"}
                     | JSON {"type": "error", "message": "..."}

    Audio format: 16-bit PCM, 16kHz mono (input and output)
    """
    from google import genai
    from google.genai import types

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": "GOOGLE_API_KEY not configured"
        }))
        return

    client = genai.Client(api_key=api_key, http_options={"api_version": "v1alpha"})

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        object_name=object_name,
        facts=facts,
    )

    live_config = types.LiveConnectConfig(
        response_modalities=["AUDIO", "TEXT"],
        system_instruction=types.Content(
            parts=[types.Part(text=system_prompt)],
            role="user",
        ),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Charon")
            )
        ),
    )

    logger.info(f"Starting Gemini Live session for object: {object_name}")

    try:
        async with client.aio.live.connect(
            model=LIVE_MODEL, config=live_config
        ) as live_session:

            # Notify client that session is ready
            await websocket.send_text(json.dumps({"type": "ready"}))

            async def receive_from_client():
                """Forward client audio/text to Gemini Live."""
                while True:
                    try:
                        raw = await websocket.receive_text()
                        msg = json.loads(raw)
                        msg_type = msg.get("type", "")

                        if msg_type == "audio":
                            audio_bytes = base64.b64decode(msg["data"])
                            await live_session.send(
                                input=types.LiveClientRealtimeInput(
                                    media_chunks=[
                                        types.Blob(
                                            data=audio_bytes,
                                            mime_type="audio/pcm;rate=16000",
                                        )
                                    ]
                                )
                            )

                        elif msg_type == "text":
                            await live_session.send(
                                input=msg["data"], end_of_turn=True
                            )

                        elif msg_type == "end":
                            logger.info("Client signaled end of session")
                            break

                    except Exception as e:
                        logger.error(f"Error receiving from client: {e}")
                        break

            async def send_to_client():
                """Forward Gemini Live responses to client."""
                async for response in live_session.receive():
                    if response.data:
                        # Audio bytes
                        audio_b64 = base64.b64encode(response.data).decode("utf-8")
                        await websocket.send_text(json.dumps({
                            "type": "audio",
                            "data": audio_b64,
                        }))

                    if response.text:
                        await websocket.send_text(json.dumps({
                            "type": "text",
                            "data": response.text,
                        }))

                await websocket.send_text(json.dumps({"type": "done"}))

            # Run both directions concurrently
            await asyncio.gather(
                receive_from_client(),
                send_to_client(),
            )

    except Exception as e:
        logger.error(f"Gemini Live session error: {e}", exc_info=True)
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": str(e),
            }))
        except Exception:
            pass

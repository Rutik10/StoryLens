"""
tts.py - Narration generation via Google Cloud Text-to-Speech.
"""

import os
import re
import time
from pathlib import Path

from google.cloud import texttospeech

DEFAULT_LANGUAGE_CODE = os.getenv("TTS_LANGUAGE_CODE", "en-US")
DEFAULT_VOICE_NAME = os.getenv("TTS_VOICE_NAME", "en-US-Neural2-D")


def _clean_text(text: str) -> str:
    text = re.sub(r"\[Source:.*?\]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


async def synthesize_narration(text: str, output_dir: str) -> str:
    cleaned = _clean_text(text)
    if not cleaned:
        raise RuntimeError("Narration text was empty")

    client = texttospeech.TextToSpeechClient()
    synthesis_input = texttospeech.SynthesisInput(text=cleaned)
    voice = texttospeech.VoiceSelectionParams(
        language_code=DEFAULT_LANGUAGE_CODE,
        name=DEFAULT_VOICE_NAME,
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=0.92,
    )

    response = client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config,
    )

    output_path = Path(output_dir) / f"narration_{int(time.time())}.mp3"
    output_path.write_bytes(response.audio_content)
    return str(output_path)

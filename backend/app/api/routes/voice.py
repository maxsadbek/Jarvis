"""Voice API routes.

Provides REST endpoints for voice configuration and non-streaming
speech-to-text and text-to-speech operations.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, UploadFile, File, HTTPException
from loguru import logger

from backend.app.config import settings
from backend.app.models.schemas import VoiceConfig

router = APIRouter(prefix="/api/voice", tags=["voice"])

# Reused TTS instance so the Piper model is loaded only once instead of
# per-request (model load takes ~2s and would risk the desktop 5s timeout).
_tts_instance = None
_tts_lock: asyncio.Lock | None = None


def _get_tts_lock() -> asyncio.Lock:
    """Lazily create the TTS lock inside an event loop."""
    global _tts_lock
    if _tts_lock is None:
        _tts_lock = asyncio.Lock()
    return _tts_lock


@router.get("/status")
async def voice_status() -> dict:
    """Get voice system status."""
    return {
        "stt_engine": settings.STT_ENGINE,
        "tts_engine": settings.TTS_ENGINE,
        "wake_word_enabled": settings.WAKE_WORD_ENABLED,
        "wake_word": settings.WAKE_WORD,
        "sample_rate": settings.SAMPLE_RATE,
    }


@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)) -> dict:
    """Transcribe an uploaded audio file."""
    try:
        from backend.app.voice.stt import SpeechToText

        # Read audio file
        audio_data = await file.read()
        logger.info(f"Received audio file: {file.filename} ({len(audio_data)} bytes)")

        # Transcribe
        stt = SpeechToText()
        await stt.initialize()
        text = await stt.transcribe(audio_data)

        return {
            "success": bool(text),
            "text": text,
            "filename": file.filename,
        }

    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/synthesize")
async def synthesize_speech(text: str) -> dict:
    """Synthesize text to speech and return audio."""
    try:
        from backend.app.voice.tts import TextToSpeech

        global _tts_instance
        async with _get_tts_lock():
            if _tts_instance is None or not _tts_instance.is_ready:
                tts = TextToSpeech()
                if await tts.initialize():
                    _tts_instance = tts
        audio_bytes = await _tts_instance.synthesize(text)

        import base64
        return {
            "success": bool(audio_bytes),
            "audio": base64.b64encode(audio_bytes).decode() if audio_bytes else "",
            "format": "wav",
            "sample_rate": settings.PIPER_OUTPUT_SAMPLE_RATE,
        }

    except Exception as e:
        logger.error(f"Synthesis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
async def get_voice_config() -> VoiceConfig:
    """Get current voice configuration."""
    return VoiceConfig(
        stt_engine=settings.STT_ENGINE,
        tts_engine=settings.TTS_ENGINE,
        wake_word_enabled=settings.WAKE_WORD_ENABLED,
        wake_word=settings.WAKE_WORD,
        tts_speed=settings.TTS_SPEED,
        sample_rate=settings.SAMPLE_RATE,
    )

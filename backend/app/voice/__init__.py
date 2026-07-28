"""Voice Module - JARVIS Voice Interaction System.

Provides:
- Speech-to-text (Faster-Whisper)
- Text-to-speech (Piper TTS)
- Voice Manager (prerecorded clips + smart phrase matching + TTS fallback)
- Wake word detection
- Audio utilities (recording, playback, devices)
- Voice Activity Detection

Architecture:
    voice/
        voice_manager.py - VoiceManager: prerecorded clips, cache, queue, priorities
        stt.py          - Legacy SpeechToText class
        tts.py          - Legacy TextToSpeech class
        wake_word.py    - Wake word detection (energy-based)
        audio.py        - Audio utilities (mic stream, player, devices)
        __init__.py     - Re-exports from sub-modules

    speech_to_text/     - New STT module (abstract + Faster-Whisper)
    text_to_speech/     - New TTS module (abstract + Piper)
    assistant_core/     - Voice pipeline orchestrator
"""

# Legacy classes (backward compatible)
from .stt import SpeechToText
from .tts import TextToSpeech
from .wake_word import WakeWordDetector
from .wake_word_engine import WakeWordEngine, EnergyWakeWordDetector, WakeWordConfig
from .audio import (
    MicrophoneStream,
    AudioPlayer,
    list_audio_devices,
    get_default_input_device,
    record_audio,
)

# Voice Manager (professional playback system)
from .voice_manager import (
    VoiceManager,
    VoiceClip,
    PlaybackPriority,
    PlaybackRequest,
    FadeConfig,
    PHRASE_MAP,
    RUSSIAN_APP_NAMES,
    UZBEK_APP_NAMES,
    UZBEK_ACTIONS,
)

# New modules (preferred for new code)
from backend.app.speech_to_text import (
    FasterWhisperSTT,
    STTEngine,
    STTResult,
    VoiceActivityDetector,
    VadConfig,
    AudioProcessor,
)
from backend.app.text_to_speech import (
    PiperTTS,
    TTSEngine,
    TTSResult,
    AudioStreamer,
)

__all__ = [
    # Legacy
    "SpeechToText",
    "TextToSpeech",
    "WakeWordDetector",
    "WakeWordEngine",
    "EnergyWakeWordDetector",
    "WakeWordConfig",
    "MicrophoneStream",
    "AudioPlayer",
    "list_audio_devices",
    "get_default_input_device",
    "record_audio",
    # Voice Manager
    "VoiceManager",
    "VoiceClip",
    "PlaybackPriority",
    "PlaybackRequest",
    "FadeConfig",
    "PHRASE_MAP",
    "RUSSIAN_APP_NAMES",
    "UZBEK_APP_NAMES",
    "UZBEK_ACTIONS",
    # New STT
    "FasterWhisperSTT",
    "STTEngine",
    "STTResult",
    "VoiceActivityDetector",
    "VadConfig",
    "AudioProcessor",
    # New TTS
    "PiperTTS",
    "TTSEngine",
    "TTSResult",
    "AudioStreamer",
    # Pipeline (backward compatible - lazy loaded)
    "VoicePipeline",
    "PipelineConfig",
    "PipelineEvent",
    "VoiceSession",
    "SessionState",
    "VoiceAssistantConfig",
]


def __getattr__(name):
    """Lazy-load assistant_core classes for backward compatibility.

    Previously, voice/__init__.py re-exported pipeline classes from
    assistant_core. That created a circular import because pipeline.py
    (inside assistant_core) imports from voice.wake_word_engine.
    
    This __getattr__ allows old import statements like:
        from backend.app.voice import VoicePipeline
    to still work, while avoiding the circular import at module load time.
    """
    if name in {
        "VoicePipeline",
        "PipelineConfig",
        "PipelineEvent",
        "VoiceSession",
        "SessionState",
        "VoiceAssistantConfig",
    }:
        import importlib
        mod = importlib.import_module("backend.app.assistant_core")
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

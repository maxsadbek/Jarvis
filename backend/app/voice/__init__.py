"""Voice Module - JARVIS Voice Interaction System.

Provides:
- Speech-to-text (Faster-Whisper)
- Text-to-speech (Piper TTS)
- Wake word detection
- Audio utilities (recording, playback, devices)
- Voice Activity Detection

Architecture:
    voice/
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
from .audio import (
    MicrophoneStream,
    AudioPlayer,
    list_audio_devices,
    get_default_input_device,
    record_audio,
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
from backend.app.assistant_core import (
    VoicePipeline,
    PipelineConfig,
    PipelineEvent,
    VoiceSession,
    SessionState,
    VoiceAssistantConfig,
)

__all__ = [
    # Legacy
    "SpeechToText",
    "TextToSpeech",
    "WakeWordDetector",
    "MicrophoneStream",
    "AudioPlayer",
    "list_audio_devices",
    "get_default_input_device",
    "record_audio",
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
    # Pipeline
    "VoicePipeline",
    "PipelineConfig",
    "PipelineEvent",
    "VoiceSession",
    "SessionState",
    "VoiceAssistantConfig",
]

# Speech-to-Text Module
# Provides speech recognition with multiple engine backends

from .engine import STTEngine, STTResult
from .faster_whisper_stt import FasterWhisperSTT
from .vad import VoiceActivityDetector, VadConfig
from .processor import AudioProcessor

__all__ = [
    "STTEngine",
    "STTResult",
    "FasterWhisperSTT",
    "VoiceActivityDetector",
    "VadConfig",
    "AudioProcessor",
]

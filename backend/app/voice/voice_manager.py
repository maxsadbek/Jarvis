"""Voice Manager - JARVIS Voice Playback System.

Professional voice manager with:
- Automatic WAV scanning and caching
- Hot reload support
- Async playback with queue and priorities
- Interrupt support (high priority interrupts current)
- Volume control, playback speed, fade in/out
- Phrase library with smart Russian matching
- TTS fallback when no prerecorded clip exists
- Generated speech caching
- Simultaneous sound effects (non-interrupting)
- Startup/shutdown sequences
- Thread-safe, fully asynchronous

Architecture:
    VoiceManager             - Top-level orchestrator
    ├── VoiceClip            - Data class for loaded audio
    ├── PlaybackPriority     - Priority levels enum
    ├── PlaybackRequest      - Playback job description
    └── FadeConfig           - Fade in/out parameters

Integration:
    - pipeline.py uses play_event() for lifecycle sounds
    - main.py initializes in lifespan
    - startup.py uses play_startup_sequence()
"""

from __future__ import annotations

import asyncio
import io
import wave
import struct
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum, auto
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
from loguru import logger


# ─── Constants ──────────────────────────────────────────────────────────────

ASSETS_DIR = Path("assets")
VOICES_DIR = ASSETS_DIR / "voices"
JARVIS_VOICES_DIR = VOICES_DIR / "jarvis"
PHRASES_DIR = JARVIS_VOICES_DIR / "phrases"
CACHE_DIR = Path("data/voice_cache")

DEFAULT_VOLUME: float = 0.8
DEFAULT_FADE_IN_MS: int = 0
DEFAULT_FADE_OUT_MS: int = 0
MAX_CACHE_SIZE_MB: int = 200

# ─── Russian phrase-to-filename mapping ────────────────────────────────────
# Maps app names and keywords to the corresponding phrase WAV filename.
# Used by the smart phrase matcher when the assistant needs to speak.
PHRASE_MAP: dict[str, str] = {
    # Browsers
    "chrome": "chrome.wav",
    "google chrome": "chrome.wav",
    "youtube": "youtube.wav",
    "telegram": "telegram.wav",
    "discord": "discord.wav",
    "spotify": "spotify.wav",
    "browser": "browser.wav",
    "edge": "edge.wav",
    "microsoft edge": "edge.wav",
    "firefox": "firefox.wav",
    "mozilla firefox": "firefox.wav",
    "opera": "opera.wav",
    "opera gx": "opera.wav",
    # Code editors
    "vscode": "vscode.wav",
    "visual studio code": "vscode.wav",
    "vs code": "vscode.wav",
    "cursor": "cursor.wav",
    # Windows utilities
    "notepad": "notepad.wav",
    "calculator": "calculator.wav",
    "settings": "settings.wav",
    "downloads": "downloads.wav",
    "documents": "documents.wav",
    "pictures": "pictures.wav",
    "music": "music.wav",
    "videos": "videos.wav",
    "desktop": "desktop.wav",
    "task manager": "taskmanager.wav",
    "taskmanager": "taskmanager.wav",
    "explorer": "explorer.wav",
    "file explorer": "explorer.wav",
    "control panel": "controlpanel.wav",
    "powershell": "powershell.wav",
    "cmd": "cmd.wav",
    "command prompt": "cmd.wav",
    "terminal": "terminal.wav",
    # Action phrases
    "opening": "opening.wav",
    "closing": "closing.wav",
    "searching": "searching.wav",
    "loading": "loading.wav",
    "launching": "launching.wav",
    "executing": "executing.wav",
    "done": "done.wav",
    "finished": "finished.wav",
}

# ─── Russian keyword extraction helpers ─────────────────────────────────────
# Maps Russian action verbs + app names to phrase files for smart matching.
RUSSIAN_APP_NAMES: dict[str, str] = {
    "хром": "chrome.wav",
    "гугл хром": "chrome.wav",
    "ютуб": "youtube.wav",
    "ютюб": "youtube.wav",
    "телеграм": "telegram.wav",
    "дискорд": "discord.wav",
    "спотифай": "spotify.wav",
    "спотифай": "spotify.wav",
    "браузер": "browser.wav",
    "опера": "opera.wav",
    "визуал студио": "vscode.wav",
    "вскод": "vscode.wav",
    "курсор": "cursor.wav",
    "блокнот": "notepad.wav",
    "калькулятор": "calculator.wav",
    "параметры": "settings.wav",
    "загрузки": "downloads.wav",
    "документы": "documents.wav",
    "изображения": "pictures.wav",
    "картинки": "pictures.wav",
    "музыка": "music.wav",
    "видео": "videos.wav",
    "рабочий стол": "desktop.wav",
    "диспетчер задач": "taskmanager.wav",
    "проводник": "explorer.wav",
    "панель управления": "controlpanel.wav",
    "терминал": "terminal.wav",
    "командная строка": "cmd.wav",
    "командная строка": "powershell.wav",
}

# ─── Uzbek keyword extraction helpers ───────────────────────────────────────
# Maps Uzbek app names to phrase files for smart matching.
UZBEK_APP_NAMES: dict[str, str] = {
    "chrome": "chrome.wav",
    "гугл": "chrome.wav",
    "хром": "chrome.wav",
    "ютуб": "youtube.wav",
    "телеграм": "telegram.wav",
    "дискорд": "discord.wav",
    "спотифай": "spotify.wav",
    "браузер": "browser.wav",
    "опера": "opera.wav",
    "визуал студио": "vscode.wav",
    "вскод": "vscode.wav",
    "курсор": "cursor.wav",
    "блокнот": "notepad.wav",
    "калькулятор": "calculator.wav",
    "параметры": "settings.wav",
    "созламалар": "settings.wav",
    "загрузки": "downloads.wav",
    "документы": "documents.wav",
    "изображения": "pictures.wav",
    "расмлар": "pictures.wav",
    "музыка": "music.wav",
    "мусица": "music.wav",
    "видео": "videos.wav",
    "рабочий стол": "desktop.wav",
    "диспетчер задач": "taskmanager.wav",
    "вазифалар": "taskmanager.wav",
    "проводник": "explorer.wav",
    "eksplorer": "explorer.wav",
    "панель управления": "controlpanel.wav",
    "boshqaruv": "controlpanel.wav",
    "терминал": "terminal.wav",
    "командная строка": "cmd.wav",
}

# ─── Uzbek action verb mapping ─────────────────────────────────────────────
# Maps Uzbek action verbs to the appropriate phrase WAV for TTS fallback.
UZBEK_ACTIONS: dict[str, tuple[str, str]] = {
    "och": ("opening", "Открываю"),
    "yop": ("closing", "Закрываю"),
    "qidir": ("searching", "Ищу"),
    "top": ("searching", "Нахожу"),
    "yarat": ("executing", "Создаю"),
    "o'chir": ("executing", "Выключаю"),
    "yukla": ("executing", "Загружаю"),
    "qo'y": ("executing", "Запускаю"),
    "qoy": ("executing", "Запускаю"),
    "tushir": ("executing", "Запускаю"),
}


# ─── Data Classes ───────────────────────────────────────────────────────────

class PlaybackPriority(IntEnum):
    """Priority levels for playback requests.

    Higher priority interrupts lower-priority playback.
    """
    HIGHEST = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    LOWEST = 4


@dataclass
class FadeConfig:
    """Fade in/out configuration for audio playback."""
    fade_in_ms: int = 0
    fade_out_ms: int = 0

    @property
    def has_fade(self) -> bool:
        return self.fade_in_ms > 0 or self.fade_out_ms > 0


@dataclass
class VoiceClip:
    """A loaded and cached voice clip with metadata.

    Attributes:
        name: Clip name (filename without extension).
        path: Absolute path to the WAV file.
        category: 'jarvis' for system sounds, 'phrases' for app sounds.
        audio_bytes: Raw WAV file bytes (cached).
        sample_rate: Audio sample rate in Hz.
        sample_width: Bytes per sample (1=8bit, 2=16bit).
        channels: Number of audio channels.
        duration_seconds: Duration of the clip.
        size_bytes: File size on disk.
        last_loaded: When this clip was last loaded.
    """
    name: str
    path: Path
    category: str
    audio_bytes: bytes
    sample_rate: int
    sample_width: int
    channels: int
    duration_seconds: float
    size_bytes: int
    last_loaded: datetime = field(default_factory=datetime.now)

    @property
    def is_valid(self) -> bool:
        """Check if the clip has valid audio data."""
        return len(self.audio_bytes) > 44 and self.duration_seconds > 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for diagnostics."""
        return {
            "name": self.name,
            "path": str(self.path),
            "category": self.category,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "duration_seconds": round(self.duration_seconds, 2),
            "size_bytes": self.size_bytes,
            "last_loaded": self.last_loaded.isoformat(),
        }


@dataclass(order=True)
class PlaybackRequest:
    """A queued playback request with priority.

    Sorting is by priority (ascending = higher priority first),
    then by creation time (FIFO within same priority).
    """
    priority: PlaybackPriority = field(compare=True)
    created_at: float = field(compare=True)
    clip_name: str = field(compare=False)
    category: str = field(compare=False, default="jarvis")
    volume: float = field(compare=False, default=DEFAULT_VOLUME)
    speed: float = field(compare=False, default=1.0)
    fade: FadeConfig = field(compare=False, default_factory=FadeConfig)
    allow_interrupt: bool = field(compare=False, default=True)
    text_fallback: Optional[str] = field(compare=False, default=None)
    callback: Optional[Callable[[bool], Any]] = field(
        compare=False, default=None, repr=False
    )
    is_generated: bool = field(compare=False, default=False)


# ─── Voice Manager ──────────────────────────────────────────────────────────

class VoiceManager:
    """Professional voice playback manager for JARVIS.

    Features:
        - Scans assets/voices/ on startup, builds a searchable index
        - Caches all WAV files in memory for instant playback
        - Hot-reload: re-scans on demand or via file watcher trigger
        - Async playback queue with priority-based ordering
        - High-priority sounds interrupt current playback
        - Volume, speed, fade-in, fade-out per clip
        - Simultaneous low-priority sound effects
        - Phrase library: smart Russian keyword matching
        - TTS fallback for missing clips (auto-caches generated speech)
        - Startup/shutdown sequences with delays
        - Thread-safe design with asyncio locks
    """

    def __init__(
        self,
        assets_dir: Path = JARVIS_VOICES_DIR,
        phrases_dir: Path = PHRASES_DIR,
        cache_dir: Path = CACHE_DIR,
        tts_engine: Optional[Any] = None,
    ) -> None:
        self._assets_dir = Path(assets_dir)
        self._phrases_dir = Path(phrases_dir)
        self._cache_dir = Path(cache_dir)
        self._tts = tts_engine  # Optional TTSEngine instance

        # Clip index: {clip_name: VoiceClip}
        self._clip_index: dict[str, VoiceClip] = {}
        # Category index for fast lookups
        self._category_index: dict[str, list[str]] = {
            "jarvis": [],
            "phrases": [],
            "generated": [],
        }

        # Playback queue: asyncio.PriorityQueue of PlaybackRequest
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._current_task: Optional[asyncio.Task] = None
        self._queue_worker_task: Optional[asyncio.Task] = None
        self._is_playing = False
        self._is_paused = False

        # Sound effects (low-priority, simultaneous)
        self._sfx_tasks: set[asyncio.Task] = set()

        # Thread safety
        self._lock = asyncio.Lock()
        self._play_lock = asyncio.Lock()

        # Volume
        self._master_volume: float = DEFAULT_VOLUME

        # Callbacks
        self._on_playback_start: Optional[Callable[[str], Any]] = None
        self._on_playback_end: Optional[Callable[[str, bool], Any]] = None

        # Statistics
        self._stats: dict[str, Any] = {
            "total_clips_loaded": 0,
            "total_playbacks": 0,
            "total_tts_fallbacks": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "interruptions": 0,
            "startup_time": 0.0,
        }

    # ─── Initialization ───────────────────────────────────────────────────

    async def initialize(self) -> bool:
        """Scan voice directories, load and cache all WAV files.

        Returns:
            True if at least one voice clip was loaded.
        """
        start = datetime.now()
        logger.info("Initializing Voice Manager...")

        # Ensure directories exist
        self._assets_dir.mkdir(parents=True, exist_ok=True)
        self._phrases_dir.mkdir(parents=True, exist_ok=True)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        # Scan and load voice clips
        await self.reload()

        # Start the queue worker
        self._queue_worker_task = asyncio.create_task(self._queue_worker())

        elapsed = (datetime.now() - start).total_seconds()
        self._stats["startup_time"] = elapsed

        total = len(self._clip_index)
        logger.info(
            f"✓ Voice Manager ready: {total} clips loaded in {elapsed*1000:.0f}ms"
        )
        return total > 0

    async def reload(self) -> bool:
        """Hot-reload: re-scan voice directories and rebuild cache.

        This is safe to call at any time; active playback continues
        using the old index until this method completes.

        Returns:
            True if new clips were loaded.
        """
        async with self._lock:
            old_count = len(self._clip_index)
            self._clip_index.clear()
            self._category_index["jarvis"] = []
            self._category_index["phrases"] = []

            # Scan jarvis system sounds: assets/voices/jarvis/*.wav
            loaded = 0
            for wav_path in sorted(self._assets_dir.glob("*.wav")):
                clip = self._load_clip(wav_path, category="jarvis")
                if clip:
                    self._clip_index[clip.name] = clip
                    self._category_index["jarvis"].append(clip.name)
                    loaded += 1

            # Scan phrase sounds: assets/voices/jarvis/phrases/*.wav
            for wav_path in sorted(self._phrases_dir.glob("*.wav")):
                clip = self._load_clip(wav_path, category="phrases")
                if clip:
                    self._clip_index[clip.name] = clip
                    self._category_index["phrases"].append(clip.name)
                    loaded += 1

            # Load cached generated speech
            for wav_path in sorted(self._cache_dir.glob("*.wav")):
                clip = self._load_clip(wav_path, category="generated")
                if clip:
                    self._clip_index[clip.name] = clip
                    self._category_index["generated"].append(clip.name)
                    loaded += 1

            self._stats["total_clips_loaded"] = len(self._clip_index)

            if loaded > old_count:
                logger.info(f"Voice cache reloaded: {loaded} clips (+{loaded - old_count} new)")
            else:
                logger.debug(f"Voice cache reloaded: {loaded} clips (no changes)")

            return loaded > 0

    def _load_clip(self, wav_path: Path, category: str) -> Optional[VoiceClip]:
        """Load a single WAV file into a VoiceClip.

        Args:
            wav_path: Path to the WAV file.
            category: Clip category ('jarvis', 'phrases', 'generated').

        Returns:
            VoiceClip if the file is valid, None otherwise.
        """
        try:
            if not wav_path.exists() or wav_path.stat().st_size < 44:
                return None

            audio_bytes = wav_path.read_bytes()
            with wave.open(io.BytesIO(audio_bytes), "rb") as wav:
                sample_rate = wav.getframerate()
                sample_width = wav.getsampwidth()
                channels = wav.getnchannels()
                frames = wav.getnframes()
                duration = frames / sample_rate if sample_rate > 0 else 0.0

            name = wav_path.stem.lower()
            return VoiceClip(
                name=name,
                path=wav_path.resolve(),
                category=category,
                audio_bytes=audio_bytes,
                sample_rate=sample_rate,
                sample_width=sample_width,
                channels=channels,
                duration_seconds=duration,
                size_bytes=wav_path.stat().st_size,
            )
        except Exception as e:
            logger.warning(f"Failed to load voice clip {wav_path.name}: {e}")
            return None

    # ─── Properties ───────────────────────────────────────────────────────

    @property
    def is_ready(self) -> bool:
        """Check if the voice manager is initialized."""
        return len(self._clip_index) > 0

    @property
    def is_playing(self) -> bool:
        """Check if audio is currently playing."""
        return self._is_playing

    @property
    def master_volume(self) -> float:
        """Get master volume (0.0 to 1.0)."""
        return self._master_volume

    @master_volume.setter
    def master_volume(self, value: float) -> None:
        """Set master volume (clamped to 0.0-1.0)."""
        self._master_volume = max(0.0, min(1.0, value))

    @property
    def loaded_clips(self) -> list[str]:
        """Get list of all loaded clip names."""
        return list(self._clip_index.keys())

    @property
    def loaded_count(self) -> int:
        """Get total number of loaded clips."""
        return len(self._clip_index)

    @property
    def stats(self) -> dict[str, Any]:
        """Get voice manager statistics."""
        return dict(self._stats)

    # ─── Callbacks ────────────────────────────────────────────────────────

    def on_playback_start(self, callback: Callable[[str], Any]) -> None:
        """Register callback called when playback starts.

        Args:
            callback: Receives clip_name as argument.
        """
        self._on_playback_start = callback

    def on_playback_end(self, callback: Callable[[str, bool], Any]) -> None:
        """Register callback called when playback ends.

        Args:
            callback: Receives (clip_name, success) as arguments.
        """
        self._on_playback_end = callback

    # ─── Core Playback ────────────────────────────────────────────────────

    async def play(
        self,
        clip_name: str,
        category: str = "jarvis",
        volume: float = DEFAULT_VOLUME,
        speed: float = 1.0,
        fade_in_ms: int = 0,
        fade_out_ms: int = 0,
        priority: PlaybackPriority = PlaybackPriority.MEDIUM,
        allow_interrupt: bool = True,
        text_fallback: Optional[str] = None,
        callback: Optional[Callable[[bool], Any]] = None,
        force_generated: bool = False,
    ) -> bool:
        """Play a voice clip by name.

        Looks up the clip in the index. If not found and text_fallback
        is provided, uses TTS to generate the speech. Queues the
        playback request with the specified priority.

        Args:
            clip_name: Name of the clip (with or without .wav).
            category: Clip category ('jarvis', 'phrases', 'generated').
            volume: Playback volume (0.0-1.0).
            speed: Playback speed multiplier (0.5-2.0).
            fade_in_ms: Fade-in duration in ms.
            fade_out_ms: Fade-out duration in ms.
            priority: Playback priority (higher = interrupts sooner).
            allow_interrupt: Whether this clip can be interrupted.
            text_fallback: Text to synthesize via TTS if clip not found.
            callback: Called with (success: bool) when playback finishes.
            force_generated: Force TTS generation even if clip exists.

        Returns:
            True if the request was queued.
        """
        clip_name = clip_name.lower().removesuffix(".wav")

        # Check if clip exists in index
        clip = self._clip_index.get(clip_name)
        is_generated = False

        if clip is None or force_generated:
            if text_fallback and self._tts and self._tts.is_ready:
                # Generate via TTS and cache
                clip = await self._generate_speech(
                    text=text_fallback,
                    clip_name=clip_name,
                )
                is_generated = True
            elif clip is None:
                self._stats["cache_misses"] += 1
                logger.debug(f"Voice clip '{clip_name}' not found and no fallback text")
                return False
            else:
                # Clip exists but we're forcing re-generation
                pass

        if clip is None:
            return False

        self._stats["cache_hits"] += 1

        # Build fade config
        fade = FadeConfig(
            fade_in_ms=max(0, fade_in_ms),
            fade_out_ms=max(0, fade_out_ms),
        )

        # Create playback request
        request = PlaybackRequest(
            priority=priority,
            created_at=asyncio.get_event_loop().time(),
            clip_name=clip_name,
            category=category,
            volume=max(0.0, min(1.0, volume)),
            speed=max(0.5, min(2.0, speed)),
            fade=fade,
            allow_interrupt=allow_interrupt,
            text_fallback=text_fallback,
            callback=callback,
            is_generated=is_generated,
        )

        await self._queue.put(request)
        self._stats["total_playbacks"] += 1
        return True

    async def play_event(self, event: str, **kwargs: Any) -> bool:
        """Play a voice event by name.

        Convenience wrapper around play() for system events.
        Maps common event names to the corresponding WAV file.

        Args:
            event: Event name (e.g., 'startup', 'listening', 'error').
            **kwargs: Additional arguments passed to play().

        Returns:
            True if the event sound was queued.
        """
        # Map event names to file names
        event_map: dict[str, str] = {
            "startup": "startup",
            "boot": "boot",
            "system_online": "system_online",
            "welcome": "welcome",
            "listening": "listening",
            "thinking": "thinking",
            "processing": "processing",
            "success": "success",
            "completed": "completed",
            "connected": "connected",
            "disconnected": "disconnected",
            "error": "error",
            "warning": "warning",
            "goodbye": "goodbye",
            "shutdown": "shutdown",
            "restart": "restart",
            "confirmation": "confirmation",
        }

        clip_name = event_map.get(event, event)
        kwargs.setdefault("category", "jarvis")

        # Set appropriate priority based on event type
        if event in ("error", "warning", "confirmation"):
            kwargs.setdefault("priority", PlaybackPriority.HIGHEST)
        elif event in ("startup", "boot", "thinking", "listening", "connected"):
            kwargs.setdefault("priority", PlaybackPriority.MEDIUM)
        else:
            kwargs.setdefault("priority", PlaybackPriority.LOW)

        # Set text fallback for critical events
        if event == "error":
            kwargs.setdefault("text_fallback", "Произошла ошибка.")
        elif event == "warning":
            kwargs.setdefault("text_fallback", "Предупреждение.")
        elif event == "connected":
            kwargs.setdefault("text_fallback", "Соединение восстановлено.")
        elif event == "disconnected":
            kwargs.setdefault("text_fallback", "Соединение потеряно.")
        elif event == "confirmation":
            kwargs.setdefault("text_fallback", "Готово.")

        return await self.play(clip_name, **kwargs)

    async def speak(
        self,
        text: str,
        volume: float = DEFAULT_VOLUME,
        priority: PlaybackPriority = PlaybackPriority.MEDIUM,
        cache_key: Optional[str] = None,
    ) -> bool:
        """Speak text using TTS (no prerecorded clip required).

        This is the main method for the assistant to speak arbitrary text.
        It checks the phrase library first; if a matching phrase clip is
        found, plays that instead of synthesizing.

        Args:
            text: Russian text to speak.
            volume: Playback volume.
            priority: Playback priority.
            cache_key: Optional key for caching the generated speech.

        Returns:
            True if speech was queued.
        """
        if not text:
            return False

        # Step 1: Try to match against phrase library
        matched_clip = self.match_phrase(text)
        if matched_clip:
            return await self.play(
                clip_name=matched_clip,
                category="phrases",
                volume=volume,
                priority=priority,
                text_fallback=text,
            )

        # Step 2: Check if we already have a cached generated clip
        cache_key = cache_key or self._text_to_cache_key(text)
        if cache_key in self._clip_index:
            self._stats["cache_hits"] += 1
            return await self.play(
                clip_name=cache_key,
                category="generated",
                volume=volume,
                priority=priority,
            )

        # Step 3: Generate via TTS
        if self._tts and self._tts.is_ready:
            clip = await self._generate_speech(
                text=text,
                clip_name=cache_key,
            )
            if clip:
                self._stats["total_tts_fallbacks"] += 1
                return await self.play(
                    clip_name=cache_key,
                    category="generated",
                    volume=volume,
                    priority=priority,
                )

        logger.warning(f"No TTS engine available to speak: {text[:50]}...")
        return False

    async def play_startup_sequence(self, user_name: str = "Максад") -> None:
        """Play the complete startup sequence.

        Order:
            1. startup.wav (with fade in)
            2. Short pause
            3. Welcome greeting (via TTS or phrase)

        Args:
            user_name: User's name for the greeting.
        """
        logger.info("Playing startup sequence...")

        # Play startup sound
        await self.play_event(
            "startup",
            volume=DEFAULT_VOLUME,
            fade_in_ms=200,
            priority=PlaybackPriority.MEDIUM,
        )

        # Wait for startup to finish (or at least start)
        await asyncio.sleep(0.5)

        # Check if system_online exists
        if "system_online" in self._clip_index:
            await self.play("system_online", priority=PlaybackPriority.MEDIUM)
            await asyncio.sleep(0.3)

        # Speak welcome greeting
        greeting = f"Добро пожаловать, {user_name}. Все системы работают. Чем могу помочь?"
        await self.speak(
            text=greeting,
            priority=PlaybackPriority.LOW,
            cache_key="welcome_greeting",
        )

    async def play_shutdown_sequence(self) -> None:
        """Play the complete shutdown sequence.

        Order:
            1. goodbye.wav
            2. Short pause
            3. shutdown.wav (with fade out)
        """
        logger.info("Playing shutdown sequence...")

        await self.play_event(
            "goodbye",
            volume=DEFAULT_VOLUME,
            priority=PlaybackPriority.MEDIUM,
        )

        await asyncio.sleep(1.0)

        await self.play_event(
            "shutdown",
            volume=DEFAULT_VOLUME,
            fade_out_ms=500,
            priority=PlaybackPriority.MEDIUM,
        )

    async def play_sfx(self, clip_name: str, **kwargs: Any) -> None:
        """Play a sound effect simultaneously with other audio.

        Sound effects are low-priority and run in separate tasks.
        They don't interrupt or get interrupted by regular playback.

        Args:
            clip_name: Name of the SFX clip.
            **kwargs: Additional arguments passed to play().
        """
        kwargs.setdefault("priority", PlaybackPriority.LOWEST)
        kwargs.setdefault("volume", 0.3)  # SFX are quieter
        kwargs.setdefault("allow_interrupt", False)

        # Create a standalone playback task
        async def _sfx_play() -> None:
            await self._internal_play(clip_name, **kwargs)

        task = asyncio.create_task(_sfx_play())
        self._sfx_tasks.add(task)
        task.add_done_callback(self._sfx_tasks.discard)

    # ─── Playback Control ────────────────────────────────────────────────

    async def stop(self) -> None:
        """Stop all current and queued playback immediately."""
        self._is_playing = False

        # Cancel current playback
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            try:
                await self._current_task
            except (asyncio.CancelledError, Exception):
                pass

        # Clear queue
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except asyncio.QueueEmpty:
                break

        # Cancel SFX tasks
        for task in list(self._sfx_tasks):
            task.cancel()

        # Stop audio output
        await self._stop_audio_device()
        logger.debug("Voice playback stopped")

    async def pause(self) -> None:
        """Pause current playback (resume with resume())."""
        self._is_paused = True
        logger.debug("Voice playback paused")

    async def resume(self) -> None:
        """Resume paused playback."""
        self._is_paused = False
        logger.debug("Voice playback resumed")

    async def interrupt(self) -> None:
        """Interrupt current playback (e.g., for new user command).

        This stops the current clip and processes high-priority
        requests from the queue immediately.
        """
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            try:
                await self._current_task
            except (asyncio.CancelledError, Exception):
                pass
            self._stats["interruptions"] += 1
            self._is_playing = False
            await self._stop_audio_device()

    # ─── Phrase Matching ─────────────────────────────────────────────────

    def match_phrase(self, text: str) -> Optional[str]:
        """Smart phrase matching for multilingual text.

        Given a phrase like "Открываю Google Chrome" (Russian) or
        "Chrome och" (Uzbek), this method extracts the app name
        and looks up the corresponding prerecorded phrase clip.

        Strategy:
            1. Check direct match in PHRASE_MAP (English names)
            2. Check RUSSIAN_APP_NAMES for Russian keywords
            3. Check UZBEK_APP_NAMES for Uzbek keywords
            4. Try partial matching on individual words (all languages)
            5. Fall back to fuzzy matching on clip names

        Args:
            text: Text to match (Uzbek, Russian, or English).

        Returns:
            Clip name if a match is found, None otherwise.
        """
        if not text:
            return None

        text_lower = text.lower().strip()

        # 1. Direct match in English PHRASE_MAP
        for keyword, clip_name in PHRASE_MAP.items():
            if keyword in text_lower:
                name = clip_name.removesuffix(".wav")
                if name in self._clip_index:
                    return name

        # 2. Russian keyword matching
        for russian_word, clip_name in RUSSIAN_APP_NAMES.items():
            if russian_word in text_lower:
                name = clip_name.removesuffix(".wav")
                if name in self._clip_index:
                    return name

        # 3. Uzbek keyword matching
        for uzbek_word, clip_name in UZBEK_APP_NAMES.items():
            if uzbek_word in text_lower:
                name = clip_name.removesuffix(".wav")
                if name in self._clip_index:
                    return name

        # 4. Check Uzbek action verbs (UZBEK_ACTIONS)
        # Maps action verbs like "och" → ("opening.wav", "Открываю")
        for action_verb, (phrase_clip, _) in UZBEK_ACTIONS.items():
            if action_verb in text_lower:
                name = phrase_clip.removesuffix(".wav")
                if name in self._clip_index:
                    return name

        # 5. Word-by-word partial matching (all languages)
        words = set(text_lower.split())
        combined_map = {**PHRASE_MAP, **RUSSIAN_APP_NAMES, **UZBEK_APP_NAMES}
        for keyword, clip_name in combined_map.items():
            keyword_words = set(keyword.split())
            if keyword_words & words:
                name = clip_name.removesuffix(".wav")
                if name in self._clip_index:
                    return name

        return None

    # ─── Internal Methods ─────────────────────────────────────────────────

    async def _queue_worker(self) -> None:
        """Background worker that processes the playback queue.

        Continuously pulls PlaybackRequests from the queue and
        plays them. Respects pause state and handles interruptions.
        """
        while True:
            try:
                request: PlaybackRequest = await self._queue.get()

                # Skip if paused
                if self._is_paused:
                    await self._queue.put(request)
                    await asyncio.sleep(0.1)
                    continue

                # If currently playing and new request is higher priority, interrupt
                if self._is_playing and request.allow_interrupt:
                    # High priority (HIGHEST, HIGH) interrupts
                    if request.priority <= PlaybackPriority.HIGH:
                        await self.interrupt()
                    else:
                        # Re-queue low priority if medium is playing
                        await self._queue.put(request)
                        self._queue.task_done()
                        continue

                # Wait for current playback to finish (if any)
                if self._current_task and not self._current_task.done():
                    try:
                        await asyncio.wait_for(
                            asyncio.shield(self._current_task),
                            timeout=None,
                        )
                    except asyncio.CancelledError:
                        pass

                # Play the request
                self._current_task = asyncio.create_task(
                    self._execute_playback(request)
                )

                self._queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Queue worker error: {e}")
                await asyncio.sleep(0.1)

    async def _execute_playback(self, request: PlaybackRequest) -> None:
        """Execute a single playback request.

        Args:
            request: The playback request to execute.
        """
        clip = self._clip_index.get(request.clip_name)
        if clip is None:
            if request.callback:
                try:
                    request.callback(False)
                except Exception:
                    pass
            return

        self._is_playing = True

        if self._on_playback_start:
            try:
                self._on_playback_start(request.clip_name)
            except Exception as e:
                logger.debug(f"Playback start callback error: {e}")

        try:
            success = await self._play_audio(
                clip=clip,
                volume=request.volume * self._master_volume,
                speed=request.speed,
                fade=request.fade,
            )

            if request.callback:
                try:
                    request.callback(success)
                except Exception:
                    pass

            if self._on_playback_end:
                try:
                    self._on_playback_end(request.clip_name, success)
                except Exception as e:
                    logger.debug(f"Playback end callback error: {e}")

        except asyncio.CancelledError:
            logger.debug(f"Playback interrupted: {request.clip_name}")
            if request.callback:
                try:
                    request.callback(False)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Playback failed for '{request.clip_name}': {e}")
            if request.callback:
                try:
                    request.callback(False)
                except Exception:
                    pass
        finally:
            self._is_playing = False

    async def _play_audio(
        self,
        clip: VoiceClip,
        volume: float = 1.0,
        speed: float = 1.0,
        fade: FadeConfig = FadeConfig(),
    ) -> bool:
        """Play audio from a VoiceClip through the system speakers.

        Handles volume adjustment, speed change, fade in/out,
        and actual audio output via sounddevice.

        Args:
            clip: The loaded voice clip to play.
            volume: Volume multiplier (0.0-1.0).
            speed: Playback speed (0.5-2.0).
            fade: Fade in/out configuration.

        Returns:
            True if playback completed successfully.
        """
        try:
            import sounddevice as sd

            # Parse WAV
            with wave.open(io.BytesIO(clip.audio_bytes), "rb") as wav:
                sample_rate = wav.getframerate()
                sample_width = wav.getsampwidth()
                channels = wav.getnchannels()
                raw_frames = wav.readframes(wav.getnframes())

            # Convert to numpy array for processing
            dtype = np.int16 if sample_width == 2 else np.int8
            audio_array = np.frombuffer(raw_frames, dtype=dtype).astype(np.float32)

            # Reshape for multi-channel
            if channels > 1:
                audio_array = audio_array.reshape(-1, channels)

            # Apply speed change (resample)
            if speed != 1.0:
                from scipy import signal
                new_length = int(len(audio_array) / speed)
                if channels > 1:
                    resampled = np.zeros((new_length, channels), dtype=np.float32)
                    for ch in range(channels):
                        resampled[:, ch] = signal.resample(
                            audio_array[:, ch], new_length
                        )
                    audio_array = resampled
                else:
                    audio_array = signal.resample(audio_array, new_length)

            # Apply volume
            audio_array *= volume

            # Apply fade in
            if fade.fade_in_ms > 0:
                fade_in_samples = int(sample_rate * fade.fade_in_ms / 1000)
                fade_in_samples = min(fade_in_samples, len(audio_array))
                fade_curve = np.linspace(0.0, 1.0, fade_in_samples)
                if channels > 1:
                    for ch in range(channels):
                        audio_array[:fade_in_samples, ch] *= fade_curve
                else:
                    audio_array[:fade_in_samples] *= fade_curve

            # Apply fade out
            if fade.fade_out_ms > 0:
                fade_out_samples = int(sample_rate * fade.fade_out_ms / 1000)
                fade_out_samples = min(fade_out_samples, len(audio_array))
                fade_curve = np.linspace(1.0, 0.0, fade_out_samples)
                if channels > 1:
                    for ch in range(channels):
                        audio_array[-fade_out_samples:, ch] *= fade_curve
                else:
                    audio_array[-fade_out_samples:] *= fade_curve

            # Convert back to int16
            audio_array = np.clip(audio_array, -32768, 32767).astype(np.int16)

            # Play in executor to avoid blocking the event loop
            def _play():
                sd.play(audio_array, samplerate=sample_rate)
                sd.wait()

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _play)
            return True

        except ImportError:
            logger.warning("sounddevice not installed. Audio playback unavailable.")
            return False
        except asyncio.CancelledError:
            raise  # Re-raise for proper interrupt handling
        except Exception as e:
            logger.error(f"Audio playback error: {e}")
            return False

    async def _stop_audio_device(self) -> None:
        """Stop any active audio output."""
        try:
            import sounddevice as sd
            sd.stop()
        except ImportError:
            pass

    async def _generate_speech(
        self,
        text: str,
        clip_name: str,
    ) -> Optional[VoiceClip]:
        """Generate speech via TTS and cache the result.

        Args:
            text: Text to synthesize.
            clip_name: Name to use for the cached clip.

        Returns:
            VoiceClip if generation succeeded, None otherwise.
        """
        if not self._tts or not self._tts.is_ready:
            return None

        try:
            result = await self._tts.synthesize(text)
            if not result or not result.success:
                return None

            # Save to cache directory
            cache_path = self._cache_dir / f"{clip_name}.wav"
            cache_path.write_bytes(result.audio_bytes)

            # Create VoiceClip
            clip = VoiceClip(
                name=clip_name,
                path=cache_path,
                category="generated",
                audio_bytes=result.audio_bytes,
                sample_rate=result.sample_rate,
                sample_width=2,  # 16-bit
                channels=result.channels,
                duration_seconds=result.duration_seconds,
                size_bytes=len(result.audio_bytes),
            )

            # Add to index
            self._clip_index[clip_name] = clip
            self._category_index["generated"].append(clip_name)

            logger.debug(
                f"Generated TTS for '{text[:40]}...' -> {clip_name}.wav "
                f"({result.duration_seconds:.1f}s)"
            )
            return clip

        except Exception as e:
            logger.error(f"TTS generation failed for '{text[:30]}...': {e}")
            return None

    async def _internal_play(self, clip_name: str, **kwargs: Any) -> None:
        """Internal one-shot playback (used by SFX)."""
        clip = self._clip_index.get(clip_name.lower().removesuffix(".wav"))
        if clip:
            await self._play_audio(
                clip=clip,
                volume=kwargs.get("volume", DEFAULT_VOLUME) * self._master_volume,
                speed=kwargs.get("speed", 1.0),
                fade=FadeConfig(
                    fade_in_ms=kwargs.get("fade_in_ms", 0),
                    fade_out_ms=kwargs.get("fade_out_ms", 0),
                ),
            )

    @staticmethod
    def _text_to_cache_key(text: str) -> str:
        """Convert text to a cache key for generated speech.

        Args:
            text: Text to convert.

        Returns:
            A deterministic hash-based key.
        """
        import hashlib
        text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()[:16]
        return f"gen_{text_hash}"

    # ─── Diagnostics ──────────────────────────────────────────────────────

    def get_clip_info(self, clip_name: str) -> Optional[dict[str, Any]]:
        """Get information about a loaded clip.

        Args:
            clip_name: Name of the clip.

        Returns:
            Dict with clip info, or None if not found.
        """
        clip = self._clip_index.get(clip_name.lower().removesuffix(".wav"))
        if clip:
            return clip.to_dict()
        return None

    def get_all_clips(self, category: Optional[str] = None) -> list[dict[str, Any]]:
        """Get information about all loaded clips.

        Args:
            category: Optional filter ('jarvis', 'phrases', 'generated').

        Returns:
            List of clip info dicts.
        """
        if category:
            names = self._category_index.get(category, [])
            return [
                self._clip_index[name].to_dict()
                for name in names
                if name in self._clip_index
            ]
        return [clip.to_dict() for clip in self._clip_index.values()]

    def get_diagnostics(self) -> dict[str, Any]:
        """Get comprehensive diagnostics for the voice manager."""
        return {
            "ready": self.is_ready,
            "playing": self._is_playing,
            "paused": self._is_paused,
            "master_volume": self._master_volume,
            "clip_count": self.loaded_count,
            "queue_size": self._queue.qsize(),
            "sfx_tasks": len(self._sfx_tasks),
            "clips_by_category": {
                cat: len(names) for cat, names in self._category_index.items()
            },
            "assets_dir": str(self._assets_dir),
            "phrases_dir": str(self._phrases_dir),
            "cache_dir": str(self._cache_dir),
            "tts_available": self._tts is not None and self._tts.is_ready,
            "stats": self._stats,
        }

    # ─── Shutdown ─────────────────────────────────────────────────────────

    async def shutdown(self) -> None:
        """Gracefully shut down the voice manager.

        Stops all playback, saves cache metadata, cancels worker tasks.
        """
        logger.info("Shutting down Voice Manager...")

        # Stop playback
        await self.stop()

        # Cancel queue worker
        if self._queue_worker_task and not self._queue_worker_task.done():
            self._queue_worker_task.cancel()
            try:
                await self._queue_worker_task
            except (asyncio.CancelledError, Exception):
                pass

        # Clean up empty cache files
        try:
            empty_files = list(self._cache_dir.glob("*.wav"))
            for f in empty_files:
                if f.stat().st_size < 44:
                    f.unlink(missing_ok=True)
        except Exception:
            pass

        self._clip_index.clear()
        logger.info("Voice Manager shut down")

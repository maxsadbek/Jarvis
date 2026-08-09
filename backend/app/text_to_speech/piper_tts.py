"""Piper TTS Implementation.

Local text-to-speech using Piper TTS engine.
Produces high-quality WAV audio with multiple voice options.

Optional RVC post-processing: when RVC_ENABLED is true and a trained RVC
model (jarvis.pth / jarvis.index) is present, the synthesized Piper audio is
converted to the JARVIS voice. RVC inference runs on CPU via rvc-python —
either in-process (if importable) or through a persistent subprocess worker
that uses a separate Python 3.10 venv (see rvc_worker.py).
"""

from __future__ import annotations

import asyncio
import io
import json
import tempfile
import wave
from pathlib import Path
from typing import Optional

from loguru import logger

from backend.app.config import settings
from backend.app.text_to_speech.engine import TTSEngine, TTSResult


class RVCPostProcessor:
    """Applies RVC voice conversion to Piper output (Jarvis voice).

    rvc-python pins numpy<=1.23.5, which is incompatible with the Python
    3.11+ interpreter used by the backend. So, if rvc-python is not
    importable in this environment, a persistent subprocess worker running
    under a dedicated Python 3.10 venv is spawned (RVC_PYTHON_PATH).
    """

    def __init__(self) -> None:
        self._rvc: Optional[object] = None  # in-process engine
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._lock = asyncio.Lock()
        self._ready = False

    @property
    def is_ready(self) -> bool:
        return self._ready

    async def initialize(self) -> bool:
        """Load the RVC model (in-process or via worker subprocess)."""
        if not settings.RVC_ENABLED:
            return False

        model_dir = Path(settings.RVC_MODEL_DIR) / settings.RVC_MODEL_NAME
        if not (model_dir / f"{settings.RVC_MODEL_NAME}.pth").exists():
            logger.warning(
                f"RVC model topilmadi: {model_dir} — 'jarvis.pth' va 'jarvis.index' "
                f"fayllarini shu papkaga qo'ying (rvc_training/QOLLANMA.md ga qarang)."
            )
            return False

        # 1) In-process: rvc-python bu muhitda import bo'lsa (masalan Linux dev muhiti)
        try:
            from rvc_python.infer import RVCInference

            self._rvc = RVCInference(models_dir=str(settings.RVC_MODEL_DIR), device="cpu")
            self._rvc.load_model(settings.RVC_MODEL_NAME)
            self._rvc.set_params(
                f0up_key=settings.RVC_F0_UP_KEY,
                f0method=settings.RVC_F0_METHOD,
                index_rate=settings.RVC_INDEX_RATE,
                protect=settings.RVC_PROTECT,
                rms_mix_rate=settings.RVC_RMS_MIX_RATE,
            )
            self._ready = True
            logger.info(f"✓ RVC voice conversion ready ({settings.RVC_MODEL_NAME}, in-process)")
            return True
        except ImportError:
            pass  # subprocess worker yo'lidan boramiz
        except Exception as e:
            self._rvc = None  # yarim initsializatsiya qilingan motorni tozalaymiz
            logger.error(f"RVC in-process init muvaffaqiyatsiz: {e}")

        # 2) Subprocess worker (Python 3.10 venv)
        try:
            import shutil
            import sys

            python = settings.RVC_PYTHON_PATH
            if not python:
                python = shutil.which("python3.10") or shutil.which("python")
                if not python and sys.platform == "win32":
                    # Windows py launcher orqali Python 3.10'ni topish
                    try:
                        probe = await asyncio.create_subprocess_exec(
                            "py", "-3.10", "-c", "import sys; print(sys.executable)",
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.DEVNULL,
                        )
                        out, _ = await asyncio.wait_for(probe.communicate(), timeout=15)
                        if probe.returncode == 0:
                            python = out.decode().strip()
                    except Exception:
                        pass
            python = python or "python"

            worker = Path(__file__).with_name("rvc_worker.py")
            self._proc = await asyncio.create_subprocess_exec(
                python,
                str(worker),
                "--model-dir", str(settings.RVC_MODEL_DIR),
                "--model-name", settings.RVC_MODEL_NAME,
                "--f0-method", settings.RVC_F0_METHOD,
                "--index-rate", str(settings.RVC_INDEX_RATE),
                "--protect", str(settings.RVC_PROTECT),
                "--rms-mix-rate", str(settings.RVC_RMS_MIX_RATE),
                "--f0-up-key", str(settings.RVC_F0_UP_KEY),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self._writer = self._proc.stdin
            self._reader = self._proc.stdout

            resp = await self._rpc({"cmd": "ping"})
            if resp and resp.get("ok"):
                if resp.get("rvc_available", True):
                    self._ready = True
                    logger.info(f"✓ RVC voice conversion ready ({settings.RVC_MODEL_NAME}, worker)")
                    return True
                logger.error(
                    "RVC worker ishlayapti, lekin unda 'rvc_python' o'rnatilmagan. "
                    "RVC_PYTHON_PATH sozlamasini Python 3.10 venv'dagi python.exe manziliga "
                    "ko'rsating (rvc_training/QOLLANMA.md ga qarang)."
                )
            else:
                logger.error(f"RVC worker javob bermadi: {resp}")
        except Exception as e:
            logger.error(f"RVC worker ishga tushmadi: {e}")

        self._ready = False
        return False

    async def _rpc(self, req: dict) -> Optional[dict]:
        """Send one JSON request to the worker and await the reply.

        Replies are prefixed with "RVC:" so stray stdout prints from
        rvc-python (e.g. base model downloads) do not break the protocol.
        """
        if not self._writer or not self._reader:
            return None
        try:
            self._writer.write((json.dumps(req) + "\n").encode("utf-8"))
            await self._writer.drain()
            # Uzoq vaqt limiti: birinchi convert'da worker asosiy modellarni
            # (~500 MB) yuklab olishi mumkin, shuning uchun 600 soniya qo'yamiz.
            while True:
                line = await asyncio.wait_for(self._reader.readline(), timeout=600)
                if not line:
                    return None  # worker exited
                line = line.decode("utf-8", errors="replace").strip()
                if line.startswith("RVC:"):
                    return json.loads(line[4:])
                # Boshqa chiqishlar (rvc-python print'lari) — e'tiborsiz qoldiramiz
                logger.debug(f"RVC worker: {line}")
        except Exception as e:
            logger.error(f"RVC worker RPC xatosi: {e}")
            return None

    async def convert(self, wav_bytes: bytes) -> bytes:
        """Convert a Piper WAV to the JARVIS voice.

        On any failure the original audio is returned so TTS never breaks.
        """
        if not self._ready:
            return wav_bytes
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                in_path = tmp_path / "in.wav"
                out_path = tmp_path / "out.wav"
                in_path.write_bytes(wav_bytes)

                async with self._lock:
                    if self._rvc is not None:
                        await asyncio.to_thread(self._rvc.infer_file, str(in_path), str(out_path))
                    else:
                        resp = await self._rpc({"cmd": "convert", "input": str(in_path), "output": str(out_path)})
                        if not resp or not resp.get("ok"):
                            raise RuntimeError(f"worker: {resp}")

                if not out_path.exists():
                    raise RuntimeError("RVC chiqish fayli yaratilmadi")
                return out_path.read_bytes()
        except Exception as e:
            logger.warning(f"RVC conversion xatosi, asl audio qaytariladi: {e}")
            return wav_bytes

    async def close(self) -> None:
        """Terminate the worker process if running."""
        if self._proc:
            try:
                self._proc.terminate()
                await asyncio.wait_for(self._proc.wait(), timeout=5)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
        self._proc = None
        self._writer = None
        self._reader = None
        self._rvc = None
        self._ready = False


class PiperTTS(TTSEngine):
    """Text-to-speech using Piper TTS (local, fast)."""

    def __init__(self) -> None:
        super().__init__()
        self._voice = None
        self._rvc = RVCPostProcessor()

    async def initialize(self) -> bool:
        """Load the Piper voice model."""
        try:
            from piper import PiperVoice

            voice_name = settings.PIPER_VOICE_MODEL
            voice_path = settings.PIPER_VOICE_PATH
            models_dir = settings.get_model_path()

            if voice_path:
                model_path = Path(voice_path)
            else:
                # Try the configured voice first, then the fallback list, so
                # an Uzbek-friendly voice (ru_RU / tr_TR) is used when the
                # primary model file is missing.
                model_path = None
                candidates = [voice_name, *settings.PIPER_VOICE_FALLBACK_MODELS]
                for candidate in candidates:
                    # Search recursively so BOTH layouts work:
                    #  - flat:           data/models/<voice>.onnx
                    #  - hf_hub_download: data/models/<lang>/<lang>_<REGION>/<voice>/<quality>/<voice>.onnx
                    candidate_paths = sorted(models_dir.glob(f"**/{candidate}.onnx"))
                    if candidate_paths:
                        model_path = candidate_paths[0]
                        voice_name = candidate
                        break

                if model_path is None:
                    logger.warning(
                        f"Piper voice model not found for any of: "
                        f"{', '.join(candidates)}.\n"
                        f"Download from: https://github.com/rhasspy/piper/releases\n"
                        f"Place the .onnx and .json files in {models_dir}"
                    )
                    return False

            # Piper convention: config is <model>.onnx.json (NOT <model>.json)
            json_path = Path(str(model_path) + ".json")
            if not json_path.exists():
                logger.warning(
                    f"Piper voice config not found at {json_path}. "
                    f"The .json file must accompany the .onnx model."
                )
                return False

            logger.info(f"Loading Piper voice: {model_path.name}...")
            self._voice = PiperVoice.load(str(model_path))
            self._voice_name = voice_name
            self._initialized = True
            logger.info(f"✓ Piper TTS ready ({voice_name})")

            # Optional RVC voice conversion (Jarvis ovozi) — failure is non-fatal
            await self._rvc.initialize()
            return True

        except ImportError:
            logger.warning("piper-tts not installed. TTS unavailable.")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize Piper TTS: {e}")
            return False

    async def synthesize(self, text: str) -> TTSResult:
        """Synthesize text to WAV audio."""
        if not self.is_ready or not self._voice or not text.strip():
            return TTSResult(
                audio_bytes=b"",
                text=text,
                error="TTS engine not initialized" if not self.is_ready else "Empty text",
            )

        try:
            audio_buffer = io.BytesIO()
            with wave.open(audio_buffer, "wb") as wav_file:
                if hasattr(self._voice, "synthesize_wav"):
                    # piper-tts >= 1.3: chunk-based API, speed via SynthesisConfig
                    from piper.voice import SynthesisConfig

                    self._voice.synthesize_wav(
                        text,
                        wav_file,
                        syn_config=SynthesisConfig(
                            length_scale=1.0 / settings.TTS_SPEED,
                        ),
                    )
                else:
                    # piper 1.2.x legacy API
                    self._voice.synthesize(
                        text,
                        wav_file,
                        speaker_id=None,
                        length_scale=1.0 / settings.TTS_SPEED,
                    )

            audio_bytes = audio_buffer.getvalue()

            # Optional: RVC voice conversion — Piper nutqini Jarvis ovoziga o'zgartirish
            if self._rvc.is_ready and audio_bytes:
                audio_bytes = await self._rvc.convert(audio_bytes)

            # Calculate duration from WAV header (RVC output sample rate may differ)
            with wave.open(io.BytesIO(audio_bytes), "rb") as wav:
                sample_rate = wav.getframerate()
                frames = wav.getnframes()
                duration = frames / sample_rate

            logger.debug(f"Synthesized {len(text)} chars -> {len(audio_bytes)} bytes ({duration:.1f}s)")

            return TTSResult(
                audio_bytes=audio_bytes,
                sample_rate=sample_rate,
                channels=1,
                bit_depth=16,
                format="wav",
                duration_seconds=duration,
                text=text,
            )

        except Exception as e:
            logger.error(f"Piper synthesis failed: {e}")
            return TTSResult(
                audio_bytes=b"",
                text=text,
                error=str(e),
            )

    async def close(self) -> None:
        """Release voice resources."""
        self._voice = None
        self._initialized = False
        await self._rvc.close()
        logger.info("Piper TTS shut down")

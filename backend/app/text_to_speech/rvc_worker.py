"""Persistent RVC inference worker.

Runs under a *separate* Python 3.10 virtual environment because
``rvc-python`` pins ``numpy<=1.23.5``, which does not support Python 3.11+
used by the JARVIS backend. The backend (``piper_tts.py``) spawns this
process once at startup and talks to it over JSON-lines on stdin/stdout.

Protocol (requests are one JSON object per line; replies are prefixed with
"RVC:" so that stray prints from rvc-python do not corrupt the protocol):
    -> {"cmd": "ping"}
    <- RVC:{"ok": true, "loaded": bool}

    -> {"cmd": "convert", "input": "/path/in.wav", "output": "/path/out.wav"}
    <- RVC:{"ok": true}  |  RVC:{"ok": false, "error": "..."}

Usage:
    python rvc_worker.py --model-dir data/models/rvc --model-name jarvis \
        --f0-method harvest --index-rate 0.7 --protect 0.33 \
        --rms-mix-rate 0.8 --f0-up-key 0

See rvc_training/QOLLANMA.md for setup instructions.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Persistent RVC inference worker")
    parser.add_argument("--model-dir", required=True, help="Folder containing model subfolders")
    parser.add_argument("--model-name", required=True, help="Model subfolder name (e.g. jarvis)")
    parser.add_argument("--f0-method", default="harvest")
    parser.add_argument("--index-rate", type=float, default=0.7)
    parser.add_argument("--protect", type=float, default=0.33)
    parser.add_argument("--rms-mix-rate", type=float, default=0.8)
    parser.add_argument("--f0-up-key", type=int, default=0)
    return parser.parse_args()


class RVCWorker:
    """Loads the RVC model lazily and converts audio on request."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self._rvc: Any = None

    def _ensure_loaded(self) -> None:
        """Load the RVC model once (lazy import keeps startup cheap)."""
        if self._rvc is not None:
            return
        from rvc_python.infer import RVCInference  # noqa: E402  (lazy import)

        self._rvc = RVCInference(models_dir=str(self.args.model_dir), device="cpu")
        self._rvc.load_model(self.args.model_name)
        self._rvc.set_params(
            f0up_key=self.args.f0_up_key,
            f0method=self.args.f0_method,
            index_rate=self.args.index_rate,
            protect=self.args.protect,
            rms_mix_rate=self.args.rms_mix_rate,
        )

    def _handle(self, req: dict) -> dict:
        cmd = req.get("cmd")
        if cmd == "ping":
            import importlib.util

            return {
                "ok": True,
                "loaded": self._rvc is not None,
                "rvc_available": importlib.util.find_spec("rvc_python") is not None,
            }
        if cmd == "convert":
            try:
                self._ensure_loaded()
                in_path = req["input"]
                out_path = req["output"]
                if not Path(in_path).exists():
                    raise RuntimeError(f"Input file not found: {in_path}")
                self._rvc.infer_file(in_path, out_path)
                if not Path(out_path).exists():
                    raise RuntimeError("Output file was not created")
                return {"ok": True}
            except Exception as e:  # noqa: BLE001  (report to backend)
                return {"ok": False, "error": f"{type(e).__name__}: {e}"}
        return {"ok": False, "error": f"Unknown command: {cmd}"}

    def run(self) -> None:
        """Read JSON requests from stdin until EOF."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
                resp = self._handle(req)
            except Exception as e:  # noqa: BLE001
                resp = {"ok": False, "error": f"{type(e).__name__}: {e}"}
            sys.stdout.write("RVC:" + json.dumps(resp) + "\n")
            sys.stdout.flush()


def main() -> None:
    RVCWorker(parse_args()).run()


if __name__ == "__main__":
    main()

"""Generate placeholder WAV files for JARVIS voice clips.
Creates minimal valid WAV files with short audible sine wave tones.
"""

import io
import wave
import struct
import math
from pathlib import Path


BASE_DIR = Path("assets/voices/jarvis")
PHRASES_DIR = BASE_DIR / "phrases"
SAMPLE_RATE = 22050

SYSTEM_SOUNDS = [
    "startup", "boot", "system_online", "welcome", "welcome_back",
    "listening", "thinking", "processing", "executing", "success",
    "completed", "connected", "disconnected", "error", "warning",
    "goodbye", "shutdown", "restart", "confirmation",
]

PHRASE_SOUNDS = [
    "chrome", "youtube", "telegram", "discord", "spotify",
    "browser", "edge", "firefox", "opera", "vscode", "cursor",
    "notepad", "calculator", "settings", "downloads", "documents",
    "pictures", "music", "videos", "desktop", "taskmanager",
    "explorer", "controlpanel", "powershell", "cmd", "terminal",
    "opening", "closing", "searching", "loading", "launching",
    "executing", "done", "finished", "search", "restart",
    "shutdown", "completed",
]


def make_wav(duration_sec, freq_hz, amplitude=0.3):
    """Generate a WAV file with a sine wave tone."""
    num_samples = int(SAMPLE_RATE * duration_sec)
    fade_n = int(SAMPLE_RATE * 0.05)
    samples = []
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        v = math.sin(2 * math.pi * freq_hz * t) * amplitude
        if i < fade_n:
            v *= i / fade_n
        if i > num_samples - fade_n:
            v *= (num_samples - i) / fade_n
        samples.append(int(v * 32767))

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(struct.pack("<" + "h" * len(samples), *samples))
    return buf.getvalue()


def main():
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    PHRASES_DIR.mkdir(parents=True, exist_ok=True)

    ok = 0
    fail = 0

    # System sounds (660Hz, 1.5s)
    print("=== System sounds ===")
    for name in SYSTEM_SOUNDS:
        try:
            path = BASE_DIR / f"{name}.wav"
            path.write_bytes(make_wav(1.5, 660))
            sz = path.stat().st_size
            print(f"  [+] {name}.wav ({sz} bytes)")
            ok += 1
        except Exception as e:
            print(f"  [X] {name}.wav: {e}")
            fail += 1

    # Phrase sounds (440Hz, 0.8s)
    print("\n=== Phrase sounds ===")
    for name in PHRASE_SOUNDS:
        try:
            path = PHRASES_DIR / f"{name}.wav"
            path.write_bytes(make_wav(0.8, 440))
            sz = path.stat().st_size
            print(f"  [+] {name}.wav ({sz} bytes)")
            ok += 1
        except Exception as e:
            print(f"  [X] {name}.wav: {e}")
            fail += 1

    total = len(SYSTEM_SOUNDS) + len(PHRASE_SOUNDS)
    print(f"\nDone: {ok}/{total} generated, {fail} errors")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    exit(main())

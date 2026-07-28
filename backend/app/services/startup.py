"""JARVIS Windows Startup Service.

Handles:
- Auto-launching the backend as a background process (no window)
- Health monitoring with automatic restart
- Windows startup registration
- Graceful shutdown
- Silent operation (no console window)
- Startup greeting via VoiceManager (prerecorded WAV + TTS fallback)

This is the primary entry point for the Windows assistant experience.

The VoiceGreetingService now integrates with the VoiceManager for
professional startup sequences:
    startup.wav -> system_online.wav -> "Добро пожаловать" (via TTS)
"""

from __future__ import annotations

import asyncio
import os
import platform
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from loguru import logger


# ─── Configuration ───────────────────────────────────────────────────────────

@dataclass
class StartupConfig:
    """Configuration for the startup service."""
    backend_url: str = "http://127.0.0.1:8000"
    health_endpoint: str = "/api/health"
    health_check_interval: float = 5.0  # Seconds between health checks
    startup_timeout: float = 30.0  # Max seconds to wait for backend to start
    restart_delay: float = 3.0  # Delay before restarting
    max_restarts: int = 5  # Max restart attempts in a window
    restart_window_minutes: int = 5  # Time window for restart counting

    # Backend process settings
    backend_script: str = ""
    backend_module: str = "backend.main"
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    python_path: str = ""

    # Logging
    log_dir: str = "data/logs"
    log_level: str = "INFO"

    def __post_init__(self) -> None:
        if not self.python_path:
            self.python_path = sys.executable or "python"
        if not self.backend_script:
            # Try to find main.py relative to this file
            possible = [
                Path(__file__).resolve().parent.parent.parent / "main.py",
                Path.cwd() / "backend" / "main.py",
                Path.cwd() / "main.py",
            ]
            for p in possible:
                if p.exists():
                    self.backend_script = str(p)
                    break


# ─── Windows Startup Manager ────────────────────────────────────────────────

class WindowsStartupManager:
    """Manages Windows auto-start registration for JARVIS."""

    @staticmethod
    def is_windows() -> bool:
        return platform.system() == "Windows"

    @staticmethod
    def get_startup_script_path() -> Path:
        """Get path to the startup script in user's AppData."""
        appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        jarvis_dir = Path(appdata) / "JARVIS"
        jarvis_dir.mkdir(parents=True, exist_ok=True)
        return jarvis_dir / "start_jarvis_backend.vbs"

    @staticmethod
    def create_startup_script(python_path: str, backend_script: str) -> Path:
        """Create a VBS script that starts the backend silently (no window).

        VBScript is used because it can launch processes completely hidden
        on Windows, unlike batch files which flash a console window.
        """
        script_path = WindowsStartupManager.get_startup_script_path()

        content = f"""' JARVIS Backend Silent Launcher
' This script launches the backend without any visible window.
' Created: {datetime.now().isoformat()}

Dim shell, pythonExe, scriptPath

Set shell = CreateObject("WScript.Shell")

pythonExe = "{python_path}"
scriptPath = "{backend_script}"

' Run with window style 0 (hidden)
shell.Run chr(34) & pythonExe & chr(34) & " " & chr(34) & scriptPath & chr(34), 0, False

Set shell = Nothing
"""

        script_path.write_text(content, encoding="utf-8")
        logger.info(f"Created startup script: {script_path}")
        return script_path

    @staticmethod
    def register_auto_start(script_path: Optional[Path] = None) -> bool:
        """Register JARVIS to start automatically with Windows.

        Uses the Windows registry Run key to start the backend silently.
        """
        if not WindowsStartupManager.is_windows():
            logger.warning("Auto-start is only supported on Windows")
            return False

        try:
            import winreg

            if script_path is None:
                script_path = WindowsStartupManager.get_startup_script_path()

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE,
            )
            winreg.SetValueEx(key, "JARVIS Backend", 0, winreg.REG_SZ, str(script_path))
            winreg.CloseKey(key)
            logger.info("JARVIS registered for Windows auto-start")
            return True
        except Exception as e:
            logger.warning(f"Failed to register auto-start: {e}")
            return False

    @staticmethod
    def unregister_auto_start() -> bool:
        """Remove JARVIS from Windows auto-start."""
        if not WindowsStartupManager.is_windows():
            return False

        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE,
            )
            try:
                winreg.DeleteValue(key, "JARVIS Backend")
            except FileNotFoundError:
                pass
            winreg.CloseKey(key)
            logger.info("JARVIS removed from Windows auto-start")
            return True
        except Exception as e:
            logger.warning(f"Failed to unregister auto-start: {e}")
            return False

    @staticmethod
    def is_auto_start_enabled() -> bool:
        """Check if JARVIS is registered for auto-start."""
        if not WindowsStartupManager.is_windows():
            return False

        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_READ,
            )
            try:
                value, _ = winreg.QueryValueEx(key, "JARVIS Backend")
                winreg.CloseKey(key)
                return Path(value).exists()
            except FileNotFoundError:
                winreg.CloseKey(key)
                return False
        except Exception:
            return False


# ─── Backend Process Manager ────────────────────────────────────────────────

class BackendProcessManager:
    """Manages the backend process lifecycle.

    Features:
    - Silent launch (no console window)
    - Health monitoring with HTTP health checks
    - Automatic restart on crash
    - Graceful shutdown on SIGTERM/SIGINT
    - Restart rate limiting
    """

    def __init__(self, config: Optional[StartupConfig] = None) -> None:
        self._config = config or StartupConfig()
        self._process: Optional[subprocess.Popen] = None
        self._running = False
        self._restart_count = 0
        self._restart_window_start = time.time()
        self._start_time: Optional[float] = None

        # Async tasks
        self._monitor_task: Optional[asyncio.Task] = None
        self._health_task: Optional[asyncio.Task] = None

        # Lock for thread-safe start/stop/restart operations
        self._operation_lock = asyncio.Lock()

        # Set up logging
        log_path = Path(self._config.log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        logger.add(
            str(log_path / "backend_service_{time:YYYY-MM-DD}.log"),
            rotation="10 MB",
            retention="30 days",
            level=self._config.log_level,
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<7} | {message}",
        )

    # ─── Process Lifecycle ─────────────────────────────────────────────────

    async def start(self) -> bool:
        """Start the backend process silently.

        On Windows, uses subprocess with CREATE_NO_WINDOW flag.
        On other platforms, starts normally.
        """
        async with self._operation_lock:
            if not self._running:
                self._running = True

            if not self._config.backend_script:
                logger.error("Backend script not found. Cannot start.")
                return False

            cmd = [
                self._config.python_path,
                self._config.backend_script,
                f"--host={self._config.backend_host}",
                f"--port={self._config.backend_port}",
            ]

            logger.info(f"Starting JARVIS backend: {' '.join(cmd)}")
            self._start_time = time.time()

            try:
                if platform.system() == "Windows":
                    # CREATE_NO_WINDOW = 0x08000000
                    # DETACHED_PROCESS = 0x00000008
                    self._process = subprocess.Popen(
                        cmd,
                        creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        stdin=subprocess.DEVNULL,
                    )
                else:
                    self._process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        stdin=subprocess.DEVNULL,
                        start_new_session=True,
                    )

                logger.info(f"Backend process started (PID: {self._process.pid})")

                # Wait for backend to become healthy
                if await self._wait_for_healthy():
                    logger.info("✓ Backend is healthy and ready")
                    # Start monitoring
                    self._start_monitoring()
                    return True
                else:
                    logger.error("Backend started but health check failed")
                    await self.stop()
                    return False

            except Exception as e:
                logger.error(f"Failed to start backend: {e}")
                self._running = False
                return False

    async def stop(self) -> None:
        """Gracefully stop the backend process."""
        async with self._operation_lock:
            self._running = False

            # Cancel monitoring tasks
            if self._monitor_task and not self._monitor_task.done():
                self._monitor_task.cancel()
            if self._health_task and not self._health_task.done():
                self._health_task.cancel()

            if self._process:
                logger.info(f"Stopping backend (PID: {self._process.pid})...")
                try:
                    if platform.system() == "Windows":
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(self._process.pid)],
                            capture_output=True, timeout=5,
                        )
                    else:
                        os.killpg(os.getpgid(self._process.pid), signal.SIGTERM)
                        try:
                            self._process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            self._process.kill()
                            self._process.wait(timeout=5)
                except Exception as e:
                    logger.warning(f"Error stopping backend: {e}")
                finally:
                    self._process = None
                    logger.info("Backend stopped")

    # ─── Health Monitoring ─────────────────────────────────────────────────

    async def _check_health(self) -> bool:
        """Check if the backend is healthy via HTTP.

        Uses stdlib urllib to avoid extra dependencies.
        """
        import json as json_mod
        import urllib.request
        import urllib.error

        url = f"{self._config.backend_url}{self._config.health_endpoint}"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                if resp.status == 200:
                    data = json_mod.loads(resp.read().decode("utf-8"))
                    return data.get("status") == "healthy"
                return False
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError):
            return False

    async def _wait_for_healthy(self) -> bool:
        """Wait for the backend to report healthy.

        Returns:
            True if backend became healthy within timeout.
        """
        start = time.time()
        while time.time() - start < self._config.startup_timeout:
            if await self._check_health():
                return True
            await asyncio.sleep(1.0)

        # Check if process is still running
        if self._process and self._process.poll() is not None:
            logger.error(f"Backend process exited with code {self._process.returncode}")
            # Capture output for debugging
            if self._process.stdout:
                try:
                    stdout = self._process.stdout.read(2000).decode("utf-8", errors="replace")
                    if stdout:
                        logger.error(f"STDOUT: {stdout[:500]}")
                except Exception:
                    pass
            if self._process.stderr:
                try:
                    stderr = self._process.stderr.read(2000).decode("utf-8", errors="replace")
                    if stderr:
                        logger.error(f"STDERR: {stderr[:500]}")
                except Exception:
                    pass

        return False

    async def _health_loop(self) -> None:
        """Continuously monitor backend health and restart if needed."""
        while self._running:
            try:
                await asyncio.sleep(self._config.health_check_interval)
                if not self._running:
                    break

                healthy = await self._check_health()
                if not healthy and self._running:
                    logger.warning("Backend health check failed")
                    await self._handle_crash()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health monitoring error: {e}")
                if self._running:
                    await self._handle_crash()

    def _start_monitoring(self) -> None:
        """Start health monitoring and process monitoring tasks."""
        if self._health_task is None or self._health_task.done():
            self._health_task = asyncio.create_task(self._health_loop())

        if self._monitor_task is None or self._monitor_task.done():
            self._monitor_task = asyncio.create_task(self._process_monitor())

    async def _process_monitor(self) -> None:
        """Monitor the process to detect unexpected exits."""
        if not self._process:
            return

        try:
            returncode = await asyncio.get_event_loop().run_in_executor(
                None, self._process.wait
            )
            if self._running and returncode != 0:
                logger.warning(f"Backend process exited unexpectedly (code: {returncode})")
                await self._handle_crash()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Process monitor error: {e}")

    async def _handle_crash(self) -> None:
        """Handle a backend crash with rate-limited restart.

        Protected by _operation_lock to prevent race conditions
        with concurrent stop() calls.
        """
        async with self._operation_lock:
            if not self._running:
                return

            # Check restart rate limit
            now = time.time()
            if now - self._restart_window_start > self._config.restart_window_minutes * 60:
                self._restart_count = 0
                self._restart_window_start = now

            self._restart_count += 1
            if self._restart_count > self._config.max_restarts:
                logger.critical(
                    f"Backend crashed {self._restart_count} times in "
                    f"{self._config.restart_window_minutes} minutes. Giving up."
                )
                self._running = False
                return

            logger.info(f"Restarting backend (attempt {self._restart_count}/{self._config.max_restarts})...")

        # Sleep outside lock to allow other operations
        await asyncio.sleep(self._config.restart_delay)

        async with self._operation_lock:
            if not self._running:
                return

            # Kill any remaining process
            if self._process:
                try:
                    if platform.system() == "Windows":
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(self._process.pid)],
                            capture_output=True, timeout=3,
                        )
                    else:
                        self._process.kill()
                except Exception:
                    pass
                self._process = None

        # Restart (start() acquires its own lock)
        success = await self.start()
        if success:
            logger.info("✓ Backend restarted successfully")
        else:
            logger.error("✗ Backend restart failed")

    # ─── Stats ─────────────────────────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        """Get current status of the backend manager."""
        uptime = time.time() - self._start_time if self._start_time else 0.0
        return {
            "running": self._running,
            "process_running": self._process is not None and self._process.poll() is None,
            "pid": self._process.pid if self._process else None,
            "uptime_seconds": uptime,
            "restart_count": self._restart_count,
            "config": {
                "host": self._config.backend_host,
                "port": self._config.backend_port,
                "auto_start": WindowsStartupManager.is_auto_start_enabled(),
            },
        }


# ─── Voice Greeting Service ─────────────────────────────────────────────────

class VoiceGreetingService:
    """Handles the startup greeting with Windows TTS."""

    @staticmethod
    def speak(text: str, language: str = "ru") -> bool:
        """Speak text using Windows SAPI (no visible window).

        Uses PowerShell to invoke the Windows Speech API silently.
        Supports Russian and English voices.

        Args:
            text: Text to speak.
            language: Language code ('ru', 'en', 'uz').

        Returns:
            True if speech synthesis was initiated.
        """
        if platform.system() != "Windows":
            logger.info(f"[VOICE GREETING] {text}")
            return False

        try:
            # Select voice based on language
            voice_selector = ""
            if language == "ru":
                voice_selector = "$voice = $speak.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture -like 'ru-*' } | Select-Object -First 1; if ($voice) { $speak.SelectVoice($voice.VoiceInfo.Name) }"
            elif language == "uz":
                voice_selector = ""

            safe_text = text.replace("'", "''").replace('"', '""')
            script = (
                f"Add-Type -AssemblyName System.Speech; "
                f"$speak = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                f"{voice_selector} "
                f"$speak.Speak('{safe_text}')"
            )

            subprocess.Popen(
                [
                    "powershell",
                    "-NoProfile",
                    "-NonInteractive",
                    "-WindowStyle", "Hidden",
                    "-Command", script,
                ],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            logger.info(f"Spoke greeting: {text[:50]}...")
            return True
        except Exception as e:
            logger.warning(f"Voice greeting failed: {e}")
            return False

    @staticmethod
    def get_greeting(user_name: str = "Maxsad", language: str = "ru") -> str:
        """Get the startup greeting text.

        Args:
            user_name: User's name.
            language: Language code.

        Returns:
            Greeting text in the specified language.
        """
        greetings = {
            "ru": f"Добро пожаловать, {user_name}. Чем могу помочь?",
            "en": f"Welcome back, {user_name}. How can I assist you?",
            "uz": f"Xush kelibsiz, {user_name}. Qanday yordam bera olaman?",
            "de": f"Willkommen zurück, {user_name}. Wie kann ich Ihnen helfen?",
            "fr": f"Bienvenue, {user_name}. Comment puis-je vous aider?",
        }
        return greetings.get(language, greetings["en"])


# ─── Main Entry Point ───────────────────────────────────────────────────────

async def run_service(config: Optional[StartupConfig] = None) -> None:
    """Run the JARVIS Windows backend service.

    This is the main entry point for the background service.
    It:
    1. Starts the backend silently
    2. Monitors its health
    3. Auto-restarts on crash
    4. Handles graceful shutdown

    Args:
        config: Optional startup configuration.
    """
    cfg = config or StartupConfig()
    manager = BackendProcessManager(cfg)

    # Set up signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()

    def shutdown_handler() -> None:
        logger.info("Shutdown signal received")
        asyncio.create_task(manager.stop())

    if platform.system() != "Windows":
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, shutdown_handler)
            except (ValueError, RuntimeError):
                pass

    logger.info("=" * 50)
    logger.info("JARVIS Backend Service Starting...")
    logger.info("=" * 50)

    try:
        success = await manager.start()
        if success:
            logger.info("✓ JARVIS backend service is running")

            # Note: Voice greeting is handled by Electron's runStartupSequence()
            # after it runs /api/diagnostics and confirms all systems operational.
            # This prevents the greeting from being spoken twice.

            # Keep running until stopped
            while manager._running:
                await asyncio.sleep(1)
        else:
            logger.error("✗ Failed to start JARVIS backend service")

    except asyncio.CancelledError:
        logger.info("Service cancelled")
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        await manager.stop()
        logger.info("JARVIS backend service stopped")


# ─── CLI Entry Point ────────────────────────────────────────────────────────

def main() -> None:
    """CLI entry point for the startup service."""
    import argparse

    parser = argparse.ArgumentParser(description="JARVIS Backend Service Manager")
    parser.add_argument("--host", default="127.0.0.1", help="Backend host")
    parser.add_argument("--port", type=int, default=8000, help="Backend port")
    parser.add_argument("--register", action="store_true", help="Register for Windows auto-start")
    parser.add_argument("--unregister", action="store_true", help="Remove Windows auto-start")
    parser.add_argument("--check", action="store_true", help="Check if auto-start is enabled")
    parser.add_argument("--greeting", type=str, default=None, help="Speak a greeting and exit")
    parser.add_argument("--language", type=str, default="ru", help="Greeting language")

    args = parser.parse_args()

    if args.register:
        if WindowsStartupManager.is_windows():
            cfg = StartupConfig(backend_host=args.host, backend_port=args.port)
            script = WindowsStartupManager.create_startup_script(
                python_path=sys.executable,
                backend_script=cfg.backend_script,
            )
            WindowsStartupManager.register_auto_start(script)
            print(f"✓ JARVIS registered for Windows auto-start")
            print(f"  Script: {script}")
        else:
            print("Auto-start is only supported on Windows")
        return

    if args.unregister:
        WindowsStartupManager.unregister_auto_start()
        print("✓ JARVIS removed from Windows auto-start")
        return

    if args.check:
        enabled = WindowsStartupManager.is_auto_start_enabled()
        print(f"JARVIS auto-start: {'Enabled' if enabled else 'Disabled'}")
        return

    if args.greeting:
        VoiceGreetingService.speak(args.greeting, args.language)
        return

    # Run the service
    cfg = StartupConfig(backend_host=args.host, backend_port=args.port)
    asyncio.run(run_service(cfg))


if __name__ == "__main__":
    main()

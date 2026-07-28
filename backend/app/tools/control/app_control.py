"""Application Control Module.

Opens, closes, and manages Windows applications.
Supports launching by name, path, or registered command.
Opens URLs in the default browser.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import webbrowser
from pathlib import Path
from typing import Any

from loguru import logger

from backend.app.tools.base import BaseTool
from backend.app.models.schemas import RiskLevel


class AppControlTool(BaseTool):
    """Open, close, and manage Windows applications."""

    def __init__(self) -> None:
        super().__init__()
        self._risk_level = RiskLevel.LOW
        self._parameters = {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "open",
                        "open_url",
                        "close",
                        "switch",
                        "list_running",
                    ],
                    "description": "Action to perform",
                },
                "target": {
                    "type": "string",
                    "description": "Application name (e.g., 'chrome', 'notepad', 'spotify')",
                },
                "url": {
                    "type": "string",
                    "description": "URL to open in browser (for open_url action)",
                },
            },
            "required": ["action"],
        }

    @property
    def name(self) -> str:
        return "app_control"

    @property
    def description(self) -> str:
        return "Open, close, and switch between Windows applications, open URLs in browser"

    # ─── App Aliases with executable names and launch strategies ───

    APP_ALIASES: dict[str, list[str]] = {
        # Browsers (multi-language)
        "браузер": ["chrome.exe", "msedge.exe", "firefox.exe"],
        "browser": ["chrome.exe", "msedge.exe", "firefox.exe"],
        "chrome": ["chrome.exe"],
        "google": ["chrome.exe"],
        "google chrome": ["chrome.exe"],
        "edge": ["msedge.exe"],
        "microsoft edge": ["msedge.exe"],
        "firefox": ["firefox.exe"],
        "mozilla firefox": ["firefox.exe"],
        # System apps
        "notepad": ["notepad.exe"],
        "блокнот": ["notepad.exe"],
        "calculator": ["calc.exe"],
        "калькулятор": ["calc.exe"],
        "paint": ["mspaint.exe"],
        "краски": ["mspaint.exe"],
        "settings": ["ms-settings:"],
        "настройки": ["ms-settings:"],
        "sozlamalar": ["ms-settings:"],
        "control panel": ["control.exe"],
        "панель управления": ["control.exe"],
        "boshqaruv": ["control.exe"],
        "cmd": ["cmd.exe"],
        "command prompt": ["cmd.exe"],
        "командная строка": ["cmd.exe"],
        "powershell": ["powershell.exe"],
        "terminal": ["WindowsTerminal.exe", "powershell.exe"],
        "терминал": ["WindowsTerminal.exe", "cmd.exe"],
        "task manager": ["Taskmgr.exe"],
        "диспетчер задач": ["Taskmgr.exe"],
        "dispetcher": ["Taskmgr.exe"],
        "taskmgr": ["Taskmgr.exe"],
        # File Explorer
        "explorer": ["explorer.exe"],
        "проводник": ["explorer.exe"],
        "file explorer": ["explorer.exe"],
        "fayl": ["explorer.exe"],
        "downloads": ["explorer.exe"],
        "загрузки": ["explorer.exe"],
        "documents": ["explorer.exe"],
        "документы": ["explorer.exe"],
        "desktop": ["explorer.exe"],
        "рабочий стол": ["explorer.exe"],
        "recycle bin": ["explorer.exe"],
        "корзина": ["explorer.exe"],
        # Editors
        "vscode": ["Code.exe"],
        "visual studio code": ["Code.exe"],
        "код": ["Code.exe"],
        "notepad++": ["notepad++.exe"],
        "cursor": ["cursor.exe"],
        # Communication
        "slack": ["slack.exe"],
        "discord": ["Discord.exe"],
        "telegram": ["Telegram.exe"],
        "whatsapp": ["WhatsApp.exe"],
        # Media
        "spotify": ["Spotify.exe"],
        "музыка": ["Spotify.exe"],
        "musiqa": ["Spotify.exe"],
        "youtube": ["chrome.exe", "msedge.exe", "firefox.exe"],
        # Office
        "word": ["WINWORD.EXE"],
        "excel": ["EXCEL.EXE"],
        "powerpoint": ["POWERPNT.EXE"],
        "outlook": ["OUTLOOK.EXE"],
    }

    # ─── Well-known shell folder CSIDL/ KNOWNFOLDERID mappings ───

    SHELL_FOLDERS: dict[str, str] = {
        "downloads": "shell:Downloads",
        "загрузки": "shell:Downloads",
        "documents": "shell:Personal",
        "документы": "shell:Personal",
        "desktop": "shell:Desktop",
        "рабочий стол": "shell:Desktop",
        "recycle bin": "shell:RecycleBinFolder",
        "корзина": "shell:RecycleBinFolder",
    }

    # ─── Chrome search locations (order matters) ───

    CHROME_PATHS: list[str] = [
        # PATH
        None,  # will be resolved via shutil.which
        # Program Files
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        # Local AppData (per-user install)
    ]

    @staticmethod
    def _find_chrome() -> str:
        """Find Chrome executable across all possible install locations.

        Returns:
            Full path to chrome.exe, or empty string if not found.
        """
        # 1. Check PATH
        if shutil.which("chrome"):
            return shutil.which("chrome")
        if shutil.which("chrome.exe"):
            return shutil.which("chrome.exe")

        # 2. Check Program Files locations
        for path in [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]:
            if os.path.isfile(path):
                return path

        # 3. Check LocalAppData (per-user Chrome installs)
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        if local_appdata:
            chrome_local = os.path.join(local_appdata, "Google", "Chrome", "Application", "chrome.exe")
            if os.path.isfile(chrome_local):
                return chrome_local

            # Check SxS (Chrome Canary, Beta, Dev)
            for variant in ["Chrome SxS", "Chrome Beta", "Chrome Dev"]:
                candidate = os.path.join(local_appdata, "Google", variant, "Application", "chrome.exe")
                if os.path.isfile(candidate):
                    return candidate

        # 4. Check Windows Registry (WOW6432Node)
        try:
            import winreg
            for key_path in [
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
                r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
            ]:
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                        value, _ = winreg.QueryValueEx(key, "")
                        if value and os.path.isfile(value):
                            return value
                except (FileNotFoundError, OSError):
                    continue

            # Also check HKCU
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe") as key:
                    value, _ = winreg.QueryValueEx(key, "")
                    if value and os.path.isfile(value):
                        return value
            except (FileNotFoundError, OSError):
                pass
        except ImportError:
            pass

        # 5. Check common Start Menu shortcuts
        for base in [
            os.environ.get("PROGRAMDATA", ""),
            os.environ.get("ALLUSERSPROFILE", ""),
            Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu",
        ]:
            if base:
                shortcut = Path(base) / "Google Chrome.lnk"
                if shortcut.exists():
                    try:
                        import win32com.client
                        shell = win32com.client.Dispatch("WScript.Shell")
                        return shell.CreateShortCut(str(shortcut)).Targetpath or ""
                    except ImportError:
                        pass

        return ""

    @staticmethod
    def _find_edge() -> str:
        """Find Microsoft Edge executable."""
        # PATH
        if shutil.which("msedge"):
            return shutil.which("msedge")
        if shutil.which("msedge.exe"):
            return shutil.which("msedge.exe")

        # Program Files
        for path in [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ]:
            if os.path.isfile(path):
                return path

        return ""

    @staticmethod
    def _find_firefox() -> str:
        """Find Firefox executable across all possible install locations."""
        # PATH
        if shutil.which("firefox"):
            return shutil.which("firefox")
        if shutil.which("firefox.exe"):
            return shutil.which("firefox.exe")

        # Program Files
        for path in [
            r"C:\Program Files\Mozilla Firefox\firefox.exe",
            r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
        ]:
            if os.path.isfile(path):
                return path

        # Local AppData
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        if local_appdata:
            ff_path = os.path.join(local_appdata, "Mozilla Firefox", "firefox.exe")
            if os.path.isfile(ff_path):
                return ff_path

        return ""

    @staticmethod
    def _get_best_browser() -> str:
        """Get the best available browser: Chrome > Edge > Firefox > default."""
        chrome = AppControlTool._find_chrome()
        if chrome:
            return chrome
        edge = AppControlTool._find_edge()
        if edge:
            return edge
        # Fallback to system default browser via webbrowser module
        return ""

    # ─── Execution ───

    async def execute(self, action: str, target: str = "", url: str = "", **kwargs: Any) -> dict[str, Any]:
        import time
        start = time.time()
        logger.info(f"AppControl: executing action='{action}' target='{target}' url='{url}'")

        handlers = {
            "open": self._open_app,
            "open_url": self._open_url,
            "close": self._close_app,
            "switch": self._switch_to_app,
            "list_running": self._list_running,
        }

        handler = handlers.get(action)
        if not handler:
            elapsed = (time.time() - start) * 1000
            logger.warning(f"AppControl: unknown action '{action}' ({elapsed:.0f}ms)")
            return {"success": False, "error": f"Unknown action: {action}", "result": ""}

        result = await handler(target=target, url=url)
        elapsed = (time.time() - start) * 1000
        result["execution_time_ms"] = elapsed
        logger.info(f"AppControl: {action} {'✓' if result.get('success') else '✗'} ({elapsed:.0f}ms): {result.get('result', '')[:100]}")
        return result

    async def _open_app(self, target: str = "", url: str = "", **kwargs: Any) -> dict[str, Any]:
        """Open an application by name."""
        if not target:
            return {"success": False, "error": "Application name required", "result": ""}

        target_lower = target.lower().strip()
        logger.info(f"AppControl._open_app: target='{target_lower}'")

        # ── Check for shell folders first (Downloads, Documents, etc.) ──
        if target_lower in self.SHELL_FOLDERS:
            shell_path = self.SHELL_FOLDERS[target_lower]
            try:
                subprocess.Popen(["explorer.exe", shell_path], shell=False)
                return {"success": True, "result": f"Opened {target}"}
            except Exception as e:
                return {"success": False, "error": str(e), "result": ""}

        # ── YouTube / Google as app names (open URL in browser) ──
        if target_lower == "youtube":
            return await self._open_url(target="", url="https://youtube.com")

        if target_lower == "google":
            return await self._open_url(target="", url="https://google.com")

        # ── Chrome detection ──
        if target_lower in ("chrome", "google chrome", "google"):
            chrome_path = self._find_chrome()
            if chrome_path:
                try:
                    subprocess.Popen([chrome_path], shell=False)
                    return {"success": True, "result": f"Opened Chrome"}
                except Exception as e:
                    logger.warning(f"Failed to launch Chrome from {chrome_path}: {e}")
                    # Fall through to Edge fallback

            # Chrome not found — fallback to Edge
            edge_path = self._find_edge()
            if edge_path:
                try:
                    subprocess.Popen([edge_path], shell=False)
                    return {"success": True, "result": f"Chrome not found, opened Edge instead"}
                except Exception as e:
                    return {"success": False, "error": f"Chrome not found and Edge failed: {e}", "result": ""}
            else:
                # Last resort: try `start chrome` via shell
                subprocess.Popen("start chrome", shell=True)
                return {"success": True, "result": "Attempted to open Chrome via start command"}

        # ── Edge detection ──
        if target_lower in ("edge", "microsoft edge"):
            edge_path = self._find_edge()
            if edge_path:
                try:
                    subprocess.Popen([edge_path], shell=False)
                    return {"success": True, "result": "Opened Edge"}
                except Exception as e:
                    return {"success": False, "error": str(e), "result": ""}
            subprocess.Popen("start msedge", shell=True)
            return {"success": True, "result": "Attempted to open Edge"}

        # ── Firefox detection ──
        if target_lower in ("firefox", "mozilla firefox"):
            ff_path = self._find_firefox()
            if ff_path:
                try:
                    subprocess.Popen([ff_path], shell=False)
                    return {"success": True, "result": "Opened Firefox"}
                except Exception as e:
                    return {"success": False, "error": str(e), "result": ""}
            subprocess.Popen("start firefox", shell=True)
            return {"success": True, "result": "Attempted to open Firefox"}

        # ── Settings (Windows Settings app via ms-settings: URI) ──
        if target_lower in ("settings", "настройки"):
            try:
                subprocess.Popen("start ms-settings:", shell=True)
                return {"success": True, "result": "Opened Settings"}
            except Exception as e:
                return {"success": False, "error": str(e), "result": ""}

        # ── Control Panel ──
        if target_lower in ("control panel", "панель управления"):
            try:
                subprocess.Popen("control", shell=False)
                return {"success": True, "result": "Opened Control Panel"}
            except Exception as e:
                return {"success": False, "error": str(e), "result": ""}

        # ── VSCode detection ──
        if target_lower in ("vscode", "visual studio code", "код", "vs code"):
            code_paths = [
                shutil.which("code") or "",
                shutil.which("code.cmd") or "",
                r"C:\Program Files\Microsoft VS Code\Code.exe",
                r"C:\Program Files (x86)\Microsoft VS Code\Code.exe",
                str(Path.home() / "AppData" / "Local" / "Programs" / "Microsoft VS Code" / "Code.exe"),
            ]
            for cp in code_paths:
                if cp and os.path.isfile(cp):
                    try:
                        subprocess.Popen([cp], shell=False)
                        return {"success": True, "result": "Opened VS Code"}
                    except Exception:
                        continue
            subprocess.Popen("start code", shell=True)
            return {"success": True, "result": "Attempted to open VS Code"}

        # ── Discord ──
        if target_lower == "discord":
            discord_paths = [
                shutil.which("Discord.exe") or "",
                str(Path.home() / "AppData" / "Local" / "Discord" / "Update.exe") + " --processStart Discord.exe",
                str(Path.home() / "AppData" / "Local" / "Discord" / "app-*" / "Discord.exe"),
            ]
            # Try Update.exe first (official launcher)
            update_exe = Path.home() / "AppData" / "Local" / "Discord" / "Update.exe"
            if update_exe.exists():
                try:
                    subprocess.Popen([str(update_exe), "--processStart", "Discord.exe"], shell=False)
                    return {"success": True, "result": "Opened Discord"}
                except Exception:
                    pass
            # Try direct
            for dp in discord_paths:
                if dp and os.path.isfile(dp):
                    try:
                        subprocess.Popen([dp], shell=False)
                        return {"success": True, "result": "Opened Discord"}
                    except Exception:
                        continue
            subprocess.Popen("start Discord", shell=True)
            return {"success": True, "result": "Attempted to open Discord"}

        # ── Spotify ──
        if target_lower in ("spotify", "музыка"):
            spotify_paths = [
                shutil.which("Spotify.exe") or "",
                str(Path.home() / "AppData" / "Roaming" / "Spotify" / "Spotify.exe"),
                os.environ.get("LOCALAPPDATA", "") + "\\Spotify\\Spotify.exe",
            ]
            for sp in spotify_paths:
                if sp and os.path.isfile(sp):
                    try:
                        subprocess.Popen([sp], shell=False)
                        return {"success": True, "result": "Opened Spotify"}
                    except Exception:
                        continue
            subprocess.Popen("start spotify", shell=True)
            return {"success": True, "result": "Attempted to open Spotify"}

        # ── Telegram ──
        if target_lower == "telegram":
            tg_paths = [
                shutil.which("Telegram.exe") or "",
                str(Path.home() / "AppData" / "Roaming" / "Telegram Desktop" / "Telegram.exe"),
            ]
            for tp in tg_paths:
                if tp and os.path.isfile(tp):
                    try:
                        subprocess.Popen([tp], shell=False)
                        return {"success": True, "result": "Opened Telegram"}
                    except Exception:
                        continue
            subprocess.Popen("start Telegram", shell=True)
            return {"success": True, "result": "Attempted to open Telegram"}

        # ── Windows Terminal ──
        if target_lower in ("terminal", "терминал"):
            wt_path = shutil.which("WindowsTerminal.exe")
            if wt_path:
                try:
                    subprocess.Popen([wt_path], shell=False)
                    return {"success": True, "result": "Opened Windows Terminal"}
                except Exception:
                    pass
            # Fallback to CMD
            subprocess.Popen(["cmd.exe", "/c", "start", "Windows Terminal"], shell=False)
            return {"success": True, "result": "Attempted to open Windows Terminal"}

        # ── Generic: Check aliases ──
        exe_names = self.APP_ALIASES.get(target_lower, [f"{target_lower}.exe"])

        # Try to find via PATH first (fastest)
        for exe in exe_names:
            found = shutil.which(exe)
            if found:
                try:
                    subprocess.Popen([found], shell=False)
                    logger.info(f"Opened via PATH: {found}")
                    return {"success": True, "result": f"Opened {target}"}
                except Exception as e:
                    logger.warning(f"Failed to launch {found}: {e}")
                    continue

            # Try direct path (for system apps like notepad.exe)
            if exe in ("notepad.exe", "calc.exe", "mspaint.exe", "cmd.exe", "powershell.exe", "Taskmgr.exe"):
                try:
                    subprocess.Popen([exe], shell=False)
                    logger.info(f"Opened system app: {exe}")
                    return {"success": True, "result": f"Opened {target}"}
                except Exception:
                    continue

        # ── Fallback: try via 'start' command ──
        try:
            subprocess.Popen(f"start {target}", shell=True)
            logger.info(f"Attempted to open via start: {target}")
            return {"success": True, "result": f"Attempted to open {target} via start"}
        except Exception as e:
            return {"success": False, "error": f"Could not open {target}: {e}", "result": ""}

    async def _open_url(self, target: str = "", url: str = "", **kwargs: Any) -> dict[str, Any]:
        """Open a URL in the default browser."""
        if not url:
            return {"success": False, "error": "URL required", "result": ""}

        logger.info(f"AppControl._open_url: url='{url}'")

        # Try using webbrowser module first (opens default browser)
        try:
            webbrowser.open(url)
            return {"success": True, "result": f"Opened {url} in default browser"}
        except Exception as e:
            logger.warning(f"webbrowser.open failed: {e}")

        # Fallback: find best browser and open with it
        browser = self._get_best_browser()
        if browser:
            try:
                subprocess.Popen([browser, url], shell=False)
                return {"success": True, "result": f"Opened {url} in browser"}
            except Exception as e:
                logger.warning(f"Browser launch failed: {e}")

        # Last resort: use start command
        try:
            subprocess.Popen(f'start "" "{url}"', shell=True)
            return {"success": True, "result": f"Attempted to open {url}"}
        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

    async def _close_app(self, target: str = "", **kwargs: Any) -> dict[str, Any]:
        """Close an application by name."""
        if not target:
            return {"success": False, "error": "Application name required", "result": ""}

        target_lower = target.lower().strip()
        exe_names = self.APP_ALIASES.get(target_lower, [f"{target_lower}.exe"])

        for exe in exe_names:
            try:
                result = subprocess.run(
                    ["taskkill", "/F", "/IM", exe],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0:
                    logger.info(f"Closed: {exe}")
                    return {"success": True, "result": f"Closed {target}"}
            except Exception:
                continue

        return {"success": False, "error": f"Could not close {target}. Process not found.", "result": ""}

    async def _switch_to_app(self, target: str = "", **kwargs: Any) -> dict[str, Any]:
        """Switch to a running application window."""
        if not target:
            return {"success": False, "error": "Application name required", "result": ""}

        try:
            target_lower = target.lower().strip()
            exe_names = self.APP_ALIASES.get(target_lower, [f"{target_lower}.exe"])

            for exe in exe_names:
                script = f"""
                $process = Get-Process {exe} -ErrorAction SilentlyContinue | Select-Object -First 1
                if ($process) {{
                    $sig = '[DllImport("user32.dll")] public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow); [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);'
                    $type = Add-Type -MemberDefinition $sig -Name "Win32SetWindow" -Namespace Win32Functions -PassThru
                    $type::ShowWindowAsync($process.MainWindowHandle, 5) | Out-Null
                    $type::SetForegroundWindow($process.MainWindowHandle) | Out-Null
                    Write-Output "switched"
                }}
                """
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", script],
                    capture_output=True, text=True, timeout=5,
                )
                if "switched" in result.stdout:
                    logger.info(f"Switched to: {exe}")
                    return {"success": True, "result": f"Switched to {target}"}

            return {"success": False, "error": f"App '{target}' not running", "result": ""}
        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

    async def _list_running(self, target: str = "", **kwargs: Any) -> dict[str, Any]:
        """List running applications."""
        try:
            import psutil
            apps = []
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    name = proc.info["name"]
                    if name and not name.startswith("svchost") and not name.startswith("conhost"):
                        apps.append(f"  {proc.info['pid']:>6}  {name}")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            apps.sort(key=lambda x: x.split()[-1].lower() if x.split() else "")
            result = f"Running applications ({len(apps)}):\n" + "\n".join(apps[:50])
            return {"success": True, "result": result, "count": len(apps)}
        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

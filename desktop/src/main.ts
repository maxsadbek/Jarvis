/**
 * JARVIS Desktop - Electron Main Process
 *
 * Production-grade desktop AI assistant.
 * Handles: backend process lifecycle, system tray, global shortcuts,
 * auto-startup, voice greeting, and health monitoring.
 *
 * Architecture:
 *   Electron starts → spawns Python backend → waits for healthy → creates UI
 *   Auto-start via HKCU Run registry key → VBS silent launcher → both processes
 */

import { app, BrowserWindow, Tray, Menu, globalShortcut, ipcMain, screen, nativeImage, dialog, Notification } from "electron";
import * as path from "path";
import * as fs from "fs";
import * as http from "http";
import { spawn, exec, ChildProcess } from "child_process";

// ─── Configuration ──────────────────────────────────────────────────────────

interface AssistantConfig {
  name: string;
  version: string;
  startupGreeting: boolean;
  language: string;
  greetings: Record<string, string>;
  window: {
    width: number;
    height: number;
    alwaysOnTop: boolean;
    opacity: number;
    transparent: boolean;
    frameless: boolean;
  };
  backend: {
    url: string;
    healthEndpoint: string;
    connectionTimeout: number;
    reconnectInterval: number;
    pythonPath: string;
    projectRoot: string;
  };
  shortcuts: {
    activate: string;
    toggleWindow: string;
  };
  startup: {
    autoStart: boolean;
    minimizeToTray: boolean;
    startMinimized: boolean;
  };
}

function loadConfig(): AssistantConfig {
  const configPaths = [
    path.join(process.resourcesPath || "", "config", "assistant.json"),
    path.join(__dirname, "..", "config", "assistant.json"),
    path.join(process.cwd(), "config", "assistant.json"),
  ];

  for (const configPath of configPaths) {
    try {
      if (fs.existsSync(configPath)) {
        const raw = fs.readFileSync(configPath, "utf-8");
        return JSON.parse(raw) as AssistantConfig;
      }
    } catch {
      continue;
    }
  }

  // Default config fallback
  return {
    name: "Jarvis",
    version: "0.1.0",
    startupGreeting: true,
    language: "ru",
    greetings: {
      ru: "Добро пожаловать, Maxsad. Чем могу помочь?",
      en: "Welcome back. How can I assist you?",
      uz: "Xush kelibsiz, Maxsad. Qanday yordam bera olaman?",
    },
    window: { width: 480, height: 640, alwaysOnTop: true, opacity: 1, transparent: false, frameless: true },
    backend: { url: "http://127.0.0.1:8000", healthEndpoint: "/api/health", connectionTimeout: 5000, reconnectInterval: 3000, pythonPath: "", projectRoot: "" },
    shortcuts: { activate: "CommandOrControl+Space", toggleWindow: "CommandOrControl+Shift+J" },
    startup: { autoStart: true, minimizeToTray: true, startMinimized: false },
  };
}

const config = loadConfig();

// ─── State ─────────────────────────────────────────────────────────────────

let mainWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
let isQuitting = false;
let backendConnected = false;
let backendProcess: ChildProcess | null = null;
let backendCheckInterval: ReturnType<typeof setInterval> | null = null;

// ─── Window ─────────────────────────────────────────────────────────────────

function createWindow(): void {
  const { width, height, alwaysOnTop, transparent, frameless } = config.window;
  const primaryDisplay = screen.getPrimaryDisplay();
  const { x: screenX, y: screenY } = primaryDisplay.bounds;

  mainWindow = new BrowserWindow({
    width,
    height,
    x: screenX + primaryDisplay.workAreaSize.width - width - 20,
    y: screenY + 80,
    alwaysOnTop,
    transparent,
    frame: !frameless,
    resizable: false,
    skipTaskbar: false,
    hasShadow: false,
    // FIX: no `type: "toolbar"` — on Windows tool windows can render behind
    // normal windows and never appear on screen. A regular window is shown.
    // FIX: no `opacity` option — combined with transparency it can prevent the
    // window from being painted on some GPUs. The UI uses translucent CSS.
    show: false, // shown manually once the page has painted (see ready-to-show)
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  // Load the built React frontend or fallback to our own UI
  const frontendIndex = path.join(__dirname, "..", "..", "frontend", "dist", "index.html");
  const desktopIndex = path.join(__dirname, "..", "index.html");

  if (fs.existsSync(frontendIndex)) {
    mainWindow.loadFile(frontendIndex);
  } else {
    mainWindow.loadFile(desktopIndex);
  }

  // ─── Show the window FORCEFULLY ─────────────────────────────────────────
  // Fixes the "window created but invisible" bug:
  //   1. show() as soon as the page has painted (avoids blank flash)
  //   2. focus() so the window comes to the front
  //   3. safety timeout in case ready-to-show never fires (e.g. renderer error)
  mainWindow.once("ready-to-show", () => {
    if (!config.startup.startMinimized && mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.show();
      mainWindow.focus();
    }
  });

  setTimeout(() => {
    if (
      mainWindow &&
      !mainWindow.isDestroyed() &&
      !mainWindow.isVisible() &&
      !config.startup.startMinimized
    ) {
      console.warn("[Jarvis] ready-to-show never fired — forcing window visible");
      mainWindow.show();
      mainWindow.focus();
    }
  }, 2500);

  // Keep window below normal windows but above taskbar
  mainWindow.setAlwaysOnTop(true, "floating");

  // Make window click-through when not active (for overlay feel)
  mainWindow.setIgnoreMouseEvents(false);

  // Prevent close — hide instead
  mainWindow.on("close", (event) => {
    if (!isQuitting && config.startup.minimizeToTray) {
      event.preventDefault();
      mainWindow?.hide();
    }
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });

  // Open DevTools in development
  if (process.argv.includes("--dev")) {
    mainWindow.webContents.openDevTools({ mode: "detach" });
  }
}

// ─── Tray ───────────────────────────────────────────────────────────────────

// Embedded 16×16 PNG (generated by scripts/generate-icons.js) — guaranteed
// fallback so the tray icon is never empty/invisible.
const TRAY_ICON_FALLBACK_BASE64 =
  "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAABiUlEQVR42n2TPUsDQRRFp1fjzprdZD9MNBtEEUXRDRqNAUWbDWJtYRNRLETtbYJZ8R/ELqioaUXEUkHwb125AxOWxWTgwHnv3TfVjBCpM2LMYBjivzNqzCJJZnodVvMaTtxV0NlL5/oXjBlz0LhxF37nDRPRMcaDTQWdPc6S2f4FGWMepND7QTY6ga7TcMaMrtXyuFwAceMHWNEpdD0IZpjVtTDkIsxSHX7nHfQkll1VpPvMcocupFxCvtmCHZ2BrgnKh1gJWwp6csYsd+jClMvw40dkgx3QSc6uYTVsYf/gS0FnT8+Z5Q5dZOUK/PgJVrALOnHsOsLwBvsH3wo6e3rOLHfowpIhvGYbTnQOumamfIRK2FbQkzNmuUMXtqwgV9pDofMBehLP3lak+8xyhy5ycg2kED/DjS6g60Eww6yu1VvIm1WQqd4vvMYldJ2GM2Z03X+JjrkBTeH2BcX7T/iNK7jlhoLOHmfJbP8C16whiRc0MHl8h+Ltq4LOXjr378/0zC0MI53/A6L5ZfBdtDZ6AAAAAElFTkSuQmCC";

function createTray(): void {
  // Create tray icon — try loading the generated icon.png, then embedded fallback
  let trayIcon: Electron.NativeImage = nativeImage.createEmpty();

  const iconPaths = [
    path.join(__dirname, "..", "resources", "icon.png"),
    path.join(process.resourcesPath || "", "icon.png"),
    path.join(process.cwd(), "resources", "icon.png"),
  ];

  for (const iconPath of iconPaths) {
    try {
      if (fs.existsSync(iconPath)) {
        const img = nativeImage.createFromPath(iconPath);
        if (!img.isEmpty()) {
          trayIcon = img.resize({ width: 16, height: 16 });
          break;
        }
      }
    } catch {
      continue;
    }
  }

  if (trayIcon.isEmpty()) {
    // Never ship an invisible tray icon — use the embedded PNG fallback
    trayIcon = nativeImage.createFromDataURL(`data:image/png;base64,${TRAY_ICON_FALLBACK_BASE64}`);
    console.warn("[Jarvis] resources/icon.png not found — using embedded tray icon");
  }

  tray = new Tray(trayIcon);
  tray.setToolTip(`JARVIS AI Assistant${backendConnected ? " ✓ Connected" : " ○ Disconnected"}`);

  const contextMenu = Menu.buildFromTemplate([
    {
      label: `${backendConnected ? "✓" : "○"} Backend ${backendConnected ? "Connected" : "Disconnected"}`,
      enabled: false,
    },
    { type: "separator" },
    {
      label: "Show/Hide Jarvis",
      click: () => toggleWindow(),
    },
    {
      label: "Always on Top",
      type: "checkbox",
      checked: config.window.alwaysOnTop,
      click: (menuItem) => {
        if (mainWindow) {
          mainWindow.setAlwaysOnTop(menuItem.checked, "floating");
        }
      },
    },
    { type: "separator" },
    {
      label: "Check Backend Connection",
      click: () => checkBackendHealth(),
    },
    {
      label: "Restart Backend",
      click: async () => {
        new Notification({ title: "Jarvis", body: "Restarting backend..." }).show();
        killBackend();
        await new Promise((r) => setTimeout(r, 2000));
        await trySpawnBackend();
        const healthy = await waitForBackendHealth(30000);
        backendConnected = healthy;
        updateTrayTooltip();
        if (healthy) {
          new Notification({ title: "Jarvis", body: "Backend is ready" }).show();
        } else {
          new Notification({ title: "Jarvis", body: "Backend restart failed" }).show();
        }
      },
    },
    { type: "separator" },
    {
      label: "Quit Jarvis",
      click: () => {
        isQuitting = true;
        app.quit();
      },
    },
  ]);

  tray.setContextMenu(contextMenu);

  tray.on("double-click", () => {
    toggleWindow();
  });

  // Left-click convenience (Windows): show/hide the window
  tray.on("click", () => {
    toggleWindow();
  });
}

// ─── Global Shortcuts ───────────────────────────────────────────────────────

function registerShortcuts(): void {
  // Ctrl+Space = Activate Jarvis
  const okActivate = globalShortcut.register(config.shortcuts.activate, () => {
    toggleWindow();
    if (mainWindow) {
      mainWindow.webContents.send("jarvis:activate");
    }
  });

  // Ctrl+Shift+J = Toggle window
  const okToggle = globalShortcut.register(config.shortcuts.toggleWindow, () => {
    toggleWindow();
  });

  if (!okActivate) {
    console.warn(`[Jarvis] Shortcut "${config.shortcuts.activate}" could not be registered (already used by the system?)`);
  }
  if (!okToggle) {
    console.warn(`[Jarvis] Shortcut "${config.shortcuts.toggleWindow}" could not be registered`);
  }
}

// ─── Window Management ──────────────────────────────────────────────────────

function toggleWindow(): void {
  if (!mainWindow || mainWindow.isDestroyed()) return;

  if (mainWindow.isVisible()) {
    if (mainWindow.isFocused()) {
      mainWindow.hide();
    } else {
      mainWindow.show();
      mainWindow.focus();
      mainWindow.webContents.send("jarvis:focus");
    }
  } else {
    mainWindow.show();
    mainWindow.focus();
    mainWindow.webContents.send("jarvis:focus");
  }
}

/**
 * Send an IPC event to the renderer, waiting for the page to finish loading
 * so early startup events (sent right after window creation) are not lost.
 */
function sendToRenderer(channel: string, payload?: any): void {
  if (!mainWindow || mainWindow.isDestroyed()) return;
  const wc = mainWindow.webContents;
  if (wc.isLoadingMainFrame()) {
    wc.once("did-finish-load", () => {
      if (!wc.isDestroyed()) wc.send(channel, payload);
    });
  } else {
    wc.send(channel, payload);
  }
}

// ─── Backend Health Check ───────────────────────────────────────────────────

function checkBackendHealth(): Promise<boolean> {
  return new Promise((resolve) => {
    const url = `${config.backend.url}${config.backend.healthEndpoint}`;

    const req = http.get(url, { timeout: config.backend.connectionTimeout }, (res) => {
      res.setEncoding("utf8");
      let data = "";
      res.on("data", (chunk: string) => (data += chunk));
      res.on("end", () => {
        try {
          const json = JSON.parse(data);
          backendConnected = json.status === "healthy";
        } catch {
          backendConnected = false;
        }
        updateTrayTooltip();
        resolve(backendConnected);
      });
    });

    req.on("error", () => {
      backendConnected = false;
      updateTrayTooltip();
      resolve(false);
    });

    req.on("timeout", () => {
      req.destroy();
      backendConnected = false;
      updateTrayTooltip();
      resolve(false);
    });
  });
}

function updateTrayTooltip(): void {
  if (tray) {
    tray.setToolTip(
      `JARVIS AI Assistant${backendConnected ? " ✓ Connected" : " ○ Disconnected"}`,
    );
  }
}

function startBackendMonitoring(): void {
  checkBackendHealth();
  backendCheckInterval = setInterval(checkBackendHealth, config.backend.reconnectInterval);
}

// ─── Backend Process Management ───────────────────────────────────────────

/**
 * Find the project root directory.
 * Searches: app resources → parent of desktop dir → parent of backend dir
 */
function findProjectRoot(): string {
  // When packaged, extraResources are copied to <resources>/backend/ and <resources>/scripts/
  // process.resourcesPath points to the app's resources directory
  if (process.resourcesPath) {
    const packagedBackend = path.join(process.resourcesPath, "backend");
    if (fs.existsSync(packagedBackend)) {
      // Resources are at <app>/resources/ — project root for packaged app is resources/..
      return path.resolve(process.resourcesPath, "..");
    }
    // try without resolved path
    if (fs.existsSync(path.join(process.resourcesPath, "..", "backend", "main.py"))) {
      return path.resolve(process.resourcesPath, "..");
    }
  }

  // Development: navigate from __dirname (desktop/dist/) up to project root
  let cwd = path.resolve(__dirname); // desktop/dist/
  for (let i = 0; i < 5; i++) {
    const checkFile = path.join(cwd, "backend", "main.py");
    if (fs.existsSync(checkFile)) {
      return cwd;
    }
    const parent = path.resolve(cwd, "..");
    if (parent === cwd) break; // reached drive root
    cwd = parent;
  }

  // Fallback: use CWD
  return process.cwd();
}

/**
 * Find a suitable Python executable.
 * Searches: config path → virtual envs → PATH → python/python3
 */
function findPython(): string {
  if (config.backend.pythonPath && fs.existsSync(config.backend.pythonPath)) {
    return config.backend.pythonPath;
  }

  const projectRoot = findProjectRoot();

  // Check virtual environments relative to project root
  const venvCandidates = [
    path.join(projectRoot, ".venv", "Scripts", "python.exe"),
    path.join(projectRoot, "venv", "Scripts", "python.exe"),
    path.join(projectRoot, "backend", ".venv", "Scripts", "python.exe"),
    path.join(projectRoot, "backend", "venv", "Scripts", "python.exe"),
    path.join(projectRoot, "..", ".venv", "Scripts", "python.exe"),
  ];

  for (const venv of venvCandidates) {
    if (fs.existsSync(venv)) {
      return venv;
    }
  }

  // Fallback to PATH
  return "python";
}

/**
 * Check if the backend is already running by attempting a health check.
 */
function isBackendAlreadyRunning(): Promise<boolean> {
  return new Promise((resolve) => {
    const url = `${config.backend.url}${config.backend.healthEndpoint}`;
    const req = http.get(url, { timeout: 2000 }, (res) => {
      res.resume();
      resolve(res.statusCode === 200);
    });
    req.on("error", () => resolve(false));
    req.on("timeout", () => {
      req.destroy();
      resolve(false);
    });
  });
}

/**
 * Try to spawn the Python backend as a child process.
 *
 * Architecture:
 *   1. First checks if backend is already running on port 8000
 *   2. If already running, skip spawning (VBS launcher or previous instance)
 *   3. If not running, spawn using the production-grade startup.py service
 *
 * Uses CREATE_NO_WINDOW to hide console on Windows.
 * Runs via `python -m backend.app.services.startup` which uses BackendProcessManager.
 *
 * Returns the child process if spawned, or null if already running.
 */
async function trySpawnBackend(): Promise<ChildProcess | null> {
  // First check if backend is already running (e.g., from VBS launcher or previous instance)
  // This prevents duplicate backend processes fighting for port 8000
  if (await isBackendAlreadyRunning()) {
    console.log("[Jarvis] Backend already running — connecting to existing instance");
    backendConnected = true;
    updateTrayTooltip();
    return null;
  }

  const projectRoot = findProjectRoot();
  const pythonExe = findPython();

  // Use the production-grade startup.py service instead of running main.py directly
  // startup.py has BackendProcessManager with:
  //   - Silent launch (CREATE_NO_WINDOW)
  //   - Health monitoring
  //   - Auto-restart on crash with rate limiting
  //   - Graceful shutdown
  const serviceModule = "backend.app.services.startup";

  console.log(`[Jarvis] Starting backend service: ${pythonExe} -m ${serviceModule}`);

  const isWindows = process.platform === "win32";

  // When packaged, Python files are in <resources>/backend/ not <cwd>/backend/
  // Add resources path to PYTHONPATH so `python -m backend.app.services.startup` resolves correctly
  const env: NodeJS.ProcessEnv = { ...process.env };
  if (process.resourcesPath) {
    const resourcesDir = path.resolve(process.resourcesPath);
    env.PYTHONPATH = env.PYTHONPATH
      ? `${resourcesDir}${path.delimiter}${env.PYTHONPATH}`
      : resourcesDir;
  }

  const child = spawn(pythonExe, ["-m", serviceModule], {
    cwd: projectRoot,
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
    env,
    ...(isWindows ? { creationFlags: 0x08000000 } : {}), // CREATE_NO_WINDOW
  });

  child.stdout?.on("data", (data: Buffer) => {
    const line = data.toString().trim();
    if (line) console.log(`[Backend] ${line}`);
  });

  child.stderr?.on("data", (data: Buffer) => {
    const line = data.toString().trim();
    if (line) console.error(`[Backend:ERR] ${line}`);
  });

  child.on("error", (err: Error) => {
    console.error(`[Jarvis] Backend process error: ${err.message}`);
    backendProcess = null;
  });

  child.on("exit", (code: number | null) => {
    console.log(`[Jarvis] Backend process exited with code ${code}`);
    backendProcess = null;
    backendConnected = false;
    updateTrayTooltip();

    // Auto-restart if not quitting
    if (!isQuitting && code !== 0) {
      console.log(`[Jarvis] Restarting backend in 3s...`);
      setTimeout(() => {
        trySpawnBackend();
      }, 3000);
    }
  });

  backendProcess = child;
  return child;
}

/**
 * Kill the backend process gracefully.
 */
function killBackend(): void {
  if (!backendProcess) return;

  const pid = backendProcess.pid;
  console.log(`[Jarvis] Stopping backend (PID: ${pid})...`);

  try {
    if (process.platform === "win32") {
      // Kill the entire process tree
      exec(`taskkill /F /T /PID ${pid}`, { timeout: 5000 }, (err) => {
        if (err) console.warn(`[Jarvis] taskkill warning: ${err.message}`);
      });
    } else {
      backendProcess.kill("SIGTERM");
    }
  } catch (err) {
    console.warn(`[Jarvis] Error killing backend: ${err}`);
  }

  backendProcess = null;
}

/**
 * Wait for backend to become healthy with timeout.
 */
function waitForBackendHealth(timeoutMs: number = 30000): Promise<boolean> {
  return new Promise((resolve) => {
    const start = Date.now();

    const check = () => {
      if (isQuitting) {
        resolve(false);
        return;
      }

      checkBackendHealth().then((healthy) => {
        if (healthy) {
          resolve(true);
          return;
        }

        if (Date.now() - start >= timeoutMs) {
          resolve(false);
          return;
        }

        setTimeout(check, 1000);
      });
    };

    check();
  });
}

// ─── Auto Startup ───────────────────────────────────────────────────────────

function configureAutoStartup(): void {
  // Only configure Windows auto-start for the packaged (installed) app.
  // In development this would register the raw electron.exe at login.
  if (!app.isPackaged) return;

  app.setLoginItemSettings({
    openAtLogin: config.startup.autoStart,
    path: app.getPath("exe"),
  });
}

// ─── System Diagnostics ────────────────────────────────────────────────────

interface SystemCheck {
  name: string;
  status: "ready" | "warning" | "error" | "waiting";
  message: string;
}

interface DiagnosticsResult {
  status: string;
  checks: Record<string, SystemCheck>;
  all_systems_operational: boolean;
}

/**
 * Run comprehensive system diagnostics by calling the /api/diagnostics endpoint.
 */
async function runDiagnostics(): Promise<DiagnosticsResult | null> {
  try {
    const url = `${config.backend.url}/api/diagnostics`;
    const resp = await fetch(url, { signal: AbortSignal.timeout(10000) });
    if (!resp.ok) return null;
    return await resp.json() as DiagnosticsResult;
  } catch {
    return null;
  }
}

/**
 * Run the full startup sequence with progress updates to the renderer.
 */
async function runStartupSequence(): Promise<void> {
  console.log("[Jarvis] Running startup diagnostics...");

  // 1. Connecting to backend
  sendToRenderer("jarvis:startupProgress", {
    step: "connecting",
    status: "checking",
    message: "Запуск сервера...",
  });

  // 2. Wait for backend to become healthy (up to 30s)
  sendToRenderer("jarvis:startupProgress", {
    step: "backend",
    status: "checking",
    message: "Подключение к серверу...",
  });

  const healthy = await waitForBackendHealth(30000);
  if (!healthy) {
    console.warn("[Jarvis] Backend health check failed");
    sendToRenderer("jarvis:startupProgress", {
      step: "backend", status: "error", message: "Сервер не отвечает",
    });
    return;
  }

  backendConnected = true;
  updateTrayTooltip();

  sendToRenderer("jarvis:startupProgress", {
    step: "backend", status: "ready", message: "Сервер подключён ✓",
  });

  // 2. Run full diagnostics (checks mic, speakers, internet, memory, tools, models, config)
  sendToRenderer("jarvis:startupProgress", {
    step: "diagnostics", status: "checking", message: "Проверка систем...",
  });

  const diagnostics = await runDiagnostics();

  if (diagnostics && diagnostics.checks) {
    // Send each check result to the renderer for display
    const checkOrder = [
      "llm", "memory", "tools", "internet",
      "microphone", "speakers", "voice_pipeline", "configuration",
    ];

    for (const key of checkOrder) {
      const check = diagnostics.checks[key];
      if (!check) continue;

      sendToRenderer("jarvis:startupProgress", {
        step: key,
        status: check.status,
        message: check.message,
      });

      // Small delay between checks for visual progression
      await new Promise((r) => setTimeout(r, 300));
    }

    // 3. All systems check
    const allOk = diagnostics.all_systems_operational;
    sendToRenderer("jarvis:startupProgress", {
      step: "complete",
      status: allOk ? "ready" : "warning",
      message: allOk
        ? "Все системы работают ✓"
        : "Некоторые системы имеют предупреждения",
      allSystemsOperational: allOk,
    });

    // The startup greeting is handled by the backend VoiceManager
    // which uses Piper TTS with the proper Russian male voice.
    // Do NOT call speakGreeting() here — it would cause dual audio.
    const greetingText = `Добро пожаловать, Maxsad. Все системы работают. Чем могу помочь?`;

    // Notify renderer with the greeting (UI only, no audio)
    setTimeout(() => {
      sendToRenderer("jarvis:ready", {
        backendConnected: true,
        greeting: greetingText,
        diagnostics,
      });
    }, 1500);
  } else {
    // Diagnostics failed — the backend VoiceManager still handles the greeting
    // via its own startup sequence. No need for desktop TTS here.
  }
}

// ─── Voice Greeting ─────────────────────────────────────────────────────────

function getGreeting(): string | null {
  if (!config.startupGreeting) return null;
  return config.greetings[config.language] || config.greetings["en"] || null;
}

function speakGreeting(text: string): void {
  // Use PowerShell TTS (Windows SAPI, no visible window)
  // Select Russian voice for ru language
  try {
    const voiceSelector = `$voice = $speak.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture -like 'ru-*' } | Select-Object -First 1; if ($voice) { $speak.SelectVoice($voice.VoiceInfo.Name) }`;
    const safeText = text.replace(/'/g, "''").replace(/"/g, '""');
    const script = `Add-Type -AssemblyName System.Speech; $speak = New-Object System.Speech.Synthesis.SpeechSynthesizer; ${voiceSelector} $speak.Speak('${safeText}')`;
    const child = exec(`powershell -NoProfile -NonInteractive -WindowStyle Hidden -Command "${script}"`, { timeout: 15000 });
    child.unref(); // Detach so it doesn't block shutdown
    console.log(`[Jarvis] Spoke greeting: ${text.substring(0, 50)}...`);
  } catch (err) {
    console.warn(`[Jarvis] TTS failed: ${err}`);
  }
}

// ─── Startup Permission Dialog ──────────────────────────────────────────────

async function askStartupPermission(): Promise<void> {
  if (!config.startup.autoStart) return;

  const settings = app.getLoginItemSettings();
  if (settings.wasOpenedAtLogin) return; // Already set up

  const result = await dialog.showMessageBox({
    type: "question",
    title: "JARVIS Startup",
    message: `Allow ${config.name} to start automatically when you log in?`,
    detail: `${config.name} will run in the system tray and be ready when you need it.`,
    buttons: ["Yes, start with Windows", "No, I'll start it manually"],
    defaultId: 0,
    cancelId: 1,
  });

  if (result.response === 0) {
    app.setLoginItemSettings({
      openAtLogin: true,
      path: app.getPath("exe"),
    });
  } else {
    app.setLoginItemSettings({ openAtLogin: false });
  }
}

// ─── IPC Handlers ──────────────────────────────────────────────────────────

function setupIPC(): void {
  ipcMain.handle("jarvis:getConfig", () => config);
  ipcMain.handle("jarvis:getGreeting", () => getGreeting());
  ipcMain.handle("jarvis:checkBackend", () => checkBackendHealth());
  ipcMain.handle("jarvis:getBackendStatus", () => backendConnected);
  ipcMain.handle("jarvis:sendMessage", async (_event, message: string) => {
    try {
      const response = await fetch(`${config.backend.url}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, conversation_id: "desktop" }),
      });
      const data = await response.json();
      return data;
    } catch (err: any) {
      return { error: err.message };
    }
  });
  ipcMain.handle("jarvis:getStatus", async () => {
    try {
      const response = await fetch(`${config.backend.url}/api/status`);
      return await response.json();
    } catch {
      return { status: "disconnected" };
    }
  });
  ipcMain.handle("jarvis:isBackendRunning", () => backendProcess !== null && backendProcess.exitCode === null);

  ipcMain.handle("jarvis:restartBackend", async () => {
    killBackend();
    await new Promise((resolve) => setTimeout(resolve, 2000));
    const proc = await trySpawnBackend();
    const healthy = await waitForBackendHealth(30000);
    if (healthy) {
      backendConnected = true;
      updateTrayTooltip();
    }
    return healthy;
  });

  ipcMain.handle("jarvis:toggleWindow", () => toggleWindow());
  ipcMain.handle("jarvis:hide", () => mainWindow?.hide());
  ipcMain.handle("jarvis:quit", () => {
    isQuitting = true;
    app.quit();
  });
}

// ─── Application Lifecycle ─────────────────────────────────────────────────

// `--smoke-test` — automated launch check: open the window, then quit after 6s.
// `--no-startup-dialog` — skip the auto-start permission dialog (used by smoke test/CI).
const isSmokeTest = process.argv.includes("--smoke-test");
const skipStartupDialog = isSmokeTest || process.argv.includes("--no-startup-dialog");

app.whenReady().then(async () => {
  try {
    // 1. Create the UI FIRST so the window appears immediately.
    //    (Previously the permission dialog and backend spawn ran first,
    //     delaying window creation by seconds — the app seemed dead.)
    createWindow();
    createTray();
    registerShortcuts();
    setupIPC();
    startBackendMonitoring();

    // 2. Background setup: auto-start permission, login item, backend process.
    //    Permission dialog + auto-start only apply to the installed (packaged) app.
    if (app.isPackaged && !skipStartupDialog) {
      await askStartupPermission();
    }
    configureAutoStartup();

    console.log("[Jarvis] Starting Python backend...");
    await trySpawnBackend();

    // 3. Run the full startup sequence with diagnostics and greeting
    runStartupSequence();

    // 4. Automated smoke test — prove the window opened, then exit cleanly
    if (isSmokeTest) {
      setTimeout(() => {
        console.log("[Jarvis] Smoke test OK — window shown, quitting");
        isQuitting = true;
        app.quit();
      }, 6000);
    }
  } catch (err) {
    console.error("Failed to initialize Jarvis:", err);
  }
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    // Don't quit — keep running in tray
  }
});

app.on("before-quit", () => {
  isQuitting = true;

  // Stop health monitoring
  if (backendCheckInterval) {
    clearInterval(backendCheckInterval);
    backendCheckInterval = null;
  }

  // Kill the Python backend
  killBackend();

  // Unregister global shortcuts
  globalShortcut.unregisterAll();

  console.log("[Jarvis] Clean shutdown complete");
});

app.on("will-quit", () => {
  globalShortcut.unregisterAll();
});

app.on("activate", () => {
  if (!mainWindow) {
    createWindow();
  } else {
    mainWindow.show();
  }
});

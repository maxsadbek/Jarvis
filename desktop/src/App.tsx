import { synthesizeSpeech } from "./services/backend";

/**

 * JARVIS Desktop - Main Overlay Application
 *
 * A futuristic holographic UI overlay with startup diagnostics animation.
 * States: startup (with progress) → idle → listening → processing → speaking
 *
 * On first launch, shows a complete system diagnostics sequence (Jarvis-style),
 * then automatically speaks the Russian greeting.
 */

// ─── Global State ──────────────────────────────────────────────────────────

type AppState = "startup" | "idle" | "listening" | "processing" | "speaking";

interface SystemCheckItem {
  key: string;
  name: string;
  status: "waiting" | "checking" | "ready" | "warning" | "error";
  message: string;
}

const state: {
  current: AppState;
  backendConnected: boolean;
  message: string;
  response: string;
  conversationId: string;
  greeting: string | null;
  config: any;
  showChat: boolean;
  checks: SystemCheckItem[];
  checkProgress: number;
  startupComplete: boolean;
  statusText: string;
} = {
  current: "startup",
  backendConnected: false,
  message: "",
  response: "",
  conversationId: "desktop_" + Date.now().toString(36),
  greeting: null,
  config: null,
  showChat: false,
  checks: [
    { key: "connecting", name: "Подключение к серверу", status: "checking", message: "Запуск сервера..." },
    { key: "backend", name: "Серверная часть", status: "waiting", message: "" },
    { key: "llm", name: "AI Модель", status: "waiting", message: "" },
    { key: "memory", name: "Система памяти", status: "waiting", message: "" },
    { key: "tools", name: "Инструменты", status: "waiting", message: "" },
    { key: "internet", name: "Интернет", status: "waiting", message: "" },
    { key: "microphone", name: "Микрофон", status: "waiting", message: "" },
    { key: "speakers", name: "Динамики", status: "waiting", message: "" },
    { key: "voice_pipeline", name: "Голосовой конвейер", status: "waiting", message: "" },
    { key: "configuration", name: "Конфигурация", status: "waiting", message: "" },
  ],
  checkProgress: 0,
  startupComplete: false,
  statusText: "Инициализация систем...",
};

// ─── DOM Helpers ───────────────────────────────────────────────────────────

function $<T extends HTMLElement>(id: string): T | null {
  return document.getElementById(id) as T | null;
}

function el(tag: string, attrs: Record<string, any> = {}, ...children: any[]): HTMLElement {
  const element = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "className") {
      element.className = value;
    } else if (key === "style" && typeof value === "object") {
      Object.assign(element.style, value);
    } else if (key.startsWith("on") && typeof value === "function") {
      element.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (key === "innerHTML") {
      element.innerHTML = value;
    } else {
      element.setAttribute(key, String(value));
    }
  }
  for (const child of children) {
    if (typeof child === "string") {
      element.appendChild(document.createTextNode(child));
    } else if (child instanceof Node) {
      element.appendChild(child);
    }
  }
  return element;
}

// ─── Styles ────────────────────────────────────────────────────────────────

const styles = document.createElement("style");
styles.textContent = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

  * { margin: 0; padding: 0; box-sizing: border-box; }

  :root {
    --jarvis-500: #6366f1;
    --jarvis-400: #818cf8;
    --jarvis-600: #4f46e5;
    --neon-blue: #00d4ff;
    --neon-purple: #8b5cf6;
    --neon-cyan: #06b6d4;
    --neon-green: #10b981;
    --neon-amber: #f59e0b;
    --neon-red: #ef4444;
    --surface: #06060f;
    --surface-50: #0a0a1a;
    --surface-100: #0f0f23;
    --text-primary: #f1f5f9;
    --text-secondary: #94a3b8;
    --glass-bg: rgba(255, 255, 255, 0.03);
    --glass-border: rgba(255, 255, 255, 0.06);
  }

  html, body {
    width: 100%;
    height: 100%;
    overflow: hidden;
    /* Solid dark background by default (window is non-transparent for now).
       When transparency is enabled via config, .jarvis-transparent restores it. */
    background: #06060f;
    font-family: 'Inter', system-ui, sans-serif;
    color: var(--text-primary);
    -webkit-app-region: drag;
  }

  body.jarvis-transparent {
    background: transparent !important;
  }

  /* ─── Shell ─── */
  .jarvis-shell {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 24px;
    position: relative;
    overflow: hidden;
    background: rgba(10, 10, 26, 0.97);
    backdrop-filter: blur(20px);
    border-radius: 16px;
    border: 1px solid var(--glass-border);
  }

  /* Ambient glow */
  .jarvis-shell::before {
    content: '';
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(ellipse 400px 300px at 20% 30%, rgba(99, 102, 241, 0.06) 0%, transparent 60%),
                radial-gradient(ellipse 300px 400px at 80% 70%, rgba(0, 212, 255, 0.04) 0%, transparent 60%);
    pointer-events: none;
    z-index: 0;
  }

  /* Scan line */
  .jarvis-shell::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(0, 212, 255, 0.15), rgba(99, 102, 241, 0.15), transparent);
    animation: scanLine 4s linear infinite;
    pointer-events: none;
    z-index: 10;
  }

  @keyframes scanLine {
    0% { transform: translateY(0); }
    100% { transform: translateY(600px); }
  }

  /* ─── Startup Splash ─── */
  .startup-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    width: 100%;
    max-width: 380px;
    z-index: 1;
    -webkit-app-region: no-drag;
    animation: fadeIn 0.5s ease-out;
  }

  .startup-container.exit {
    animation: fadeOut 0.6s ease-in forwards;
  }

  .startup-logo {
    font-size: 28px;
    font-weight: 700;
    letter-spacing: 6px;
    text-transform: uppercase;
    background: linear-gradient(135deg, var(--neon-blue), var(--jarvis-400), var(--neon-purple));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 4px;
  }

  .startup-subtitle {
    font-size: 11px;
    color: rgba(148, 163, 184, 0.5);
    letter-spacing: 4px;
    text-transform: uppercase;
    margin-bottom: 24px;
  }

  /* Progress bar */
  .startup-progress-bar {
    width: 100%;
    height: 2px;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 2px;
    margin-bottom: 24px;
    overflow: hidden;
    position: relative;
  }

  .startup-progress-fill {
    height: 100%;
    width: 0%;
    background: linear-gradient(90deg, var(--neon-blue), var(--jarvis-400), var(--neon-purple));
    border-radius: 2px;
    transition: width 0.5s ease;
    box-shadow: 0 0 8px rgba(99, 102, 241, 0.3);
  }

  /* Check list */
  .startup-checks {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-bottom: 20px;
  }

  .startup-check-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 10px;
    border-radius: 6px;
    transition: all 0.3s;
    font-size: 12px;
    opacity: 0.4;
  }

  .startup-check-item.active {
    opacity: 1;
    background: rgba(99, 102, 241, 0.04);
  }

  .startup-check-item.done {
    opacity: 0.8;
  }

  .startup-check-icon {
    width: 18px;
    height: 18px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 9px;
    flex-shrink: 0;
    border: 1.5px solid rgba(255, 255, 255, 0.1);
    transition: all 0.3s;
  }

  .startup-check-icon.waiting {
    border-color: rgba(255, 255, 255, 0.08);
    color: transparent;
  }

  .startup-check-icon.checking {
    border-color: var(--neon-amber);
    color: var(--neon-amber);
    animation: spin 0.8s linear infinite;
    font-size: 0;
  }

  .startup-check-icon.checking::after {
    content: '';
    width: 6px;
    height: 6px;
    border-radius: 50%;
    border: 1.5px solid var(--neon-amber);
    border-top-color: transparent;
    animation: spin 0.6s linear infinite;
  }

  .startup-check-icon.ready {
    background: rgba(16, 185, 129, 0.15);
    border-color: var(--neon-green);
    color: var(--neon-green);
  }

  .startup-check-icon.warning {
    background: rgba(245, 158, 11, 0.15);
    border-color: var(--neon-amber);
    color: var(--neon-amber);
  }

  .startup-check-icon.error {
    background: rgba(239, 68, 68, 0.15);
    border-color: var(--neon-red);
    color: var(--neon-red);
  }

  .startup-check-label {
    flex: 1;
    color: var(--text-secondary);
    font-size: 12px;
    font-weight: 400;
  }

  .startup-check-item.done .startup-check-label {
    color: var(--text-primary);
  }

  .startup-check-msg {
    font-size: 10px;
    color: rgba(148, 163, 184, 0.5);
    max-width: 160px;
    text-align: right;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .startup-check-msg.checking {
    color: var(--neon-amber);
    animation: pulse 1s ease-in-out infinite;
  }

  .startup-check-msg.ready {
    color: var(--neon-green);
  }

  .startup-check-msg.warning {
    color: var(--neon-amber);
  }

  .startup-check-msg.error {
    color: var(--neon-red);
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
  }

  @keyframes fadeOut {
    from { opacity: 1; transform: translateY(0); }
    to { opacity: 0; transform: translateY(-8px); }
  }

  @keyframes pulse {
    0%, 100% { opacity: 0.5; }
    50% { opacity: 1; }
  }

  /* ─── Main UI (post-startup) ─── */
  .main-ui {
    display: none;
    flex-direction: column;
    align-items: center;
    width: 100%;
    animation: fadeIn 0.6s ease-out;
  }

  .main-ui.visible {
    display: flex;
  }

  /* Drag handle */
  .drag-handle {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 32px;
    -webkit-app-region: drag;
    z-index: 100;
    cursor: move;
  }

  /* Title Bar */
  .title-bar {
    position: absolute;
    top: 8px;
    right: 12px;
    display: flex;
    gap: 8px;
    z-index: 200;
    -webkit-app-region: no-drag;
  }

  .title-btn {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    border: 1px solid rgba(255, 255, 255, 0.1);
    background: rgba(255, 255, 255, 0.03);
    color: var(--text-secondary);
    font-size: 10px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
  }

  .title-btn:hover {
    background: rgba(255, 255, 255, 0.1);
    border-color: rgba(255, 255, 255, 0.2);
  }

  .title-btn.close:hover { background: rgba(239, 68, 68, 0.3); border-color: rgba(239, 68, 68, 0.5); }

  /* Jarvis Orb */
  .jarvis-orb-container {
    position: relative;
    width: 100px;
    height: 100px;
    margin-bottom: 14px;
    z-index: 1;
    -webkit-app-region: no-drag;
  }

  .jarvis-orb {
    width: 100%;
    height: 100%;
    border-radius: 50%;
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.3s;
  }

  .jarvis-orb:hover {
    transform: scale(1.05);
  }

  .jarvis-orb-core {
    width: 50px;
    height: 50px;
    border-radius: 50%;
    background: radial-gradient(circle at 30% 30%, var(--jarvis-400), var(--jarvis-600));
    box-shadow: 0 0 30px rgba(99, 102, 241, 0.3), 0 0 60px rgba(99, 102, 241, 0.1);
    position: relative;
    z-index: 2;
    transition: all 0.5s;
  }

  .jarvis-orb-ring {
    position: absolute;
    inset: -6px;
    border-radius: 50%;
    border: 1px solid rgba(99, 102, 241, 0.15);
    animation: ringPulse 3s ease-in-out infinite;
  }

  .jarvis-orb-ring:nth-child(2) {
    inset: -12px;
    animation-delay: 1s;
    border-color: rgba(0, 212, 255, 0.1);
  }

  .jarvis-orb-ring:nth-child(3) {
    inset: -18px;
    animation-delay: 2s;
    border-color: rgba(139, 92, 246, 0.08);
  }

  .jarvis-orb.listening .jarvis-orb-core {
    box-shadow: 0 0 40px rgba(0, 212, 255, 0.4), 0 0 80px rgba(0, 212, 255, 0.15);
  }
  .jarvis-orb.listening .jarvis-orb-ring { border-color: rgba(0, 212, 255, 0.25); }

  .jarvis-orb.processing .jarvis-orb-core {
    animation: pulseProcessing 1s ease-in-out infinite;
  }

  .jarvis-orb.speaking .jarvis-orb-core {
    box-shadow: 0 0 50px rgba(139, 92, 246, 0.5), 0 0 100px rgba(139, 92, 246, 0.2);
    animation: pulseSpeaking 0.8s ease-in-out infinite;
  }

  @keyframes ringPulse {
    0%, 100% { transform: scale(1); opacity: 0.5; }
    50% { transform: scale(1.05); opacity: 1; }
  }

  @keyframes pulseProcessing {
    0%, 100% { transform: scale(1); box-shadow: 0 0 30px rgba(245, 158, 11, 0.3); }
    50% { transform: scale(1.08); box-shadow: 0 0 50px rgba(245, 158, 11, 0.5); }
  }

  @keyframes pulseSpeaking {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.05); }
  }

  /* Waveform */
  .waveform-container {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 3px;
    height: 28px;
    margin-bottom: 8px;
    z-index: 1;
    -webkit-app-region: no-drag;
  }

  .wave-bar {
    width: 3px;
    background: linear-gradient(to top, var(--jarvis-500), var(--neon-blue));
    border-radius: 2px;
    transition: height 0.15s;
  }

  .waveform-container.active .wave-bar {
    animation: waveAnim 1.5s ease-in-out infinite;
  }

  .waveform-container.speaking .wave-bar {
    background: linear-gradient(to top, var(--neon-purple), var(--neon-blue));
  }

  @keyframes waveAnim {
    0%, 100% { height: 4px; }
    25% { height: 16px; }
    50% { height: 22px; }
    75% { height: 10px; }
  }

  .wave-bar:nth-child(1) { animation-delay: 0s; }
  .wave-bar:nth-child(2) { animation-delay: 0.1s; }
  .wave-bar:nth-child(3) { animation-delay: 0.2s; }
  .wave-bar:nth-child(4) { animation-delay: 0.3s; }
  .wave-bar:nth-child(5) { animation-delay: 0.4s; }
  .wave-bar:nth-child(6) { animation-delay: 0.5s; }
  .wave-bar:nth-child(7) { animation-delay: 0.6s; }
  .wave-bar:nth-child(8) { animation-delay: 0.7s; }
  .wave-bar:nth-child(9) { animation-delay: 0.8s; }
  .wave-bar:nth-child(10) { animation-delay: 0.9s; }

  /* Status */
  .status-container {
    text-align: center;
    margin-bottom: 10px;
    z-index: 1;
    -webkit-app-region: no-drag;
  }

  .status-text {
    font-size: 13px;
    font-weight: 500;
    letter-spacing: 0.5px;
    transition: all 0.3s;
  }

  .status-text.idle { color: var(--text-secondary); }
  .status-text.listening { color: var(--neon-blue); }
  .status-text.processing { color: #f59e0b; }
  .status-text.speaking { color: var(--neon-purple); }

  .status-subtitle {
    font-size: 10px;
    color: rgba(148, 163, 184, 0.5);
    margin-top: 3px;
    letter-spacing: 0.3px;
  }

  /* Backend indicator */
  .backend-indicator {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    font-size: 10px;
    color: var(--text-secondary);
    margin-top: 4px;
    z-index: 1;
    -webkit-app-region: no-drag;
  }

  .backend-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    transition: all 0.3s;
  }

  .backend-dot.connected { background: var(--neon-green); box-shadow: 0 0 6px rgba(16, 185, 129, 0.5); }
  .backend-dot.disconnected { background: #ef4444; box-shadow: 0 0 6px rgba(239, 68, 68, 0.3); }
  .backend-dot.checking { background: #f59e0b; animation: pulseProcessing 1s infinite; }

  /* Chat */
  .chat-area {
    width: 100%;
    max-width: 380px;
    margin-top: 6px;
    z-index: 1;
    -webkit-app-region: no-drag;
  }

  .chat-input-group {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  .chat-input {
    flex: 1;
    padding: 8px 14px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    color: var(--text-primary);
    font-family: 'Inter', sans-serif;
    font-size: 12px;
    outline: none;
    transition: all 0.2s;
  }

  .chat-input:focus {
    border-color: rgba(99, 102, 241, 0.3);
    background: rgba(255, 255, 255, 0.06);
    box-shadow: 0 0 12px rgba(99, 102, 241, 0.08);
  }

  .chat-input::placeholder { color: rgba(148, 163, 184, 0.4); }

  .chat-send-btn {
    width: 34px;
    height: 34px;
    border-radius: 50%;
    border: 1px solid rgba(99, 102, 241, 0.2);
    background: rgba(99, 102, 241, 0.1);
    color: var(--text-primary);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
    font-size: 13px;
  }

  .chat-send-btn:hover {
    background: rgba(99, 102, 241, 0.2);
    border-color: rgba(99, 102, 241, 0.4);
    box-shadow: 0 0 12px rgba(99, 102, 241, 0.15);
  }

  .chat-send-btn:active { transform: scale(0.95); }

  /* Response */
  .response-area {
    width: 100%;
    max-width: 380px;
    margin-top: 6px;
    max-height: 100px;
    overflow-y: auto;
    z-index: 1;
    -webkit-app-region: no-drag;
  }

  .response-text {
    font-size: 11px;
    line-height: 1.5;
    color: var(--text-secondary);
    padding: 6px 10px;
    background: rgba(255, 255, 255, 0.02);
    border-radius: 8px;
    border-left: 2px solid rgba(99, 102, 241, 0.2);
  }

  /* Greeting Toast */
  .greeting-toast {
    position: absolute;
    bottom: 72px;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(99, 102, 241, 0.1);
    border: 1px solid rgba(99, 102, 241, 0.2);
    border-radius: 12px;
    padding: 10px 18px;
    font-size: 12px;
    color: var(--text-primary);
    text-align: center;
    animation: fadeInUp 0.5s ease-out;
    z-index: 50;
    backdrop-filter: blur(8px);
    white-space: nowrap;
    -webkit-app-region: no-drag;
  }

  @keyframes fadeInUp {
    from { opacity: 0; transform: translateX(-50%) translateY(10px); }
    to { opacity: 1; transform: translateX(-50%) translateY(0); }
  }

  /* Scrollbar */
  ::-webkit-scrollbar { width: 3px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.1); border-radius: 2px; }
`;
document.head.appendChild(styles);

// ─── UI Creation ───────────────────────────────────────────────────────────

function createDragHandle(): HTMLElement {
  return el("div", { className: "drag-handle" });
}

function createTitleBar(): HTMLElement {
  const bar = el("div", { className: "title-bar" });

  const alwaysOnTopBtn = el("button", {
    className: "title-btn", innerHTML: "📌", title: "Toggle always-on-top",
  });
  alwaysOnTopBtn.addEventListener("click", () => {
    if (window.jarvis) window.jarvis.toggleWindow();
  });

  const hideBtn = el("button", {
    className: "title-btn", innerHTML: "─", title: "Minimize to tray",
  });
  hideBtn.addEventListener("click", () => {
    if (window.jarvis) window.jarvis.hide();
  });

  const closeBtn = el("button", {
    className: "title-btn close", innerHTML: "✕", title: "Quit Jarvis",
  });
  closeBtn.addEventListener("click", () => {
    if (window.jarvis) window.jarvis.quit();
  });

  bar.appendChild(alwaysOnTopBtn);
  bar.appendChild(hideBtn);
  bar.appendChild(closeBtn);
  return bar;
}

// ─── Startup UI ────────────────────────────────────────────────────────────

function createStartupUI(): HTMLElement {
  const container = el("div", { className: "startup-container", id: "startupContainer" });

  container.appendChild(el("div", { className: "startup-logo", innerHTML: "J.A.R.V.I.S." }));
  container.appendChild(el("div", { className: "startup-subtitle", innerHTML: "Инициализация систем..." }));

  // Progress bar
  const progressBar = el("div", { className: "startup-progress-bar" });
  progressBar.appendChild(el("div", { className: "startup-progress-fill", id: "progressFill" }));
  container.appendChild(progressBar);

  // Check items
  const checksContainer = el("div", { className: "startup-checks", id: "startupChecks" });

  for (const check of state.checks) {
    const item = el("div", {
      className: "startup-check-item",
      id: `check-${check.key}`,
    });
    item.appendChild(el("div", {
      className: `startup-check-icon ${check.status}`,
      id: `check-icon-${check.key}`,
      innerHTML: check.status === "ready" ? "✓" : check.status === "warning" ? "!" : check.status === "error" ? "✕" : "",
    }));
    item.appendChild(el("span", { className: "startup-check-label", innerHTML: check.name }));
    item.appendChild(el("span", {
      className: "startup-check-msg",
      id: `check-msg-${check.key}`,
      innerHTML: check.message || "",
    }));
    checksContainer.appendChild(item);
  }

  container.appendChild(checksContainer);

  return container;
}

function updateStartupCheck(key: string, status: SystemCheckItem["status"], message: string): void {
  const item = $(`check-${key}`);
  const icon = $(`check-icon-${key}`);
  const msg = $(`check-msg-${key}`);

  if (item) {
    if (status === "checking") {
      item.className = "startup-check-item active";
    } else if (status === "ready" || status === "warning" || status === "error") {
      item.className = "startup-check-item done";
    }
  }

  if (icon) {
    icon.className = `startup-check-icon ${status}`;
    icon.innerHTML = status === "ready" ? "✓" : status === "warning" ? "!" : status === "error" ? "✕" : "";
  }

  if (msg) {
    msg.className = `startup-check-msg${status === "checking" ? " checking" : ""} ${status !== "waiting" ? status : ""}`;
    msg.innerHTML = message || "";
  }

  // Update check in state
  const checkState = state.checks.find((c) => c.key === key);
  if (checkState) {
    checkState.status = status;
    checkState.message = message;
  }

  // Update progress
  const doneCount = state.checks.filter((c) => c.status === "ready" || c.status === "warning" || c.status === "error").length;
  const checkingCount = state.checks.filter((c) => c.status === "checking").length;
  const total = state.checks.length;
  const progress = Math.round(((doneCount + checkingCount * 0.5) / total) * 100);

  const fill = $<HTMLElement>("progressFill");
  if (fill) fill.style.width = `${Math.min(progress, 100)}%`;
}

// ─── Main UI (idle/listening/processing/speaking) ──────────────────────────

function createJarvisOrb(): HTMLElement {
  const container = el("div", { className: "jarvis-orb-container" });
  const orb = el("div", { className: "jarvis-orb idle", id: "jarvisOrb" });

  orb.appendChild(el("div", { className: "jarvis-orb-ring" }));
  orb.appendChild(el("div", { className: "jarvis-orb-ring" }));
  orb.appendChild(el("div", { className: "jarvis-orb-ring" }));
  orb.appendChild(el("div", { className: "jarvis-orb-core" }));

  orb.addEventListener("click", () => {
    if (state.current === "idle") {
      setState("listening");
      simulateVoiceInput();
    } else {
      setState("idle");
    }
  });

  container.appendChild(orb);
  return container;
}

function createWaveform(): HTMLElement {
  const container = el("div", { className: "waveform-container", id: "waveform" });
  for (let i = 0; i < 10; i++) {
    container.appendChild(el("div", { className: "wave-bar", style: { height: "4px" } }));
  }
  return container;
}

function createStatusPanel(): HTMLElement {
  const container = el("div", { className: "status-container" });
  container.appendChild(el("div", {
    className: "status-text idle", id: "statusText", innerHTML: "Waiting...",
  }));
  container.appendChild(el("div", {
    className: "status-subtitle", innerHTML: "Press Ctrl+Space or click the orb",
  }));
  return container;
}

function createChatArea(): HTMLElement {
  const container = el("div", { className: "chat-area" });
  const group = el("div", { className: "chat-input-group" });
  const input = el("input", {
    className: "chat-input", id: "chatInput", type: "text",
    placeholder: "Введите сообщение...",
  }) as HTMLInputElement;

  const sendBtn = el("button", {
    className: "chat-send-btn", id: "sendBtn", innerHTML: "➤",
  });

  input.addEventListener("keydown", (e: KeyboardEvent) => {
    if (e.key === "Enter") sendMessage();
  });
  sendBtn.addEventListener("click", sendMessage);

  group.appendChild(input);
  group.appendChild(sendBtn);
  container.appendChild(group);
  return container;
}

function createResponseArea(): HTMLElement {
  return el("div", { className: "response-area", id: "responseArea" });
}

function createBackendIndicator(): HTMLElement {
  const container = el("div", { className: "backend-indicator", id: "backendIndicator" });
  container.appendChild(el("div", { className: "backend-dot checking", id: "backendDot" }));
  container.appendChild(el("span", { id: "backendLabel", innerHTML: "Connecting..." }));
  return container;
}

// ─── App Logic ─────────────────────────────────────────────────────────────

function setState(newState: AppState): void {
  state.current = newState;
  const orb = $<HTMLElement>("jarvisOrb");
  const statusText = $<HTMLElement>("statusText");
  const waveform = $<HTMLElement>("waveform");

  if (orb) orb.className = `jarvis-orb ${newState}`;

  if (statusText) {
    statusText.className = `status-text ${newState}`;
    const labels: Record<AppState, string> = {
      startup: "Initializing...",
      idle: "Waiting...",
      listening: "Listening...",
      processing: "Processing...",
      speaking: "Speaking...",
    };
    statusText.innerHTML = labels[newState];
  }

  if (waveform) {
    waveform.className = `waveform-container ${newState === "listening" || newState === "speaking" ? "active" : ""} ${newState === "speaking" ? "speaking" : ""}`;
  }
}

async function sendMessage(): Promise<void> {
  const input = $<HTMLInputElement>("chatInput");
  const responseArea = $<HTMLElement>("responseArea");
  if (!input || !responseArea) return;

  const text = input.value.trim();
  if (!text) return;

  input.value = "";
  setState("processing");

  const userMsg = el("div", {
    className: "response-text",
    style: { borderLeft: "2px solid rgba(0, 212, 255, 0.3)", marginBottom: "4px" },
    innerHTML: `<span style="color: var(--text-primary)">You:</span> ${escapeHtml(text)}`,
  });
  const thinkingMsg = el("div", {
    className: "response-text", id: "thinkingMsg",
    style: { borderLeft: "2px solid rgba(245, 158, 11, 0.3)", opacity: "0.6" },
    innerHTML: "Jarvis is thinking...",
  });

  responseArea.innerHTML = "";
  responseArea.appendChild(userMsg);
  responseArea.appendChild(thinkingMsg);

  try {
    let result;
    if (window.jarvis) {
      result = await window.jarvis.sendMessage(text);
    } else {
      const resp = await fetch("http://127.0.0.1:8000/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, conversation_id: state.conversationId }),
      });
      result = await resp.json();
    }

    const $thinking = $<HTMLElement>("thinkingMsg");
    if ($thinking) $thinking.remove();

    if (result && result.message && result.message.content) {
      const response = result.message.content;
      state.response = response;
      const respMsg = el("div", {
        className: "response-text",
        innerHTML: `<span style="color: var(--neon-blue)">Jarvis:</span> ${escapeHtml(response)}`,
      });
      responseArea.appendChild(respMsg);
      setState("speaking");
      
      const base64Audio = await synthesizeSpeech(response);
      if (base64Audio) {
        const audio = new Audio(`data:audio/wav;base64,${base64Audio}`);
        audio.play().catch(() => {
          // Autoplay blocked or decode failure — fall back to silent mode.
          console.warn("[JARVIS] Audio playback blocked");
        });
      }

      await sleep(Math.min(response.length * 30, 3000));
    } else if (result && result.error) {
      const errorMsg = el("div", {
        className: "response-text",
        style: { borderLeft: "2px solid rgba(239, 68, 68, 0.3)" },
        innerHTML: `<span style="color: #ef4444">Error:</span> ${escapeHtml(result.error)}`,
      });
      responseArea.appendChild(errorMsg);
    }
  } catch (err: any) {
    const $thinking = $<HTMLElement>("thinkingMsg");
    if ($thinking) $thinking.remove();
    const errorMsg = el("div", {
      className: "response-text",
      style: { borderLeft: "2px solid rgba(239, 68, 68, 0.3)" },
      innerHTML: `<span style="color: #ef4444">Error:</span> ${escapeHtml(err.message || "Connection failed")}`,
    });
    responseArea.appendChild(errorMsg);
  }

  setState("idle");
}

async function simulateVoiceInput(): Promise<void> {
  await sleep(2000);
  setState("processing");
  await sleep(1500);
  setState("speaking");
  await sleep(1500);
  setState("idle");
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function escapeHtml(text: string): string {
  const div = document.createElement("div");
  div.appendChild(document.createTextNode(text));
  return div.innerHTML;
}

function showGreeting(greeting: string): void {
  const shell = $<HTMLElement>("jarvisShell");
  if (!shell) return;

  const toast = el("div", { className: "greeting-toast", innerHTML: greeting });
  shell.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transition = "opacity 0.5s";
    setTimeout(() => toast.remove(), 500);
  }, 5000);
}

// ─── Initialize App ────────────────────────────────────────────────────────

function initApp(): void {
  const root = document.getElementById("root");
  if (!root) return;

  const shell = el("div", { className: "jarvis-shell", id: "jarvisShell" });

  // Elements that always exist
  shell.appendChild(createDragHandle());
  shell.appendChild(createTitleBar());

  // Startup splash UI
  const startupUI = createStartupUI();
  shell.appendChild(startupUI);

  // Main UI (hidden until startup completes)
  const mainUI = el("div", { className: "main-ui", id: "mainUI" });
  mainUI.appendChild(createJarvisOrb());
  mainUI.appendChild(createWaveform());
  mainUI.appendChild(createStatusPanel());
  mainUI.appendChild(createChatArea());
  mainUI.appendChild(createResponseArea());
  mainUI.appendChild(createBackendIndicator());
  shell.appendChild(mainUI);

  root.appendChild(shell);

  // If the window is transparent (config), allow the page background to be
  // see-through so the rounded glass shell is visible over the desktop.
  if (window.jarvis) {
    window.jarvis.getConfig().then((cfg: any) => {
      if (cfg && cfg.window && cfg.window.transparent) {
        document.body.classList.add("jarvis-transparent");
      }
    });
  }

  // ─── Listen for startup progress events ────────────────────────────────

  if (window.jarvis) {
    window.jarvis.onStartupProgress((data: any) => {
      const { step, status, message } = data;

      if (step === "connecting" && status === "checking") {
        updateStartupCheck("connecting", "checking", message || "Запуск сервера...");
      }

      if (step === "backend") {
        if (status === "checking") {
          updateStartupCheck("connecting", "ready", "Сервер запущен ✓");
          updateStartupCheck("backend", "checking", message || "Подключение...");
        } else {
          updateStartupCheck("backend", status, message || "");
        }
      }

      // System checks from /api/diagnostics
      if (["llm", "memory", "tools", "internet", "microphone", "speakers", "voice_pipeline", "configuration"].includes(step)) {
        updateStartupCheck(step, status, message || "");
      }

      // Diagnostic phase starting
      if (step === "diagnostics" && status === "checking") {
        // Mark backend as done, start all other checks
        ["llm", "memory", "tools", "internet", "microphone", "speakers", "voice_pipeline", "configuration"].forEach((key) => {
          const existing = state.checks.find((c) => c.key === key);
          if (existing && existing.status === "waiting") {
            updateStartupCheck(key, "checking", "Проверка...");
          }
        });
      }

      // Startup complete
      if (step === "complete") {
        const allOk = data.allSystemsOperational !== false;
        state.startupComplete = true;

        // Mark any remaining waiting items as ready
        state.checks.forEach((check) => {
          if (check.status === "waiting" || check.status === "checking") {
            updateStartupCheck(check.key, "ready", "Готово ✓");
          }
        });

        // Set progress to 100%
        const fill = $<HTMLElement>("progressFill");
        if (fill) fill.style.width = "100%";

        // Transition from startup → idle after a brief pause
        setTimeout(() => {
          const startupEl = $<HTMLElement>("startupContainer");
          if (startupEl) startupEl.classList.add("exit");

          setTimeout(() => {
            const mainEl = $<HTMLElement>("mainUI");
            if (mainEl) mainEl.classList.add("visible");
            state.current = "idle";
          }, 600);
        }, 800);
      }
    });

    // Listen for ready event (contains greeting + diagnostics data)
    window.jarvis.onReady((data: any) => {
      if (data.backendConnected) {
        state.backendConnected = true;
        const dot = $<HTMLElement>("backendDot");
        const label = $<HTMLElement>("backendLabel");
        if (dot && label) {
          dot.className = "backend-dot connected";
          label.innerHTML = "Backend Connected";
        }
      }

      if (data.greeting) {
        setTimeout(() => showGreeting(data.greeting), 3000);
      }
    });

    // Activate / Focus handlers
    window.jarvis.onActivate(() => {
      if (state.current === "idle") {
        const input = $<HTMLInputElement>("chatInput");
        if (input) input.focus();
      }
    });

    window.jarvis.onFocus(() => {
      const input = $<HTMLInputElement>("chatInput");
      if (input) input.focus();
    });
  }

  // Fallback: auto-check backend via HTTP if no IPC
  if (!window.jarvis) {
    checkBackendHttp();
  }
}

async function checkBackendHttp(): Promise<void> {
  try {
    const resp = await fetch("http://127.0.0.1:8000/api/health");
    if (resp.ok) {
      const data = await resp.json();
      if (data.status === "healthy") {
        state.backendConnected = true;
        updateStartupCheck("connecting", "ready", "Сервер запущен ✓");
        updateStartupCheck("backend", "ready", "Сервер подключён ✓");

        // Try diagnostics
        try {
          const diagResp = await fetch("http://127.0.0.1:8000/api/diagnostics");
          const diagData = await diagResp.json();
          if (diagData.checks) {
            const order = ["llm", "memory", "tools", "internet", "microphone", "speakers", "voice_pipeline", "configuration"];
            for (const key of order) {
              const check = diagData.checks[key];
              if (check) {
                updateStartupCheck(key, check.status, check.message);
                await sleep(300);
              }
            }
          }
        } catch {}

        // Complete
        state.checks.forEach((check) => {
          if (check.status === "waiting" || check.status === "checking") {
            updateStartupCheck(check.key, "ready", "Готово ✓");
          }
        });
        const fill = $<HTMLElement>("progressFill");
        if (fill) fill.style.width = "100%";
        state.startupComplete = true;

        setTimeout(() => {
          const startupEl = $<HTMLElement>("startupContainer");
          if (startupEl) startupEl.classList.add("exit");
          setTimeout(() => {
            const mainEl = $<HTMLElement>("mainUI");
            if (mainEl) mainEl.classList.add("visible");
            state.current = "idle";
          }, 600);
        }, 800);

        setTimeout(() => {
          showGreeting("Добро пожаловать, Maxsad. Все системы работают. Чем могу помочь?");
        }, 3000);
      }
    }
  } catch {
    // Backend not ready yet, retry later
    setTimeout(checkBackendHttp, 2000);
  }
}

// Wait for DOM
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initApp);
} else {
  initApp();
}
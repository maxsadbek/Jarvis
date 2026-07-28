# JARVIS Desktop Application

The Windows desktop application layer for the JARVIS AI Assistant. Built with Electron, TypeScript, and React.

## Architecture

```
desktop/
├── config/
│   └── assistant.json        # Voice greeting & app configuration
├── src/
│   ├── main.ts               # Electron main process
│   ├── preload.ts            # Secure IPC bridge
│   ├── App.tsx               # React overlay UI
│   ├── global.d.ts           # TypeScript declarations
│   └── services/
│       └── backend.ts        # FastAPI backend client
├── public/                   # Static assets
├── resources/                # Icons and installer resources
├── package.json
├── tsconfig.json
├── electron-builder.yml
└── README.md
```

## Prerequisites

- Node.js >= 18
- Python >= 3.11 (for backend)
- FastAPI backend running on `http://127.0.0.1:8000`

## Quick Start

### 1. Start the Backend

From the project root:

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 2. Start the Desktop App (Development)

```bash
cd desktop
npm install
npm run dev
```

### 3. Build the Desktop App

```bash
cd desktop
npm run dist
```

This will produce `release/Jarvis-Setup-0.1.0.exe`.

## Features

### 🪟 Frameless Window
- Transparent, always-on-top overlay window
- Drag to reposition (click and drag the top bar)
- Close/minimize buttons in the top-right corner

### 🖥️ System Tray
- Right-click the tray icon for options
- Double-click to show/hide the window
- Quick access to backend connection check

### ⌨️ Global Shortcuts
- `Ctrl+Space` — Activate Jarvis (show window and focus input)
- `Ctrl+Shift+J` — Toggle window visibility

### 🔄 Auto-Startup
- Automatically launches when Windows starts
- Configurable in `config/assistant.json`
- First launch may ask for permission

### 🗣️ Voice Greeting
- Plays a greeting on successful startup
- Configurable language: Russian, English, Uzbek
- Edit `config/assistant.json` to customize

### 🔗 Backend Integration
- Automatically detects the FastAPI backend
- Shows connection status in the UI
- Chat messages sent through the backend API

## Configuration

Edit `config/assistant.json` to customize:

```json
{
  "name": "Jarvis",
  "startupGreeting": true,
  "language": "ru",
  "window": {
    "width": 480,
    "height": 600,
    "alwaysOnTop": true,
    "opacity": 0.92
  },
  "backend": {
    "url": "http://127.0.0.1:8000"
  },
  "shortcuts": {
    "activate": "CommandOrControl+Space"
  },
  "startup": {
    "autoStart": true,
    "minimizeToTray": true
  }
}
```

## Development

### Commands

| Command | Description |
|---------|-------------|
| `npm run dev` | Start in development mode (watch + electron) |
| `npm run build` | Compile TypeScript |
| `npm run dist` | Build installer (Jarvis.exe) |
| `npm run dist:win` | Build Windows installer |

### Adding Resources

1. Place `icon.ico` in `resources/` for the installer icon
2. Place `icon.png` for the tray icon
3. Update `config/assistant.json` for custom greetings

## Security

- `contextIsolation: true` — Renderer is isolated from Node.js
- `nodeIntegration: false` — No direct Node.js access in renderer
- Secure preload bridge — Only specific APIs are exposed
- CSP headers — Restricts content sources

## Troubleshooting

**Backend not connecting:**
1. Ensure the backend is running: `http://127.0.0.1:8000/api/health`
2. Check the connection status indicator in the app
3. Restart the desktop app

**Build fails:**
1. Ensure all dependencies: `npm install`
2. Check Node.js version: `node --version` (>= 18)
3. Run `npm run build` before `npm run dist`

**Window doesn't appear:**
1. Check system tray for the Jarvis icon
2. Press `Ctrl+Space` to activate
3. Check if another instance is running

/**
 * JARVIS Desktop - Secure Preload Bridge
 *
 * Exposes a safe API to the renderer process via contextBridge.
 * No direct Node.js or Electron access is leaked to the UI.
 */

import { contextBridge, ipcRenderer } from "electron";

/**
 * Safe API surface exposed to the renderer (React UI).
 * All communication goes through IPC — no raw Node.js access.
 */
const JarvisAPI = {
  // ─── Config ────────────────────────────────────────────────────────────────

  /** Get the full assistant configuration */
  getConfig: (): Promise<any> => ipcRenderer.invoke("jarvis:getConfig"),

  /** Get the startup greeting text based on configured language */
  getGreeting: (): Promise<string | null> => ipcRenderer.invoke("jarvis:getGreeting"),

  // ─── Backend ──────────────────────────────────────────────────────────────

  /** Check if the backend server is healthy */
  checkBackend: (): Promise<boolean> => ipcRenderer.invoke("jarvis:checkBackend"),

  /** Get cached backend connection status */
  getBackendStatus: (): Promise<boolean> => ipcRenderer.invoke("jarvis:getBackendStatus"),

  /** Send a chat message through the backend */
  sendMessage: (message: string): Promise<any> => ipcRenderer.invoke("jarvis:sendMessage", message),

  /** Get full system status from backend */
  getStatus: (): Promise<any> => ipcRenderer.invoke("jarvis:getStatus"),

  /** Check if the backend process is running */
  isBackendRunning: (): Promise<boolean> => ipcRenderer.invoke("jarvis:isBackendRunning"),

  /** Restart the backend process */
  restartBackend: (): Promise<boolean> => ipcRenderer.invoke("jarvis:restartBackend"),

  // ─── Window ───────────────────────────────────────────────────────────────

  /** Toggle the window visibility */
  toggleWindow: () => ipcRenderer.invoke("jarvis:toggleWindow"),

  /** Hide the window */
  hide: () => ipcRenderer.invoke("jarvis:hide"),

  /** Quit the application */
  quit: () => ipcRenderer.invoke("jarvis:quit"),

  // ─── Events ───────────────────────────────────────────────────────────────

  /** Listen for activation events (Ctrl+Space) */
  onActivate: (callback: () => void) => {
    const handler = () => callback();
    ipcRenderer.on("jarvis:activate", handler);
    return () => ipcRenderer.removeListener("jarvis:activate", handler);
  },

  /** Listen for focus events */
  onFocus: (callback: () => void) => {
    const handler = () => callback();
    ipcRenderer.on("jarvis:focus", handler);
    return () => ipcRenderer.removeListener("jarvis:focus", handler);
  },

  /** Listen for ready event (app initialized) */
  onReady: (callback: (data: any) => void) => {
    const handler = (_event: any, data: any) => callback(data);
    ipcRenderer.on("jarvis:ready", handler);
    return () => ipcRenderer.removeListener("jarvis:ready", handler);
  },

  /** Listen for startup progress updates */
  onStartupProgress: (callback: (data: any) => void) => {
    const handler = (_event: any, data: any) => callback(data);
    ipcRenderer.on("jarvis:startupProgress", handler);
    return () => ipcRenderer.removeListener("jarvis:startupProgress", handler);
  },
};

// Expose the API safely to the renderer
contextBridge.exposeInMainWorld("jarvis", JarvisAPI);

// Type declaration for the renderer
export type JarvisAPIType = typeof JarvisAPI;

/**
 * TypeScript declarations for the window.jarvis API
 * exposed by preload.ts via contextBridge.
 */

interface JarvisAPI {
  getConfig: () => Promise<any>;
  getGreeting: () => Promise<string | null>;
  checkBackend: () => Promise<boolean>;
  getBackendStatus: () => Promise<boolean>;
  sendMessage: (message: string) => Promise<any>;
  getStatus: () => Promise<any>;
  toggleWindow: () => void;
  hide: () => void;
  quit: () => void;
  onActivate: (callback: () => void) => () => void;
  onFocus: (callback: () => void) => () => void;
  onReady: (callback: (data: any) => void) => () => void;
  onStartupProgress: (callback: (data: any) => void) => () => void;
}

declare global {
  interface Window {
    jarvis: JarvisAPI;
  }
}

export {};

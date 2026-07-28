/**
 * JARVIS Backend Service
 *
 * Client for communicating with the FastAPI backend.
 * All calls go through the secure preload bridge.
 */

export interface BackendStatus {
  status: string;
  llm_ready: boolean;
  memory_ready: boolean;
  tools_loaded: string[];
  voice_pipeline_ready: boolean;
  uptime_seconds: number;
}

export interface ChatResponse {
  message: {
    role: string;
    content: string;
    type: string;
  };
  conversation_id: string;
  tokens_used: number;
  processing_time_ms: number;
}

export interface HealthResponse {
  status: string;
  llm_ready: boolean;
  connections: number;
  voice_ready: boolean;
}

const BACKEND_URL = "http://127.0.0.1:8000";
const TIMEOUT_MS = 5000;

/**
 * Fetch wrapper with timeout.
 */
async function fetchWithTimeout(url: string, options: RequestInit = {}): Promise<Response> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    return response;
  } finally {
    clearTimeout(timeout);
  }
}

/**
 * Check backend health.
 * Returns true if the backend is running and healthy.
 */
export async function checkHealth(): Promise<boolean> {
  try {
    const response = await fetchWithTimeout(`${BACKEND_URL}/api/health`);
    if (!response.ok) return false;
    const data: HealthResponse = await response.json();
    return data.status === "healthy";
  } catch {
    return false;
  }
}

/**
 * Send a text message to the AI and get a response.
 */
export async function sendMessage(
  message: string,
  conversationId: string = "desktop",
): Promise<ChatResponse | { error: string }> {
  try {
    const response = await fetchWithTimeout(`${BACKEND_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        conversation_id: conversationId,
      }),
    });
    if (!response.ok) {
      return { error: `HTTP ${response.status}: ${response.statusText}` };
    }
    return await response.json();
  } catch (err: any) {
    return { error: err.message || "Connection failed" };
  }
}

/**
 * Get the full system status from the backend.
 */
export async function getStatus(): Promise<BackendStatus | { status: string }> {
  try {
    const response = await fetchWithTimeout(`${BACKEND_URL}/api/status`);
    if (!response.ok) return { status: "error" };
    return await response.json();
  } catch {
    return { status: "disconnected" };
  }
}

/**
 * Get system statistics from the backend.
 */
export async function getStats(): Promise<any> {
  try {
    const response = await fetchWithTimeout(`${BACKEND_URL}/api/stats`);
    if (!response.ok) return {};
    return await response.json();
  } catch {
    return {};
  }
}

/**
 * Start a voice session (requires voice pipeline to be initialized).
 */
export async function startVoice(): Promise<any> {
  try {
    const response = await fetchWithTimeout(`${BACKEND_URL}/api/voice/pipeline/session/start`, {
      method: "POST",
    });
    if (!response.ok) return { success: false };
    return await response.json();
  } catch {
    return { success: false };
  }
}

/**
 * End the current voice session.
 */
export async function endVoice(): Promise<any> {
  try {
    const response = await fetchWithTimeout(`${BACKEND_URL}/api/voice/pipeline/session/end`, {
      method: "POST",
    });
    if (!response.ok) return { success: false };
    return await response.json();
  } catch {
    return { success: false };
  }
}

/**
 * Get voice pipeline status.
 */
export async function getVoiceStatus(): Promise<any> {
  try {
    const response = await fetchWithTimeout(`${BACKEND_URL}/api/voice/pipeline/status`);
    if (!response.ok) return { status: "unavailable" };
    return await response.json();
  } catch {
    return { status: "unavailable" };
  }
}

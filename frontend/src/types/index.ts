/* ============================================
   JARVIS - Type Definitions
   ============================================ */

// --- Message Types ---

export type MessageRole = "user" | "assistant" | "system";

export type MessageType = "text" | "voice" | "command" | "error" | "code";

export interface Message {
  id: string;
  role: MessageRole;
  type: MessageType;
  content: string;
  timestamp: string;
  metadata?: Record<string, unknown>;
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  created_at: string;
  updated_at: string;
}

// --- Connection Types ---

export type ConnectionState =
  | "disconnected"
  | "connecting"
  | "connected"
  | "listening"
  | "processing"
  | "speaking";

export interface WSMessage {
  type: string;
  data: Record<string, unknown>;
  timestamp: string;
}

// --- Voice Types ---

export interface VoiceConfig {
  stt_engine: string;
  tts_engine: string;
  wake_word_enabled: boolean;
  wake_word: string;
  tts_speed: number;
  sample_rate: number;
}

// --- System Types ---

export interface SystemStatus {
  app_name: string;
  app_version: string;
  status: string;
  llm_connected: boolean;
  llm_model: string | null;
  stt_ready: boolean;
  tts_ready: boolean;
  memory_ready: boolean;
  tools_loaded: string[];
  cpu_usage: number;
  memory_usage: number;
  uptime_seconds: number;
}

// --- Component Props ---

export interface ChatMessageProps {
  message: Message;
  isLatest?: boolean;
}

export interface VoiceButtonProps {
  isListening: boolean;
  onToggle: () => void;
  disabled?: boolean;
  connectionState: ConnectionState;
}

export interface StatusIndicatorProps {
  state: ConnectionState;
  label?: string;
}

// --- Store Types ---

export interface ChatStore {
  conversations: Map<string, Conversation>;
  activeConversationId: string | null;
  isStreaming: boolean;
  connectionState: ConnectionState;
  
  // Actions
  addMessage: (conversationId: string, message: Message) => void;
  setActiveConversation: (id: string) => void;
  createConversation: () => string;
  setConnectionState: (state: ConnectionState) => void;
  setIsStreaming: (streaming: boolean) => void;
}

export interface SettingsStore {
  voiceConfig: VoiceConfig;
  theme: "dark" | "light";
  openAIKey: string | null;
  
  // Actions
  setVoiceConfig: (config: Partial<VoiceConfig>) => void;
  setTheme: (theme: "dark" | "light") => void;
  setOpenAIKey: (key: string | null) => void;
}

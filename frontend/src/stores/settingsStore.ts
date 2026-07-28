import { create } from "zustand";
import type { SettingsStore, VoiceConfig } from "@/types";

const DEFAULT_VOICE_CONFIG: VoiceConfig = {
  stt_engine: "faster_whisper",
  tts_engine: "piper",
  wake_word_enabled: true,
  wake_word: "jarvis",
  tts_speed: 1.0,
  sample_rate: 16000,
};

export const useSettingsStore = create<SettingsStore>((set) => ({
  voiceConfig: DEFAULT_VOICE_CONFIG,
  theme: "dark",
  openAIKey: null,

  setVoiceConfig: (config: Partial<VoiceConfig>) => {
    set((state) => ({
      voiceConfig: { ...state.voiceConfig, ...config },
    }));
  },

  setTheme: (theme: "dark" | "light") => {
    set({ theme });
  },

  setOpenAIKey: (key: string | null) => {
    set({ openAIKey: key });
  },
}));

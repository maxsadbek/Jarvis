import React from "react";
import { Card } from "@/components/ui/Card";
import { Slider } from "@/components/ui/Slider";
import { useSettingsStore } from "@/stores/settingsStore";
import { Switch } from "@/components/ui/Switch";
import { Input } from "@/components/ui/Input";
import { Mic, Volume2, Radio } from "lucide-react";

export function VoiceSettings() {
  const voiceConfig = useSettingsStore((s) => s.voiceConfig);
  const setVoiceConfig = useSettingsStore((s) => s.setVoiceConfig);

  return (
    <Card className="space-y-6">
      <h3 className="text-sm font-semibold text-gray-200 flex items-center gap-2">
        <Mic className="w-4 h-4 text-accent-blue" />
        Voice Settings
      </h3>

      {/* Wake Word */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-300">Wake Word Detection</p>
          <p className="text-xs text-gray-600 mt-0.5">Activate JARVIS by saying "{voiceConfig.wake_word}"</p>
        </div>
        <Switch
          checked={voiceConfig.wake_word_enabled}
          onCheckedChange={(checked) => setVoiceConfig({ wake_word_enabled: checked })}
        />
      </div>

      {voiceConfig.wake_word_enabled && (
        <Input
          label="Wake Word"
          value={voiceConfig.wake_word}
          onChange={(e) => setVoiceConfig({ wake_word: e.target.value })}
          icon={<Radio className="w-4 h-4" />}
          placeholder="jarvis"
        />
      )}

      {/* TTS Speed */}
      <Slider
        label="Speech Speed"
        value={Math.round(voiceConfig.tts_speed * 100)}
        onChange={(value) => setVoiceConfig({ tts_speed: value / 100 })}
        min={50}
        max={200}
        formatValue={(v) => `${(v / 100).toFixed(1)}x`}
      />

      {/* Engine status */}
      <div className="grid grid-cols-2 gap-3 pt-2 border-t border-white/5">
        <div className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.04]">
          <p className="text-xs text-gray-500">STT Engine</p>
          <p className="text-sm font-medium text-gray-200 mt-1 capitalize">
            {voiceConfig.stt_engine.replace("_", " ")}
          </p>
        </div>
        <div className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.04]">
          <p className="text-xs text-gray-500">TTS Engine</p>
          <p className="text-sm font-medium text-gray-200 mt-1 capitalize">
            {voiceConfig.tts_engine.replace("_", " ")}
          </p>
        </div>
      </div>
    </Card>
  );
}

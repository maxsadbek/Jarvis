import React from "react";
import { VoiceSettings } from "@/components/settings/VoiceSettings";
import { AISettings } from "@/components/settings/AISettings";
import { Card } from "@/components/ui/Card";
import { Switch } from "@/components/ui/Switch";
import { useSettingsStore } from "@/stores/settingsStore";
import { Info, Shield, Bell } from "lucide-react";

export function SettingsPage() {
  const voiceConfig = useSettingsStore((s) => s.voiceConfig);
  const setVoiceConfig = useSettingsStore((s) => s.setVoiceConfig);

  return (
    <div className="flex-1 overflow-y-auto p-6">
      {/* Page header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gradient">Settings</h1>
        <p className="text-sm text-gray-500 mt-1">
          Configure JARVIS to your preferences
        </p>
      </div>

      <div className="max-w-2xl space-y-4">
        {/* Voice settings */}
        <VoiceSettings />

        {/* AI settings */}
        <AISettings />

        {/* General settings */}
        <Card className="space-y-4">
          <h3 className="text-sm font-semibold text-gray-200 flex items-center gap-2">
            <Shield className="w-4 h-4 text-accent-green" />
            Privacy & Preferences
          </h3>

          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-300">Memory Enabled</p>
                <p className="text-xs text-gray-600 mt-0.5">
                  JARVIS remembers past conversations for context
                </p>
              </div>
              <Switch
                checked={true}
                onCheckedChange={() => {}}
              />
            </div>

            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-300">Status Notifications</p>
                <p className="text-xs text-gray-600 mt-0.5">
                  Show desktop notifications for important events
                </p>
              </div>
              <Switch
                checked={true}
                onCheckedChange={() => {}}
              />
            </div>

            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-300">Auto-Launch</p>
                <p className="text-xs text-gray-600 mt-0.5">
                  Start JARVIS when you log in to Windows
                </p>
              </div>
              <Switch
                checked={false}
                onCheckedChange={() => {}}
              />
            </div>
          </div>
        </Card>

        {/* About */}
        <Card className="space-y-3">
          <h3 className="text-sm font-semibold text-gray-200 flex items-center gap-2">
            <Info className="w-4 h-4 text-accent-blue" />
            About JARVIS
          </h3>
          <div className="space-y-1 text-sm">
            <div className="flex justify-between py-1">
              <span className="text-gray-500">Version</span>
              <span className="text-gray-300">0.1.0</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-gray-500">Status</span>
              <span className="text-accent-green">Operational</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-gray-500">AI Model</span>
              <span className="text-gray-300">OpenRouter Multi-Model</span>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}

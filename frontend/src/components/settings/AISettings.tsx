import React from "react";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Slider } from "@/components/ui/Slider";
import { Button } from "@/components/ui/Button";
import { useSettingsStore } from "@/stores/settingsStore";
import { Brain, Key, ExternalLink } from "lucide-react";

export function AISettings() {
  const openAIKey = useSettingsStore((s) => s.openAIKey);
  const setOpenAIKey = useSettingsStore((s) => s.setOpenAIKey);

  const handleSaveKey = () => {
    // In production, save to backend
    console.log("Saving API key...");
  };

  return (
    <Card className="space-y-6">
      <h3 className="text-sm font-semibold text-gray-200 flex items-center gap-2">
        <Brain className="w-4 h-4 text-accent-purple" />
        AI Configuration
      </h3>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <p className="text-sm font-medium text-gray-300">OpenRouter API Key</p>
          <a
            href="https://openrouter.ai/keys"
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-accent-blue hover:text-accent-blue/80 flex items-center gap-1"
          >
            Get key <ExternalLink className="w-3 h-3" />
          </a>
        </div>
        <div className="flex gap-2">
          <Input
            type="password"
            value={openAIKey || ""}
            onChange={(e) => setOpenAIKey(e.target.value || null)}
            placeholder="sk-or-v1-..."
            icon={<Key className="w-4 h-4" />}
            className="flex-1"
          />
          <Button variant="secondary" size="sm" onClick={handleSaveKey}>
            Save
          </Button>
        </div>
      </div>

      <div className="p-3 rounded-xl bg-accent-amber/5 border border-accent-amber/10">
        <p className="text-xs text-accent-amber">
          Your API key is stored locally and never shared. It's used to
          communicate with OpenRouter's API for AI responses.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.04]">
          <p className="text-xs text-gray-500">Current Model</p>
          <p className="text-sm font-medium text-gray-200 mt-1">
            openai/gpt-4o-mini
          </p>
        </div>
        <div className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.04]">
          <p className="text-xs text-gray-500">Fallback Model</p>
          <p className="text-sm font-medium text-gray-200 mt-1">
            claude-3-haiku
          </p>
        </div>
      </div>
    </Card>
  );
}

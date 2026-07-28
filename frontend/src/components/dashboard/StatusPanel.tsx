import React from "react";
import { Card } from "@/components/ui/Card";
import { StatusIndicator } from "@/components/ui/StatusIndicator";
import { cn } from "@/lib/utils";
import {
  Brain,
  Mic,
  Volume2,
  Database,
  Wrench,
  Cpu,
  HardDrive,
  Activity,
} from "lucide-react";
import type { ConnectionState, SystemStatus } from "@/types";

interface StatusPanelProps {
  connectionState: ConnectionState;
  systemStatus?: SystemStatus | null;
  className?: string;
}

export function StatusPanel({
  connectionState,
  systemStatus,
  className,
}: StatusPanelProps) {
  const services = [
    {
      name: "AI Engine",
      icon: Brain,
      ready: systemStatus?.llm_connected ?? false,
      detail: systemStatus?.llm_model || "Not connected",
    },
    {
      name: "Speech-to-Text",
      icon: Mic,
      ready: systemStatus?.stt_ready ?? false,
      detail: "Faster-Whisper",
    },
    {
      name: "Text-to-Speech",
      icon: Volume2,
      ready: systemStatus?.tts_ready ?? false,
      detail: "Piper TTS",
    },
    {
      name: "Memory",
      icon: Database,
      ready: systemStatus?.memory_ready ?? false,
      detail: "ChromaDB",
    },
    {
      name: "Tools",
      icon: Wrench,
      ready: (systemStatus?.tools_loaded?.length ?? 0) > 0,
      detail: `${systemStatus?.tools_loaded?.length ?? 0} tools loaded`,
    },
  ];

  return (
    <Card className={cn("space-y-4", className)} scanLine>
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-200">System Status</h3>
        <StatusIndicator state={connectionState} size="sm" />
      </div>

      {/* Services grid */}
      <div className="grid grid-cols-2 gap-2">
        {services.map((service) => {
          const IconComponent = service.icon;
          return (
            <div
              key={service.name}
              className="flex items-center gap-2.5 p-2.5 rounded-xl bg-white/[0.02] border border-white/[0.04]"
            >
              <div
                className={cn(
                  "w-8 h-8 rounded-lg flex items-center justify-center",
                  service.ready
                    ? "bg-accent-green/10 text-accent-green"
                    : "bg-white/5 text-gray-500"
                )}
              >
                <IconComponent className="w-4 h-4" />
              </div>
              <div>
                <p className="text-xs font-medium text-gray-300">{service.name}</p>
                <p className="text-[10px] text-gray-600">{service.detail}</p>
              </div>
            </div>
          );
        })}
      </div>

      {/* System metrics */}
      {systemStatus && (
        <div className="grid grid-cols-2 gap-3 pt-2 border-t border-white/5">
          <div className="flex items-center gap-2">
            <Cpu className="w-3 h-3 text-gray-500" />
            <div className="flex-1">
              <div className="flex justify-between text-xs">
                <span className="text-gray-500">CPU</span>
                <span className="text-gray-300">{systemStatus.cpu_usage.toFixed(1)}%</span>
              </div>
              <div className="h-1 bg-white/5 rounded-full mt-1 overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-accent-blue to-accent-purple rounded-full transition-all duration-500"
                  style={{ width: `${systemStatus.cpu_usage}%` }}
                />
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <HardDrive className="w-3 h-3 text-gray-500" />
            <div className="flex-1">
              <div className="flex justify-between text-xs">
                <span className="text-gray-500">RAM</span>
                <span className="text-gray-300">{systemStatus.memory_usage.toFixed(1)}%</span>
              </div>
              <div className="h-1 bg-white/5 rounded-full mt-1 overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-accent-green to-accent-cyan rounded-full transition-all duration-500"
                  style={{ width: `${systemStatus.memory_usage}%` }}
                />
              </div>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}

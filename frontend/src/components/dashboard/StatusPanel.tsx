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
  Zap,
  TrendingUp,
  Layers,
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
      gradient: "from-accent-blue/20 to-accent-blue/5",
      accent: "text-accent-blue",
      glow: "rgba(0, 212, 255, 0.3)",
    },
    {
      name: "Speech-to-Text",
      icon: Mic,
      ready: systemStatus?.stt_ready ?? false,
      detail: "Faster-Whisper",
      gradient: "from-accent-purple/20 to-accent-purple/5",
      accent: "text-accent-purple",
      glow: "rgba(139, 92, 246, 0.3)",
    },
    {
      name: "Text-to-Speech",
      icon: Volume2,
      ready: systemStatus?.tts_ready ?? false,
      detail: "Piper TTS",
      gradient: "from-accent-cyan/20 to-accent-cyan/5",
      accent: "text-accent-cyan",
      glow: "rgba(34, 211, 238, 0.3)",
    },
    {
      name: "Memory",
      icon: Database,
      ready: systemStatus?.memory_ready ?? false,
      detail: systemStatus?.memory_usage
        ? `${(systemStatus.memory_usage * 100).toFixed(0)}% used`
        : "ChromaDB",
      gradient: "from-accent-emerald/20 to-accent-emerald/5",
      accent: "text-accent-emerald",
      glow: "rgba(52, 211, 153, 0.3)",
    },
    {
      name: "Tools",
      icon: Wrench,
      ready: (systemStatus?.tools_loaded?.length ?? 0) > 0,
      detail: `${systemStatus?.tools_loaded?.length ?? 0} tools loaded`,
      gradient: "from-accent-amber/20 to-accent-amber/5",
      accent: "text-accent-amber",
      glow: "rgba(245, 158, 11, 0.3)",
    },
  ];

  return (
    <Card className={cn("space-y-4", className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-accent-blue" />
          <h3 className="text-sm font-semibold text-gray-200">
            System Status
          </h3>
        </div>
        <StatusIndicator state={connectionState} size="sm" />
      </div>

      {/* Services grid */}
      <div className="grid grid-cols-2 gap-2">
        {services.map((service) => {
          const IconComponent = service.icon;
          return (
            <div
              key={service.name}
              className={cn(
                "group relative flex items-center gap-2.5 p-2.5 rounded-xl overflow-hidden",
                "bg-white/[0.02] border border-white/[0.04]",
                "hover:bg-white/[0.04] hover:border-white/10",
                "transition-all duration-300"
              )}
            >
              {/* Hover glow */}
              <div
                className={cn(
                  "absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 rounded-xl",
                  "bg-gradient-to-br",
                  service.gradient
                )}
              />

              {/* Icon */}
              <div
                className={cn(
                  "relative z-10 w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-300",
                  service.ready
                    ? cn("bg-gradient-to-br", service.gradient, service.accent)
                    : "bg-white/5 text-gray-500"
                )}
                style={
                  service.ready
                    ? {
                        boxShadow: `0 0 12px ${service.glow}`,
                      }
                    : undefined
                }
              >
                <IconComponent className="w-4 h-4" />
              </div>

              {/* Text */}
              <div className="relative z-10">
                <p className="text-xs font-medium text-gray-300">
                  {service.name}
                </p>
                <p className="text-[10px] text-gray-600">{service.detail}</p>
              </div>

              {/* Status dot */}
              <div className="relative z-10 ml-auto">
                <span
                  className={cn(
                    "w-1.5 h-1.5 rounded-full",
                    service.ready
                      ? "bg-accent-green shadow-[0_0_6px_rgba(52,211,153,0.5)]"
                      : "bg-gray-600"
                  )}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* System metrics */}
      {systemStatus && (
        <div className="space-y-3 pt-3 border-t border-white/5">
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <TrendingUp className="w-3 h-3" />
            <span>Performance Metrics</span>
          </div>

          {/* CPU */}
          <div className="flex items-center gap-2.5">
            <Cpu className="w-3.5 h-3.5 text-accent-blue shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="flex justify-between text-xs mb-1">
                <span className="text-gray-500">CPU</span>
                <span className="text-gray-300 font-mono">
                  {systemStatus.cpu_usage.toFixed(1)}%
                </span>
              </div>
              <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-700 ease-out"
                  style={{
                    width: `${systemStatus.cpu_usage}%`,
                    background:
                      "linear-gradient(90deg, #00d4ff, #8b5cf6)",
                    boxShadow: "0 0 8px rgba(0, 212, 255, 0.3)",
                  }}
                />
              </div>
            </div>
          </div>

          {/* Memory */}
          <div className="flex items-center gap-2.5">
            <HardDrive className="w-3.5 h-3.5 text-accent-purple shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="flex justify-between text-xs mb-1">
                <span className="text-gray-500">RAM</span>
                <span className="text-gray-300 font-mono">
                  {systemStatus.memory_usage.toFixed(1)}%
                </span>
              </div>
              <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-700 ease-out"
                  style={{
                    width: `${systemStatus.memory_usage}%`,
                    background:
                      "linear-gradient(90deg, #8b5cf6, #22d3ee)",
                    boxShadow: "0 0 8px rgba(139, 92, 246, 0.3)",
                  }}
                />
              </div>
            </div>
          </div>

          {/* Tools loaded count as mini bar */}
          {systemStatus.tools_loaded && systemStatus.tools_loaded.length > 0 && (
            <div className="flex items-center gap-2.5">
              <Layers className="w-3.5 h-3.5 text-accent-amber shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap gap-1">
                  {systemStatus.tools_loaded.slice(0, 6).map((tool, i) => (
                    <span
                      key={i}
                      className="text-[9px] px-1.5 py-0.5 rounded-md bg-white/5 text-gray-500 border border-white/5"
                    >
                      {tool.replace("_", " ")}
                    </span>
                  ))}
                  {systemStatus.tools_loaded.length > 6 && (
                    <span className="text-[9px] px-1.5 py-0.5 rounded-md bg-white/5 text-gray-600">
                      +{systemStatus.tools_loaded.length - 6}
                    </span>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

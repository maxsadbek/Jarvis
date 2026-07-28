import React from "react";
import { cn } from "@/lib/utils";
import { Database, Cpu, HardDrive } from "lucide-react";
import type { SystemStatus } from "@/types";

interface MemoryIndicatorProps {
  systemStatus?: SystemStatus | null;
  memoryStats?: {
    total_facts?: number;
    total_habits?: number;
    total_preferences?: number;
    vector_items?: number;
    conversations?: number;
    total_messages?: number;
  } | null;
  className?: string;
}

export function MemoryIndicator({
  systemStatus,
  memoryStats,
  className,
}: MemoryIndicatorProps) {
  const memoryReady = systemStatus?.memory_ready ?? false;
  const cpuUsage = systemStatus?.cpu_usage ?? 0;
  const ramUsage = systemStatus?.memory_usage ?? 0;

  const items = [
    {
      label: "Facts",
      value: memoryStats?.total_facts ?? 0,
      icon: Database,
      color: "text-neon-blue",
      glow: "shadow-neon-blue",
    },
    {
      label: "Habits",
      value: memoryStats?.total_habits ?? 0,
      icon: Cpu,
      color: "text-neon-purple",
      glow: "shadow-neon-purple",
    },
    {
      label: "Preferences",
      value: memoryStats?.total_preferences ?? 0,
      icon: HardDrive,
      color: "text-neon-cyan",
      glow: "shadow-neon-blue",
    },
  ];

  return (
    <div className={cn("space-y-3", className)}>
      {/* Memory health bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "w-1.5 h-1.5 rounded-full",
              memoryReady
                ? "bg-neon-green shadow-[0_0_8px_rgba(16,185,129,0.5)]"
                : "bg-gray-600"
            )}
          />
          <span className="text-[11px] font-medium text-gray-400 uppercase tracking-wider">
            Memory Cortex
          </span>
        </div>
        <span className="text-[10px] text-gray-600">
          {memoryReady ? "Active" : "Offline"}
        </span>
      </div>

      {/* Memory items */}
      <div className="grid grid-cols-3 gap-2">
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <div
              key={item.label}
              className={cn(
                "glass-panel px-2.5 py-2 flex flex-col items-center gap-1",
                item.glow
              )}
            >
              <Icon className={cn("w-3.5 h-3.5", item.color)} />
              <span className="text-xs font-bold text-gray-200">
                {item.value}
              </span>
              <span className="text-[9px] text-gray-600 uppercase tracking-wider">
                {item.label}
              </span>
            </div>
          );
        })}
      </div>

      {/* System resources */}
      <div className="space-y-1.5">
        <div className="flex justify-between text-[10px]">
          <span className="text-gray-600">CPU</span>
          <span className={cn(
            "font-medium",
            cpuUsage > 80 ? "text-neon-rose" : cpuUsage > 50 ? "text-neon-amber" : "text-gray-400"
          )}>
            {cpuUsage.toFixed(1)}%
          </span>
        </div>
        <div className="h-0.5 bg-white/[0.04] rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${cpuUsage}%`,
              background: `linear-gradient(90deg, rgba(99,102,241,0.6), rgba(0,212,255,0.6))`,
            }}
          />
        </div>

        <div className="flex justify-between text-[10px]">
          <span className="text-gray-600">RAM</span>
          <span className={cn(
            "font-medium",
            ramUsage > 80 ? "text-neon-rose" : ramUsage > 50 ? "text-neon-amber" : "text-gray-400"
          )}>
            {ramUsage.toFixed(1)}%
          </span>
        </div>
        <div className="h-0.5 bg-white/[0.04] rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${ramUsage}%`,
              background: `linear-gradient(90deg, rgba(139,92,246,0.6), rgba(6,182,212,0.6))`,
            }}
          />
        </div>
      </div>
    </div>
  );
}

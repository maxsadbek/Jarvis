import React from "react";
import { cn } from "@/lib/utils";
import type { ConnectionState } from "@/types";

interface StatusIndicatorProps {
  state: ConnectionState;
  label?: string;
  showLabel?: boolean;
  size?: "sm" | "md" | "lg";
}

const stateConfig: Record<ConnectionState, { color: string; label: string }> = {
  disconnected: { color: "bg-gray-500", label: "Disconnected" },
  connecting: { color: "bg-accent-amber animate-pulse", label: "Connecting..." },
  connected: { color: "bg-accent-green shadow-[0_0_10px_rgba(16,185,129,0.5)]", label: "Connected" },
  listening: { color: "bg-accent-blue shadow-[0_0_10px_rgba(0,212,255,0.5)] animate-pulse-glow", label: "Listening..." },
  processing: { color: "bg-accent-amber shadow-[0_0_10px_rgba(245,158,11,0.5)] animate-pulse-glow", label: "Processing..." },
  speaking: { color: "bg-accent-purple shadow-[0_0_10px_rgba(139,92,246,0.5)] animate-pulse-glow", label: "Speaking..." },
};

const sizes = {
  sm: "w-1.5 h-1.5",
  md: "w-2.5 h-2.5",
  lg: "w-3.5 h-3.5",
};

export function StatusIndicator({
  state,
  label,
  showLabel = true,
  size = "md",
}: StatusIndicatorProps) {
  const config = stateConfig[state];

  return (
    <div className="flex items-center gap-2">
      <span
        className={cn(
          "rounded-full transition-all duration-500",
          sizes[size],
          config.color
        )}
      />
      {showLabel && (
        <span className="text-xs font-medium text-gray-500">
          {label || config.label}
        </span>
      )}
    </div>
  );
}

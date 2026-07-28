import React from "react";
import { cn } from "@/lib/utils";

interface WaveformVisualizerProps {
  isActive: boolean;
  audioLevel?: number;
  barCount?: number;
  className?: string;
}

export function WaveformVisualizer({
  isActive,
  audioLevel = 0,
  barCount = 32,
  className,
}: WaveformVisualizerProps) {
  return (
    <div
      className={cn(
        "flex items-center justify-center gap-[3px] h-16",
        className
      )}
    >
      {Array.from({ length: barCount }).map((_, i) => {
        // Create a waveform pattern based on audio level
        const center = barCount / 2;
        const distance = Math.abs(i - center);
        const maxDistance = barCount / 2;
        const baseHeight = isActive ? 4 + (1 - distance / maxDistance) * 32 : 2;
        const height = isActive
          ? Math.max(2, baseHeight * (0.5 + audioLevel * 0.5))
          : 2;

        return (
          <div
            key={i}
            className={cn(
              "w-1 rounded-full transition-all duration-150",
              isActive
                ? "bg-gradient-to-t from-accent-blue to-accent-purple"
                : "bg-white/10"
            )}
            style={{
              height: `${height}px`,
              animation: isActive
                ? `waveform 1.5s ease-in-out infinite`
                : "none",
              animationDelay: `${i * 0.05}s`,
            }}
          />
        );
      })}
    </div>
  );
}

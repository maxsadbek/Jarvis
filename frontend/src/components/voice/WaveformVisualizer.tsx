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
  barCount = 48,
  className,
}: WaveformVisualizerProps) {
  return (
    <div
      className={cn(
        "relative flex items-center justify-center gap-[2px] h-20 overflow-hidden",
        className
      )}
    >
      {/* Holographic glow behind the waveform */}
      {isActive && (
        <div className="absolute inset-0 bg-gradient-to-r from-accent-blue/5 via-accent-purple/5 to-accent-cyan/5 blur-xl" />
      )}

      {/* Bars */}
      {Array.from({ length: barCount }).map((_, i) => {
        const center = barCount / 2;
        const distance = Math.abs(i - center);
        const maxDistance = barCount / 2;

        // Create a dynamic waveform pattern
        const normalizedDistance = 1 - distance / maxDistance;
        const baseHeight = isActive
          ? 4 + normalizedDistance * 48
          : 2 + normalizedDistance * 4;

        // Add some randomness for organic feel
        const organicOffset = Math.sin((i / barCount) * Math.PI * 4) * 0.15;
        const height = isActive
          ? Math.max(
              3,
              baseHeight * (0.4 + audioLevel * 0.6 + organicOffset * audioLevel)
            )
          : Math.max(2, baseHeight * 0.3);

        // Gradient based on position (left to right: blue -> purple -> cyan)
        const gradientPosition = i / barCount;
        const blueOpacity = Math.max(0, 1 - gradientPosition * 2);
        const purpleOpacity = 1 - Math.abs(gradientPosition - 0.5) * 2;
        const cyanOpacity = Math.max(0, (gradientPosition - 0.5) * 2);

        const barColor = isActive
          ? `rgba(0, 212, 255, ${blueOpacity * (0.6 + audioLevel * 0.4)})`
          : "rgba(255, 255, 255, 0.06)";

        const glowColor = isActive
          ? `drop-shadow(0 0 ${3 + audioLevel * 6}px rgba(0, 212, 255, ${0.2 + audioLevel * 0.2}))`
          : "none";

        return (
          <div
            key={i}
            className={cn(
              "w-[3px] rounded-full transition-all duration-[80ms]",
              isActive && "bg-gradient-to-t"
            )}
            style={{
              height: `${height}px`,
              background: isActive
                ? `linear-gradient(to top,
                    rgba(0, 212, 255, ${blueOpacity * (0.3 + audioLevel * 0.3)}),
                    rgba(139, 92, 246, ${purpleOpacity * (0.4 + audioLevel * 0.3)}),
                    rgba(34, 211, 238, ${cyanOpacity * (0.3 + audioLevel * 0.3)}))`
                : "linear-gradient(to top, rgba(255,255,255,0.04), rgba(255,255,255,0.08))",
              filter: glowColor,
              animation: isActive
                ? `waveform-bounce 0.8s ease-in-out infinite`
                : "none",
              animationDelay: `${i * 0.03}s`,
            }}
          />
        );
      })}

      {/* Subtle bottom glow line */}
      <div
        className={cn(
          "absolute bottom-0 left-0 right-0 h-px transition-opacity duration-500",
          isActive
            ? "bg-gradient-to-r from-accent-blue/30 via-accent-purple/30 to-accent-cyan/30"
            : "bg-white/5"
        )}
      />
    </div>
  );
}

import React from "react";
import { cn } from "@/lib/utils";

interface TypingAnimationProps {
  className?: string;
}

export function TypingAnimation({ className }: TypingAnimationProps) {
  return (
    <div className={cn("flex items-center gap-1.5", className)}>
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="w-2 h-2 rounded-full bg-jarvis-400"
          style={{
            animation: `waveform 1.5s ease-in-out infinite`,
            animationDelay: `${i * 0.2}s`,
          }}
        />
      ))}
    </div>
  );
}

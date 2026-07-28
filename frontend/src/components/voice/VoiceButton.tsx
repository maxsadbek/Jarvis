import React from "react";
import { cn } from "@/lib/utils";
import { Mic, MicOff, Sparkles } from "lucide-react";
import type { ConnectionState } from "@/types";

interface VoiceButtonProps {
  isListening: boolean;
  onToggle: () => void;
  disabled?: boolean;
  connectionState: ConnectionState;
  audioLevel?: number;
}

export function VoiceButton({
  isListening,
  onToggle,
  disabled = false,
  connectionState,
  audioLevel = 0,
}: VoiceButtonProps) {
  const isProcessing =
    connectionState === "processing" || connectionState === "speaking";

  return (
    <button
      onClick={onToggle}
      disabled={disabled || isProcessing}
      className={cn(
        "group relative w-20 h-20 rounded-full flex items-center justify-center transition-all duration-500",
        "focus:outline-none focus:ring-2 focus:ring-jarvis-400/50 focus:ring-offset-2 focus:ring-offset-[#0a0a1a]",
        isListening
          ? "shadow-[0_0_30px_rgba(0,212,255,0.3)]"
          : "hover:shadow-[0_0_20px_rgba(139,92,246,0.15)]",
        disabled && "opacity-50 cursor-not-allowed",
        isProcessing && "cursor-wait"
      )}
      title={isListening ? "Stop listening" : "Start voice input"}
    >
      {/* Holographic ring */}
      <span
        className={cn(
          "absolute inset-0 rounded-full transition-all duration-700",
          isListening
            ? "bg-gradient-to-r from-accent-blue via-accent-purple to-accent-cyan animate-spin-slow"
            : "bg-gradient-to-r from-white/10 via-white/5 to-white/10 group-hover:from-white/20 group-hover:via-white/10 group-hover:to-white/20"
        )}
        style={{
          mask: "radial-gradient(transparent 62%, black 65%)",
          WebkitMask: "radial-gradient(transparent 62%, black 65%)",
        }}
      />

      {/* Pulse rings when listening */}
      {isListening && (
        <>
          <span className="absolute inset-0 rounded-full animate-ping bg-accent-blue/30" />
          <span
            className="absolute inset-0 rounded-full animate-ping bg-accent-purple/20"
            style={{ animationDelay: "0.5s" }}
          />
          <span
            className="absolute inset-0 rounded-full animate-ping bg-accent-cyan/15"
            style={{ animationDelay: "1s" }}
          />
        </>
      )}

      {/* Glass core */}
      <span
        className={cn(
          "absolute inset-2 rounded-full transition-all duration-500",
          isListening
            ? "bg-gradient-to-br from-accent-blue/20 via-accent-purple/10 to-accent-cyan/20 backdrop-blur-sm border border-white/10"
            : "bg-white/5 backdrop-blur-sm border border-white/10 group-hover:bg-white/10 group-hover:border-white/20"
        )}
      />

      {/* Scan line overlay */}
      <span
        className={cn(
          "absolute inset-2 rounded-full overflow-hidden opacity-0 transition-opacity duration-500",
          isListening && "opacity-30"
        )}
      >
        <span className="absolute inset-0 bg-gradient-to-b from-transparent via-accent-blue/20 to-transparent animate-scan" />
      </span>

      {/* Audio level visualization ring */}
      {isListening && (
        <svg
          className="absolute inset-0 w-full h-full -rotate-90"
          viewBox="0 0 64 64"
        >
          {/* Background ring */}
          <circle
            cx="32"
            cy="32"
            r="29"
            fill="none"
            stroke="rgba(0, 212, 255, 0.1)"
            strokeWidth="2"
          />
          {/* Active ring */}
          <circle
            cx="32"
            cy="32"
            r="29"
            fill="none"
            stroke="url(#voiceGradient)"
            strokeWidth="2"
            strokeDasharray={`${audioLevel * 182} 182`}
            strokeLinecap="round"
            className="transition-all duration-75"
            style={{
              filter: `drop-shadow(0 0 ${4 + audioLevel * 8}px rgba(0, 212, 255, ${0.3 + audioLevel * 0.5}))`,
            }}
          />
          {/* Gradient definition */}
          <defs>
            <linearGradient id="voiceGradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#00d4ff" />
              <stop offset="50%" stopColor="#8b5cf6" />
              <stop offset="100%" stopColor="#22d3ee" />
            </linearGradient>
          </defs>
        </svg>
      )}

      {/* Holographic shimmer on hover */}
      {!isListening && (
        <span className="absolute inset-0 rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-500 overflow-hidden">
          <span className="absolute inset-0 bg-gradient-to-br from-accent-blue/10 via-transparent to-accent-purple/10 animate-shimmer" />
        </span>
      )}

      {/* Icon */}
      <div
        className={cn(
          "relative z-10 transition-all duration-500",
          isListening && "scale-110"
        )}
      >
        {isListening ? (
          <Mic className="w-7 h-7 text-white drop-shadow-[0_0_8px_rgba(0,212,255,0.8)]" />
        ) : (
          <MicOff className="w-6 h-6 text-gray-400 group-hover:text-gray-200 transition-colors" />
        )}
      </div>

      {/* Small sparkle icon when listening */}
      {isListening && (
        <Sparkles className="absolute -top-1 -right-1 w-4 h-4 text-accent-cyan animate-pulse" />
      )}
    </button>
  );
}

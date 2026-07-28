import React from "react";
import { cn } from "@/lib/utils";
import { Mic, MicOff } from "lucide-react";
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
  const isProcessing = connectionState === "processing" || connectionState === "speaking";

  return (
    <button
      onClick={onToggle}
      disabled={disabled || isProcessing}
      className={cn(
        "relative w-16 h-16 rounded-full flex items-center justify-center transition-all duration-300",
        "focus:outline-none focus:ring-2 focus:ring-jarvis-500/50 focus:ring-offset-2 focus:ring-offset-[#0a0a1a]",
        isListening
          ? "bg-gradient-to-r from-accent-blue to-accent-purple shadow-lg shadow-accent-blue/30"
          : "bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20",
        disabled && "opacity-50 cursor-not-allowed",
        isProcessing && "cursor-wait"
      )}
      title={isListening ? "Stop listening" : "Start voice input"}
    >
      {/* Pulse rings when listening */}
      {isListening && (
        <>
          <span className="absolute inset-0 rounded-full animate-ping bg-accent-blue/20" />
          <span
            className="absolute inset-0 rounded-full animate-ping bg-accent-purple/20"
            style={{ animationDelay: "0.5s" }}
          />
        </>
      )}

      {/* Audio level visualization ring */}
      {isListening && (
        <svg
          className="absolute inset-0 w-full h-full -rotate-90"
          viewBox="0 0 64 64"
        >
          <circle
            cx="32"
            cy="32"
            r="29"
            fill="none"
            stroke="rgba(0, 212, 255, 0.2)"
            strokeWidth="2"
          />
          <circle
            cx="32"
            cy="32"
            r="29"
            fill="none"
            stroke="rgba(0, 212, 255, 0.8)"
            strokeWidth="2"
            strokeDasharray={`${audioLevel * 182} 182`}
            strokeLinecap="round"
            className="transition-all duration-100"
          />
        </svg>
      )}

      {/* Icon */}
      <div className={cn(
        "relative z-10 transition-transform duration-300",
        isListening && "scale-110"
      )}>
        {isListening ? (
          <Mic className="w-6 h-6 text-white" />
        ) : (
          <MicOff className="w-5 h-5 text-gray-400" />
        )}
      </div>
    </button>
  );
}

import React from "react";
import { cn, formatTime } from "@/lib/utils";
import { User, Bot, AlertCircle, Code, Sparkles } from "lucide-react";
import type { Message } from "@/types";

interface ChatMessageProps {
  message: Message;
  isLatest?: boolean;
}

export function ChatMessage({ message, isLatest = false }: ChatMessageProps) {
  const isUser = message.role === "user";
  const isError = message.type === "error";
  const isCode = message.type === "code";

  return (
    <div
      className={cn(
        "flex gap-3 w-full",
        isUser ? "flex-row-reverse" : "flex-row",
        isLatest ? "animate-fade-in-up" : "animate-fade-in"
      )}
    >
      {/* Holographic avatar */}
      <div className="flex-shrink-0 relative">
        {isUser ? (
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-jarvis-600 to-jarvis-800 flex items-center justify-center shadow-lg shadow-jarvis-500/10">
            <User className="w-4 h-4 text-white" />
          </div>
        ) : isError ? (
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-red-600 to-rose-700 flex items-center justify-center">
            <AlertCircle className="w-4 h-4 text-white" />
          </div>
        ) : (
          <div className="relative">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-neon-blue via-jarvis-500 to-neon-purple flex items-center justify-center shadow-lg shadow-jarvis-500/15">
              <Bot className="w-4 h-4 text-white" />
            </div>
            {/* Glow ring on latest */}
            {isLatest && (
              <div className="absolute -inset-1 rounded-xl bg-gradient-to-br from-neon-blue/20 via-jarvis-500/20 to-neon-purple/20 blur-sm -z-10 animate-pulse-glow" />
            )}
          </div>
        )}
      </div>

      {/* Message content */}
      <div className={cn("max-w-[75%] space-y-1")}>
        <div
          className={cn(
            "rounded-2xl px-4 py-3",
            isUser
              ? "bg-gradient-to-r from-jarvis-600/90 to-jarvis-500/90 text-white rounded-tr-[4px] shadow-md shadow-jarvis-500/10"
              : isError
              ? "bg-red-500/10 border border-red-500/20 text-red-200 rounded-tl-[4px]"
              : "glass-panel rounded-tl-[4px]"
          )}
        >
          {/* Role label */}
          <div className={cn(
            "flex items-center gap-1.5 mb-1.5",
            isUser && "flex-row-reverse"
          )}>
            <span className={cn(
              "text-[10px] font-medium uppercase tracking-wider",
              isUser ? "text-white/60" : "text-gray-600"
            )}>
              {isUser ? "You" : "JARVIS"}
            </span>
            {!isUser && !isError && (
              <Sparkles className="w-2.5 h-2.5 text-neon-blue" />
            )}
          </div>

          {/* Code indicator */}
          {isCode && (
            <div className="flex items-center gap-1.5 text-[10px] text-gray-500 mb-2 pb-2 border-b border-white/[0.06]">
              <Code className="w-3 h-3" />
              <span>Code</span>
            </div>
          )}

          {/* Message text */}
          <p className={cn(
            "text-sm leading-relaxed whitespace-pre-wrap",
            isUser ? "text-white" : "text-gray-200"
          )}>
            {message.content}
          </p>
        </div>

        {/* Timestamp */}
        <p className={cn(
          "text-[10px] text-gray-700 px-1",
          isUser && "text-right"
        )}>
          {formatTime(message.timestamp)}
        </p>
      </div>
    </div>
  );
}

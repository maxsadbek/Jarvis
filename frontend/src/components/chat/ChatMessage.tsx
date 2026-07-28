import React from "react";
import { cn } from "@/lib/utils";
import { formatTime } from "@/lib/utils";
import { User, Bot, AlertCircle, Code } from "lucide-react";
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
        "flex gap-3 w-full animate-slide-up",
        isUser ? "flex-row-reverse" : "flex-row",
        isLatest && "opacity-100"
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center",
          isUser
            ? "bg-gradient-to-br from-jarvis-500 to-jarvis-700"
            : isError
            ? "bg-gradient-to-br from-red-500 to-rose-600"
            : "bg-gradient-to-br from-accent-blue to-accent-purple"
        )}
      >
        {isUser ? (
          <User className="w-4 h-4 text-white" />
        ) : isError ? (
          <AlertCircle className="w-4 h-4 text-white" />
        ) : (
          <Bot className="w-4 h-4 text-white" />
        )}
      </div>

      {/* Message bubble */}
      <div
        className={cn(
          "max-w-[75%] space-y-1",
          isUser && "items-end"
        )}
      >
        <div
          className={cn(
            "rounded-2xl px-4 py-3",
            isUser
              ? "bg-gradient-to-r from-jarvis-600 to-jarvis-500 text-white rounded-tr-sm"
              : isError
              ? "bg-red-500/10 border border-red-500/20 text-red-200 rounded-tl-sm"
              : "glass-card rounded-tl-sm"
          )}
        >
          {/* Code indicator */}
          {isCode && (
            <div className="flex items-center gap-1.5 text-xs text-gray-500 mb-2 pb-2 border-b border-white/5">
              <Code className="w-3 h-3" />
              <span>Code</span>
            </div>
          )}

          <p className={cn(
            "text-sm leading-relaxed whitespace-pre-wrap",
            isUser ? "text-white" : "text-gray-200"
          )}>
            {message.content}
          </p>
        </div>

        {/* Timestamp */}
        <p className={cn(
          "text-[10px] text-gray-600 px-1",
          isUser && "text-right"
        )}>
          {formatTime(message.timestamp)}
        </p>
      </div>
    </div>
  );
}

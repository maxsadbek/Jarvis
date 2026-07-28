import React, { useRef, useEffect } from "react";
import { useChatStore } from "@/stores/chatStore";
import { ChatMessage } from "./ChatMessage";
import { TypingAnimation } from "@/components/ui/TypingAnimation";
import { Bot, Sparkles, MessageSquare, Globe, Code, FileText } from "lucide-react";

export function ChatContainer() {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const conversations = useChatStore((s) => s.conversations);
  const activeConversationId = useChatStore((s) => s.activeConversationId);
  const isStreaming = useChatStore((s) => s.isStreaming);

  const activeConversation = activeConversationId
    ? conversations.get(activeConversationId)
    : undefined;

  const messages = activeConversation?.messages || [];

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isStreaming]);

  // Holographic welcome screen
  if (messages.length === 0) {
    const suggestions = [
      { icon: Globe, text: "Search the web for...", color: "text-neon-blue" },
      { icon: Code, text: "Help me write code for...", color: "text-neon-purple" },
      { icon: FileText, text: "Analyze this file...", color: "text-neon-cyan" },
      { icon: Sparkles, text: "What can you do?", color: "text-neon-amber" },
    ];

    return (
      <div className="flex-1 flex items-center justify-center px-6">
        <div className="text-center space-y-6 max-w-lg animate-fade-in-up">
          {/* Holographic avatar */}
          <div className="relative inline-flex">
            <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-jarvis-500 via-neon-blue to-neon-purple flex items-center justify-center shadow-2xl shadow-jarvis-500/20 relative">
              <Bot className="w-10 h-10 text-white" />
              {/* Glow ring */}
              <div className="absolute -inset-1 rounded-2xl bg-gradient-to-br from-jarvis-500/20 via-neon-blue/20 to-neon-purple/20 blur-md -z-10" />
            </div>
            {/* Animated ring */}
            <div className="absolute -inset-2 rounded-2xl border border-jarvis-500/20 animate-pulse-slow" />
            <div className="absolute -inset-3 rounded-2xl border border-neon-blue/10 animate-pulse-slow" style={{ animationDelay: "1s" }} />
          </div>

          <div className="space-y-2">
            <h2 className="text-2xl font-bold text-gradient-primary">
              Good to see you again
            </h2>
            <p className="text-sm text-gray-500 leading-relaxed max-w-sm mx-auto">
              I'm your AI companion. I can help with coding, research, file management,
              and automate your computer. Just ask.
            </p>
          </div>

          {/* Suggestion chips */}
          <div className="grid grid-cols-2 gap-2 max-w-sm mx-auto">
            {suggestions.map((s) => {
              const Icon = s.icon;
              return (
                <button
                  key={s.text}
                  className="group flex items-center gap-2 px-3 py-2.5 rounded-xl text-xs bg-white/[0.02] border border-white/[0.06] hover:bg-white/[0.05] hover:border-white/10 transition-all duration-200 text-left"
                >
                  <Icon className={cn("w-3.5 h-3.5 flex-shrink-0", s.color)} />
                  <span className="text-gray-500 group-hover:text-gray-300 transition-colors truncate">
                    {s.text}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Status */}
          <div className="flex items-center justify-center gap-2 text-[10px] text-gray-700">
            <span className="w-1 h-1 rounded-full bg-neon-green" />
            <span>AI Engine Ready</span>
            <span className="text-gray-800">·</span>
            <span>Voice Enabled</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4 scrollbar-hidden">
      {messages.map((message, index) => (
        <ChatMessage
          key={message.id}
          message={message}
          isLatest={index === messages.length - 1}
        />
      ))}

      {/* Typing indicator - holographic style */}
      {isStreaming && (
        <div className="flex items-center gap-3 animate-fade-in">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-neon-blue/20 to-neon-purple/20 border border-white/[0.06] flex items-center justify-center">
            <Bot className="w-3.5 h-3.5 text-neon-blue" />
          </div>
          <div className="glass-panel px-4 py-3 rounded-tl-[4px]">
            <div className="flex items-center gap-2.5">
              <TypingAnimation />
              <span className="text-xs text-gray-600 font-mono">Thinking...</span>
            </div>
          </div>
        </div>
      )}

      <div ref={messagesEndRef} />
    </div>
  );
}

import { cn } from "@/lib/utils";

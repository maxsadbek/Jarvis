import React, { useRef, useEffect } from "react";
import { useChatStore } from "@/stores/chatStore";
import { ChatMessage } from "./ChatMessage";
import { TypingAnimation } from "@/components/ui/TypingAnimation";
import { MessageSquare, Bot } from "lucide-react";

export function ChatContainer() {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const conversations = useChatStore((s) => s.conversations);
  const activeConversationId = useChatStore((s) => s.activeConversationId);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const connectionState = useChatStore((s) => s.connectionState);

  const activeConversation = activeConversationId
    ? conversations.get(activeConversationId)
    : undefined;

  const messages = activeConversation?.messages || [];

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isStreaming]);

  // Welcome state when no messages
  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center space-y-4 max-w-md">
          <div className="w-16 h-16 rounded-full bg-gradient-to-br from-jarvis-500 to-accent-blue mx-auto flex items-center justify-center shadow-lg shadow-jarvis-500/20">
            <Bot className="w-8 h-8 text-white" />
          </div>
          <h2 className="text-xl font-semibold text-gradient">
            How can I help you today?
          </h2>
          <p className="text-sm text-gray-500">
            I'm JARVIS, your personal AI assistant. I can help you with coding,
            research, file management, and more. Try asking me anything!
          </p>
          <div className="grid grid-cols-2 gap-2 mt-6">
            {[
              "What can you do?",
              "Search the web for AI news",
              "Help me write code",
              "Analyze this file...",
            ].map((suggestion) => (
              <button
                key={suggestion}
                className="text-xs text-gray-400 bg-white/[0.03] border border-white/[0.06] rounded-xl px-3 py-2.5 hover:bg-white/[0.06] hover:border-white/10 transition-all duration-200 text-left"
              >
                {suggestion}
              </button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
      {messages.map((message, index) => (
        <ChatMessage
          key={message.id}
          message={message}
          isLatest={index === messages.length - 1}
        />
      ))}

      {/* Typing indicator */}
      {isStreaming && (
        <div className="flex items-center gap-2 text-sm text-gray-500 ml-2">
          <TypingAnimation />
          <span className="text-xs">JARVIS is thinking...</span>
        </div>
      )}

      {/* Invisible div for scrolling */}
      <div ref={messagesEndRef} />
    </div>
  );
}

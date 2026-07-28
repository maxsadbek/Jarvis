import React from "react";
import { StatusIndicator } from "@/components/ui/StatusIndicator";
import { Button } from "@/components/ui/Button";
import { MessageSquarePlus, Trash2, Bot } from "lucide-react";
import { useChatStore } from "@/stores/chatStore";
import type { ConnectionState } from "@/types";

interface ChatHeaderProps {
  connectionState: ConnectionState;
  onNewConversation: () => void;
  onClearConversation: () => void;
}

export function ChatHeader({
  connectionState,
  onNewConversation,
  onClearConversation,
}: ChatHeaderProps) {
  const activeConversationId = useChatStore((s) => s.activeConversationId);
  const conversations = useChatStore((s) => s.conversations);
  const activeConversation = activeConversationId
    ? conversations.get(activeConversationId)
    : undefined;

  return (
    <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/[0.04] glass-panel rounded-none">
      {/* Left: Status + Info */}
      <div className="flex items-center gap-3">
        <StatusIndicator state={connectionState} size="sm" showLabel={false} />
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-neon-blue/20 to-neon-purple/20 border border-white/[0.06] flex items-center justify-center">
            <Bot className="w-3.5 h-3.5 text-neon-blue" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-gray-200">
              {activeConversation?.title || "New Conversation"}
            </h2>
            <p className="text-[10px] text-gray-600">
              {activeConversation?.messages.length
                ? `${activeConversation.messages.length} messages`
                : "Start a new conversation"}
            </p>
          </div>
        </div>
      </div>

      {/* Right: Actions */}
      <div className="flex items-center gap-1">
        <button
          onClick={onNewConversation}
          className="p-2 rounded-lg hover:bg-white/[0.05] text-gray-500 hover:text-gray-300 transition-all duration-200"
          title="New conversation"
        >
          <MessageSquarePlus className="w-4 h-4" />
        </button>
        <button
          onClick={onClearConversation}
          className="p-2 rounded-lg hover:bg-white/[0.05] text-gray-600 hover:text-red-400 transition-all duration-200"
          title="Clear conversation"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}

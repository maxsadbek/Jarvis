import React from "react";
import { StatusIndicator } from "@/components/ui/StatusIndicator";
import { Button } from "@/components/ui/Button";
import { MessageSquarePlus, Trash2 } from "lucide-react";
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
    <div className="flex items-center justify-between px-4 py-3 border-b border-white/5 glass-card rounded-none">
      {/* Left: Status */}
      <div className="flex items-center gap-3">
        <StatusIndicator state={connectionState} size="sm" />
        <div>
          <h2 className="text-sm font-semibold text-gray-200">
            {activeConversation?.title || "Conversation"}
          </h2>
          <p className="text-xs text-gray-500">
            {activeConversation?.messages.length || 0} messages
          </p>
        </div>
      </div>

      {/* Right: Actions */}
      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="sm"
          onClick={onNewConversation}
          title="New conversation"
        >
          <MessageSquarePlus className="w-4 h-4" />
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={onClearConversation}
          title="Clear conversation"
        >
          <Trash2 className="w-4 h-4 text-red-400" />
        </Button>
      </div>
    </div>
  );
}

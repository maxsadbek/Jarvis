import React from "react";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/utils";
import { MessageSquare, Clock, ArrowRight } from "lucide-react";
import { useChatStore } from "@/stores/chatStore";
import { formatTime } from "@/lib/utils";
import type { Conversation } from "@/types";

interface RecentConversationsProps {
  onSelectConversation: (id: string) => void;
  className?: string;
}

export function RecentConversations({
  onSelectConversation,
  className,
}: RecentConversationsProps) {
  const conversations = useChatStore((s) => s.conversations);
  const conversationList = Array.from(conversations.values())
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
    .slice(0, 5);

  return (
    <Card className={cn("space-y-3", className)}>
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-200">Recent Conversations</h3>
        <span className="text-[10px] text-gray-600">
          {conversations.size} total
        </span>
      </div>

      {conversationList.length === 0 ? (
        <div className="text-center py-6">
          <MessageSquare className="w-8 h-8 text-gray-600 mx-auto mb-2" />
          <p className="text-xs text-gray-500">No conversations yet</p>
          <p className="text-[10px] text-gray-600 mt-1">
            Start chatting with JARVIS!
          </p>
        </div>
      ) : (
        <div className="space-y-1">
          {conversationList.map((conv) => (
            <button
              key={conv.id}
              onClick={() => onSelectConversation(conv.id)}
              className="w-full flex items-center gap-3 p-2.5 rounded-xl hover:bg-white/[0.03] transition-colors group text-left"
            >
              <div className="w-8 h-8 rounded-lg bg-jarvis-500/10 flex items-center justify-center flex-shrink-0">
                <MessageSquare className="w-4 h-4 text-jarvis-400" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-gray-300 truncate">
                  {conv.title}
                </p>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <Clock className="w-3 h-3 text-gray-600" />
                  <span className="text-[10px] text-gray-600">
                    {formatTime(conv.updated_at)}
                  </span>
                  <span className="text-[10px] text-gray-600">
                    · {conv.messages.length} messages
                  </span>
                </div>
              </div>
              <ArrowRight className="w-4 h-4 text-gray-600 opacity-0 group-hover:opacity-100 transition-opacity" />
            </button>
          ))}
        </div>
      )}
    </Card>
  );
}

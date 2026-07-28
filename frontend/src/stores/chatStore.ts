import { create } from "zustand";
import type { ChatStore, Conversation, Message, ConnectionState } from "@/types";
import { generateId } from "@/lib/utils";

export const useChatStore = create<ChatStore>((set, get) => ({
  conversations: new Map(),
  activeConversationId: null,
  isStreaming: false,
  connectionState: "disconnected",

  addMessage: (conversationId: string, message: Message) => {
    set((state) => {
      const conversations = new Map(state.conversations);
      const conversation = conversations.get(conversationId);

      if (conversation) {
        conversations.set(conversationId, {
          ...conversation,
          messages: [...conversation.messages, message],
          updated_at: new Date().toISOString(),
        });
      }

      return { conversations };
    });
  },

  setActiveConversation: (id: string) => {
    set({ activeConversationId: id });
  },

  createConversation: () => {
    const id = generateId();
    const conversation: Conversation = {
      id,
      title: "New Conversation",
      messages: [],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    set((state) => {
      const conversations = new Map(state.conversations);
      conversations.set(id, conversation);
      return { conversations, activeConversationId: id };
    });

    return id;
  },

  setConnectionState: (state: ConnectionState) => {
    set({ connectionState: state });
  },

  setIsStreaming: (streaming: boolean) => {
    set({ isStreaming: streaming });
  },
}));

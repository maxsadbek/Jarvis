import React, { useCallback, useEffect } from "react";
import { ChatHeader } from "@/components/chat/ChatHeader";
import { ChatContainer } from "@/components/chat/ChatContainer";
import { ChatInput } from "@/components/chat/ChatInput";
import { WaveformVisualizer } from "@/components/voice/WaveformVisualizer";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useVoice } from "@/hooks/useVoice";
import { useChatStore } from "@/stores/chatStore";

export function ChatPage() {
  const connectionState = useChatStore((s) => s.connectionState);
  const activeConversationId = useChatStore((s) => s.activeConversationId);
  const createConversation = useChatStore((s) => s.createConversation);
  const setActiveConversation = useChatStore((s) => s.setActiveConversation);

  const { sendChat, sendAudio, isConnected } = useWebSocket();
  const {
    isListening,
    startListening,
    stopListening,
    audioLevel,
    error: voiceError,
  } = useVoice(sendAudio);

  // Auto-create conversation
  useEffect(() => {
    if (!activeConversationId) {
      const id = createConversation();
      setActiveConversation(id);
    }
  }, [activeConversationId, createConversation, setActiveConversation]);

  const handleSendMessage = useCallback(
    (text: string) => {
      if (isConnected && text.trim()) {
        sendChat(text.trim());
      }
    },
    [isConnected, sendChat]
  );

  const handleVoiceToggle = useCallback(() => {
    if (isListening) {
      stopListening();
    } else {
      voiceError && console.warn("Voice error:", voiceError);
      startListening();
    }
  }, [isListening, startListening, stopListening, voiceError]);

  const handleNewConversation = useCallback(() => {
    const id = createConversation();
    setActiveConversation(id);
  }, [createConversation, setActiveConversation]);

  const handleClearConversation = useCallback(() => {
    const id = createConversation();
    setActiveConversation(id);
  }, [createConversation, setActiveConversation]);

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <ChatHeader
        connectionState={connectionState}
        onNewConversation={handleNewConversation}
        onClearConversation={handleClearConversation}
      />

      {/* Waveform visualizer when listening */}
      {isListening && (
        <div className="px-4 py-2">
          <WaveformVisualizer
            isActive={true}
            audioLevel={audioLevel}
            barCount={48}
            className="h-12"
          />
        </div>
      )}

      {/* Chat messages */}
      <ChatContainer />

      {/* Input area */}
      <div className="px-4 pb-4 pt-2">
        <ChatInput
          onSend={handleSendMessage}
          onVoiceToggle={handleVoiceToggle}
          isListening={isListening}
          connectionState={connectionState}
          audioLevel={audioLevel}
          disabled={!isConnected}
        />
      </div>

      {/* Voice error toast */}
      {voiceError && (
        <div className="fixed bottom-24 left-1/2 -translate-x-1/2 glass-card px-4 py-2 z-50">
          <p className="text-xs text-red-400">{voiceError}</p>
        </div>
      )}
    </div>
  );
}

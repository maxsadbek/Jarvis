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
    <div className="flex flex-col h-full relative">
      {/* Header with scan line */}
      <div className="scan-line">
        <ChatHeader
          connectionState={connectionState}
          onNewConversation={handleNewConversation}
          onClearConversation={handleClearConversation}
        />
      </div>

      {/* Waveform visualizer - holographic when listening */}
      {isListening && (
        <div className="px-4 py-3 animate-fade-in-down">
          <div className="glass-panel px-4 py-3">
            <div className="flex items-center gap-2 mb-2">
              <span className="w-1.5 h-1.5 rounded-full bg-neon-blue shadow-[0_0_8px_rgba(0,212,255,0.6)] animate-pulse-glow" />
              <span className="text-[10px] text-neon-blue uppercase tracking-widest font-medium">
                Listening
              </span>
            </div>
            <WaveformVisualizer
              isActive={true}
              audioLevel={audioLevel}
              barCount={64}
              className="h-14"
            />
          </div>
        </div>
      )}

      {/* Chat messages */}
      <ChatContainer />

      {/* Input area */}
      <div className="px-4 pb-4 pt-2 animate-fade-in-up">
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
        <div className="fixed bottom-28 left-1/2 -translate-x-1/2 z-50 animate-fade-in-up">
          <div className="glass-panel-strong px-4 py-2.5 border border-red-500/20">
            <div className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-neon-rose" />
              <p className="text-xs text-red-300">{voiceError}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

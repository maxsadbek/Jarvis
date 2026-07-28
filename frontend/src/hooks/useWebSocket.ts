import { useCallback, useEffect, useRef, useState } from "react";
import { useChatStore } from "@/stores/chatStore";
import { useSettingsStore } from "@/stores/settingsStore";
import type { ConnectionState, Message, WSMessage } from "@/types";
import { generateId } from "@/lib/utils";

type MessageHandler = (data: WSMessage) => void;

interface UseWebSocketReturn {
  connect: () => void;
  disconnect: () => void;
  sendChat: (text: string) => void;
  sendAudio: (audioData: ArrayBuffer) => void;
  sendCommand: (action: string, params?: Record<string, unknown>) => void;
  isConnected: boolean;
  onMessage: (handler: MessageHandler) => void;
}

export function useWebSocket(): UseWebSocketReturn {
  const wsRef = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const messageHandlersRef = useRef<Set<MessageHandler>>(new Set());
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const reconnectAttemptsRef = useRef(0);
  const maxReconnectAttempts = 5;

  const setConnectionState = useChatStore((s) => s.setConnectionState);
  const addMessage = useChatStore((s) => s.addMessage);
  const activeConversationId = useChatStore((s) => s.activeConversationId);
  const setIsStreaming = useChatStore((s) => s.setIsStreaming);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.hostname || "localhost";
    const port = "8000";
    const url = `${protocol}//${host}:${port}/ws?client_id=web_${generateId()}`;

    setConnectionState("connecting");

    const ws = new WebSocket(url);

    ws.onopen = () => {
      console.log("WebSocket connected");
      setIsConnected(true);
      setConnectionState("connected");
      reconnectAttemptsRef.current = 0;
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as WSMessage;

        // Handle different message types
        switch (data.type) {
          case "state":
            const state = data.data.state as ConnectionState;
            setConnectionState(state);
            break;

          case "response":
            if (activeConversationId) {
              const message: Message = {
                id: generateId(),
                role: "assistant",
                type: (data.data.type as string) as Message["type"] || "text",
                content: data.data.text as string,
                timestamp: data.timestamp,
                metadata: data.data as Record<string, unknown>,
              };
              addMessage(activeConversationId, message);
            }
            setIsStreaming(false);
            break;

          case "error":
            console.error("Server error:", data.data.message);
            setIsStreaming(false);
            break;

          case "audio":
            // Audio chunks are handled by the audio element
            break;
        }

        // Notify all message handlers
        messageHandlersRef.current.forEach((handler) => handler(data));
      } catch (e) {
        console.error("Failed to parse WebSocket message:", e);
      }
    };

    ws.onerror = (error) => {
      console.error("WebSocket error:", error);
    };

    ws.onclose = () => {
      setIsConnected(false);
      setConnectionState("disconnected");
      wsRef.current = null;

      // Auto-reconnect
      if (reconnectAttemptsRef.current < maxReconnectAttempts) {
        const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 10000);
        reconnectTimeoutRef.current = setTimeout(() => {
          reconnectAttemptsRef.current++;
          connect();
        }, delay);
      }
    };

    wsRef.current = ws;
  }, [setConnectionState, activeConversationId, addMessage]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    wsRef.current?.close();
    wsRef.current = null;
    setIsConnected(false);
    setConnectionState("disconnected");
  }, [setConnectionState]);

  const sendChat = useCallback(
    (text: string) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        console.warn("WebSocket not connected");
        return;
      }

      // Add user message to store
      if (activeConversationId) {
        const message: Message = {
          id: generateId(),
          role: "user",
          type: "text",
          content: text,
          timestamp: new Date().toISOString(),
        };
        addMessage(activeConversationId, message);
      }

      setIsStreaming(true);

      wsRef.current.send(
        JSON.stringify({
          type: "chat",
          data: { text },
        })
      );
    },
    [activeConversationId, addMessage, setIsStreaming]
  );

  const sendAudio = useCallback(
    (audioData: ArrayBuffer) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
      wsRef.current.send(audioData);
    },
    []
  );

  const sendCommand = useCallback(
    (action: string, params?: Record<string, unknown>) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

      wsRef.current.send(
        JSON.stringify({
          type: "command",
          data: { action, params: params || {} },
        })
      );
    },
    []
  );

  const onMessage = useCallback((handler: MessageHandler) => {
    messageHandlersRef.current.add(handler);
    return () => {
      messageHandlersRef.current.delete(handler);
    };
  }, []);

  // Auto-connect on mount; cleanup on unmount
  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = undefined;
      }
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    connect,
    disconnect,
    sendChat,
    sendAudio,
    sendCommand,
    isConnected,
    onMessage,
  };
}

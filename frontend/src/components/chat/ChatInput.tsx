import React, { useRef, useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import { VoiceButton } from "@/components/voice/VoiceButton";
import { Send, Sparkles } from "lucide-react";
import type { ConnectionState } from "@/types";

interface ChatInputProps {
  onSend: (message: string) => void;
  onVoiceToggle: () => void;
  isListening: boolean;
  connectionState: ConnectionState;
  audioLevel?: number;
  disabled?: boolean;
}

export function ChatInput({
  onSend,
  onVoiceToggle,
  isListening,
  connectionState,
  audioLevel = 0,
  disabled = false,
}: ChatInputProps) {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const isProcessing = connectionState === "processing" || connectionState === "speaking";

  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = `${Math.min(textarea.scrollHeight, 120)}px`;
    }
  }, [input]);

  const handleSend = () => {
    const text = input.trim();
    if (!text || disabled || isProcessing) return;
    onSend(text);
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="glass-panel p-2 glow-neon-violet">
      {/* Gradient border accent */}
      <div className="h-px bg-gradient-to-r from-transparent via-jarvis-500/20 to-transparent mb-1 mx-1" />

      <div className="flex items-end gap-2">
        {/* Voice button */}
        <VoiceButton
          isListening={isListening}
          onToggle={onVoiceToggle}
          disabled={disabled || isProcessing}
          connectionState={connectionState}
          audioLevel={audioLevel}
        />

        {/* Text input */}
        <div className="flex-1 relative">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isListening ? "Listening..." : "Type a message or use voice..."}
            disabled={disabled || isProcessing || isListening}
            rows={1}
            className={cn(
              "w-full bg-transparent text-sm text-gray-100 placeholder-gray-600 resize-none",
              "focus:outline-none px-3 py-3 max-h-[120px]",
              "scrollbar-hidden"
            )}
          />

          {/* AI badge */}
          {!input && !isListening && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-1.5 text-[10px] text-gray-700">
              <Sparkles className="w-3 h-3 text-neon-blue" />
              <span className="font-mono">AI</span>
            </div>
          )}
        </div>

        {/* Send button */}
        <Button
          onClick={handleSend}
          disabled={!input.trim() || disabled || isProcessing}
          variant="primary"
          size="sm"
          className="rounded-xl px-3 h-10"
        >
          <Send className="w-4 h-4" />
        </Button>
      </div>
    </div>
  );
}

import React, { useState } from "react";
import { Routes, Route } from "react-router-dom";
import { Sidebar } from "@/components/Sidebar";
import { ChatPage } from "@/pages/ChatPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { HolographicBackground } from "@/components/ui/HolographicBackground";
import { useChatStore } from "@/stores/chatStore";
import { Bot, CircuitBoard } from "lucide-react";
import { cn } from "@/lib/utils";

export default function App() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const connectionState = useChatStore((s) => s.connectionState);

  const stateLabel: Record<string, string> = {
    connected: "System Online",
    listening: "Listening...",
    processing: "Processing...",
    speaking: "Speaking...",
    disconnected: "Disconnected",
    connecting: "Connecting...",
  };

  const stateColor: Record<string, string> = {
    connected: "bg-neon-green shadow-[0_0_8px_rgba(16,185,129,0.5)]",
    listening: "bg-neon-blue shadow-[0_0_8px_rgba(0,212,255,0.5)]",
    processing: "bg-neon-amber shadow-[0_0_8px_rgba(245,158,11,0.5)]",
    speaking: "bg-neon-purple shadow-[0_0_8px_rgba(139,92,246,0.5)]",
    disconnected: "bg-gray-600",
    connecting: "bg-neon-amber/50 animate-pulse-slow",
  };

  return (
    <div className="flex h-screen overflow-hidden relative">
      {/* Ambient holographic background */}
      <HolographicBackground intensity="medium" />

      {/* Sidebar */}
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden relative z-10">
        {/* Top bar - holographic style */}
        <div className="scan-line">
          <div className="flex items-center justify-between px-5 py-2.5 border-b border-white/[0.04] bg-surface/70 backdrop-blur-2xl">
            {/* Left: Brand */}
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <div className="relative">
                  <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-jarvis-500 via-neon-blue to-neon-purple flex items-center justify-center">
                    <Bot className="w-4 h-4 text-white" />
                  </div>
                  <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-neon-green shadow-[0_0_6px_rgba(16,185,129,0.6)]" />
                </div>
                <div>
                  <h1 className="text-sm font-bold text-gradient-primary">JARVIS</h1>
                  <p className="text-[9px] text-gray-600 uppercase tracking-widest">AI Assistant</p>
                </div>
              </div>
              <div className="w-px h-6 bg-white/[0.06] mx-1" />
              <div className="flex items-center gap-2 text-[10px] text-gray-500">
                <CircuitBoard className="w-3 h-3" />
                <span>v0.1.0</span>
              </div>
            </div>

            {/* Center: Status */}
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2 text-[11px]">
                <span
                  className={cn(
                    "w-1.5 h-1.5 rounded-full transition-all duration-500",
                    stateColor[connectionState] || "bg-gray-600"
                  )}
                />
                <span className="text-gray-400 font-medium">
                  {stateLabel[connectionState] || "Unknown"}
                </span>
              </div>
            </div>

            {/* Right: Status bar */}
            <div className="flex items-center gap-3 text-[10px] text-gray-600">
              <div className="flex items-center gap-1.5">
                <span className="w-1 h-1 rounded-full bg-neon-green" />
                <span>Online</span>
              </div>
            </div>
          </div>
        </div>

        {/* Page content */}
        <div className="flex-1 overflow-hidden">
          <Routes>
            <Route path="/" element={<ChatPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </div>
      </div>
    </div>
  );
}

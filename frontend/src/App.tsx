import React, { useState } from "react";
import { Routes, Route } from "react-router-dom";
import { Sidebar } from "@/components/Sidebar";
import { ChatPage } from "@/pages/ChatPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { cn } from "@/lib/utils";
import { StatusIndicator } from "@/components/ui/StatusIndicator";
import { useChatStore } from "@/stores/chatStore";

export default function App() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const connectionState = useChatStore((s) => s.connectionState);

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar with global status */}
        <div className="flex items-center justify-between px-4 py-2 border-b border-white/5 bg-[#0a0a1a]/80 backdrop-blur-xl">
          <div className="flex items-center gap-3">
            <h2 className="text-sm font-semibold text-gradient">JARVIS</h2>
            <StatusIndicator state={connectionState} size="sm" showLabel={false} />
          </div>
          <div className="flex items-center gap-2 text-[10px] text-gray-600">
            <span className="w-1.5 h-1.5 rounded-full bg-accent-green" />
            System Online
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

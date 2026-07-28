import React, { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { StatusPanel } from "@/components/dashboard/StatusPanel";
import { QuickActions } from "@/components/dashboard/QuickActions";
import { RecentConversations } from "@/components/dashboard/RecentConversations";
import { MemoryIndicator } from "@/components/ui/MemoryIndicator";
import { ToolsPanel } from "@/components/ui/ToolsPanel";
import { useChatStore } from "@/stores/chatStore";
import type { SystemStatus } from "@/types";
import {
  Bot,
  Activity,
  Zap,
  Cpu,
  Sparkles,
  Gauge,
} from "lucide-react";
import { cn } from "@/lib/utils";

export function DashboardPage() {
  const navigate = useNavigate();
  const connectionState = useChatStore((s) => s.connectionState);
  const setActiveConversation = useChatStore((s) => s.setActiveConversation);
  const createConversation = useChatStore((s) => s.createConversation);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);

  // Fetch system status on mount
  useEffect(() => {
    fetch("/api/status")
      .then((res) => res.json())
      .then((data) => setSystemStatus(data))
      .catch(() => {});
  }, []);

  const handleAction = useCallback(
    (action: string) => {
      switch (action) {
        case "web_search":
        case "write_code":
        default: {
          const convId = createConversation();
          setActiveConversation(convId);
          navigate("/");
        }
      }
    },
    [navigate, createConversation, setActiveConversation]
  );

  const handleSelectConversation = useCallback(
    (id: string) => {
      setActiveConversation(id);
      navigate("/");
    },
    [setActiveConversation, navigate]
  );

  const stats = [
    {
      label: "Uptime",
      value: systemStatus
        ? `${Math.floor(systemStatus.uptime_seconds / 3600)}h ${Math.floor((systemStatus.uptime_seconds % 3600) / 60)}m`
        : "--",
      icon: Activity,
      iconColor: "from-accent-blue to-accent-cyan",
      glow: "rgba(0, 212, 255, 0.3)",
    },
    {
      label: "CPU",
      value: systemStatus ? `${systemStatus.cpu_usage.toFixed(1)}%` : "--",
      icon: Cpu,
      iconColor: "from-accent-purple to-accent-rose",
      glow: "rgba(139, 92, 246, 0.3)",
    },
    {
      label: "Memory",
      value: systemStatus ? `${systemStatus.memory_usage.toFixed(1)}%` : "--",
      icon: Gauge,
      iconColor: "from-accent-emerald to-accent-cyan",
      glow: "rgba(52, 211, 153, 0.3)",
    },
    {
      label: "Tools",
      value: systemStatus ? `${systemStatus.tools_loaded.length}` : "--",
      icon: Bot,
      iconColor: "from-accent-amber to-accent-rose",
      glow: "rgba(245, 158, 11, 0.3)",
    },
  ];

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      {/* Page header with holographic accent */}
      <div className="relative">
        <div className="absolute -top-4 -left-4 w-32 h-32 bg-accent-blue/5 rounded-full blur-3xl pointer-events-none" />
        <div className="relative">
          <div className="flex items-center gap-3 mb-1">
            <Sparkles className="w-5 h-5 text-accent-blue" />
            <h1 className="text-2xl font-bold text-gradient">Dashboard</h1>
          </div>
          <p className="text-sm text-gray-500 ml-8">
            System overview, quick actions, and AI companion status
          </p>
        </div>
      </div>

      {/* Stats bar */}
      <div className="grid grid-cols-4 gap-3">
        {stats.map((stat) => {
          const IconComponent = stat.icon;
          return (
            <div
              key={stat.label}
              className={cn(
                "group relative overflow-hidden rounded-2xl p-4",
                "bg-white/[0.03] border border-white/[0.06]",
                "hover:bg-white/[0.05] hover:border-white/10",
                "transition-all duration-300"
              )}
            >
              {/* Hover glow - split gradient into two opacity-applied classes */}
              <div
                className={cn(
                  "absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 rounded-2xl",
                  "bg-gradient-to-br",
                  stat.iconColor.split(" ").map(c => c + "/5").join(" ")
                )}
              />
              <div className="relative z-10 flex items-center gap-3">
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center bg-white/[0.03]"
                  style={{
                    boxShadow: `0 0 20px ${stat.glow}`,
                  }}
                >
                  <IconComponent className="w-5 h-5 text-white" />
                </div>
                <div>
                  <p className="text-lg font-bold text-gray-200">
                    {stat.value}
                  </p>
                  <p className="text-xs text-gray-500">{stat.label}</p>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Main grid */}
      <div className="grid grid-cols-4 gap-4">
        {/* Left column - Status + Actions */}
        <div className="col-span-2 space-y-4">
          <StatusPanel
            connectionState={connectionState}
            systemStatus={systemStatus}
          />
          <QuickActions onAction={handleAction} />
        </div>

        {/* Right column - Memory + Tools + Conversations */}
        <div className="col-span-2 space-y-4">
          {/* Memory and Tools in a 2-col subgrid */}
          <div className="grid grid-cols-2 gap-4">
            <MemoryIndicator
              systemStatus={systemStatus}
            />
            <ToolsPanel
              systemStatus={systemStatus}
            />
          </div>
          <RecentConversations onSelectConversation={handleSelectConversation} />
        </div>
      </div>
    </div>
  );
}

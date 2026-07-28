import React, { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { StatusPanel } from "@/components/dashboard/StatusPanel";
import { QuickActions } from "@/components/dashboard/QuickActions";
import { RecentConversations } from "@/components/dashboard/RecentConversations";
import { useChatStore } from "@/stores/chatStore";
import type { SystemStatus } from "@/types";
import { Bot, Activity, Zap, Cpu } from "lucide-react";
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
      color: "text-accent-green",
    },
    {
      label: "CPU",
      value: systemStatus ? `${systemStatus.cpu_usage.toFixed(1)}%` : "--",
      icon: Cpu,
      color: "text-accent-blue",
    },
    {
      label: "Memory",
      value: systemStatus ? `${systemStatus.memory_usage.toFixed(1)}%` : "--",
      icon: Zap,
      color: "text-accent-purple",
    },
    {
      label: "Tools",
      value: systemStatus ? `${systemStatus.tools_loaded.length}` : "--",
      icon: Bot,
      color: "text-accent-amber",
    },
  ];

  return (
    <div className="flex-1 overflow-y-auto p-6">
      {/* Page header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gradient">Dashboard</h1>
        <p className="text-sm text-gray-500 mt-1">
          System overview and quick actions
        </p>
      </div>

      {/* Stats bar */}
      <div className="grid grid-cols-4 gap-3 mb-6">
        {stats.map((stat) => {
          const IconComponent = stat.icon;
          return (
            <div
              key={stat.label}
              className="glass-card px-4 py-3 flex items-center gap-3"
            >
              <div className={cn("w-10 h-10 rounded-xl bg-white/[0.03] flex items-center justify-center", stat.color)}>
                <IconComponent className="w-5 h-5" />
              </div>
              <div>
                <p className="text-lg font-bold text-gray-200">{stat.value}</p>
                <p className="text-xs text-gray-500">{stat.label}</p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Main grid */}
      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2 space-y-4">
          <StatusPanel
            connectionState={connectionState}
            systemStatus={systemStatus}
          />
          <QuickActions onAction={handleAction} />
        </div>
        <div className="space-y-4">
          <RecentConversations onSelectConversation={handleSelectConversation} />
        </div>
      </div>
    </div>
  );
}

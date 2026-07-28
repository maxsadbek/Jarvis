import React from "react";
import { cn } from "@/lib/utils";
import {
  Globe,
  FileText,
  Code,
  Terminal,
  Monitor,
  Settings,
  Shield,
  Search,
} from "lucide-react";
import type { SystemStatus } from "@/types";

interface ToolsPanelProps {
  systemStatus?: SystemStatus | null;
  onToolClick?: (toolName: string) => void;
  className?: string;
}

const toolConfig = [
  { id: "web_search", label: "Web Search", icon: Globe, color: "text-neon-blue" },
  { id: "file_ops", label: "File Manager", icon: FileText, color: "text-neon-green" },
  { id: "code_exec", label: "Code Runner", icon: Code, color: "text-neon-purple" },
  { id: "command_runner", label: "Terminal", icon: Terminal, color: "text-neon-amber" },
  { id: "browser", label: "Browser", icon: Monitor, color: "text-neon-cyan" },
  { id: "system_ctl", label: "System", icon: Settings, color: "text-neon-pink" },
  { id: "memory", label: "Memory", icon: Shield, color: "text-neon-violet" },
  { id: "search", label: "Research", icon: Search, color: "text-neon-blue" },
];

export function ToolsPanel({
  systemStatus,
  onToolClick,
  className,
}: ToolsPanelProps) {
  const loadedTools = systemStatus?.tools_loaded ?? [];

  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex items-center gap-2">
        <div className="w-1 h-3 rounded-full bg-gradient-to-b from-neon-blue to-neon-purple" />
        <span className="text-[11px] font-medium text-gray-400 uppercase tracking-wider">
          Tool System
        </span>
        <span className="text-[10px] text-gray-600 ml-auto">
          {loadedTools.length} active
        </span>
      </div>

      <div className="grid grid-cols-4 gap-1.5">
        {toolConfig.map((tool) => {
          const Icon = tool.icon;
          const isLoaded = loadedTools.includes(tool.id);

          return (
            <button
              key={tool.id}
              onClick={() => onToolClick?.(tool.id)}
              disabled={!isLoaded}
              className={cn(
                "flex flex-col items-center gap-1 p-2 rounded-xl transition-all duration-200 group",
                isLoaded
                  ? "bg-white/[0.02] hover:bg-white/[0.06] border border-white/[0.04] hover:border-white/10 cursor-pointer"
                  : "bg-white/[0.01] border border-white/[0.02] opacity-40 cursor-not-allowed"
              )}
              title={isLoaded ? `Open ${tool.label}` : `${tool.label} (unavailable)`}
            >
              <div className={cn(
                "w-7 h-7 rounded-lg flex items-center justify-center transition-colors",
                isLoaded
                  ? "bg-white/[0.03] group-hover:bg-white/[0.06]"
                  : "bg-white/[0.02]",
                isLoaded ? tool.color : "text-gray-600"
              )}>
                <Icon className="w-3.5 h-3.5" />
              </div>
              <span className={cn(
                "text-[8px] uppercase tracking-wider text-center",
                isLoaded ? "text-gray-500 group-hover:text-gray-300" : "text-gray-700"
              )}>
                {tool.label}
              </span>
            </button>
          );
        })}
      </div>

      {/* Active connection indicator */}
      <div className="flex items-center gap-2 text-[10px] text-gray-600 pt-1 border-t border-white/[0.04]">
        <span className="w-1.5 h-1.5 rounded-full bg-neon-green shadow-[0_0_6px_rgba(16,185,129,0.4)]" />
        <span>API Connected</span>
      </div>
    </div>
  );
}

import React from "react";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/utils";
import {
  Globe,
  FileText,
  Code,
  Terminal,
  Clock,
  Calculator,
  Lightbulb,
  Sparkles,
  Zap,
} from "lucide-react";

interface QuickActionsProps {
  onAction: (action: string) => void;
  className?: string;
}

const actions = [
  {
    id: "web_search",
    label: "Search Web",
    icon: Globe,
    gradient: "from-accent-blue to-accent-cyan",
    glow: "rgba(0, 212, 255, 0.25)",
  },
  {
    id: "file_ops",
    label: "Manage Files",
    icon: FileText,
    gradient: "from-accent-emerald to-accent-green",
    glow: "rgba(52, 211, 153, 0.25)",
  },
  {
    id: "write_code",
    label: "Write Code",
    icon: Code,
    gradient: "from-accent-purple to-accent-violet",
    glow: "rgba(139, 92, 246, 0.25)",
  },
  {
    id: "run_terminal",
    label: "Run Command",
    icon: Terminal,
    gradient: "from-accent-amber to-accent-orange",
    glow: "rgba(245, 158, 11, 0.25)",
  },
  {
    id: "system_info",
    label: "System Info",
    icon: Clock,
    gradient: "from-accent-cyan to-accent-blue",
    glow: "rgba(34, 211, 238, 0.25)",
  },
  {
    id: "calculate",
    label: "Calculate",
    icon: Calculator,
    gradient: "from-accent-rose to-accent-pink",
    glow: "rgba(244, 63, 94, 0.25)",
  },
  {
    id: "brainstorm",
    label: "Brainstorm",
    icon: Lightbulb,
    gradient: "from-accent-amber to-accent-yellow",
    glow: "rgba(250, 204, 21, 0.25)",
  },
  {
    id: "summarize",
    label: "Summarize",
    icon: Sparkles,
    gradient: "from-accent-blue to-accent-purple",
    glow: "rgba(99, 102, 241, 0.25)",
  },
];

export function QuickActions({ onAction, className }: QuickActionsProps) {
  return (
    <Card className={cn("space-y-3", className)}>
      <div className="flex items-center gap-2">
        <Zap className="w-4 h-4 text-accent-amber" />
        <h3 className="text-sm font-semibold text-gray-200">Quick Actions</h3>
      </div>
      <div className="grid grid-cols-4 gap-2">
        {actions.map((action) => {
          const IconComponent = action.icon;
          return (
            <button
              key={action.id}
              onClick={() => onAction(action.id)}
              className="group relative flex flex-col items-center gap-1.5 p-3 rounded-xl overflow-hidden
                         bg-white/[0.02] border border-white/[0.04]
                         hover:bg-white/[0.05] hover:border-white/10
                         transition-all duration-300"
            >
              {/* Hover glow */}
              <div
                className={cn(
                  "absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 rounded-xl",
                  "bg-gradient-to-br",
                  action.gradient + "/10"
                )}
              />
              {/* Icon */}
              <div
                className={cn(
                  "relative z-10 w-8 h-8 rounded-lg flex items-center justify-center",
                  "bg-white/[0.03] group-hover:bg-white/[0.06] transition-all duration-300"
                )}
                style={{
                  boxShadow: `0 0 0px ${action.glow}`,
                }}
              >
                <IconComponent
                  className={cn(
                    "w-4 h-4 text-gray-500 group-hover:text-white transition-all duration-300",
                    "group-hover:drop-shadow-[0_0_6px_rgba(255,255,255,0.3)]"
                  )}
                />
              </div>
              {/* Label */}
              <span className="relative z-10 text-[10px] text-gray-500 group-hover:text-gray-300 transition-colors text-center leading-tight">
                {action.label}
              </span>
            </button>
          );
        })}
      </div>
    </Card>
  );
}

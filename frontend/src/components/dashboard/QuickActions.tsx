import React from "react";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/utils";
import {
  Globe,
  FileText,
  Code,
  Terminal,
  Music,
  Clock,
  Calculator,
  Lightbulb,
} from "lucide-react";

interface QuickActionsProps {
  onAction: (action: string) => void;
  className?: string;
}

const actions = [
  { id: "web_search", label: "Search Web", icon: Globe, color: "text-accent-blue" },
  { id: "file_ops", label: "Manage Files", icon: FileText, color: "text-accent-green" },
  { id: "write_code", label: "Write Code", icon: Code, color: "text-accent-purple" },
  { id: "run_terminal", label: "Run Command", icon: Terminal, color: "text-accent-amber" },
  { id: "system_info", label: "System Info", icon: Clock, color: "text-accent-cyan" },
  { id: "calculate", label: "Calculate", icon: Calculator, color: "text-accent-rose" },
  { id: "brainstorm", label: "Brainstorm", icon: Lightbulb, color: "text-accent-amber" },
  { id: "summarize", label: "Summarize", icon: FileText, color: "text-accent-blue" },
];

export function QuickActions({ onAction, className }: QuickActionsProps) {
  return (
    <Card className={cn("space-y-3", className)}>
      <h3 className="text-sm font-semibold text-gray-200">Quick Actions</h3>
      <div className="grid grid-cols-4 gap-2">
        {actions.map((action) => {
          const IconComponent = action.icon;
          return (
            <button
              key={action.id}
              onClick={() => onAction(action.id)}
              className="flex flex-col items-center gap-1.5 p-3 rounded-xl bg-white/[0.02] border border-white/[0.04] hover:bg-white/[0.06] hover:border-white/10 transition-all duration-200 group"
            >
              <div className={cn(
                "w-8 h-8 rounded-lg flex items-center justify-center bg-white/[0.03] group-hover:bg-white/[0.06] transition-colors",
                action.color
              )}>
                <IconComponent className="w-4 h-4" />
              </div>
              <span className="text-[10px] text-gray-500 group-hover:text-gray-300 transition-colors text-center">
                {action.label}
              </span>
            </button>
          );
        })}
      </div>
    </Card>
  );
}

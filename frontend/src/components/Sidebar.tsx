import React from "react";
import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";
import { useChatStore } from "@/stores/chatStore";
import { Button } from "@/components/ui/Button";
import {
  Bot,
  MessageSquare,
  LayoutDashboard,
  Settings,
  Plus,
  History,
  ChevronLeft,
  ChevronRight,
  Search,
} from "lucide-react";

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const conversations = useChatStore((s) => s.conversations);
  const setActiveConversation = useChatStore((s) => s.setActiveConversation);

  const recentConversations = Array.from(conversations.values())
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
    .slice(0, 5);

  const navItems = [
    { to: "/", icon: MessageSquare, label: "Chat", end: true },
    { to: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
    { to: "/settings", icon: Settings, label: "Settings" },
  ];

  return (
    <aside
      className={cn(
        "relative h-screen flex flex-col bg-[#0a0a1a] border-r border-white/5 transition-all duration-300",
        collapsed ? "w-16" : "w-64"
      )}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 h-16 border-b border-white/5">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-jarvis-500 to-accent-blue flex items-center justify-center flex-shrink-0">
          <Bot className="w-5 h-5 text-white" />
        </div>
        {!collapsed && (
          <div>
            <h1 className="text-sm font-bold text-gradient">JARVIS</h1>
            <p className="text-[10px] text-gray-600">AI Assistant</p>
          </div>
        )}
      </div>

      {/* Nav items */}
      <nav className="p-2 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all duration-200",
                collapsed && "justify-center px-0",
                isActive
                  ? "bg-jarvis-500/10 text-jarvis-400 border border-jarvis-500/20"
                  : "text-gray-500 hover:text-gray-300 hover:bg-white/[0.03]"
              )
            }
            title={collapsed ? item.label : undefined}
          >
            <item.icon className="w-4 h-4 flex-shrink-0" />
            {!collapsed && <span>{item.label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* New Conversation Button */}
      <div className="px-2 mt-1">
        <Button
          variant="primary"
          size="sm"
          className={cn("w-full", collapsed && "px-0")}
          onClick={() => {
            const id = useChatStore.getState().createConversation();
            setActiveConversation(id);
          }}
          title={collapsed ? "New conversation" : undefined}
        >
          <Plus className="w-4 h-4" />
          {!collapsed && <span>New Chat</span>}
        </Button>
      </div>

      {/* Recent conversations */}
      {!collapsed && recentConversations.length > 0 && (
        <div className="flex-1 overflow-y-auto px-2 mt-4">
          <div className="flex items-center gap-1 px-3 mb-2">
            <History className="w-3 h-3 text-gray-600" />
            <span className="text-[10px] text-gray-600 font-medium uppercase tracking-wider">
              Recent
            </span>
          </div>
          <div className="space-y-0.5">
            {recentConversations.map((conv) => (
              <button
                key={conv.id}
                onClick={() => setActiveConversation(conv.id)}
                className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs text-gray-500 hover:text-gray-300 hover:bg-white/[0.03] transition-colors text-left truncate"
              >
                <MessageSquare className="w-3 h-3 flex-shrink-0" />
                <span className="truncate">{conv.title}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Collapse toggle */}
      <div className="p-2 border-t border-white/5">
        <button
          onClick={onToggle}
          className="w-full flex items-center justify-center p-2 rounded-lg text-gray-500 hover:text-gray-300 hover:bg-white/[0.03] transition-colors"
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? (
            <ChevronRight className="w-4 h-4" />
          ) : (
            <ChevronLeft className="w-4 h-4" />
          )}
        </button>
      </div>
    </aside>
  );
}

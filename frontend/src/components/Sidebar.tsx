import React from "react";
import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";
import { useChatStore } from "@/stores/chatStore";
import {
  Bot,
  MessageSquare,
  LayoutDashboard,
  Settings,
  Plus,
  History,
  ChevronLeft,
  ChevronRight,
  Sparkles,
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
        "relative h-screen flex flex-col bg-surface/90 backdrop-blur-2xl border-r border-white/[0.04] transition-all duration-300 z-20",
        collapsed ? "w-[68px]" : "w-[240px]"
      )}
    >
      {/* Scan line effect */}
      <div className="scan-line">
        {/* Logo */}
        <div className="flex items-center gap-3 px-4 h-14 border-b border-white/[0.04]">
          <div className="relative flex-shrink-0">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-jarvis-500 via-neon-blue to-neon-purple flex items-center justify-center shadow-lg shadow-jarvis-500/20">
              <Bot className="w-5 h-5 text-white" />
            </div>
            <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-neon-green shadow-[0_0_6px_rgba(16,185,129,0.6)]" />
          </div>
          {!collapsed && (
            <div className="animate-fade-in">
              <h1 className="text-sm font-bold text-gradient-primary">JARVIS</h1>
              <p className="text-[9px] text-gray-600 uppercase tracking-[0.2em]">
                AI Assistant
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Nav items */}
      <nav className="p-2 space-y-0.5 mt-2">
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
                  ? "bg-jarvis-500/10 text-neon-violet border border-jarvis-500/20 shadow-[0_0_12px_rgba(99,102,241,0.08)]"
                  : "text-gray-500 hover:text-gray-300 hover:bg-white/[0.03]"
              )
            }
            title={collapsed ? item.label : undefined}
          >
            <item.icon className="w-4 h-4 flex-shrink-0" />
            {!collapsed && <span className="animate-fade-in">{item.label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* New Conversation Button */}
      <div className="px-2 mt-1">
        <button
          onClick={() => {
            const id = useChatStore.getState().createConversation();
            setActiveConversation(id);
          }}
          className={cn(
            "flex items-center gap-2 w-full px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200",
            "bg-gradient-to-r from-jarvis-600/20 to-neon-blue/10 border border-jarvis-500/20",
            "hover:from-jarvis-600/30 hover:to-neon-blue/20 hover:border-jarvis-500/30",
            "text-gray-300 hover:text-white",
            collapsed && "justify-center px-0"
          )}
          title={collapsed ? "New conversation" : undefined}
        >
          <Plus className="w-4 h-4 flex-shrink-0" />
          {!collapsed && (
            <span className="animate-fade-in flex items-center gap-1.5">
              New Chat
              <Sparkles className="w-3 h-3 text-neon-blue" />
            </span>
          )}
        </button>
      </div>

      {/* Recent conversations */}
      {!collapsed && (
        <div className="flex-1 overflow-y-auto px-2 mt-4 animate-fade-in">
          <div className="flex items-center gap-1.5 px-3 mb-2">
            <History className="w-3 h-3 text-gray-600" />
            <span className="text-[9px] text-gray-600 font-medium uppercase tracking-[0.15em]">
              Recent
            </span>
          </div>

          {recentConversations.length === 0 ? (
            <div className="px-3 py-4 text-center">
              <p className="text-[10px] text-gray-700">No conversations yet</p>
            </div>
          ) : (
            <div className="space-y-0.5">
              {recentConversations.map((conv) => (
                <button
                  key={conv.id}
                  onClick={() => setActiveConversation(conv.id)}
                  className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs text-gray-500 hover:text-gray-300 hover:bg-white/[0.03] transition-colors text-left group"
                >
                  <MessageSquare className="w-3 h-3 flex-shrink-0 text-gray-600 group-hover:text-neon-blue transition-colors" />
                  <span className="truncate">{conv.title}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Collapse toggle */}
      <div className="p-2 border-t border-white/[0.04]">
        <button
          onClick={onToggle}
          className="w-full flex items-center justify-center p-2 rounded-lg text-gray-600 hover:text-gray-400 hover:bg-white/[0.03] transition-all duration-200"
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

import React from "react";
import { cn } from "@/lib/utils";
import { Loader2 } from "lucide-react";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger" | "glow";
  size?: "sm" | "md" | "lg";
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export function Button({
  className,
  variant = "primary",
  size = "md",
  isLoading = false,
  leftIcon,
  rightIcon,
  children,
  disabled,
  ...props
}: ButtonProps) {
  const variants = {
    primary:
      "bg-gradient-to-r from-jarvis-600 to-jarvis-500 hover:from-jarvis-500 hover:to-jarvis-400 text-white shadow-lg shadow-jarvis-500/25 hover:shadow-jarvis-500/40",
    secondary:
      "bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 text-gray-200",
    ghost:
      "hover:bg-white/5 text-gray-400 hover:text-gray-200",
    danger:
      "bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-500 hover:to-rose-500 text-white shadow-lg shadow-red-500/25",
    glow:
      "bg-gradient-to-r from-jarvis-600 to-accent-blue hover:from-jarvis-500 hover:to-accent-blue text-white shadow-lg shadow-jarvis-500/30 glow-blue",
  };

  const sizes = {
    sm: "px-3 py-1.5 text-sm",
    md: "px-4 py-2 text-sm",
    lg: "px-6 py-3 text-base",
  };

  return (
    <button
      className={cn(
        "relative inline-flex items-center justify-center gap-2 font-medium rounded-xl transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-jarvis-500/50 focus:ring-offset-2 focus:ring-offset-[#0a0a1a] disabled:opacity-50 disabled:pointer-events-none",
        variants[variant],
        sizes[size],
        className
      )}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading ? (
        <Loader2 className="w-4 h-4 animate-spin" />
      ) : (
        leftIcon
      )}
      {children}
      {!isLoading && rightIcon}
    </button>
  );
}

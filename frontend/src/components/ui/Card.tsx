import React from "react";
import { cn } from "@/lib/utils";

interface CardProps {
  className?: string;
  children: React.ReactNode;
  hover?: boolean;
  glow?: boolean;
  scanLine?: boolean;
  onClick?: () => void;
}

export function Card({
  className,
  children,
  hover = false,
  glow = false,
  scanLine = false,
  onClick,
}: CardProps) {
  const Component = onClick ? "button" : "div";

  return (
    <Component
      className={cn(
        "glass-card p-6",
        hover && "glass-card-hover cursor-pointer",
        glow && "glow-blue",
        scanLine && "scan-line",
        className
      )}
      onClick={onClick}
    >
      {children}
    </Component>
  );
}

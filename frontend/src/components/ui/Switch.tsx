import React from "react";
import { cn } from "@/lib/utils";
import * as SwitchPrimitive from "@radix-ui/react-switch";

interface SwitchProps {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  label?: string;
  className?: string;
}

export function Switch({
  checked,
  onCheckedChange,
  disabled = false,
  label,
  className,
}: SwitchProps) {
  return (
    <div className={cn("flex items-center gap-3", className)}>
      {label && (
        <span className="text-sm text-gray-300">{label}</span>
      )}
      <SwitchPrimitive.Root
        checked={checked}
        onCheckedChange={onCheckedChange}
        disabled={disabled}
        className={cn(
          "relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200",
          "focus:outline-none focus:ring-2 focus:ring-jarvis-500/50 focus:ring-offset-2 focus:ring-offset-[#0a0a1a]",
          checked
            ? "bg-gradient-to-r from-jarvis-600 to-accent-blue"
            : "bg-white/10",
          disabled && "opacity-50 cursor-not-allowed"
        )}
      >
        <SwitchPrimitive.Thumb
          className={cn(
            "inline-block h-4 w-4 rounded-full bg-white shadow-lg transition-transform duration-200",
            checked ? "translate-x-6" : "translate-x-1"
          )}
        />
      </SwitchPrimitive.Root>
    </div>
  );
}

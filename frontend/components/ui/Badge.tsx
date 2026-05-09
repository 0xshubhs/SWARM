"use client";
import * as React from "react";
import { cn } from "@/lib/cn";

type Variant = "default" | "outline" | "secondary" | "success" | "warning";

const VARIANT: Record<Variant, string> = {
  default: "bg-violet-950/40 text-violet-300 border border-violet-800/40",
  outline: "border border-zinc-700 text-zinc-300",
  secondary: "bg-zinc-800 text-zinc-300",
  success: "bg-emerald-950/40 text-emerald-300 border border-emerald-800/40",
  warning: "bg-amber-950/40 text-amber-300 border border-amber-800/40",
};

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: Variant;
}

export function Badge({ variant = "default", className, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium",
        VARIANT[variant],
        className,
      )}
      {...props}
    />
  );
}

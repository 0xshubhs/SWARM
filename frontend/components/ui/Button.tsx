"use client";
import * as React from "react";
import { cn } from "@/lib/cn";

type Variant = "primary" | "outline" | "ghost" | "secondary";
type Size = "sm" | "md" | "lg";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

const VARIANT: Record<Variant, string> = {
  primary: "bg-violet-600 hover:bg-violet-500 text-white",
  outline:
    "border border-zinc-700 hover:border-zinc-600 hover:bg-zinc-900 text-zinc-100",
  ghost: "hover:bg-zinc-900 text-zinc-300",
  secondary: "bg-zinc-800 hover:bg-zinc-700 text-zinc-100",
};

const SIZE: Record<Size, string> = {
  sm: "h-8 px-3 text-sm",
  md: "h-10 px-4 text-sm",
  lg: "h-12 px-6 text-base",
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center rounded-md font-medium transition-colors disabled:opacity-50 disabled:pointer-events-none focus:outline-none focus:ring-2 focus:ring-violet-500/40",
        VARIANT[variant],
        SIZE[size],
        className,
      )}
      {...props}
    />
  ),
);
Button.displayName = "Button";

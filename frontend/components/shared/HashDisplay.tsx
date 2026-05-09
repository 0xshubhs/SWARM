"use client";
import { Copy, Check } from "lucide-react";
import { useState } from "react";
import { truncateHash } from "@/lib/format";
import { cn } from "@/lib/cn";

export function HashDisplay({
  hash,
  className,
}: {
  hash: string;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    await navigator.clipboard.writeText(hash);
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  }
  return (
    <span className={cn("inline-flex items-center gap-1 font-mono text-xs", className)}>
      <span title={hash}>{truncateHash(hash)}</span>
      <button onClick={copy} aria-label="copy" className="text-zinc-500 hover:text-zinc-300">
        {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
      </button>
    </span>
  );
}

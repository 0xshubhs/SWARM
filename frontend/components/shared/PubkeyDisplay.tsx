"use client";
import { Copy, ExternalLink, Check } from "lucide-react";
import { useState } from "react";
import { explorerAddressUrl, truncatePubkey } from "@/lib/format";
import { cn } from "@/lib/cn";

interface PubkeyDisplayProps {
  pubkey: string;
  className?: string;
  showCopy?: boolean;
  showExplorer?: boolean;
}

export function PubkeyDisplay({
  pubkey,
  className,
  showCopy = true,
  showExplorer = true,
}: PubkeyDisplayProps) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    await navigator.clipboard.writeText(pubkey);
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  }
  return (
    <span className={cn("inline-flex items-center gap-1 font-mono text-xs", className)}>
      <span title={pubkey}>{truncatePubkey(pubkey)}</span>
      {showCopy && (
        <button onClick={copy} aria-label="copy" className="text-zinc-500 hover:text-zinc-300">
          {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
        </button>
      )}
      {showExplorer && (
        <a
          href={explorerAddressUrl(pubkey)}
          target="_blank"
          rel="noopener noreferrer"
          className="text-zinc-500 hover:text-zinc-300"
          aria-label="explorer"
        >
          <ExternalLink className="w-3 h-3" />
        </a>
      )}
    </span>
  );
}

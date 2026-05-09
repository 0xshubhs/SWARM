"use client";
import { useState } from "react";
import { useConnection, useWallet } from "@solana/wallet-adapter-react";
import { Send, Loader2, X } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { x402Pay } from "@/lib/x402-client";
import { BACKEND_URL } from "@/lib/constants";
import { explorerTxUrl, formatUsdc } from "@/lib/format";

interface Props {
  listingId: string;
  listingTitle: string;
  priceUsdc: number;
  open: boolean;
  onClose: () => void;
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  txSig?: string;
}

export function SandboxModal({
  listingId,
  listingTitle,
  priceUsdc,
  open,
  onClose,
}: Props) {
  const { connection } = useConnection();
  const wallet = useWallet();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [queriesLeft, setQueriesLeft] = useState<number | null>(null);

  if (!open) return null;

  async function handleSend() {
    if (!input.trim() || !wallet.publicKey) return;
    setLoading(true);
    const userMsg = input.trim();
    setInput("");
    setMessages((m) => [...m, { role: "user", content: userMsg }]);
    try {
      const resp = await x402Pay({
        url: `${BACKEND_URL}/v1/sandbox/${listingId}`,
        body: { query: userMsg },
        wallet,
        connection,
      });
      const data = await resp.json();
      setMessages((m) => [
        ...m,
        { role: "assistant", content: data.response, txSig: data.tx_signature },
      ]);
      setQueriesLeft(data.queries_remaining ?? null);
    } catch (e: any) {
      setMessages((m) => [
        ...m,
        { role: "assistant", content: `Sandbox error: ${e.message}` },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="w-full max-w-2xl rounded-lg border border-zinc-800 bg-zinc-950 p-6 shadow-2xl">
        <div className="flex items-start justify-between mb-2">
          <div>
            <h3 className="text-lg font-semibold">Sandbox: {listingTitle}</h3>
            <p className="text-sm text-zinc-400">
              Pay {formatUsdc(priceUsdc)} USDC per query.
              {queriesLeft !== null && ` ${queriesLeft} queries remaining.`}
            </p>
          </div>
          <button onClick={onClose} aria-label="close" className="text-zinc-500 hover:text-zinc-300">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="space-y-2 max-h-96 overflow-y-auto py-3">
          {messages.length === 0 && (
            <p className="text-sm text-zinc-500">Ask the agent something to start.</p>
          )}
          {messages.map((m, i) => (
            <div key={i} className={m.role === "user" ? "ml-12" : "mr-12"}>
              <div
                className={
                  "p-3 rounded-md text-sm " +
                  (m.role === "user" ? "bg-violet-950/40" : "bg-zinc-900")
                }
              >
                <pre className="whitespace-pre-wrap font-sans">{m.content}</pre>
              </div>
              {m.txSig && (
                <a
                  href={explorerTxUrl(m.txSig)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-1 inline-block text-xs font-mono text-zinc-500 hover:text-zinc-300"
                >
                  tx: {m.txSig.slice(0, 8)}…{m.txSig.slice(-6)}
                </a>
              )}
            </div>
          ))}
          {loading && (
            <div className="flex items-center text-zinc-500 text-sm">
              <Loader2 className="w-4 h-4 animate-spin mr-2" />
              Paying via x402, loading memory, generating…
            </div>
          )}
        </div>

        <div className="flex gap-2 mt-3">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="Ask the agent something..."
            disabled={loading}
          />
          <Button onClick={handleSend} disabled={loading || !input.trim()} size="md">
            <Send className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}

"use client";
import { useState, use } from "react";
import { Sparkles, ShoppingCart, Loader2 } from "lucide-react";
import { useConnection, useWallet } from "@solana/wallet-adapter-react";
import { PublicKey } from "@solana/web3.js";
import { Card, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { PubkeyDisplay } from "@/components/shared/PubkeyDisplay";
import { HashDisplay } from "@/components/shared/HashDisplay";
import { SandboxModal } from "@/components/listings/SandboxModal";
import { useListing } from "@/lib/hooks/useListings";
import { arweaveUrl, formatUsdc } from "@/lib/format";
import { buyMemory } from "@/lib/anchor-client";

export default function ListingDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data, isLoading, error } = useListing(id);
  const [sandboxOpen, setSandboxOpen] = useState(false);
  const [buying, setBuying] = useState(false);
  const [buyResult, setBuyResult] = useState<
    { signature: string } | { error: string } | null
  >(null);
  const { connection } = useConnection();
  const wallet = useWallet();

  async function handleBuy() {
    if (!data) return;
    if (!wallet.publicKey) {
      setBuyResult({ error: "Connect a wallet first." });
      return;
    }
    setBuying(true);
    setBuyResult(null);
    try {
      const signature = await buyMemory({
        connection,
        wallet,
        listing: new PublicKey(data.id),
        seller: new PublicKey(data.seller),
      });
      setBuyResult({ signature });
    } catch (e: any) {
      setBuyResult({ error: e?.message ?? String(e) });
    } finally {
      setBuying(false);
    }
  }

  if (isLoading) {
    return (
      <main className="max-w-4xl mx-auto px-6 py-10">
        <Skeleton className="h-12 w-2/3 mb-4" />
        <Skeleton className="h-64" />
      </main>
    );
  }

  if (error || !data) {
    return (
      <main className="max-w-4xl mx-auto px-6 py-10">
        <p className="text-zinc-400">Listing not found.</p>
      </main>
    );
  }

  return (
    <main className="max-w-4xl mx-auto px-6 py-10">
      <h1 className="text-3xl font-bold mb-2">{data.title}</h1>
      <div className="flex items-center gap-3 text-sm text-zinc-400 mb-6">
        <span>seller</span>
        <PubkeyDisplay pubkey={data.seller} />
        <span>·</span>
        <span>{data.purchases} sold</span>
      </div>

      <Card>
        <CardContent className="space-y-6">
          <div className="flex flex-wrap gap-2">
            {data.tags.map((t) => (
              <Badge key={t} variant="secondary">{t}</Badge>
            ))}
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Stat label="Model" value={data.model_id} />
            <Stat label="Tokens" value={data.seq_len.toLocaleString()} />
            <Stat label="Quantization" value={`${(data.bits_per_channel / 10).toFixed(1)} bpc`} />
            <Stat label="Status" value={data.active ? "active" : "delisted"} />
          </div>

          <div className="space-y-2 text-sm">
            <Row label="Content hash">
              <HashDisplay hash={data.content_hash_hex} />
            </Row>
            <Row label="Arweave tx">
              <a
                href={arweaveUrl(data.arweave_tx)}
                target="_blank"
                rel="noopener noreferrer"
                className="font-mono text-xs underline-offset-2 hover:underline"
              >
                {data.arweave_tx}
              </a>
            </Row>
          </div>

          <div className="flex flex-wrap gap-3 pt-2 border-t border-zinc-800">
            <Button variant="outline" onClick={() => setSandboxOpen(true)}>
              <Sparkles className="w-4 h-4 mr-2" />
              Try sandbox · {formatUsdc(data.sandbox_price_usdc)}
            </Button>
            <Button onClick={handleBuy} disabled={buying || !data.active}>
              {buying ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <ShoppingCart className="w-4 h-4 mr-2" />
              )}
              Buy memory · {formatUsdc(data.price_usdc)}
            </Button>
          </div>
          {buyResult && "signature" in buyResult && (
            <p className="text-emerald-400 text-xs font-mono pt-2">
              tx: {buyResult.signature}
            </p>
          )}
          {buyResult && "error" in buyResult && (
            <p className="text-red-400 text-xs pt-2">{buyResult.error}</p>
          )}
        </CardContent>
      </Card>

      <SandboxModal
        listingId={data.id}
        listingTitle={data.title}
        priceUsdc={data.sandbox_price_usdc}
        open={sandboxOpen}
        onClose={() => setSandboxOpen(false)}
      />
    </main>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-zinc-500 uppercase tracking-wide mb-1">{label}</div>
      <div className="font-mono text-sm">{value}</div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-zinc-500 text-xs uppercase w-28">{label}</span>
      <span>{children}</span>
    </div>
  );
}

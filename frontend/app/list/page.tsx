"use client";
import { useState, useCallback, useEffect } from "react";
import { useDropzone } from "react-dropzone";
import { useConnection, useWallet } from "@solana/wallet-adapter-react";
import { Upload, Loader2, CheckCircle2, AlertCircle } from "lucide-react";

import { Card, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { Progress } from "@/components/ui/Progress";
import { api } from "@/lib/api";
import { formatUsdc } from "@/lib/format";
import { useUploadProgress } from "@/lib/hooks/useUploadProgress";
import { listMemory } from "@/lib/anchor-client";

type Step = "upload" | "metadata" | "submit" | "done";

export default function ListPage() {
  const wallet = useWallet();
  const { connection } = useConnection();
  const [step, setStep] = useState<Step>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [tags, setTags] = useState("");
  const [priceUsdc, setPriceUsdc] = useState(25);
  const [sandboxPriceUsdc, setSandboxPriceUsdc] = useState(0.05);
  const [uploadId, setUploadId] = useState<string | null>(null);
  const [wsToken, setWsToken] = useState<string | null>(null);
  const [signing, setSigning] = useState(false);
  const [signError, setSignError] = useState<string | null>(null);
  const [listingTx, setListingTx] = useState<string | null>(null);

  const onDrop = useCallback((accepted: File[]) => {
    if (accepted[0]) {
      setFile(accepted[0]);
      setStep("metadata");
    }
  }, []);
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: false,
    accept: { "application/octet-stream": [".avlt", ".bin"] },
  });

  const progress = useUploadProgress(uploadId, wsToken);

  // When the worker reports listing.pending, fetch the build args and ask the
  // wallet to sign listMemory. We only fire once per upload to avoid double
  // submissions if the WS reconnects.
  useEffect(() => {
    if (progress.phase !== "listing_pending") return;
    if (!uploadId || !wallet.publicKey || signing || listingTx) return;
    let cancelled = false;
    (async () => {
      setSigning(true);
      setSignError(null);
      try {
        const finalizeRes = await api.finalizeUpload({
          upload_id: uploadId,
          seller_pubkey: wallet.publicKey!.toBase58(),
          title,
          tags: tags
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean),
          price_usdc: Math.round(priceUsdc * 1_000_000),
          sandbox_price_usdc: Math.round(sandboxPriceUsdc * 1_000_000),
        });
        if (cancelled) return;
        const { args } = finalizeRes as any;
        const { signature } = await listMemory({
          connection,
          wallet,
          arweaveTx: args.arweave_tx,
          contentHash: Uint8Array.from(args.content_hash),
          modelId: args.model_id,
          quantSeed: BigInt(args.quant_seed),
          bitsPerChannel: args.bits_per_channel,
          seqLen: args.seq_len,
          priceUsdc: BigInt(args.price_usdc),
          sandboxPriceUsdc: BigInt(args.sandbox_price_usdc),
          title: args.title,
          tags: args.tags,
        });
        if (!cancelled) setListingTx(signature);
      } catch (e: any) {
        if (!cancelled) setSignError(e?.message ?? String(e));
      } finally {
        if (!cancelled) setSigning(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [
    progress.phase,
    uploadId,
    wallet.publicKey,
    signing,
    listingTx,
    title,
    tags,
    priceUsdc,
    sandboxPriceUsdc,
    connection,
    wallet,
  ]);

  async function startSubmit() {
    if (!wallet.publicKey || !file) return;
    const init = await api.initUpload({
      seller_pubkey: wallet.publicKey.toBase58(),
      expected_size_bytes: file.size,
    });
    setUploadId(init.upload_id);
    setWsToken(init.ws_token);
    setStep("submit");
  }

  return (
    <main className="max-w-3xl mx-auto px-6 py-10">
      <header className="mb-8">
        <h1 className="text-3xl font-bold">List your memory</h1>
        <p className="text-zinc-400 mt-1">
          Compress, anchor on Solana, and earn when others use your trained context.
        </p>
      </header>

      <Stepper step={step} />

      <div className="mt-8 space-y-4">
        {step === "upload" && (
          <Card>
            <CardContent>
              <div
                {...getRootProps()}
                className={
                  "flex flex-col items-center justify-center border-2 border-dashed rounded-lg py-16 cursor-pointer transition-colors " +
                  (isDragActive
                    ? "border-violet-500 bg-violet-950/20"
                    : "border-zinc-800 hover:border-zinc-700")
                }
              >
                <input {...getInputProps()} />
                <Upload className="w-8 h-8 text-zinc-500 mb-3" />
                <p className="text-sm">Drop your .avlt or KV cache file here</p>
                <p className="text-xs text-zinc-500 mt-1">
                  or click to browse
                </p>
              </div>
            </CardContent>
          </Card>
        )}

        {step === "metadata" && file && (
          <Card>
            <CardContent className="space-y-4">
              <p className="text-sm text-zinc-400">
                File: <span className="font-mono">{file.name}</span> ·{" "}
                <Badge variant="outline">{(file.size / 1024 / 1024).toFixed(1)} MB</Badge>
              </p>
              <Field label="Title">
                <Input value={title} onChange={(e) => setTitle(e.target.value)} />
              </Field>
              <Field label="Tags (comma-separated)">
                <Input value={tags} onChange={(e) => setTags(e.target.value)} />
              </Field>
              <div className="grid grid-cols-2 gap-4">
                <Field label="Buy price (USDC)">
                  <Input
                    type="number"
                    step="0.01"
                    value={priceUsdc}
                    onChange={(e) => setPriceUsdc(Number(e.target.value))}
                  />
                </Field>
                <Field label="Sandbox price (USDC)">
                  <Input
                    type="number"
                    step="0.001"
                    value={sandboxPriceUsdc}
                    onChange={(e) => setSandboxPriceUsdc(Number(e.target.value))}
                  />
                </Field>
              </div>
              <div className="flex justify-between pt-2">
                <Button variant="ghost" onClick={() => setStep("upload")}>Back</Button>
                <Button onClick={startSubmit} disabled={!wallet.publicKey || !title}>
                  Start upload
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {step === "submit" && uploadId && (
          <Card>
            <CardContent className="space-y-4">
              <PhaseRow phase="Compress" pct={progress.compressPercent} />
              <PhaseRow phase="Arweave" pct={progress.uploadPercent} />
              {progress.phase === "listing_pending" && (
                <p className="text-sm text-amber-400 inline-flex items-center gap-1">
                  {signing ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Sign the listMemory transaction in your wallet…
                    </>
                  ) : (
                    "Preparing listMemory transaction…"
                  )}
                </p>
              )}
              {listingTx && (
                <p className="text-emerald-400 text-xs font-mono">
                  listing tx: {listingTx}
                </p>
              )}
              {signError && (
                <p className="text-red-400 text-xs inline-flex items-center gap-1">
                  <AlertCircle className="w-4 h-4" /> {signError}
                </p>
              )}
              {progress.phase === "confirmed" && (
                <p className="text-sm text-emerald-400 inline-flex items-center gap-1">
                  <CheckCircle2 className="w-4 h-4" /> Listed on-chain.
                </p>
              )}
              {progress.phase === "error" && (
                <p className="text-sm text-red-400 inline-flex items-center gap-1">
                  <AlertCircle className="w-4 h-4" /> {progress.error}
                </p>
              )}
              <p className="text-xs text-zinc-500">
                Total fee: {formatUsdc(priceUsdc * 1_000_000)} buy /{" "}
                {formatUsdc(sandboxPriceUsdc * 1_000_000)} sandbox
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </main>
  );
}

function Stepper({ step }: { step: Step }) {
  const steps: Step[] = ["upload", "metadata", "submit", "done"];
  const idx = steps.indexOf(step);
  return (
    <div className="flex items-center gap-2 text-xs text-zinc-500">
      {steps.map((s, i) => (
        <span
          key={s}
          className={
            i === idx
              ? "text-violet-400 font-medium"
              : i < idx
              ? "text-emerald-500"
              : ""
          }
        >
          {i + 1}. {s}
          {i < steps.length - 1 && <span className="mx-2 text-zinc-700">›</span>}
        </span>
      ))}
    </div>
  );
}

function PhaseRow({ phase, pct }: { phase: string; pct: number }) {
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span>{phase}</span>
        <span className="text-zinc-500">
          {pct < 100 ? <Loader2 className="w-3 h-3 inline animate-spin" /> : null} {pct.toFixed(0)}%
        </span>
      </div>
      <Progress value={pct} />
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs text-zinc-400 mb-1">{label}</label>
      {children}
    </div>
  );
}

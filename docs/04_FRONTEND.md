# 04 — Frontend (Next.js + Vercel)

**Where:** `frontend/`
**Stack:** Next.js 15 + React 19 + Tailwind v4 + shadcn/ui + Solana wallet adapter
**Deploy target:** Vercel
**Build last:** Yes — only after backend, program, and buyer agent are working. UI is polish, not foundation.

---

## 1. Responsibilities

The frontend is the **human-facing surface** of AgentVault:
- Browse marketplace listings
- List your own memories (sellers)
- Try sandbox previews (with wallet-signed x402 payments)
- Buy memories (signed Solana transactions)
- Dashboard: your listings, purchases, earnings, decision audit trail

The frontend is also the **demo polish layer** — it's what hackathon judges see. It needs to look like a real product.

The frontend does **not**:
- Trust user input for trust-critical data (always verify hashes)
- Hold private keys (uses wallet adapter for signing)
- Compute prices independently (always fetches from `/v1/pricing`)
- Index Solana directly (uses backend's API)

---

## 2. Pages & routing

```
/                           Landing page
/browse                     Marketplace (default tab)
/listing/[id]               Single listing detail
/list                       Create new listing (seller flow)
/dashboard                  Your stuff (auth-gated by wallet)
  /dashboard/listings       My active listings
  /dashboard/purchases      My licenses
  /dashboard/earnings       Royalty stats
  /dashboard/decisions      Audit trail (if you've anchored decisions)
/agent                      Live demo: autonomous agent purchasing memory
/docs                       Read-the-docs style explainer (for judges)
```

---

## 3. File structure

```
frontend/
├── package.json
├── next.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── postcss.config.mjs
├── components.json                 # shadcn config
├── .env.local.example
│
├── public/
│   ├── logo.svg
│   ├── og.png
│   └── favicon.ico
│
├── app/
│   ├── layout.tsx                  # Root layout, providers
│   ├── globals.css
│   ├── page.tsx                    # Landing
│   ├── providers.tsx               # Wallet, theme, query providers
│   │
│   ├── browse/
│   │   └── page.tsx
│   │
│   ├── listing/
│   │   └── [id]/
│   │       └── page.tsx
│   │
│   ├── list/
│   │   └── page.tsx
│   │
│   ├── dashboard/
│   │   ├── layout.tsx              # Wallet-gated
│   │   ├── page.tsx
│   │   ├── listings/page.tsx
│   │   ├── purchases/page.tsx
│   │   ├── earnings/page.tsx
│   │   └── decisions/page.tsx
│   │
│   ├── agent/
│   │   └── page.tsx                # Demo: live buyer agent run
│   │
│   ├── docs/
│   │   └── page.tsx
│   │
│   └── api/
│       └── og/                     # OG image generator (optional)
│
├── components/
│   ├── ui/                         # shadcn components (auto-generated)
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── badge.tsx
│   │   ├── dialog.tsx
│   │   ├── input.tsx
│   │   ├── select.tsx
│   │   ├── tabs.tsx
│   │   ├── progress.tsx
│   │   ├── tooltip.tsx
│   │   ├── toast.tsx
│   │   └── ...
│   │
│   ├── wallet/
│   │   ├── WalletButton.tsx        # Connect / disconnect / show balance
│   │   ├── WalletProvider.tsx      # Adapter setup
│   │   └── useWallet.ts            # Custom hooks
│   │
│   ├── listings/
│   │   ├── ListingCard.tsx
│   │   ├── ListingGrid.tsx
│   │   ├── ListingFilters.tsx
│   │   ├── ListingDetail.tsx
│   │   └── SandboxModal.tsx        # The x402-handshake chat modal
│   │
│   ├── list-form/
│   │   ├── UploadDropzone.tsx
│   │   ├── PricingPreview.tsx      # Reads /v1/pricing
│   │   ├── MetadataForm.tsx
│   │   ├── ProgressStepper.tsx     # 5-step listing flow
│   │   └── ListingSubmission.tsx   # WS subscription for compress/upload progress
│   │
│   ├── shared/
│   │   ├── PubkeyDisplay.tsx       # Truncated, click-to-copy, explorer link
│   │   ├── HashDisplay.tsx         # Same for hashes
│   │   ├── PriceTag.tsx            # USDC formatting
│   │   ├── SolanaTxLink.tsx
│   │   ├── ArweaveLink.tsx
│   │   └── EmptyState.tsx
│   │
│   └── nav/
│       ├── TopNav.tsx
│       ├── Footer.tsx
│       └── MobileMenu.tsx
│
├── lib/
│   ├── api.ts                      # Backend API client (fetch wrapper)
│   ├── solana.ts                   # Connection, network helpers
│   ├── program.ts                  # AnchorProgram client (uses generated IDL)
│   ├── x402-client.ts              # Wraps x402-solana for browser signing
│   ├── hooks/
│   │   ├── useListings.ts          # TanStack Query
│   │   ├── useListing.ts
│   │   ├── useUserListings.ts
│   │   ├── useUserPurchases.ts
│   │   ├── useWebSocket.ts         # Generic WS hook
│   │   └── useUploadProgress.ts    # Specific to upload WS channel
│   ├── format.ts                   # Number/date/address formatters
│   └── constants.ts                # Network constants, USDC decimals, etc.
│
└── shared-types/                   # Symlink to ../shared/types
```

---

## 4. Dependencies

```json
{
  "name": "agentvault-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev --turbo",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "next": "15.0.0",
    "react": "19.0.0",
    "react-dom": "19.0.0",

    "@solana/web3.js": "^1.95.0",
    "@solana/wallet-adapter-base": "^0.9.23",
    "@solana/wallet-adapter-react": "^0.15.35",
    "@solana/wallet-adapter-react-ui": "^0.9.35",
    "@solana/wallet-adapter-wallets": "^0.19.32",
    "@solana/spl-token": "^0.4.0",
    "@coral-xyz/anchor": "^0.30.1",

    "x402-solana": "^0.2.0",

    "@tanstack/react-query": "^5.59.0",
    "@tanstack/react-query-devtools": "^5.59.0",

    "tailwindcss": "^4.0.0",
    "@radix-ui/react-dialog": "^1.1.2",
    "@radix-ui/react-tabs": "^1.1.1",
    "@radix-ui/react-select": "^2.1.2",
    "@radix-ui/react-progress": "^1.1.0",
    "@radix-ui/react-toast": "^1.2.2",
    "@radix-ui/react-tooltip": "^1.1.3",

    "class-variance-authority": "^0.7.0",
    "clsx": "^2.1.1",
    "tailwind-merge": "^2.5.0",
    "lucide-react": "^0.451.0",

    "framer-motion": "^11.11.0",
    "sonner": "^1.5.0",

    "react-dropzone": "^14.2.0",
    "zod": "^3.23.0",
    "react-hook-form": "^7.53.0",
    "@hookform/resolvers": "^3.9.0",

    "agentvault-types": "workspace:*"
  },
  "devDependencies": {
    "typescript": "^5.6.0",
    "@types/react": "^19.0.0",
    "@types/node": "^22.0.0",
    "eslint": "^9.0.0",
    "eslint-config-next": "15.0.0"
  }
}
```

---

## 5. Visual style

### Color palette

```css
/* globals.css */
:root {
  /* Background gradient */
  --bg-base: #09090b;            /* zinc-950 */
  --bg-elevated: #18181b;        /* zinc-900 */
  --bg-card: #1f1f23;
  --border: #27272a;             /* zinc-800 */
  --border-hover: #3f3f46;       /* zinc-700 */

  /* Foreground */
  --fg-primary: #fafafa;
  --fg-secondary: #a1a1aa;       /* zinc-400 */
  --fg-tertiary: #71717a;        /* zinc-500 */

  /* Solana brand */
  --solana-purple: #9945FF;
  --solana-green: #14F195;
  --solana-gradient: linear-gradient(135deg, #9945FF 0%, #14F195 100%);

  /* Status */
  --success: #10b981;
  --warning: #f59e0b;
  --error: #ef4444;
  --info: #3b82f6;
}
```

### Typography

```typescript
// app/layout.tsx
import { Inter, JetBrains_Mono } from "next/font/google";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});
```

### Design rules

1. **No emoji clutter** — use Lucide icons sparingly, only when meaning is added
2. **Typography hierarchy** — h1/h2 use bold weights, body 400-500
3. **Generous spacing** — Tailwind gap-6 or gap-8 minimum between sections
4. **Subtle motion** — fade-in + slight slide-up on mount (framer-motion 200ms ease-out)
5. **Hash/address display** — always truncate `AbCd...XyZ9`, click to copy + explorer link
6. **Skeleton loaders** — never blank cards; use shadcn's skeleton component
7. **Hover states** — cards lift slightly (1px shadow + 2px translate)
8. **No gradients on text except the wordmark**

---

## 6. Wallet provider setup

```tsx
// app/providers.tsx
"use client";

import { useMemo, type ReactNode } from "react";
import { ConnectionProvider, WalletProvider } from "@solana/wallet-adapter-react";
import { WalletAdapterNetwork } from "@solana/wallet-adapter-base";
import { WalletModalProvider } from "@solana/wallet-adapter-react-ui";
import {
  PhantomWalletAdapter,
  SolflareWalletAdapter,
  BackpackWalletAdapter,
} from "@solana/wallet-adapter-wallets";
import { clusterApiUrl } from "@solana/web3.js";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { Toaster } from "sonner";

require("@solana/wallet-adapter-react-ui/styles.css");

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

export function Providers({ children }: { children: ReactNode }) {
  const network = WalletAdapterNetwork.Devnet;
  const endpoint = useMemo(
    () => process.env.NEXT_PUBLIC_RPC_URL ?? clusterApiUrl(network),
    [network]
  );

  const wallets = useMemo(
    () => [
      new PhantomWalletAdapter(),
      new SolflareWalletAdapter({ network }),
      new BackpackWalletAdapter(),
    ],
    [network]
  );

  return (
    <QueryClientProvider client={queryClient}>
      <ConnectionProvider endpoint={endpoint}>
        <WalletProvider wallets={wallets} autoConnect>
          <WalletModalProvider>
            {children}
            <Toaster position="bottom-right" theme="dark" />
          </WalletModalProvider>
        </WalletProvider>
      </ConnectionProvider>
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}
```

---

## 7. Listing card — the unit of UI

```tsx
// components/listings/ListingCard.tsx
"use client";

import Link from "next/link";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Sparkles, ShoppingCart } from "lucide-react";
import type { Listing } from "agentvault-types";
import { formatUsdc } from "@/lib/format";

export function ListingCard({ listing }: { listing: Listing }) {
  return (
    <Card className="group hover:border-zinc-700 transition-colors">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <Badge variant="outline" className="font-mono text-xs">
            {listing.modelId}
          </Badge>
          <span className="text-xs text-zinc-500 font-mono">
            {listing.purchases} sold
          </span>
        </div>
        <Link href={`/listing/${listing.id}`}>
          <h3 className="text-lg font-semibold leading-snug group-hover:text-white transition-colors mt-2">
            {listing.title}
          </h3>
        </Link>
      </CardHeader>

      <CardContent className="space-y-3">
        <div className="grid grid-cols-3 gap-2">
          <Stat label="tokens" value={listing.seqLen.toLocaleString()} />
          <Stat label="precision" value={`${(listing.bitsPerChannel/10).toFixed(1)}b`} />
          <Stat label="size" value={`${listing.compressedMB.toFixed(0)}MB`} />
        </div>

        <div className="flex flex-wrap gap-1">
          {listing.tags.slice(0, 4).map((tag) => (
            <Badge key={tag} variant="secondary" className="text-xs">
              {tag}
            </Badge>
          ))}
          {listing.tags.length > 4 && (
            <Badge variant="secondary" className="text-xs">
              +{listing.tags.length - 4}
            </Badge>
          )}
        </div>
      </CardContent>

      <CardFooter className="flex gap-2">
        <SandboxButton listingId={listing.id} priceUsdc={listing.sandboxPriceUsdc} />
        <BuyButton listingId={listing.id} priceUsdc={listing.priceUsdc} />
      </CardFooter>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="font-mono text-sm">{value}</div>
      <div className="text-xs text-zinc-500">{label}</div>
    </div>
  );
}

function SandboxButton({ listingId, priceUsdc }: { listingId: string; priceUsdc: bigint }) {
  return (
    <Button variant="outline" size="sm" className="flex-1">
      <Sparkles className="w-3.5 h-3.5 mr-1.5" />
      Try · {formatUsdc(priceUsdc)}
    </Button>
  );
}

function BuyButton({ listingId, priceUsdc }: { listingId: string; priceUsdc: bigint }) {
  return (
    <Button size="sm" className="flex-1 bg-violet-600 hover:bg-violet-500">
      <ShoppingCart className="w-3.5 h-3.5 mr-1.5" />
      Buy · {formatUsdc(priceUsdc)}
    </Button>
  );
}
```

---

## 8. Sandbox modal — x402 handshake in the browser

```tsx
// components/listings/SandboxModal.tsx
"use client";

import { useState } from "react";
import { useConnection, useWallet } from "@solana/wallet-adapter-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Send, Loader2 } from "lucide-react";
import { x402Pay } from "@/lib/x402-client";
import { toast } from "sonner";

interface SandboxModalProps {
  listingId: string;
  listingTitle: string;
  priceUsdc: bigint;
  open: boolean;
  onClose: () => void;
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  txSig?: string;
}

export function SandboxModal({ listingId, listingTitle, priceUsdc, open, onClose }: SandboxModalProps) {
  const { connection } = useConnection();
  const wallet = useWallet();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [queriesRemaining, setQueriesRemaining] = useState<number | null>(null);

  async function handleSend() {
    if (!input.trim() || !wallet.publicKey || !wallet.signTransaction) return;

    setLoading(true);
    const userMsg = input;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: userMsg }]);

    try {
      // x402Pay handles the 402 response, payment, retry
      const response = await x402Pay({
        url: `${process.env.NEXT_PUBLIC_BACKEND_URL}/v1/sandbox/${listingId}`,
        body: { query: userMsg },
        wallet,
        connection,
      });

      const data = await response.json();
      setMessages((m) => [
        ...m,
        { role: "assistant", content: data.response, txSig: data.tx_signature },
      ]);
      setQueriesRemaining(data.queries_remaining);

      if (data.queries_remaining === 0) {
        toast.info("Sandbox quota exhausted. Buy full memory to continue.");
      }
    } catch (e: any) {
      toast.error(`Sandbox error: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Sandbox: {listingTitle}</DialogTitle>
          <p className="text-sm text-zinc-400">
            Pay-per-query at ${(Number(priceUsdc)/1_000_000).toFixed(2)} USDC each.
            {queriesRemaining !== null && ` ${queriesRemaining} queries remaining.`}
          </p>
        </DialogHeader>

        <div className="space-y-3 max-h-96 overflow-y-auto py-4">
          {messages.map((msg, i) => (
            <ChatBubble key={i} msg={msg} />
          ))}
          {loading && (
            <div className="flex items-center text-zinc-500 text-sm">
              <Loader2 className="w-4 h-4 animate-spin mr-2" />
              Paying via x402, loading memory, generating...
            </div>
          )}
        </div>

        <div className="flex gap-2">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="Ask the agent something..."
            disabled={loading}
          />
          <Button onClick={handleSend} disabled={loading || !input.trim()}>
            <Send className="w-4 h-4" />
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function ChatBubble({ msg }: { msg: ChatMessage }) {
  return (
    <div className={msg.role === "user" ? "ml-12" : "mr-12"}>
      <div className={`p-3 rounded-lg ${
        msg.role === "user" ? "bg-violet-950/40" : "bg-zinc-800"
      }`}>
        <pre className="text-sm whitespace-pre-wrap font-sans">{msg.content}</pre>
      </div>
      {msg.txSig && (
        <a
          href={`https://explorer.solana.com/tx/${msg.txSig}?cluster=devnet`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-zinc-500 hover:text-zinc-400 mt-1 inline-block font-mono"
        >
          tx: {msg.txSig.slice(0, 8)}...{msg.txSig.slice(-6)}
        </a>
      )}
    </div>
  );
}
```

---

## 9. x402 client wrapper

```typescript
// lib/x402-client.ts
import { Transaction, PublicKey } from "@solana/web3.js";
import { createX402Client } from "x402-solana/client";
import type { WalletContextState } from "@solana/wallet-adapter-react";
import type { Connection } from "@solana/web3.js";

interface X402PayParams {
  url: string;
  body: any;
  wallet: WalletContextState;
  connection: Connection;
  method?: "POST" | "GET";
}

export async function x402Pay({
  url,
  body,
  wallet,
  connection,
  method = "POST",
}: X402PayParams): Promise<Response> {
  if (!wallet.publicKey || !wallet.signTransaction) {
    throw new Error("Wallet not connected");
  }

  // First request — expect 402
  let response = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (response.status !== 402) {
    return response;  // No payment required
  }

  // Parse payment requirements
  const requirements = (await response.json()).accepts[0];

  // Use x402-solana client to construct + sign payment
  const client = createX402Client({
    wallet: {
      publicKey: wallet.publicKey,
      signTransaction: wallet.signTransaction,
    },
    network: "solana-devnet",
    connection,
  });

  // The client handles building the payment payload header
  const paidResponse = await client.fetch(url, {
    method,
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
  });

  return paidResponse;
}
```

---

## 10. Listing creation flow (the most complex page)

```tsx
// app/list/page.tsx
"use client";

import { useState } from "react";
import { ProgressStepper } from "@/components/list-form/ProgressStepper";
import { UploadDropzone } from "@/components/list-form/UploadDropzone";
import { MetadataForm } from "@/components/list-form/MetadataForm";
import { PricingPreview } from "@/components/list-form/PricingPreview";
import { ListingSubmission } from "@/components/list-form/ListingSubmission";
import { useUploadProgress } from "@/lib/hooks/useUploadProgress";

type Step = "upload" | "metadata" | "pricing" | "submit" | "done";

export default function ListPage() {
  const [step, setStep] = useState<Step>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [uploadId, setUploadId] = useState<string | null>(null);
  const [metadata, setMetadata] = useState({
    title: "",
    tags: [] as string[],
    priceUsdc: 25,
    sandboxPriceUsdc: 0.05,
  });

  const progress = useUploadProgress(uploadId);

  return (
    <div className="max-w-3xl mx-auto py-8 px-4">
      <h1 className="text-3xl font-bold mb-2">List your memory</h1>
      <p className="text-zinc-400 mb-8">
        Compress, anchor on Solana, and start earning when others use your trained agent context.
      </p>

      <ProgressStepper currentStep={step} />

      <div className="mt-8">
        {step === "upload" && (
          <UploadDropzone
            onFile={(f) => {
              setFile(f);
              setStep("metadata");
            }}
          />
        )}

        {step === "metadata" && file && (
          <MetadataForm
            file={file}
            metadata={metadata}
            onChange={setMetadata}
            onNext={() => setStep("pricing")}
            onBack={() => setStep("upload")}
          />
        )}

        {step === "pricing" && file && (
          <PricingPreview
            sizeBytes={file.size}
            metadata={metadata}
            onChange={setMetadata}
            onNext={async () => {
              const id = await initUpload(file, metadata);
              setUploadId(id);
              setStep("submit");
            }}
            onBack={() => setStep("metadata")}
          />
        )}

        {step === "submit" && uploadId && (
          <ListingSubmission
            uploadId={uploadId}
            file={file!}
            metadata={metadata}
            progress={progress}
            onComplete={() => setStep("done")}
          />
        )}

        {step === "done" && (
          <DoneScreen />
        )}
      </div>
    </div>
  );
}
```

The submission component uses the WebSocket from `useUploadProgress` to show:
1. Compressing... 0%-100%
2. Uploading to Arweave... 0%-100%
3. Listing on-chain... pending → confirmed
4. Done!

See `05_WEBSOCKET_DESIGN.md` for the WS contract.

---

## 11. The agent demo page (`/agent`)

This is the **most important page for the hackathon demo**. It's a live, scripted demo of the autonomous buyer agent in action.

```tsx
// app/agent/page.tsx
"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { useAgentStream } from "@/lib/hooks/useAgentStream";
import { Play, Pause, RotateCcw } from "lucide-react";

export default function AgentDemoPage() {
  const [task, setTask] = useState("Write a production Anchor PDA derivation function");
  const [running, setRunning] = useState(false);
  const stream = useAgentStream(running ? task : null);

  return (
    <div className="max-w-5xl mx-auto py-8 px-4">
      <header className="mb-8">
        <h1 className="text-4xl font-bold mb-2">Live Agent Demo</h1>
        <p className="text-zinc-400">
          Watch an autonomous agent discover, evaluate, purchase, and use trained memory — all on Solana.
        </p>
      </header>

      <Card className="p-6 mb-6">
        <label className="block text-sm text-zinc-400 mb-2">Task</label>
        <Input
          value={task}
          onChange={(e) => setTask(e.target.value)}
          disabled={running}
        />
        <div className="flex gap-2 mt-4">
          <Button onClick={() => setRunning(true)} disabled={running}>
            <Play className="w-4 h-4 mr-2" /> Run Agent
          </Button>
          <Button variant="outline" onClick={() => setRunning(false)} disabled={!running}>
            <Pause className="w-4 h-4 mr-2" /> Stop
          </Button>
          <Button variant="outline" onClick={() => { setRunning(false); }}>
            <RotateCcw className="w-4 h-4 mr-2" /> Reset
          </Button>
        </div>
      </Card>

      {/* Reasoning stream */}
      <Card className="p-6 mb-6 max-h-[600px] overflow-y-auto">
        <h2 className="text-xl font-semibold mb-4">Agent Reasoning</h2>
        {stream.events.map((event, i) => (
          <AgentEvent key={i} event={event} />
        ))}
      </Card>

      {/* Final output */}
      {stream.result && (
        <Card className="p-6 border-green-700">
          <h2 className="text-xl font-semibold mb-2 text-green-400">Result</h2>
          <pre className="text-sm whitespace-pre-wrap">{stream.result}</pre>
        </Card>
      )}
    </div>
  );
}
```

The `useAgentStream` hook subscribes to a WebSocket from the buyer agent service that emits events as the agent makes decisions. See `06_BUYER_AGENT.md`.

---

## 12. Landing page

```tsx
// app/page.tsx
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ArrowRight, Database, Lock, Activity } from "lucide-react";

export default function LandingPage() {
  return (
    <main>
      {/* Hero */}
      <section className="relative px-6 py-24 md:py-40">
        <div className="max-w-5xl mx-auto text-center">
          <h1 className="text-5xl md:text-7xl font-bold tracking-tight mb-6">
            Persistent memory for{" "}
            <span className="bg-gradient-to-r from-violet-400 to-emerald-400 bg-clip-text text-transparent">
              autonomous Solana agents
            </span>
          </h1>
          <p className="text-xl text-zinc-400 max-w-2xl mx-auto mb-10">
            AgentVault makes AI agent memory ownable, transferable, and verifiable.
            TurboQuant-compressed KV cache, anchored on Solana, served on Arweave.
          </p>
          <div className="flex gap-4 justify-center">
            <Button size="lg" asChild>
              <Link href="/browse">
                Browse memories <ArrowRight className="w-4 h-4 ml-2" />
              </Link>
            </Button>
            <Button size="lg" variant="outline" asChild>
              <Link href="/agent">See live agent demo</Link>
            </Button>
          </div>
        </div>
      </section>

      {/* Three pillars */}
      <section className="px-6 py-16 border-t border-zinc-800">
        <div className="max-w-5xl mx-auto grid md:grid-cols-3 gap-8">
          <Pillar
            icon={Database}
            title="Audit Trail"
            description="DAO treasury agents commit decision context on-chain. Immutable, queryable, transferable."
          />
          <Pillar
            icon={Lock}
            title="Cold Start Elimination"
            description="Senior agents sell their learned protocol context. New agents skip days of training."
          />
          <Pillar
            icon={Activity}
            title="Memory Marketplace"
            description="Trained agent memory becomes a tradeable asset. Buy expertise; sell what you've taught."
          />
        </div>
      </section>

      {/* Stack diagram */}
      <section className="px-6 py-16 border-t border-zinc-800">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-3xl font-bold mb-8 text-center">The missing layer</h2>
          <StackDiagram />
        </div>
      </section>
    </main>
  );
}

function Pillar({ icon: Icon, title, description }: any) {
  return (
    <div>
      <Icon className="w-6 h-6 mb-4 text-violet-400" />
      <h3 className="text-xl font-semibold mb-2">{title}</h3>
      <p className="text-zinc-400 leading-relaxed">{description}</p>
    </div>
  );
}
```

---

## 13. Setup commands

```bash
cd frontend

# Bootstrap
npx create-next-app@latest . \
  --typescript --tailwind --app \
  --no-src-dir --import-alias "@/*"

# shadcn
npx shadcn@latest init -d
npx shadcn@latest add button card badge input dialog tabs progress \
                       select tooltip toast sonner skeleton

# Solana
npm install @solana/web3.js @solana/wallet-adapter-base \
            @solana/wallet-adapter-react @solana/wallet-adapter-react-ui \
            @solana/wallet-adapter-wallets @solana/spl-token \
            @coral-xyz/anchor

# x402
npm install x402-solana

# State + utility
npm install @tanstack/react-query @tanstack/react-query-devtools \
            framer-motion sonner react-dropzone \
            zod react-hook-form @hookform/resolvers \
            lucide-react clsx tailwind-merge \
            class-variance-authority

# Workspace types
npm link ../shared/types
```

---

## 14. Environment variables

```bash
# .env.local.example

NEXT_PUBLIC_BACKEND_URL=https://api.agentvault.xyz
NEXT_PUBLIC_AGENT_WS_URL=wss://agent.agentvault.xyz/ws
NEXT_PUBLIC_RPC_URL=https://api.devnet.solana.com
NEXT_PUBLIC_NETWORK=devnet

NEXT_PUBLIC_PROGRAM_ID=AgntV1tXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
NEXT_PUBLIC_USDC_MINT=4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU
```

---

## 15. Vercel deployment

```bash
# Install Vercel CLI (one time)
npm i -g vercel

# Link project
vercel link

# Deploy
vercel --prod
```

Vercel auto-detects Next.js. Just set the env vars from `.env.local.example` in the Vercel dashboard.

For preview deploys on PRs, connect the GitHub repo and Vercel does it automatically.

---

## 16. Claude Code prompt — paste this verbatim

````
You are building the AgentVault frontend — a Next.js 15 marketplace UI for AI agent memory on Solana. This is what hackathon judges see, so it has to look like a real product, not a hackathon demo.

## Read the spec
Open `docs/04_FRONTEND.md` and read everything. The spec covers: page structure, components, visual style, wallet integration, x402 client, listing flow, and the live agent demo page.

Also read `docs/05_WEBSOCKET_DESIGN.md` for the WS hooks (useUploadProgress, useAgentStream).

## Hard requirements
- Next.js 15 with App Router
- React 19, Tailwind v4
- shadcn/ui components (don't build custom button/card/etc.)
- Solana wallet adapter with Phantom + Solflare + Backpack
- TanStack Query for all API state
- Visual style EXACTLY as section 5 specifies: zinc-950 background, Inter for UI, JetBrains Mono for hashes, no emoji clutter
- All hash/address displays use the `<HashDisplay />` and `<PubkeyDisplay />` components with truncation + click-to-copy + explorer link
- All prices displayed via `formatUsdc()` helper

## Build order
1. `app/providers.tsx` — wallet, query, toast providers
2. `app/layout.tsx` — root layout with providers, fonts, top nav
3. `lib/api.ts` — typed fetch wrapper for backend
4. `lib/format.ts` — formatUsdc, truncatePubkey, formatTimestamp helpers
5. `components/shared/PubkeyDisplay.tsx`, `HashDisplay.tsx`, `PriceTag.tsx` — reusable display primitives
6. `components/wallet/WalletButton.tsx` — connect/disconnect/balance display
7. `components/nav/TopNav.tsx`, `Footer.tsx`
8. `lib/hooks/useListings.ts`, `useListing.ts` — TanStack Query hooks
9. `components/listings/ListingCard.tsx` — the unit of UI
10. `app/browse/page.tsx` — listing grid with filters
11. `app/listing/[id]/page.tsx` — single listing detail
12. `lib/x402-client.ts` — wallet-signing wrapper for x402
13. `components/listings/SandboxModal.tsx` — chat UI for sandbox previews
14. `lib/hooks/useUploadProgress.ts` — WS hook for upload progress
15. `app/list/page.tsx` + `components/list-form/*` — multi-step listing creation
16. `app/dashboard/*` — user's listings, purchases, earnings
17. `lib/hooks/useAgentStream.ts` + `app/agent/page.tsx` — live agent demo
18. `app/page.tsx` — landing
19. Polish: animations, empty states, loading skeletons

## Critical implementation notes
- The wallet adapter requires the CSS import: `require("@solana/wallet-adapter-react-ui/styles.css")`
- USDC has 6 decimals; always use bigint for prices, format on display
- TanStack Query key naming: `["listings", filters]`, `["listing", id]`, `["user-listings", pubkey]`
- All Solana txs go through `wallet.signTransaction` then `connection.sendRawTransaction` — never expose private keys
- Don't validate prices client-side; always fetch from `/v1/pricing?size_bytes=X`
- Use `next/dynamic` with `ssr: false` for any wallet-dependent components

## Common pitfalls
- "window is not defined" — wrap wallet components with `dynamic(() => ..., { ssr: false })`
- Hydration mismatch — use `suppressHydrationWarning` on time-sensitive elements (timestamps)
- Wallet adapter sometimes needs `ConnectionProvider` to be ABOVE `WalletProvider` (it is in the spec, follow exactly)
- Long hashes don't wrap properly without `break-all` or truncation

## Visual polish (judges notice this)
- Cards lift on hover (transition-all duration-200, hover:border-zinc-700)
- Tab switches use Framer Motion fade
- Empty states have a Lucide icon, helpful text, and a CTA button
- Loading: shadcn Skeleton components, never blank
- Toast notifications via sonner for all wallet/tx feedback

## Test
After building each page:
```bash
npm run dev
```
Connect Phantom (with devnet enabled), browse listings (mock data first, then real from backend).

For deployment:
```bash
npm run build
vercel --prod
```

Build it. Polish it. The frontend is the demo's face.
````

---

## 17. Definition of done

- [ ] All 6 routes implemented and styled
- [ ] Wallet connection works with Phantom (test on devnet)
- [ ] Browse page shows listings from backend with filtering
- [ ] Listing detail page shows full memory metadata
- [ ] Sandbox modal handles 402 → x402 payment → 200 flow
- [ ] List page completes full flow: upload → metadata → pricing → submit → confirmation
- [ ] WebSocket progress updates display in listing submission
- [ ] Dashboard shows user's listings, purchases, earnings
- [ ] Agent demo page streams live reasoning events
- [ ] Landing page is polished and persuasive
- [ ] All hash/pubkey displays use shared component with truncation
- [ ] Lighthouse mobile score ≥85
- [ ] Deployed to Vercel with environment variables set
- [ ] Custom domain configured (optional but nice)

When this list is checked, the demo is recordable and the submission UI is judge-ready.

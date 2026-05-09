# 06 — Buyer Agent (Autonomous purchaser)

**Where:** `buyer-agent/`
**Stack:** TypeScript + Node 20+ + Solana Agent Kit + x402-solana + Anchor client
**Deploy target:** Local for demo / Optional: Railway service for the `/agent` page on frontend
**Build third or fourth:** After Solana program + backend + WS layer; before final frontend polish

---

## 1. Why this component is critical

The hackathon judging weights are 40% Innovation / **30% Agentic Sophistication** / 30% Traction. The Agentic Sophistication score is won here. The reviewer feedback was explicit: *"You need an agent that USES the memory autonomously, not just a pipeline that stores it."*

This component is the demo. Everything else exists to support it. It must:

- Make decisions without human intervention (task → action)
- Pay for things using x402 (no human signing)
- Verify cryptographic guarantees (hash check on Arweave fetch)
- Use the runtime (load expert memory, produce expert output)
- Look beautiful while doing it (live narration over websocket)

If the buyer agent runs in <60 seconds end-to-end on demo day, you win the Agentic Sophistication category.

---

## 2. The agent's job, broken into phases

```
INPUT: A task description (string)

PHASE 1: CLASSIFY
  - LLM call: extract tags from task
  - Output: tags[], task_complexity_estimate

PHASE 2: DISCOVER
  - Backend API: GET /v1/listings?tags=...
  - Output: 5 candidate listings

PHASE 3: EVALUATE
  - For top 3 candidates:
    - Construct a diagnostic probe query for the task domain
    - x402-pay for sandbox query
    - Score the response (LLM-judge)
  - Output: ranked candidates with scores

PHASE 4: DECIDE
  - Apply budget constraint
  - Pick highest-score affordable listing
  - Output: winner_listing

PHASE 5: PURCHASE
  - Solana tx: buy_memory(winner_listing)
  - Wait for confirmation
  - Output: license PDA, tx signature

PHASE 6: FETCH
  - Read listing.arweave_tx
  - GET arweave.net/{tx}
  - Verify SHA-256(blob) == listing.content_hash
  - Output: verified compressed blob

PHASE 7: LOAD
  - POST /worker/decompress (TurboQuant worker)
  - Load decompressed cache into vLLM via LMCache
  - Output: cache_id

PHASE 8: EXECUTE
  - POST /worker/inference with cache_id and original task
  - Stream tokens back
  - Output: final response

OUTPUT: { task, response, memory_used, total_cost_usdc, duration_ms, tx_signatures[] }
```

Every phase emits an event over the agent WebSocket channel. The frontend `/agent` page shows the agent's "thinking" live.

---

## 3. File structure

```
buyer-agent/
├── package.json
├── tsconfig.json
├── .env.example
├── src/
│   ├── index.ts                    # CLI entry (npm run agent -- "task")
│   ├── server.ts                   # HTTP server (POST /v1/agent/runs) for frontend integration
│   │
│   ├── agent.ts                    # Main MemoryShoppingAgent class
│   │
│   ├── reasoning/
│   │   ├── classifier.ts           # Task → tags
│   │   ├── probe_generator.ts      # Task → diagnostic query
│   │   ├── evaluator.ts            # Sandbox response → quality score
│   │   ├── decision.ts             # Score + budget → winner
│   │   └── llm_client.ts           # Anthropic/OpenAI wrapper
│   │
│   ├── solana/
│   │   ├── client.ts               # AnchorProvider + Program
│   │   ├── listings.ts             # findListings, getListing
│   │   ├── purchase.ts             # buyMemory transaction
│   │   ├── pdas.ts                 # PDA derivation
│   │   └── usdc.ts                 # Get/check USDC balance
│   │
│   ├── x402/
│   │   ├── client.ts               # x402-solana wrapper for sandbox calls
│   │   └── types.ts
│   │
│   ├── arweave/
│   │   ├── fetcher.ts              # Download + hash verify
│   │   └── progress.ts             # Track download progress
│   │
│   ├── runtime/
│   │   ├── worker_client.ts        # Talk to TurboQuant worker (decompress + inference)
│   │   └── streaming.ts            # SSE/WS stream from worker
│   │
│   ├── narrator/
│   │   ├── stdout.ts               # Pretty terminal log (chalk + boxen)
│   │   ├── ws_publisher.ts         # Publish to backend WS channel for frontend
│   │   └── types.ts                # Shared event types (matches doc 05)
│   │
│   ├── config.ts                   # env config
│   └── types.ts                    # TaskResult, Listing, etc.
│
└── tests/
    ├── agent.test.ts
    ├── classifier.test.ts
    ├── evaluator.test.ts
    └── e2e.test.ts                 # Mock backend + Solana, run full agent
```

---

## 4. Dependencies

```json
{
  "name": "agentvault-buyer-agent",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "tsx watch src/index.ts",
    "agent": "tsx src/index.ts",
    "server": "tsx src/server.ts",
    "build": "tsc",
    "test": "vitest run"
  },
  "dependencies": {
    "@solana/web3.js": "^1.95.0",
    "@solana/spl-token": "^0.4.0",
    "@coral-xyz/anchor": "^0.30.1",
    "solana-agent-kit": "^1.4.0",

    "x402-solana": "^0.2.0",

    "@anthropic-ai/sdk": "^0.32.0",
    "openai": "^4.65.0",

    "fastify": "^5.0.0",
    "@fastify/websocket": "^11.0.0",
    "ws": "^8.18.0",

    "chalk": "^5.3.0",
    "boxen": "^7.1.0",
    "ora": "^8.1.0",

    "axios": "^1.7.0",
    "p-retry": "^6.2.0",
    "zod": "^3.23.0",
    "bs58": "^6.0.0",

    "agentvault-types": "workspace:*"
  },
  "devDependencies": {
    "typescript": "^5.6.0",
    "@types/node": "^22.0.0",
    "@types/ws": "^8.5.0",
    "tsx": "^4.19.0",
    "vitest": "^2.1.0"
  }
}
```

---

## 5. The MemoryShoppingAgent class — the centerpiece

```typescript
// src/agent.ts
import { Connection, Keypair, PublicKey } from "@solana/web3.js";
import { SolanaAgentKit } from "solana-agent-kit";
import { AgentVaultClient } from "./solana/client";
import { X402Client } from "./x402/client";
import { fetchFromArweave } from "./arweave/fetcher";
import { WorkerClient } from "./runtime/worker_client";
import { Narrator } from "./narrator/types";
import { classifyTask } from "./reasoning/classifier";
import { generateProbe } from "./reasoning/probe_generator";
import { evaluateResponse } from "./reasoning/evaluator";
import { pickWinner } from "./reasoning/decision";
import { sha256, hexEqual } from "./util/crypto";
import type { Listing, TaskResult, AgentRunOptions } from "./types";

export class MemoryShoppingAgent {
  constructor(
    private opts: AgentRunOptions,
    private narrator: Narrator,
    private avc: AgentVaultClient,
    private x402: X402Client,
    private worker: WorkerClient,
  ) {}

  async run(task: string): Promise<TaskResult> {
    const startedAt = Date.now();
    const txSignatures: string[] = [];
    let totalCostUsdc = 0;

    this.narrator.start({ task, budget_usdc: this.opts.maxBudgetUsdc });

    try {
      // ────── PHASE 1: CLASSIFY ──────
      const classified = await classifyTask(task, this.opts.llm);
      this.narrator.classify(classified);

      // ────── PHASE 2: DISCOVER ──────
      const candidates = await this.avc.findListings({
        tags: classified.tags,
        modelId: this.opts.preferredModelId,
        activeOnly: true,
        limit: 5,
      });
      this.narrator.discover(candidates);

      if (candidates.length === 0) {
        return this.failResult(task, "no_candidates", startedAt, txSignatures, totalCostUsdc);
      }

      // ────── PHASE 3: EVALUATE ──────
      const probe = await generateProbe(task, classified.tags, this.opts.llm);
      const top = candidates.slice(0, 3);
      const scored: Array<{ listing: Listing; score: number; response: string; tx: string }> = [];

      for (const listing of top) {
        try {
          this.narrator.sandboxStart({ listing_id: listing.address, query: probe });

          // x402-pay for sandbox
          const result = await this.x402.fetch({
            url: `${this.opts.backendUrl}/v1/sandbox/${listing.address}`,
            method: "POST",
            body: { query: probe },
          });

          this.narrator.sandboxX402({
            listing_id: listing.address,
            tx_signature: result.txSignature,
            amount_usdc: Number(listing.sandboxPriceUsdc),
          });

          totalCostUsdc += Number(listing.sandboxPriceUsdc);
          txSignatures.push(result.txSignature);

          // Score the response
          const score = await evaluateResponse({
            task,
            probe,
            response: result.response,
            llm: this.opts.llm,
          });

          this.narrator.sandboxResponse({
            listing_id: listing.address,
            response: result.response,
            score,
          });

          scored.push({
            listing,
            score,
            response: result.response,
            tx: result.txSignature,
          });
        } catch (e: any) {
          this.narrator.warn(`sandbox failed for ${listing.title}: ${e.message}`);
        }
      }

      if (scored.length === 0) {
        return this.failResult(task, "all_sandboxes_failed", startedAt, txSignatures, totalCostUsdc);
      }

      // ────── PHASE 4: DECIDE ──────
      const winner = pickWinner(scored, {
        maxBudgetUsdc: this.opts.maxBudgetUsdc * 1_000_000 - totalCostUsdc,
      });

      if (!winner) {
        return this.failResult(task, "over_budget", startedAt, txSignatures, totalCostUsdc);
      }

      this.narrator.decision({
        winner_id: winner.listing.address,
        reasoning: `score ${winner.score.toFixed(2)} at ${Number(winner.listing.priceUsdc) / 1_000_000} USDC`,
        score: winner.score,
      });

      // ────── PHASE 5: PURCHASE ──────
      this.narrator.purchaseSigning({ listing_id: winner.listing.address });
      const purchase = await this.avc.buyMemory(winner.listing.address);
      txSignatures.push(purchase.txSignature);
      totalCostUsdc += Number(winner.listing.priceUsdc);
      this.narrator.purchaseConfirmed({
        tx_signature: purchase.txSignature,
        license_pda: purchase.licensePda,
      });

      // ────── PHASE 6: FETCH ──────
      const blob = await fetchFromArweave(winner.listing.arweaveTx, (bytes) => {
        this.narrator.fetchProgress(bytes);
      });
      this.narrator.fetchDone({
        arweave_tx: winner.listing.arweaveTx,
        bytes: blob.length,
      });

      // ────── HASH VERIFY ──────
      const actualHashHex = sha256(blob);
      const expectedHashHex = winner.listing.contentHashHex;
      const verified = hexEqual(actualHashHex, expectedHashHex);
      this.narrator.verifyHash({
        hash_hex: actualHashHex,
        verified,
      });

      if (!verified) {
        throw new Error(`Hash mismatch — Arweave returned tampered blob! expected ${expectedHashHex}, got ${actualHashHex}`);
      }

      // ────── PHASE 7: LOAD ──────
      const loadStart = Date.now();
      const cacheId = await this.worker.decompressAndLoad({
        blob,
        metadata: winner.listing.metadata,
        modelId: winner.listing.modelId,
      });
      this.narrator.decompress({
        decompressed_size_mb: this.estimateDecompressedSize(blob.length, winner.listing.metadata),
        load_time_ms: Date.now() - loadStart,
      });

      // ────── PHASE 8: EXECUTE ──────
      this.narrator.executeStart({ prompt: task });
      const tokens: string[] = [];
      const response = await this.worker.inferenceStream({
        cache_id: cacheId,
        prompt: task,
        max_tokens: 500,
        on_token: (tok) => {
          tokens.push(tok);
          this.narrator.executeToken(tok);
        },
      });
      this.narrator.executeDone({
        output: response,
        total_tokens: tokens.length,
      });

      // ────── DONE ──────
      const durationMs = Date.now() - startedAt;
      this.narrator.complete({
        total_cost_usdc: totalCostUsdc / 1_000_000,
        duration_ms: durationMs,
      });

      return {
        status: "success",
        task,
        response,
        memoryUsed: winner.listing.title,
        totalCostUsdc: totalCostUsdc / 1_000_000,
        durationMs,
        txSignatures,
      };
    } catch (e: any) {
      this.narrator.error({ phase: "unknown", error: e.message });
      return this.failResult(task, e.message, startedAt, txSignatures, totalCostUsdc);
    }
  }

  private failResult(
    task: string,
    reason: string,
    startedAt: number,
    txSigs: string[],
    cost: number,
  ): TaskResult {
    return {
      status: "failure",
      task,
      reason,
      durationMs: Date.now() - startedAt,
      txSignatures: txSigs,
      totalCostUsdc: cost / 1_000_000,
    };
  }

  private estimateDecompressedSize(compressedBytes: number, metadata: any): number {
    // Rough estimate — TurboQuant typically gets 4-5x compression
    return (compressedBytes * 4.5) / (1024 * 1024);
  }
}
```

---

## 6. Phase implementations

### 6.1 Classifier

```typescript
// src/reasoning/classifier.ts
import type { LLMClient } from "./llm_client";

export interface ClassifiedTask {
  tags: string[];
  domain: string;        // "defi" | "governance" | "code-generation" | ...
  complexity: "simple" | "moderate" | "complex";
}

const SYSTEM = `You classify AI agent tasks. Output JSON:
{
  "tags": ["string", ...],     // 3-7 short, lowercase, hyphen-separated terms
  "domain": "string",          // single category
  "complexity": "simple" | "moderate" | "complex"
}

Examples:
Task: "Write a production Anchor PDA derivation function"
{"tags":["anchor","solana","rust","pda","program-derived-address"],"domain":"code-generation","complexity":"moderate"}

Task: "Should we vote yes on MIP-12?"
{"tags":["dao","governance","mango","voting","proposal-analysis"],"domain":"governance","complexity":"complex"}

Output ONLY the JSON, no prose.`;

export async function classifyTask(task: string, llm: LLMClient): Promise<ClassifiedTask> {
  const result = await llm.complete({
    system: SYSTEM,
    user: task,
    maxTokens: 200,
    responseFormat: "json",
  });
  return JSON.parse(result);
}
```

### 6.2 Probe generator

```typescript
// src/reasoning/probe_generator.ts
export async function generateProbe(
  task: string,
  tags: string[],
  llm: LLMClient,
): Promise<string> {
  const result = await llm.complete({
    system: `Given a task, generate a SHORT diagnostic probe query (1-2 sentences) that tests whether an AI agent has expertise in this domain. The probe should be answerable in 100 tokens. The probe should reveal expertise depth — surface answers should differ from expert answers.`,
    user: `Task: ${task}\nTags: ${tags.join(", ")}\n\nProbe:`,
    maxTokens: 100,
  });
  return result.trim();
}
```

### 6.3 Evaluator

```typescript
// src/reasoning/evaluator.ts
export interface EvalInput {
  task: string;
  probe: string;
  response: string;
  llm: LLMClient;
}

export async function evaluateResponse(input: EvalInput): Promise<number> {
  const result = await input.llm.complete({
    system: `You evaluate agent responses. Score from 0.0 to 1.0 based on:
- Technical accuracy (40%)
- Domain expertise depth (30%)
- Specificity vs generic (20%)
- Code quality if applicable (10%)

Output ONLY the score as a number, e.g., "0.87"`,
    user: `Original task: ${input.task}\nProbe: ${input.probe}\nResponse: ${input.response}\n\nScore:`,
    maxTokens: 10,
  });

  const score = parseFloat(result.trim());
  if (isNaN(score) || score < 0 || score > 1) {
    return 0.5; // Fallback
  }
  return score;
}
```

### 6.4 Decision

```typescript
// src/reasoning/decision.ts
import type { Listing } from "../types";

export interface ScoredCandidate {
  listing: Listing;
  score: number;
  response: string;
  tx: string;
}

export interface DecisionConstraints {
  maxBudgetUsdc: number;       // remaining budget in micro-USDC
  minScore?: number;           // floor score (default 0.5)
}

export function pickWinner(
  scored: ScoredCandidate[],
  constraints: DecisionConstraints,
): ScoredCandidate | null {
  const minScore = constraints.minScore ?? 0.5;

  const eligible = scored.filter((s) =>
    s.score >= minScore && Number(s.listing.priceUsdc) <= constraints.maxBudgetUsdc
  );

  if (eligible.length === 0) return null;

  // Sort by score desc, break ties by lower price
  eligible.sort((a, b) => {
    if (Math.abs(a.score - b.score) > 0.05) return b.score - a.score;
    return Number(a.listing.priceUsdc) - Number(b.listing.priceUsdc);
  });

  return eligible[0];
}
```

### 6.5 LLM client (Anthropic by default)

```typescript
// src/reasoning/llm_client.ts
import Anthropic from "@anthropic-ai/sdk";

export interface LLMCompleteParams {
  system: string;
  user: string;
  maxTokens?: number;
  responseFormat?: "text" | "json";
}

export interface LLMClient {
  complete(params: LLMCompleteParams): Promise<string>;
}

export function createAnthropicClient(apiKey: string, model = "claude-sonnet-4"): LLMClient {
  const client = new Anthropic({ apiKey });
  return {
    async complete(params) {
      const result = await client.messages.create({
        model,
        max_tokens: params.maxTokens ?? 1000,
        system: params.system,
        messages: [{ role: "user", content: params.user }],
      });
      const text = result.content.filter((b) => b.type === "text").map((b: any) => b.text).join("");
      return text;
    },
  };
}
```

---

## 7. Solana client wrapper

```typescript
// src/solana/client.ts
import { AnchorProvider, Program, BN } from "@coral-xyz/anchor";
import { Connection, Keypair, PublicKey, Transaction } from "@solana/web3.js";
import { TOKEN_PROGRAM_ID, getAssociatedTokenAddress } from "@solana/spl-token";
import idl from "agentvault-types/idl.json";
import type { Listing } from "../types";

const PROGRAM_ID = new PublicKey(process.env.AGENTVAULT_PROGRAM_ID!);

export class AgentVaultClient {
  program: Program;
  provider: AnchorProvider;

  constructor(connection: Connection, wallet: Keypair) {
    const anchorWallet = {
      publicKey: wallet.publicKey,
      signTransaction: async (tx: Transaction) => { tx.partialSign(wallet); return tx; },
      signAllTransactions: async (txs: Transaction[]) => { txs.forEach((tx) => tx.partialSign(wallet)); return txs; },
    };
    this.provider = new AnchorProvider(connection, anchorWallet as any, { commitment: "confirmed" });
    this.program = new Program(idl as any, PROGRAM_ID, this.provider);
  }

  async findListings(filters: {
    tags?: string[];
    modelId?: string;
    activeOnly?: boolean;
    limit?: number;
  }): Promise<Listing[]> {
    // For hackathon: query backend API which has indexed listings
    // (raw on-chain getProgramAccounts is too slow + no tag filtering)
    const url = new URL(`${process.env.BACKEND_URL}/v1/listings`);
    if (filters.tags) url.searchParams.set("tags", filters.tags.join(","));
    if (filters.modelId) url.searchParams.set("model", filters.modelId);
    if (filters.activeOnly) url.searchParams.set("active", "true");
    if (filters.limit) url.searchParams.set("limit", String(filters.limit));

    const resp = await fetch(url.toString());
    const data = await resp.json();
    return data.items.map(this.parseListing);
  }

  async getListing(address: string): Promise<Listing> {
    const account = await this.program.account.memoryListing.fetch(new PublicKey(address));
    return this.parseListing({ address, ...account });
  }

  async buyMemory(listingAddress: string): Promise<{ txSignature: string; licensePda: string }> {
    const listing = new PublicKey(listingAddress);
    const buyer = this.provider.wallet.publicKey;
    const usdcMint = new PublicKey(process.env.USDC_MINT!);

    // Derive license PDA
    const [licensePda] = PublicKey.findProgramAddressSync(
      [Buffer.from("license"), buyer.toBuffer(), listing.toBuffer()],
      PROGRAM_ID,
    );

    // Derive ATAs
    const buyerAta = await getAssociatedTokenAddress(usdcMint, buyer);
    const listingAccount = await this.program.account.memoryListing.fetch(listing);
    const sellerAta = await getAssociatedTokenAddress(usdcMint, listingAccount.seller);
    const treasuryAta = await getAssociatedTokenAddress(
      usdcMint,
      new PublicKey(process.env.PLATFORM_TREASURY!),
    );

    const [configPda] = PublicKey.findProgramAddressSync(
      [Buffer.from("config")],
      PROGRAM_ID,
    );

    const txSig = await this.program.methods
      .buyMemory()
      .accounts({
        buyer,
        listing,
        license: licensePda,
        buyerUsdcAta: buyerAta,
        sellerUsdcAta: sellerAta,
        treasuryUsdcAta: treasuryAta,
        usdcMint,
        platformConfig: configPda,
        tokenProgram: TOKEN_PROGRAM_ID,
        systemProgram: PublicKey.default,
      })
      .rpc();

    return { txSignature: txSig, licensePda: licensePda.toBase58() };
  }

  private parseListing(raw: any): Listing {
    return {
      address: raw.address,
      seller: raw.seller.toString?.() ?? raw.seller,
      title: raw.title,
      modelId: raw.modelId,
      tags: raw.tags,
      priceUsdc: BigInt(raw.priceUsdc.toString()),
      sandboxPriceUsdc: BigInt(raw.sandboxPriceUsdc.toString()),
      arweaveTx: raw.arweaveTx,
      contentHashHex: Buffer.from(raw.contentHash).toString("hex"),
      seqLen: raw.seqLen,
      bitsPerChannel: raw.bitsPerChannel,
      purchases: Number(raw.purchases),
      metadata: {
        seed: Number(raw.quantSeed),
        bits: raw.bitsPerChannel / 10,
        seq_len: raw.seqLen,
        model_id: raw.modelId,
      },
    };
  }
}
```

---

## 8. x402 client

```typescript
// src/x402/client.ts
import { createX402Client } from "x402-solana/client";
import type { Connection, Keypair } from "@solana/web3.js";

export interface X402FetchParams {
  url: string;
  method?: string;
  body?: any;
}

export interface X402FetchResult {
  response: string;
  txSignature: string;
  queriesRemaining?: number;
}

export class X402Client {
  private inner;

  constructor(connection: Connection, wallet: Keypair) {
    this.inner = createX402Client({
      wallet: {
        publicKey: wallet.publicKey,
        signTransaction: async (tx: any) => { tx.partialSign(wallet); return tx; },
      },
      network: "solana-devnet",
      connection,
    });
  }

  async fetch(params: X402FetchParams): Promise<X402FetchResult> {
    const resp = await this.inner.fetch(params.url, {
      method: params.method ?? "POST",
      headers: { "Content-Type": "application/json" },
      body: params.body ? JSON.stringify(params.body) : undefined,
    });

    if (!resp.ok) {
      throw new Error(`x402 fetch failed: ${resp.status} ${await resp.text()}`);
    }

    const data = await resp.json();
    return {
      response: data.response,
      txSignature: data.tx_signature,
      queriesRemaining: data.queries_remaining,
    };
  }
}
```

---

## 9. Arweave fetcher with progress + verify

```typescript
// src/arweave/fetcher.ts
import axios from "axios";
import { createHash } from "node:crypto";

export async function fetchFromArweave(
  arweaveTx: string,
  onProgress: (bytes: number) => void,
): Promise<Buffer> {
  const url = `https://arweave.net/${arweaveTx}`;
  const resp = await axios.get(url, {
    responseType: "arraybuffer",
    onDownloadProgress: (e) => onProgress(e.loaded),
    timeout: 300_000, // 5 min for large blobs
  });
  return Buffer.from(resp.data);
}

export function sha256Hex(buf: Buffer): string {
  return createHash("sha256").update(buf).digest("hex");
}

export function verifyContentHash(blob: Buffer, expectedHashHex: string): boolean {
  return sha256Hex(blob) === expectedHashHex.toLowerCase();
}
```

---

## 10. Worker client

```typescript
// src/runtime/worker_client.ts
import axios from "axios";

export interface DecompressLoadParams {
  blob: Buffer;
  metadata: any;
  modelId: string;
}

export interface InferenceStreamParams {
  cache_id: string;
  prompt: string;
  max_tokens: number;
  on_token: (token: string) => void;
}

export class WorkerClient {
  constructor(
    private workerUrl: string,
    private apiKey: string,
  ) {}

  async decompressAndLoad(params: DecompressLoadParams): Promise<string> {
    // Send compressed blob + metadata to worker
    const form = new FormData();
    form.append("blob", new Blob([params.blob]));
    form.append("metadata", JSON.stringify(params.metadata));
    form.append("model_id", params.modelId);

    const resp = await axios.post(`${this.workerUrl}/decompress_and_load`, form, {
      headers: { "X-API-Key": this.apiKey },
      timeout: 120_000,
    });
    return resp.data.cache_id;
  }

  async inferenceStream(params: InferenceStreamParams): Promise<string> {
    // Use SSE for token-by-token streaming
    const resp = await fetch(`${this.workerUrl}/inference_stream`, {
      method: "POST",
      headers: {
        "X-API-Key": this.apiKey,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        cache_id: params.cache_id,
        prompt: params.prompt,
        max_tokens: params.max_tokens,
      }),
    });

    const reader = resp.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let full = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE: split on \n\n
      const events = buffer.split("\n\n");
      buffer = events.pop() ?? "";

      for (const event of events) {
        const line = event.split("\n").find((l) => l.startsWith("data: "));
        if (!line) continue;
        const data = JSON.parse(line.slice(6));
        if (data.type === "token") {
          params.on_token(data.token);
          full += data.token;
        } else if (data.type === "done") {
          return data.output ?? full;
        }
      }
    }

    return full;
  }
}
```

---

## 11. Narrator (the part judges actually see)

The narrator has two backends: **stdout** (for terminal demos) and **WebSocket publisher** (for the frontend `/agent` page).

### Stdout narrator

```typescript
// src/narrator/stdout.ts
import chalk from "chalk";
import boxen from "boxen";
import ora, { Ora } from "ora";
import type { Narrator, Listing } from "./types";

export function createStdoutNarrator(): Narrator {
  let activeSpinner: Ora | null = null;

  function stop() {
    if (activeSpinner) {
      activeSpinner.stop();
      activeSpinner = null;
    }
  }

  return {
    start({ task, budget_usdc }) {
      console.log("\n" + boxen(chalk.bold.cyan("Memory Shopping Agent"), {
        padding: 1, borderStyle: "round", borderColor: "cyan",
      }));
      console.log(chalk.yellow("Task:") + " " + task);
      console.log(chalk.dim(`Budget: $${budget_usdc} USDC\n`));
    },

    classify({ tags, domain }) {
      console.log(chalk.green("→") + " Classified");
      console.log(chalk.dim(`    domain: ${domain}`));
      console.log(chalk.dim(`    tags: [${tags.join(", ")}]\n`));
    },

    discover(candidates: Listing[]) {
      console.log(chalk.green("→") + ` Found ${candidates.length} candidates`);
      candidates.forEach((c, i) => {
        console.log(chalk.dim(`    ${i + 1}. ${c.title.padEnd(40)} $${(Number(c.priceUsdc) / 1e6).toFixed(2).padStart(6)} • ${c.purchases} sold`));
      });
      console.log();
    },

    sandboxStart({ listing_id, query }) {
      stop();
      activeSpinner = ora(chalk.dim(`Sandbox: ${listing_id.slice(0, 8)}...`)).start();
    },

    sandboxX402({ listing_id, tx_signature, amount_usdc }) {
      stop();
      console.log(chalk.magenta("    💸") + chalk.dim(` x402 paid $${(amount_usdc / 1e6).toFixed(3)} → tx ${tx_signature.slice(0, 8)}...`));
    },

    sandboxResponse({ listing_id, score }) {
      const bar = "█".repeat(Math.round(score * 10)) + "░".repeat(10 - Math.round(score * 10));
      console.log(chalk.dim(`    score: ${bar} ${score.toFixed(2)}`));
    },

    decision({ winner_id, reasoning, score }) {
      console.log("\n" + chalk.green("→") + " Decision");
      console.log(chalk.dim(`    winner: ${winner_id.slice(0, 12)}...`));
      console.log(chalk.dim(`    ${reasoning}\n`));
    },

    purchaseSigning({ listing_id }) {
      stop();
      activeSpinner = ora("Signing buy_memory transaction...").start();
    },

    purchaseConfirmed({ tx_signature, license_pda }) {
      stop();
      console.log(chalk.green("→") + " Purchased");
      console.log(chalk.magenta(`    🔗 https://explorer.solana.com/tx/${tx_signature}?cluster=devnet`));
      console.log(chalk.dim(`    license: ${license_pda.slice(0, 12)}...\n`));
    },

    fetchProgress(bytes: number) {
      // Throttle in real implementation
    },

    fetchDone({ arweave_tx, bytes }) {
      stop();
      console.log(chalk.green("→") + ` Downloaded from Arweave (${(bytes / 1024 / 1024).toFixed(1)} MB)`);
      console.log(chalk.dim(`    tx: https://arweave.net/${arweave_tx}\n`));
    },

    verifyHash({ hash_hex, verified }) {
      if (verified) {
        console.log(chalk.green("→") + " ✓ Hash verified " + chalk.dim(hash_hex.slice(0, 16) + "..."));
      } else {
        console.log(chalk.red("→ ✗ Hash MISMATCH — possible tampering!"));
      }
      console.log();
    },

    decompress({ decompressed_size_mb, load_time_ms }) {
      console.log(chalk.green("→") + ` Decompressed (${decompressed_size_mb.toFixed(0)} MB) and loaded in ${load_time_ms}ms\n`);
    },

    executeStart({ prompt }) {
      console.log(chalk.green("→") + " Executing with loaded memory:\n");
      process.stdout.write(chalk.cyan("  "));
    },

    executeToken(token) {
      process.stdout.write(token);
    },

    executeDone({ total_tokens }) {
      process.stdout.write("\n\n");
    },

    complete({ total_cost_usdc, duration_ms }) {
      console.log(boxen(
        chalk.bold.green("✓ Task complete") + "\n\n" +
        chalk.dim(`Cost: $${total_cost_usdc.toFixed(3)} USDC\n`) +
        chalk.dim(`Duration: ${(duration_ms / 1000).toFixed(1)}s`),
        { padding: 1, borderStyle: "round", borderColor: "green" },
      ));
    },

    warn(msg) { console.log(chalk.yellow("⚠ ") + chalk.dim(msg)); },
    error({ phase, error }) {
      stop();
      console.log(chalk.red(`✗ Failed at ${phase}: ${error}`));
    },
  };
}
```

### WebSocket publisher narrator

```typescript
// src/narrator/ws_publisher.ts
import type { Narrator } from "./types";
import axios from "axios";

export function createWSPublisherNarrator(
  backendUrl: string,
  runId: string,
  publishToken: string,
): Narrator {
  async function publish(type: string, data: any) {
    try {
      await axios.post(
        `${backendUrl}/internal/publish`,
        { channel: `events:agent:${runId}`, type, data },
        { headers: { Authorization: `Bearer ${publishToken}` }, timeout: 5000 },
      );
    } catch (e: any) {
      console.error(`failed to publish ${type}:`, e.message);
    }
  }

  return {
    start: (data) => publish("agent.start", data),
    classify: (data) => publish("agent.classify", data),
    discover: (candidates) => publish("agent.discover", { candidates: candidates.map(c => ({ id: c.address, title: c.title, price: Number(c.priceUsdc), purchases: c.purchases })) }),
    sandboxStart: (data) => publish("agent.sandbox.start", data),
    sandboxX402: (data) => publish("agent.sandbox.x402", data),
    sandboxResponse: (data) => publish("agent.sandbox.response", data),
    decision: (data) => publish("agent.decision", data),
    purchaseSigning: (data) => publish("agent.purchase.signing", data),
    purchaseConfirmed: (data) => publish("agent.purchase.confirmed", data),
    fetchProgress: (bytes) => {}, // throttled
    fetchDone: (data) => publish("agent.fetch.arweave", data),
    verifyHash: (data) => publish("agent.verify.hash", data),
    decompress: (data) => publish("agent.decompress", data),
    executeStart: (data) => publish("agent.execute.start", data),
    executeToken: (token) => publish("agent.execute.token", { token }),
    executeDone: (data) => publish("agent.execute.done", data),
    complete: (data) => publish("agent.complete", data),
    warn: (msg) => publish("agent.warn", { message: msg }),
    error: (data) => publish("agent.error", data),
  };
}
```

### Tee narrator (for development — both backends)

```typescript
// src/narrator/tee.ts
export function createTeeNarrator(...narrators: Narrator[]): Narrator {
  return new Proxy({} as Narrator, {
    get(_, prop: string) {
      return (...args: any[]) => narrators.forEach((n) => (n as any)[prop]?.(...args));
    },
  });
}
```

---

## 12. CLI entrypoint

```typescript
// src/index.ts
import { Connection, Keypair } from "@solana/web3.js";
import bs58 from "bs58";
import { MemoryShoppingAgent } from "./agent";
import { AgentVaultClient } from "./solana/client";
import { X402Client } from "./x402/client";
import { WorkerClient } from "./runtime/worker_client";
import { createAnthropicClient } from "./reasoning/llm_client";
import { createStdoutNarrator } from "./narrator/stdout";

async function main() {
  const task = process.argv.slice(2).join(" ").trim();
  if (!task) {
    console.error("Usage: npm run agent -- \"<task description>\"");
    process.exit(1);
  }

  const connection = new Connection(process.env.SOLANA_RPC_URL!, "confirmed");
  const wallet = Keypair.fromSecretKey(bs58.decode(process.env.AGENT_KEYPAIR_BS58!));

  const agent = new MemoryShoppingAgent(
    {
      backendUrl: process.env.BACKEND_URL!,
      maxBudgetUsdc: Number(process.env.AGENT_MAX_BUDGET_USDC ?? 30),
      preferredModelId: "qwen2.5-7b-instruct",
      llm: createAnthropicClient(process.env.ANTHROPIC_API_KEY!),
    },
    createStdoutNarrator(),
    new AgentVaultClient(connection, wallet),
    new X402Client(connection, wallet),
    new WorkerClient(process.env.WORKER_URL!, process.env.WORKER_API_KEY!),
  );

  const result = await agent.run(task);
  process.exit(result.status === "success" ? 0 : 1);
}

main().catch((e) => { console.error(e); process.exit(1); });
```

Run with:
```bash
npm run agent -- "Write a production Anchor PDA derivation function"
```

---

## 13. HTTP server for frontend integration

```typescript
// src/server.ts
import Fastify from "fastify";
import { Connection, Keypair } from "@solana/web3.js";
import bs58 from "bs58";
import { randomUUID } from "node:crypto";
import { MemoryShoppingAgent } from "./agent";
import { AgentVaultClient } from "./solana/client";
import { X402Client } from "./x402/client";
import { WorkerClient } from "./runtime/worker_client";
import { createAnthropicClient } from "./reasoning/llm_client";
import { createWSPublisherNarrator } from "./narrator/ws_publisher";

const fastify = Fastify({ logger: true });

const connection = new Connection(process.env.SOLANA_RPC_URL!, "confirmed");
const wallet = Keypair.fromSecretKey(bs58.decode(process.env.AGENT_KEYPAIR_BS58!));

fastify.post<{ Body: { task: string } }>("/v1/agent/runs", async (req, reply) => {
  const { task } = req.body;
  const runId = randomUUID();

  // Fire and forget — agent publishes events to WS
  const narrator = createWSPublisherNarrator(
    process.env.BACKEND_URL!,
    runId,
    process.env.AGENT_PUBLISH_TOKEN!,
  );

  const agent = new MemoryShoppingAgent(
    {
      backendUrl: process.env.BACKEND_URL!,
      maxBudgetUsdc: 30,
      preferredModelId: "qwen2.5-7b-instruct",
      llm: createAnthropicClient(process.env.ANTHROPIC_API_KEY!),
    },
    narrator,
    new AgentVaultClient(connection, wallet),
    new X402Client(connection, wallet),
    new WorkerClient(process.env.WORKER_URL!, process.env.WORKER_API_KEY!),
  );

  // Don't await — return run_id immediately
  agent.run(task).catch((e) => fastify.log.error({ err: e }, "agent run failed"));

  return { run_id: runId, ws_channel: `/v1/ws/agent/${runId}` };
});

await fastify.listen({ port: 3030, host: "0.0.0.0" });
```

---

## 14. Demo orchestration

For the hackathon demo, you want a **scripted, deterministic run** that always works. Pre-stage 3-4 demo memories on devnet:

1. **"Anchor Framework Senior Dev"** — $25, tags: anchor/solana/rust/pda
2. **"DeFi Slippage Specialist (Drift)"** — $50, tags: drift/jupiter/defi/trading
3. **"Solana DAO Governance Expert"** — $15, tags: dao/governance/realms

For demo task `"Write a production Anchor PDA derivation function"`:
- Should classify to anchor/solana/rust/pda
- Should discover all 3, score Anchor highest
- Total cost: $0.15 (3 sandbox queries) + $25 (purchase) = $25.15
- Total time: ~30-60 seconds end-to-end

Pre-run the demo 5+ times to ensure consistency. Time the slow phases:
- Sandbox queries: ~3s each (LLM eval + Solana confirm + inference)
- Buy tx: ~2s
- Arweave fetch (130MB): ~5-10s
- Decompress: ~3s
- Inference: ~2-5s

Total: ~30-45s. Acceptable for a 3-min demo video.

---

## 15. Claude Code prompt — paste this verbatim

````
You are building the AgentVault buyer agent — an autonomous TypeScript service that discovers, evaluates, purchases, and uses AI agent memory from the AgentVault marketplace. This is the centerpiece of the demo and worth 30% of the hackathon judging score (Agentic Sophistication).

## Read the spec
Open `docs/06_BUYER_AGENT.md`. Read every section. The 8-phase agent loop, the file structure, the narrator design, and the demo orchestration are all specified.

Also read `docs/05_WEBSOCKET_DESIGN.md` for the WS publishing pattern (the agent publishes events that the `/agent` frontend page consumes).

## Hard requirements
- TypeScript with Node 20+, ESM
- 8 phases as specified: classify → discover → evaluate → decide → purchase → fetch → load → execute
- Two narrator backends: stdout (terminal demo) and WebSocket publisher (frontend live demo)
- Uses solana-agent-kit ONLY where it's actually useful (token balances, basic tx ops). The marketplace-specific Anchor calls go through our custom AgentVaultClient.
- LLM-driven reasoning at THREE points: classification, probe generation, response evaluation
- Hash verification is non-skippable — fail loudly if Arweave returns a bad blob
- Streaming token output for the execute phase

## Build order
1. `package.json` with dependencies from section 4
2. `src/types.ts` — TaskResult, Listing, AgentRunOptions, AgentEvent
3. `src/narrator/types.ts` — Narrator interface
4. `src/narrator/stdout.ts` — pretty terminal narrator (nail this; it's the terminal demo)
5. `src/reasoning/llm_client.ts` — Anthropic wrapper
6. `src/reasoning/classifier.ts`, `probe_generator.ts`, `evaluator.ts`, `decision.ts`
7. `src/solana/client.ts` — AnchorVaultClient with findListings, buyMemory
8. `src/x402/client.ts` — wraps x402-solana
9. `src/arweave/fetcher.ts` — download with progress + sha256 verify
10. `src/runtime/worker_client.ts` — talks to TurboQuant worker, with SSE streaming
11. `src/agent.ts` — MemoryShoppingAgent with the 8 phases
12. `src/index.ts` — CLI entry
13. `src/narrator/ws_publisher.ts` — WS narrator
14. `src/server.ts` — HTTP server for frontend integration
15. Tests with vitest (mock backend + Solana + worker)

## Demo orchestration setup (do this BEFORE running demo)
- Pre-stage 3 memory listings on devnet (anchor expert / defi specialist / dao governance)
- Pre-fund the agent's USDC ATA with at least $50 USDC on devnet
- Set AGENT_MAX_BUDGET_USDC=30 to constrain it tastefully
- Pre-record a successful run as backup video

## Critical implementation notes
- Solana txs need fresh blockhash — use commitment "confirmed" everywhere
- USDC has 6 decimals — be religious about converting to/from micro-units
- Arweave fetches can be slow (5-15s for 100MB+); use 5-min timeout
- The classifier prompt is sensitive to format; test with several tasks before relying on it
- Score evaluator should fall back to 0.5 if LLM returns garbage (don't crash on bad parsing)
- WS publisher must not block agent execution — use fire-and-forget axios calls

## Common pitfalls
- "TypeError: cannot read property 'partialSign' of undefined" — wallet adapter mismatch; use Keypair directly here, not WalletContextState
- Anchor BN serialization — when calling buyMemory, no args needed (PDAs derived from accounts), all amounts read from listing
- LLM returns markdown-wrapped JSON — strip ```json ``` before parsing
- Solana confirmation can take 5-10s on devnet — don't set tight timeouts
- Streaming SSE: many libraries close on first newline; use raw Response.body reader

## Demo polish
The narrator is what judges see. Spend time here:
- Use boxen for the start/end frames
- Color-code: yellow for tasks, green for progress, magenta for blockchain links, dim for metadata
- Print explorer links for every Solana tx
- The token-by-token streaming in execute phase is mesmerizing — make sure it works
- Total run time should be 30-60s; if it's >90s, something is slow

## Stretch goals (only if core works)
- Multiple LLM providers (OpenAI fallback)
- Concurrent sandbox evaluation (Promise.all) — 3x speedup
- Sticky memory: remember which listings worked well across runs
- Multi-task batch mode

Build it. Run it end-to-end on devnet with seeded listings. The demo is everything.
````

---

## 16. Definition of done

- [ ] All 8 phases implemented and run sequentially
- [ ] Stdout narrator produces beautiful terminal output
- [ ] WebSocket narrator publishes events that frontend can consume
- [ ] Agent runs end-to-end on devnet in <90 seconds
- [ ] Hash verification correctly fails on tampered blobs (test by mutating one byte)
- [ ] Sandbox x402 payments work with multiple candidates
- [ ] Decision logic respects budget constraint
- [ ] Streaming token output during execute phase
- [ ] HTTP server accepts run requests from frontend
- [ ] At least 5 successful demo runs in a row (no flakiness)
- [ ] Total cost per run logged accurately
- [ ] Clean error handling at every phase boundary

When this list is checked, the demo is recordable and the Agentic Sophistication score is locked in.

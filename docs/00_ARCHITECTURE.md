# 00 — Architecture & Data Flow

**Read this first. Everything else assumes you know this.**

---

## 1. The product in one paragraph

AgentVault is a Solana-native marketplace + audit layer for AI agent memory. Sellers run the CLI to capture their LLM agent's accumulated context (KV cache from vLLM/LMCache or replayed conversations), the system compresses it 4-5× using TurboQuant, uploads to Arweave for permanent storage, and registers the listing on Solana. Buyers (humans via frontend, or autonomous agents via x402) discover listings, pay a small fee for sandbox previews, then purchase full memory access — atomically through the Solana program. The buyer's agent then downloads the blob from Arweave, verifies the on-chain hash, decompresses, and loads the cache into its runtime. Same model, same prompt, expert-level output — without weeks of training. Additionally, agents can anchor their decisions on-chain with context-hash receipts, producing the immutable audit trail DAOs need for AI treasury management.

---

## 2. Repository layout

```
agentvault/
│
├── docs/                            # All build documents
│   ├── README.md                    # This index
│   ├── 00_ARCHITECTURE.md
│   ├── 01_SOLANA_PROGRAM.md
│   ├── 02_BACKEND.md
│   ├── 03_TURBOQUANT_WORKER.md
│   ├── 04_FRONTEND.md
│   ├── 05_WEBSOCKET_DESIGN.md
│   └── 06_BUYER_AGENT.md
│
├── programs/agentvault/             # Solana Anchor program (Rust)
├── backend/                         # FastAPI server (Railway)
├── worker/                          # TurboQuant compression service (Python + GPU)
├── frontend/                        # Next.js marketplace (Vercel)
├── buyer-agent/                     # Autonomous buyer (TypeScript)
├── cli/                             # Seller CLI (Rust) — optional v2
│
├── shared/
│   └── types/                       # Generated IDL + shared TS types
│
├── scripts/
│   ├── deploy.sh
│   ├── seed_listings.sh
│   └── runpod_setup.sh
│
├── .github/workflows/               # CI/CD
├── Anchor.toml
├── package.json                     # Root workspace
└── README.md
```

---

## 3. The complete data flow

### 3.1 Seller flow (listing memory)

```
USER's MACHINE                BACKEND (Railway)              SOLANA              ARWEAVE
     │                              │                          │                    │
     │ 1. Open frontend             │                          │                    │
     │   /list page                 │                          │                    │
     │                              │                          │                    │
     │ 2. Drag-drop .avlt file      │                          │                    │
     │ ─── HTTPS POST /upload/init ─►                          │                    │
     │                              │                          │                    │
     │                              │ 3. Calculate fee         │                    │
     │                              │    (deterministic)       │                    │
     │ ◄─── { fee, upload_id } ─────│                          │                    │
     │                              │                          │                    │
     │ 4. Sign+pay listing fee tx   │                          │                    │
     │ ─── POST /upload/blob ──────►│                          │                    │
     │     (file in body)           │                          │                    │
     │                              │ 5. Stream to GPU worker  │                    │
     │                              │    via Redis queue       │                    │
     │                              │                          │                    │
     │                              │   GPU WORKER:            │                    │
     │                              │   - TurboQuant compress  │                    │
     │                              │   - SHA-256 hash         │                    │
     │                              │                          │                    │
     │                              │ 6. Upload to Arweave     │                    │
     │                              │ ──── via Bundlr/Irys ───────────────────────► │
     │                              │ ◄────── arweave_tx ────────────────────────── │
     │                              │                          │                    │
     │ ─── WS: progress updates ───►│                          │                    │
     │                              │                          │                    │
     │ 7. Sign list_memory tx       │                          │                    │
     │ ──── (frontend wallet) ─────────────────────────────────►                    │
     │                              │                          │                    │
     │                              │                          │ 8. Create          │
     │                              │                          │    MemoryListing   │
     │                              │                          │    PDA             │
     │                              │                          │                    │
     │                              │ 9. Indexer picks up event│                    │
     │                              │ ◄── webhook/poll ────────│                    │
     │                              │                          │                    │
     │                              │ 10. Mirror to Supabase   │                    │
     │ ──── WS: listing live ──────►│                          │                    │
     │                              │                          │                    │
```

### 3.2 Buyer flow (autonomous agent purchase)

```
BUYER AGENT                   BACKEND                        SOLANA              ARWEAVE
     │                            │                             │                    │
     │ 1. Task: "write Anchor PDA"│                             │                    │
     │                            │                             │                    │
     │ 2. Classify task tags      │                             │                    │
     │                            │                             │                    │
     │ 3. Query listings          │                             │                    │
     │ ──── GET /listings ───────►│                             │                    │
     │                            │ 4. Read from Supabase       │                    │
     │                            │    (cached from on-chain)   │                    │
     │ ◄──── 5 candidates ────────│                             │                    │
     │                            │                             │                    │
     │ 5. For each top-3:         │                             │                    │
     │    Request sandbox preview │                             │                    │
     │ ─── POST /sandbox/{id} ───►│                             │                    │
     │                            │ ◄── 402 Payment Required ──│                    │
     │ ◄── 402 + payment reqs ────│                             │                    │
     │                            │                             │                    │
     │ 6. Sign x402 payment       │                             │                    │
     │ ──── (USDC transfer) ──────────────────────────────────► │                    │
     │                            │                             │                    │
     │ 7. Retry with payment hdr  │                             │                    │
     │ ─── POST /sandbox/{id} ───►│                             │                    │
     │     X-PAYMENT: ...         │                             │                    │
     │                            │ 8. Verify x402 payment      │                    │
     │                            │    Run inference w/ memory  │                    │
     │ ◄── { response, score } ───│ (calls RunPod Qwen)         │                    │
     │                            │                             │                    │
     │ 9. Pick best, buy_memory   │                             │                    │
     │ ─── invoke buy_memory ──────────────────────────────────►                     │
     │                            │                             │ 10. Atomic:        │
     │                            │                             │   - USDC transfer  │
     │                            │                             │   - License PDA    │
     │ ◄── tx signature ─────────────────────────────────────── │                    │
     │                            │                             │                    │
     │ 11. Read license,          │                             │                    │
     │    fetch arweave_tx        │                             │                    │
     │ ──────────────────────────────────────────────────────────────────────────────►
     │ ◄────────────────────────────────────────────── compressed blob (~130MB) ────│
     │                            │                             │                    │
     │ 12. Verify SHA-256(blob)   │                             │                    │
     │     == on-chain hash       │                             │                    │
     │                            │                             │                    │
     │ 13. Decompress (TurboQuant)│                             │                    │
     │     Load into vLLM         │                             │                    │
     │                            │                             │                    │
     │ 14. Run task with          │                             │                    │
     │     loaded memory          │                             │                    │
     │     → expert output        │                             │                    │
```

### 3.3 Audit trail flow (Use Case 1 — DAO governance)

```
DAO TREASURY AGENT            BACKEND                        SOLANA
     │                            │                             │
     │ 1. Decision time:          │                             │
     │    "rebalance to USDC"     │                             │
     │                            │                             │
     │ 2. Snapshot context        │                             │
     │    (current KV cache)      │                             │
     │                            │                             │
     │ 3. Compress (TurboQuant)   │                             │
     │ ─── POST /audit/anchor ───►│                             │
     │                            │ 4. Hash, upload to Arweave  │
     │                            │ 5. Submit anchor_decision   │
     │                            │ ─────────────────────────► │
     │                            │                             │ 6. Create
     │                            │                             │    DecisionRecord
     │                            │                             │    PDA
     │ ◄──── tx signature ────────│                             │
     │                            │                             │
     │ 7. Execute on-chain trade  │                             │
     │    (now linked to audit    │                             │
     │     record via tx memo)    │                             │
```

---

## 4. Component responsibilities (no overlap)

| Component | Responsibility | Does NOT |
|---|---|---|
| **Solana program** | Asset registry, atomic payments, audit anchoring | Store blobs, run inference |
| **Backend (FastAPI)** | API gateway, indexer, x402 verification, job orchestration | Compress (delegates to worker), execute on-chain (user's wallet does) |
| **TurboQuant worker** | Compression, decompression, quality benchmarking | Touch the database, talk to Solana |
| **Frontend** | Browse, list, buy, dashboard UI | Trust-critical operations (only signs, never validates) |
| **Buyer agent** | Autonomous discovery → evaluation → purchase → load | Be a runtime (uses RunPod Qwen as runtime) |
| **CLI (optional)** | Power-user seller interface | Replace frontend (overlap is fine) |

---

## 5. Stack decisions, justified

### Why Railway for backend (not AWS/GCP)
- One-command deploy from GitHub
- Built-in Postgres + Redis (we only use Redis from Railway, Postgres from Supabase)
- Native WebSocket support (no extra config)
- $5/month plan handles hackathon demo easily
- Logs and metrics built-in
- Fast cold starts (<2s)

### Why Supabase for Postgres (not Railway Postgres)
- Generous free tier (500MB, more than we'll use)
- Built-in connection pooling (PgBouncer)
- Real-time subscriptions via Postgres replication (free WS-like fanout if we want it later)
- Auto-generated REST + GraphQL APIs (handy escape hatch)
- Best free Postgres UI in the market for debugging

### Why Vercel for frontend (not Railway/Netlify)
- Next.js is built by Vercel, deploys are flawless
- Edge functions for x402 payment verification at the edge
- Free tier is generous
- Preview deploys on every PR

### Why RunPod for GPU (not AWS/Lambda Labs)
- A10G at $0.40/hr beats AWS by ~3x
- Pre-built vLLM containers
- Per-second billing (no hourly minimums)
- Can pause/resume easily during dev

### Why Arweave via Bundlr (not IPFS/Filecoin)
- Pay-once, store-forever fits our "permanent memory" pitch
- Bundlr/Irys SDK takes Solana payments natively (single-signature upload)
- IPFS pinning is operationally fragile
- Filecoin requires deal-making complexity

### Why Anchor (not native Solana program)
- Type safety + IDL generation
- Half the boilerplate of native programs
- Anchor 0.30+ has good test infrastructure
- Most Solana hackathon judges expect Anchor

---

## 6. Glossary

- **KV cache** — Internal LLM state stored layer-by-layer during inference. The "working memory" of an agent session.
- **TurboQuant** — Google Research's vector quantization technique. Achieves 3.5 bits/channel with quality neutrality on KV cache.
- **LMCache** — Production-stable open-source KV cache management layer for vLLM. Supports custom serde and remote storage.
- **x402** — HTTP 402 "Payment Required" status code, revived by Coinbase as an internet-native payment protocol.
- **Bundlr / Irys** — Service for uploading to Arweave with payment in any chain's native token (incl. Solana).
- **PDA** — Program Derived Address. Deterministic Solana account owned by a program (no private key).
- **Anchor** — Rust framework for Solana smart contract development with IDL generation.
- **vLLM** — High-throughput LLM inference engine with paged attention.
- **avlt** — The CLI binary name + file extension for compressed memory blobs.

---

## 7. Versioning strategy

We're at v0.1.0 throughout the hackathon. After judging:
- v0.2: Rust CLI (skipped during hackathon for time)
- v0.3: ZK proofs of correct decompression
- v1.0: Mainnet launch with audited program

---

## 8. Environment variables (reference)

These will be referenced across docs:

```bash
# Solana
SOLANA_NETWORK=devnet                         # devnet | mainnet-beta
SOLANA_RPC_URL=https://api.devnet.solana.com  # or Helius
AGENTVAULT_PROGRAM_ID=...                     # filled after deploy
USDC_MINT=4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU  # devnet USDC
TREASURY_WALLET=...

# Supabase
DATABASE_URL=postgresql://postgres:...@db.xxx.supabase.co:5432/postgres
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...   # backend-only

# Redis (Railway plugin)
REDIS_URL=redis://...

# Arweave / Bundlr
BUNDLR_NETWORK=https://node1.bundlr.network
BUNDLR_KEYPAIR=...                  # base58-encoded Solana keypair

# x402
X402_FACILITATOR_URL=https://facilitator.payai.network
X402_TREASURY=...                   # platform's USDC ATA

# Worker (RunPod)
WORKER_URL=https://worker.agentvault.xyz
WORKER_API_KEY=...

# Qwen runtime (RunPod)
VLLM_ENDPOINT=https://your-runpod.proxy.runpod.net
LMCACHE_REMOTE_URL=https://api.agentvault.xyz/v1/lmcache
```

---

## 9. Bootstrap commands (run once)

```bash
# 1. Clone or create the repo
mkdir agentvault && cd agentvault
git init

# 2. Create the structure
mkdir -p docs programs/agentvault/src backend worker frontend buyer-agent cli shared/types scripts

# 3. Set up workspaces
cat > package.json <<'EOF'
{
  "name": "agentvault",
  "private": true,
  "workspaces": ["frontend", "buyer-agent", "shared/types"]
}
EOF

# 4. Anchor workspace
cat > Anchor.toml <<'EOF'
[features]
seeds = false
skip-lint = false

[programs.devnet]
agentvault = "AgntV1tXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"

[provider]
cluster = "devnet"
wallet = "~/.config/solana/id.json"
EOF

# 5. Install Solana + Anchor toolchain (if not already)
sh -c "$(curl -sSfL https://release.solana.com/v1.18.0/install)"
cargo install --git https://github.com/coral-xyz/anchor anchor-cli --force

# 6. Configure Solana for devnet
solana config set --url devnet
solana-keygen new --outfile ~/.config/solana/id.json
solana airdrop 5

# 7. Drop the docs in place
# (copy 00_ARCHITECTURE.md etc. into docs/)

echo "✓ Repo bootstrapped. Read docs/00_ARCHITECTURE.md, then build component-by-component."
```

---

## 10. The 5-week build path

| Week | Goal | Files |
|---|---|---|
| **1** | De-risk: Solana program live on devnet, TurboQuant proven on Qwen | `01_SOLANA_PROGRAM.md`, `03_TURBOQUANT_WORKER.md` |
| **2** | Backend + WebSocket + indexer working | `02_BACKEND.md`, `05_WEBSOCKET_DESIGN.md` |
| **3** | Buyer agent runs autonomously end-to-end | `06_BUYER_AGENT.md` |
| **4** | Frontend polished, 3 demo memories pre-trained | `04_FRONTEND.md` |
| **5** | Demo recording, partner outreach, submission | (no new docs) |

---

Now go to `01_SOLANA_PROGRAM.md`.

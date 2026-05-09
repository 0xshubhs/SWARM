# AgentVault — Build Documents Index

Six self-contained build documents, one per component. Drop each into Claude Code in the matching directory.

## Documents

| File | Component | Stack | Repo location |
|---|---|---|---|
| `00_ARCHITECTURE.md` | System overview, data flow, glossary | — | `/` (root) |
| `01_SOLANA_PROGRAM.md` | On-chain Anchor program | Rust + Anchor 0.30 | `/programs/agentvault` |
| `02_BACKEND.md` | API server, business logic, indexer | FastAPI + SQLAlchemy + Supabase | `/backend` (Railway) |
| `03_TURBOQUANT_WORKER.md` | KV cache compression service | Python + PyTorch + GPU | `/worker` (Railway with GPU, or RunPod) |
| `04_FRONTEND.md` | Marketplace UI | Next.js 15 + Tailwind + shadcn | `/frontend` (Vercel) |
| `05_WEBSOCKET_DESIGN.md` | Realtime channels (CLI ↔ backend ↔ frontend) | FastAPI WS + Redis pub/sub | Cross-cutting |
| `06_BUYER_AGENT.md` | Autonomous purchaser (the demo star) | TypeScript + Solana Agent Kit + x402 | `/buyer-agent` |

## Stack at a glance

```
┌──────────────────────────────────────────────────────────────────┐
│                         AGENTVAULT STACK                          │
└──────────────────────────────────────────────────────────────────┘

  USER LAYER          [ CLI (Rust) ]   [ Frontend (Next.js → Vercel) ]
                            │                       │
                            │ WS                    │ HTTPS
                            ▼                       ▼
  PLATFORM LAYER     ┌──────────────────────────────────────┐
                     │  Railway: FastAPI Backend            │
                     │  - REST API                          │
                     │  - WebSocket gateway                 │
                     │  - Solana indexer                    │
                     │  - x402 payment middleware           │
                     │  - Job queue (Redis)                 │
                     └────────┬─────────┬──────────┬────────┘
                              │         │          │
                              ▼         ▼          ▼
                     ┌──────────────┐ ┌──────┐ ┌──────────┐
                     │ Supabase     │ │Redis │ │ TurboQ   │
                     │ Postgres     │ │      │ │ Worker   │
                     │ (metadata)   │ │      │ │ (GPU)    │
                     └──────────────┘ └──────┘ └──────────┘

  TRUST LAYER        [ Solana Devnet → Mainnet ]
                     - AgentVault Anchor program
                     - SPL Token (USDC) for payments
                     - x402 facilitator

  STORAGE LAYER      [ Arweave via Bundlr/Irys ]
                     - Compressed KV cache blobs
                     - Permanent, content-addressed

  RUNTIME LAYER      [ RunPod: Qwen 2.5 7B + vLLM + LMCache ]
                     - Demo inference endpoint
                     - Custom TurboQuant serde plugin
```

## How to use these docs

1. Read `00_ARCHITECTURE.md` first — it grounds you on data flow and decisions.
2. Set up the monorepo skeleton (instructions in `00_ARCHITECTURE.md`).
3. For each component, `cd` into the directory and paste the matching MD into Claude Code.
4. Build in this order:
   - Solana program (Day 1-2 — foundation)
   - TurboQuant worker (Day 3-7 — de-risk the AI)
   - Backend (Week 2 — glue)
   - WebSocket layer (Week 2 — real-time)
   - Buyer agent (Week 3 — demo)
   - Frontend (Week 4 — surface)

## Deployment targets

| Component | Target | Why |
|---|---|---|
| Anchor program | Solana devnet → mainnet | Where it has to live |
| Backend | Railway | One-click deploy, postgres-friendly, $5/mo, easy WS support |
| TurboQuant worker | Railway (CPU dev) + RunPod (GPU prod) | GPU only needed for real compression jobs |
| Frontend | Vercel | Next.js native, free tier sufficient |
| Postgres | Supabase | Free tier, generous, Postgres-native |
| Redis | Railway (built-in) or Upstash | Pub/sub for WS fanout |
| Storage | Arweave via Bundlr/Irys | Permanent, Solana-payable |
| GPU runtime | RunPod (A10G, ~$0.40/hr) | Demo Qwen instance |

## Cost estimate for hackathon

| Service | Cost (5 weeks) |
|---|---|
| Railway (backend + redis) | $10 |
| Supabase (free tier) | $0 |
| Vercel (free tier) | $0 |
| RunPod A10G (~50 hours active) | $20 |
| Bundlr/Arweave uploads (~5GB total) | $30 |
| Solana devnet | $0 |
| Domain (optional) | $10 |
| **Total** | **~$70** |

— End of index —

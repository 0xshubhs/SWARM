# 02 — Backend (Railway + Supabase)

**Where:** `backend/`
**Stack:** Python 3.12 + FastAPI + SQLAlchemy 2 + Supabase Postgres + Redis
**Deploy target:** Railway
**Build after:** Solana program (need IDL); can build in parallel with TurboQuant worker

---

## 1. Responsibilities

The backend is the **orchestration + indexing layer**. It:
- Serves the REST API consumed by frontend, CLI, and buyer agent
- Hosts the WebSocket gateway (see `05_WEBSOCKET_DESIGN.md`)
- Indexes Solana program events into Supabase (so listings can be queried fast)
- Mediates communication with the TurboQuant worker (job queue via Redis)
- Handles x402 payment verification for sandbox queries
- Calls Bundlr/Irys to upload to Arweave
- Talks to RunPod Qwen for sandbox inference

The backend does **not**:
- Execute Solana transactions on behalf of users (users sign with their wallet)
- Compress KV cache (delegates to worker)
- Run the LLM (delegates to RunPod Qwen)
- Store the actual blob (Arweave does)

---

## 2. Stack & deployment

### Why Railway
- One-click deploy from GitHub
- Native WebSocket support (no nginx config)
- Built-in Redis plugin
- Generous free tier ($5/month covers hackathon)
- Automatic HTTPS, custom domains
- Env var management UI
- Logs + metrics dashboard

### Why Supabase Postgres (not Railway's)
- Free 500MB tier (we'll use <50MB)
- PgBouncer connection pooling included
- Best Postgres UI for debugging queries
- Real-time subscriptions if we need them later
- Survives Railway restarts cleanly (separation of concerns)

### Service architecture on Railway

```
Railway Project: agentvault-backend
│
├── Service: api               (web service)
│   - Domain: api.agentvault.xyz
│   - Runs: uvicorn api.main:app
│   - Auto-scales: no (single instance fine for hackathon)
│
├── Service: indexer          (worker)
│   - No public domain
│   - Runs: python -m indexer.run
│   - Subscribes to Solana logs, writes to Supabase
│
├── Service: job_runner       (worker)
│   - Runs: python -m workers.run
│   - Pulls from Redis, dispatches to TurboQuant worker
│
└── Plugin: Redis             (managed)
    - REDIS_URL env var auto-injected
```

The TurboQuant worker is a **separate deployment** (not Railway — it needs GPU). See `03_TURBOQUANT_WORKER.md`.

---

## 3. File structure

```
backend/
├── pyproject.toml                     # uv-managed dependencies
├── Dockerfile                         # Railway uses this
├── railway.json                       # Railway service config
├── .env.example
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/                      # Migration files
├── api/
│   ├── __init__.py
│   ├── main.py                        # FastAPI app, middleware, routers
│   ├── config.py                      # Settings via pydantic-settings
│   ├── deps.py                        # FastAPI dependencies (db, redis, auth)
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── upload.py                  # /v1/upload/*
│   │   ├── listings.py                # /v1/listings/*
│   │   ├── pricing.py                 # /v1/pricing
│   │   ├── sandbox.py                 # /v1/sandbox/{id} (x402-gated)
│   │   ├── verify.py                  # /v1/verify/{hash}
│   │   ├── decisions.py               # /v1/decisions/{agent_id}
│   │   └── ws.py                      # WebSocket endpoints (see doc 05)
│   └── x402/
│       ├── __init__.py
│       ├── handler.py                 # x402 payment verification
│       └── facilitator.py             # Talks to PayAI facilitator
├── solana/
│   ├── __init__.py
│   ├── client.py                      # AnchorPy program client
│   ├── pdas.py                        # PDA derivation helpers
│   └── events.py                      # Event parsing (matches IDL)
├── storage/
│   ├── __init__.py
│   ├── arweave.py                     # Bundlr/Irys client
│   └── models.py                      # SQLAlchemy models
├── jobs/
│   ├── __init__.py
│   ├── queue.py                       # Redis-backed job queue (arq)
│   └── tasks.py                       # Job definitions
├── workers/
│   ├── __init__.py
│   ├── run.py                         # Main worker entrypoint
│   ├── compress_dispatcher.py         # Sends to TurboQuant worker
│   └── arweave_uploader.py            # Bundlr upload jobs
├── indexer/
│   ├── __init__.py
│   ├── run.py                         # Indexer entrypoint
│   ├── listings_indexer.py            # Mirror MemoryListed events
│   ├── purchases_indexer.py           # Mirror MemoryPurchased events
│   └── decisions_indexer.py           # Mirror DecisionAnchored events
├── runtime/
│   ├── __init__.py
│   └── vllm_client.py                 # Talk to RunPod Qwen
└── tests/
    ├── conftest.py
    ├── test_listings.py
    ├── test_pricing.py
    ├── test_sandbox.py
    ├── test_indexer.py
    └── test_x402.py
```

---

## 4. Dependencies

```toml
# pyproject.toml
[project]
name = "agentvault-backend"
version = "0.1.0"
requires-python = ">=3.12"

dependencies = [
    # Web framework
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "pydantic>=2.9",
    "pydantic-settings>=2.6",

    # Database
    "sqlalchemy>=2.0.36",
    "asyncpg>=0.30",
    "alembic>=1.13",
    "psycopg2-binary>=2.9",     # for alembic

    # Redis + jobs
    "redis>=5.2",
    "arq>=0.26",                # async job queue

    # Solana
    "solana>=0.34",
    "anchorpy>=0.20",
    "solders>=0.21",

    # Arweave (Python SDK is limited; use HTTP wrapper to Bundlr)
    "httpx>=0.27",
    "base58>=2.1",

    # Utility
    "python-multipart>=0.0.12",  # File uploads
    "websockets>=13.1",
    "python-jose[cryptography]>=3.3",
    "structlog>=24.4",
]

[tool.uv.sources]
# (none for now)

[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "pytest-mock>=3.14",
    "httpx>=0.27",   # for TestClient
    "ruff>=0.7",
]
```

Use `uv` for environment management:
```bash
uv venv
uv sync
```

---

## 5. Database schema (Supabase)

### Migration 1 — initial schema

```python
# alembic/versions/001_initial.py
"""initial schema"""
revision = "001"
down_revision = None

def upgrade():
    op.create_table(
        "listings",
        sa.Column("id", sa.String(64), primary_key=True),  # listing PDA
        sa.Column("seller", sa.String(44), nullable=False, index=True),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("model_id", sa.String(64), nullable=False, index=True),
        sa.Column("tags", sa.ARRAY(sa.String), nullable=False, index=True),
        sa.Column("price_usdc", sa.BigInteger, nullable=False),
        sa.Column("sandbox_price_usdc", sa.BigInteger, nullable=False),
        sa.Column("arweave_tx", sa.String(43), nullable=False),
        sa.Column("content_hash", sa.LargeBinary(32), nullable=False, unique=True),
        sa.Column("quant_seed", sa.BigInteger, nullable=False),
        sa.Column("bits_per_channel", sa.SmallInteger, nullable=False),
        sa.Column("seq_len", sa.Integer, nullable=False),
        sa.Column("active", sa.Boolean, default=True, index=True),
        sa.Column("purchases", sa.BigInteger, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("on_chain_slot", sa.BigInteger, nullable=False),
    )

    op.create_index(
        "idx_listings_active_tags",
        "listings",
        ["active"],
        postgresql_where=sa.text("active = true"),
    )

    op.create_table(
        "purchases",
        sa.Column("license_pda", sa.String(64), primary_key=True),
        sa.Column("buyer", sa.String(44), nullable=False, index=True),
        sa.Column("listing_id", sa.String(64), nullable=False, index=True),
        sa.Column("price_paid_usdc", sa.BigInteger, nullable=False),
        sa.Column("tx_signature", sa.String(88), nullable=False),
        sa.Column("purchased_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"]),
    )

    op.create_table(
        "sandbox_queries",
        sa.Column("id", sa.String(36), primary_key=True),  # uuid
        sa.Column("buyer", sa.String(44), nullable=False, index=True),
        sa.Column("listing_id", sa.String(64), nullable=False, index=True),
        sa.Column("query", sa.Text, nullable=False),
        sa.Column("response", sa.Text),
        sa.Column("quality_score", sa.Float),
        sa.Column("payment_tx", sa.String(88)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"]),
    )

    op.create_table(
        "decisions",
        sa.Column("id", sa.String(64), primary_key=True),  # decision PDA
        sa.Column("agent_id", sa.String(44), nullable=False, index=True),
        sa.Column("decision_type", sa.String(32), nullable=False, index=True),
        sa.Column("context_hash", sa.LargeBinary(32), nullable=False),
        sa.Column("arweave_tx", sa.String(43), nullable=False),
        sa.Column("decision_data", sa.LargeBinary, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("on_chain_slot", sa.BigInteger, nullable=False),
    )

    op.create_table(
        "compress_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("seller", sa.String(44), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, index=True),  # queued/running/done/failed
        sa.Column("input_size_bytes", sa.BigInteger, nullable=False),
        sa.Column("output_size_bytes", sa.BigInteger),
        sa.Column("content_hash", sa.LargeBinary(32)),
        sa.Column("arweave_tx", sa.String(43)),
        sa.Column("error", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )

def downgrade():
    op.drop_table("compress_jobs")
    op.drop_table("decisions")
    op.drop_table("sandbox_queries")
    op.drop_table("purchases")
    op.drop_table("listings")
```

---

## 6. API Specification

### Authentication
- Public endpoints: no auth (browse, get listing details)
- Mutating endpoints: signed message via wallet (verified via solders/web3.js standard)
- Internal endpoints: API key in `Authorization: Bearer xxx` header

### Endpoints

#### `POST /v1/upload/init`
Initiate an upload. Returns a job ID and the listing fee.

**Request:**
```json
{
  "seller_pubkey": "Abc...",
  "expected_size_bytes": 220358912
}
```

**Response:**
```json
{
  "upload_id": "uuid-...",
  "fee_breakdown": {
    "base_usdc": 500000,
    "compute_usdc": 21000000,
    "storage_usdc": 10500000,
    "total_usdc": 32000000
  },
  "fee_payment_address": "platform_fee_ata",
  "ws_channel": "/v1/ws/upload/uuid-..."
}
```

#### `POST /v1/upload/blob/{upload_id}`
Stream the raw KV cache file. Backend dispatches to compression worker.

**Request:** multipart/form-data with the file
**Response:** `202 Accepted` (job started)

The actual progress (compression %, upload to Arweave %, on-chain confirmation) flows over the WebSocket.

#### `POST /v1/upload/finalize`
After WS notifies completion, the seller calls this to register the listing on-chain. Backend returns the call params; the seller's frontend signs and submits.

**Request:**
```json
{
  "upload_id": "uuid-...",
  "seller_pubkey": "Abc...",
  "title": "Anchor Framework Senior Dev",
  "tags": ["anchor", "solana", "rust", "pda"],
  "price_usdc": 25000000,
  "sandbox_price_usdc": 50000
}
```

**Response:**
```json
{
  "listing_pda": "...",
  "instruction": {
    "program_id": "AgntV1t...",
    "accounts": [...],
    "data": "base64..."
  }
}
```

The frontend builds the transaction, the wallet signs it, sends. The indexer picks up the event and finalizes.

#### `GET /v1/listings`
Browse listings.

**Query params:**
- `tags` (comma-separated): filter by any matching tag
- `model`: filter by model_id
- `min_price`, `max_price`: USDC range
- `seller`: specific seller's listings
- `active` (default true)
- `sort`: `created_at` | `purchases` | `price` (default: `created_at` desc)
- `limit` (default 20, max 100)
- `cursor`: opaque cursor for pagination

**Response:**
```json
{
  "items": [
    {
      "id": "listing_pda_...",
      "title": "...",
      "model_id": "qwen2.5-7b-instruct",
      "tags": [...],
      "price_usdc": 25000000,
      "sandbox_price_usdc": 50000,
      "purchases": 8,
      "seq_len": 4096,
      "bits_per_channel": 35,
      "created_at": "2026-04-20T...",
      "seller": "Abc..."
    }
  ],
  "next_cursor": null
}
```

#### `GET /v1/listings/{id}`
Single listing detail.

**Response:** full listing object + `arweave_tx` + `content_hash` (hex).

#### `POST /v1/sandbox/{listing_id}` — **x402-gated**

This is the hot endpoint. Implements x402 protocol.

**First call (no payment):**
- Returns `402 Payment Required`
- Headers include `X-PAYMENT-REQUIREMENTS` with USDC amount and treasury address

**Second call (with payment):**
- Header `X-PAYMENT: <base64-encoded-payment-proof>`
- Backend verifies via x402 facilitator
- Loads memory into Qwen runtime via LMCache
- Runs query, returns response
- Decrements queries_remaining on the SandboxAccess PDA (or backend tracks it)

**Response (200):**
```json
{
  "response": "...",
  "quality_score": 0.87,
  "queries_remaining": 4,
  "tx_signature": "..."
}
```

#### `GET /v1/pricing?size_bytes=X`
Pure function returning fee breakdown.

**Response:**
```json
{
  "base_usdc": 500000,
  "compute_usdc": 21000000,
  "storage_usdc": 10500000,
  "total_usdc": 32000000,
  "currency": "USDC",
  "decimals": 6
}
```

#### `GET /v1/verify/{content_hash}`
Audit endpoint. "Does AgentVault know about this hash?"

**Response:**
```json
{
  "found": true,
  "kind": "memory_listing",  // or "decision_record"
  "on_chain_pda": "...",
  "arweave_tx": "...",
  "anchored_at_slot": 287654321,
  "anchored_at": "2026-04-20T..."
}
```

#### `GET /v1/decisions/{agent_id}`
Get all DecisionRecords for an agent. Useful for DAO audits.

**Query params:**
- `decision_type` (optional)
- `from_slot`, `to_slot` (range)
- `limit`, `cursor`

**Response:** list of decisions with full context.

---

## 7. The pricing logic (deterministic, not ML)

```python
# api/routers/pricing.py
from pydantic import BaseModel

class FeeBreakdown(BaseModel):
    base_usdc: int
    compute_usdc: int
    storage_usdc: int
    total_usdc: int
    currency: str = "USDC"
    decimals: int = 6


# Constants live in api/config.py
BASE_FEE_USDC = 500_000           # $0.50
PER_MB_COMPUTE_USDC = 100_000     # $0.10/MB
PER_MB_STORAGE_USDC = 50_000      # $0.05/MB (Arweave passthrough + margin)


def calculate_fee(size_bytes: int) -> FeeBreakdown:
    mb = size_bytes / (1024 * 1024)
    compute = int(mb * PER_MB_COMPUTE_USDC)
    storage = int(mb * PER_MB_STORAGE_USDC)
    return FeeBreakdown(
        base_usdc=BASE_FEE_USDC,
        compute_usdc=compute,
        storage_usdc=storage,
        total_usdc=BASE_FEE_USDC + compute + storage,
    )
```

No ML. Transparent. Auditable. Sellers know exactly what they pay for.

---

## 8. x402 integration

### The flow

```python
# api/x402/handler.py
import httpx
import base64
import json
from solders.transaction import VersionedTransaction
from typing import Optional


class X402Handler:
    def __init__(self, facilitator_url: str, treasury_address: str, network: str):
        self.facilitator_url = facilitator_url
        self.treasury = treasury_address
        self.network = network

    def create_payment_requirements(
        self,
        amount_usdc_micro: int,
        resource_url: str,
        description: str,
    ) -> dict:
        return {
            "scheme": "exact",
            "network": self.network,
            "maxAmountRequired": str(amount_usdc_micro),
            "resource": resource_url,
            "description": description,
            "mimeType": "application/json",
            "payTo": self.treasury,
            "asset": {
                "address": "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU"  # USDC devnet
            },
            "maxTimeoutSeconds": 60,
        }

    def extract_payment(self, headers: dict) -> Optional[str]:
        return headers.get("x-payment") or headers.get("X-PAYMENT")

    async def verify_payment(self, payment_b64: str, requirements: dict) -> bool:
        """Calls facilitator to verify payment proof."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.facilitator_url}/verify",
                json={
                    "paymentPayload": payment_b64,
                    "paymentRequirements": requirements,
                },
                timeout=30,
            )
            if resp.status_code != 200:
                return False
            data = resp.json()
            return data.get("isValid", False)

    async def settle_payment(self, payment_b64: str, requirements: dict) -> str:
        """Submits payment on-chain via facilitator. Returns tx signature."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.facilitator_url}/settle",
                json={
                    "paymentPayload": payment_b64,
                    "paymentRequirements": requirements,
                },
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()["transaction"]
```

### Sandbox endpoint integration

```python
# api/routers/sandbox.py
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter()

@router.post("/v1/sandbox/{listing_id}")
async def sandbox_query(
    listing_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    x402: X402Handler = Depends(get_x402),
    runtime: VLLMClient = Depends(get_runtime),
):
    listing = await db.get(Listing, listing_id)
    if not listing or not listing.active:
        raise HTTPException(404, "Listing not found")

    requirements = x402.create_payment_requirements(
        amount_usdc_micro=listing.sandbox_price_usdc,
        resource_url=f"{settings.BASE_URL}/v1/sandbox/{listing_id}",
        description=f"Sandbox preview: {listing.title}",
    )

    payment = x402.extract_payment(dict(request.headers))
    if not payment:
        return JSONResponse(
            content={"x402Version": 1, "accepts": [requirements]},
            status_code=402,
            headers={"X-PAYMENT-REQUIREMENTS": json.dumps(requirements)},
        )

    if not await x402.verify_payment(payment, requirements):
        raise HTTPException(402, "Invalid payment proof")

    # Settle on-chain
    tx_sig = await x402.settle_payment(payment, requirements)

    # Run sandbox inference
    body = await request.json()
    query = body.get("query", "")

    response = await runtime.run_with_memory(
        listing=listing,
        query=query,
        max_tokens=200,
    )

    # Store sandbox query for analytics
    await db.add(SandboxQuery(
        id=str(uuid.uuid4()),
        buyer=requirements_buyer_from(payment),
        listing_id=listing_id,
        query=query,
        response=response.text,
        quality_score=response.quality_score,
        payment_tx=tx_sig,
        created_at=datetime.utcnow(),
    ))
    await db.commit()

    return {
        "response": response.text,
        "quality_score": response.quality_score,
        "queries_remaining": response.queries_remaining,
        "tx_signature": tx_sig,
    }
```

---

## 9. The Solana indexer

```python
# indexer/run.py
import asyncio
from anchorpy import Program, Provider
from solders.pubkey import Pubkey
from solana.rpc.async_api import AsyncClient
from solana.rpc.websocket_api import connect

from .listings_indexer import handle_memory_listed, handle_memory_purchased
from .decisions_indexer import handle_decision_anchored


async def run_indexer():
    program_id = Pubkey.from_string(settings.AGENTVAULT_PROGRAM_ID)
    rpc = AsyncClient(settings.SOLANA_RPC_URL)

    # Load IDL
    with open("shared/types/idl.json") as f:
        idl = json.load(f)

    program = Program(idl, program_id, Provider(rpc, ...))

    # Subscribe to logs
    async with connect(settings.SOLANA_WS_URL) as ws:
        await ws.logs_subscribe(commitment="confirmed", filter_=str(program_id))
        async for msg in ws:
            for log_msg in msg.result.value.logs:
                if "MemoryListed" in log_msg:
                    event = program.coder.events.parse(log_msg)
                    await handle_memory_listed(event)
                elif "MemoryPurchased" in log_msg:
                    event = program.coder.events.parse(log_msg)
                    await handle_memory_purchased(event)
                elif "DecisionAnchored" in log_msg:
                    event = program.coder.events.parse(log_msg)
                    await handle_decision_anchored(event)


if __name__ == "__main__":
    asyncio.run(run_indexer())
```

For production-grade indexing, use Helius webhooks instead of WS (more reliable):

```python
# api/routers/webhooks.py
@router.post("/internal/helius_webhook")
async def helius_webhook(payload: list[dict], db: AsyncSession = Depends(get_db)):
    """Helius pushes events here when our program emits."""
    for tx in payload:
        for log in tx.get("logs", []):
            if "MemoryListed" in log:
                await handle_memory_listed_from_log(log, db)
            # ...
    return {"ok": True}
```

For the hackathon, **either WS or Helius webhook is fine**. WS is simpler to set up; webhooks are more reliable. Pick one.

---

## 10. Job queue with arq

```python
# jobs/queue.py
from arq import create_pool
from arq.connections import RedisSettings

async def get_queue():
    return await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))


# jobs/tasks.py — runs in worker process
from .compress_dispatcher import dispatch_compression
from .arweave_uploader import upload_to_arweave

async def compress_and_upload(ctx, job_id: str, raw_bytes: bytes, metadata: dict):
    """
    Full pipeline:
    1. Send to TurboQuant worker (separate service on RunPod)
    2. Get compressed blob back
    3. Upload to Arweave via Bundlr
    4. Update job record in DB
    5. Notify via WebSocket
    """
    db = ctx["db"]
    ws_pub = ctx["ws_pub"]

    # Step 1: compression
    await ws_pub.publish(job_id, {"phase": "compressing", "progress": 0})
    compressed_blob, blob_metadata = await dispatch_compression(raw_bytes, metadata)

    # Step 2: hash
    import hashlib
    content_hash = hashlib.sha256(compressed_blob).digest()

    # Step 3: Arweave upload
    await ws_pub.publish(job_id, {"phase": "uploading", "progress": 50})
    arweave_tx = await upload_to_arweave(compressed_blob, blob_metadata)

    # Step 4: update job
    await db.execute(
        update(CompressJob)
        .where(CompressJob.id == job_id)
        .values(
            status="done",
            output_size_bytes=len(compressed_blob),
            content_hash=content_hash,
            arweave_tx=arweave_tx,
            completed_at=datetime.utcnow(),
        )
    )
    await db.commit()

    # Step 5: notify
    await ws_pub.publish(job_id, {
        "phase": "complete",
        "progress": 100,
        "arweave_tx": arweave_tx,
        "content_hash": content_hash.hex(),
    })


class WorkerSettings:
    functions = [compress_and_upload]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
```

---

## 11. Bundlr/Irys integration

The Python SDK is limited; we shell out to a small Node sidecar OR use HTTP API directly.

**Option A — Node sidecar (recommended):**

```python
# storage/arweave.py
import httpx
import base64

class ArweaveClient:
    def __init__(self, sidecar_url: str = "http://localhost:3030"):
        self.sidecar_url = sidecar_url

    async def upload(self, blob: bytes, tags: list[dict]) -> str:
        """
        Upload via Node.js sidecar that wraps @irys/sdk.
        Returns Arweave TX ID.
        """
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(
                f"{self.sidecar_url}/upload",
                json={
                    "blob": base64.b64encode(blob).decode(),
                    "tags": tags,
                },
            )
            resp.raise_for_status()
            return resp.json()["arweave_tx"]

    async def fetch(self, arweave_tx: str) -> bytes:
        """Fetch blob from Arweave gateway."""
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.get(f"https://arweave.net/{arweave_tx}")
            resp.raise_for_status()
            return resp.content
```

The sidecar is ~30 lines of Express:

```javascript
// scripts/irys-sidecar.js
const express = require("express");
const Irys = require("@irys/sdk");
const bs58 = require("bs58");

const app = express();
app.use(express.json({ limit: "500mb" }));

const irys = new Irys({
  network: "devnet",
  token: "solana",
  key: process.env.BUNDLR_KEYPAIR,
});

app.post("/upload", async (req, res) => {
  const blob = Buffer.from(req.body.blob, "base64");
  const tags = req.body.tags;
  const receipt = await irys.upload(blob, { tags });
  res.json({ arweave_tx: receipt.id });
});

app.listen(3030, () => console.log("Irys sidecar on :3030"));
```

Run as a Railway service alongside the API.

---

## 12. Runtime client (talks to RunPod Qwen)

```python
# runtime/vllm_client.py
import httpx
from typing import Optional

class VLLMClient:
    def __init__(self, endpoint: str, api_key: Optional[str] = None):
        self.endpoint = endpoint
        self.api_key = api_key

    async def run_with_memory(self, listing, query: str, max_tokens: int = 200):
        """
        1. Fetch + verify + decompress the listing's memory
        2. Load into vLLM via LMCache
        3. Run inference
        """
        # Fetch from Arweave
        blob = await arweave.fetch(listing.arweave_tx)

        # Verify hash
        import hashlib
        if hashlib.sha256(blob).digest() != listing.content_hash:
            raise ValueError("Hash mismatch — Arweave returned tampered blob")

        # Send compressed blob to TurboQuant worker for decompression + LMCache load
        cache_id = await self._dispatch_decompress_and_load(blob, listing)

        # Run inference with cache_id pointing to loaded state
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.endpoint}/v1/completions",
                headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
                json={
                    "model": listing.model_id,
                    "prompt": query,
                    "max_tokens": max_tokens,
                    "extra_body": {"kv_cache_id": cache_id},  # LMCache hook
                },
            )
            resp.raise_for_status()
            data = resp.json()

        return SandboxResponse(
            text=data["choices"][0]["text"],
            quality_score=self._score(query, data["choices"][0]["text"]),
            queries_remaining=4,  # decrement separately
        )
```

---

## 13. Settings via pydantic-settings

```python
# api/config.py
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # App
    BASE_URL: str = "https://api.agentvault.xyz"
    ENVIRONMENT: str = "production"

    # Database
    DATABASE_URL: str = Field(...)

    # Redis
    REDIS_URL: str = Field(...)

    # Solana
    SOLANA_NETWORK: str = "devnet"
    SOLANA_RPC_URL: str = "https://api.devnet.solana.com"
    SOLANA_WS_URL: str = "wss://api.devnet.solana.com"
    AGENTVAULT_PROGRAM_ID: str = Field(...)
    USDC_MINT: str = "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU"
    PLATFORM_TREASURY: str = Field(...)

    # x402
    X402_FACILITATOR_URL: str = "https://facilitator.payai.network"

    # Arweave (sidecar URL, Bundlr keypair lives in sidecar's env)
    IRYS_SIDECAR_URL: str = "http://irys-sidecar.railway.internal:3030"

    # TurboQuant worker
    WORKER_URL: str = Field(...)
    WORKER_API_KEY: str = Field(...)

    # vLLM runtime (RunPod)
    VLLM_ENDPOINT: str = Field(...)
    VLLM_API_KEY: str = ""

    # Pricing
    BASE_FEE_USDC: int = 500_000
    PER_MB_COMPUTE_USDC: int = 100_000
    PER_MB_STORAGE_USDC: int = 50_000

    # Pagination
    MAX_PAGE_SIZE: int = 100
    DEFAULT_PAGE_SIZE: int = 20

    class Config:
        env_file = ".env"


settings = Settings()
```

---

## 14. Deployment to Railway

### `railway.json`

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "Dockerfile"
  },
  "deploy": {
    "startCommand": "uvicorn api.main:app --host 0.0.0.0 --port $PORT",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10,
    "healthcheckPath": "/health",
    "healthcheckTimeout": 100
  }
}
```

### `Dockerfile`

```dockerfile
FROM python:3.12-slim

# Install uv
RUN pip install --no-cache-dir uv

WORKDIR /app

# Install dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy app
COPY . .

# Run migrations on start
CMD alembic upgrade head && \
    uvicorn api.main:app --host 0.0.0.0 --port $PORT --workers 1
```

### Environment variables in Railway dashboard

Set all of these:
- `DATABASE_URL` (from Supabase project settings)
- `REDIS_URL` (Railway Redis plugin auto-injects)
- `SOLANA_RPC_URL`, `SOLANA_WS_URL`
- `AGENTVAULT_PROGRAM_ID`
- `PLATFORM_TREASURY`
- `WORKER_URL`, `WORKER_API_KEY`
- `VLLM_ENDPOINT`
- `IRYS_SIDECAR_URL`

Deploy:
```bash
# Connect GitHub repo to Railway, then:
git push origin main
# Railway auto-deploys
```

---

## 15. Claude Code prompt — paste this verbatim

````
You are building the AgentVault backend — a FastAPI server that runs on Railway, uses Supabase Postgres + Railway Redis, indexes a Solana program, and serves a marketplace API + x402-gated sandbox endpoints + WebSocket gateway.

## Read the spec
Open `docs/02_BACKEND.md` and read everything. Build exactly what's specified. The spec covers: file structure, API contract, database schema, x402 integration, Solana indexer, job queue, Bundlr integration, deployment.

Also read `docs/05_WEBSOCKET_DESIGN.md` for the WebSocket portions of this build.

## Hard requirements
- Python 3.12, FastAPI, SQLAlchemy 2.0 async
- Supabase Postgres (just a regular Postgres URL)
- Redis via Railway plugin
- All endpoints from section 6 of the spec
- x402 integration via PayAI facilitator
- Indexer can subscribe to Solana program events (use websocket subscribe for hackathon, Helius webhooks as a stretch)
- Background workers via arq

## Build order
1. `pyproject.toml` with all dependencies from section 4
2. `api/config.py` — Settings via pydantic-settings
3. `storage/models.py` — SQLAlchemy models matching the migration in section 5
4. Alembic setup + initial migration
5. `solana/client.py` — AnchorPy program client
6. `solana/pdas.py` — PDA derivation helpers
7. `api/main.py` — FastAPI app skeleton with CORS, lifespan, health check
8. `api/deps.py` — DB session, Redis pool, x402 handler dependencies
9. `api/routers/listings.py` — GET endpoints (read from Supabase)
10. `api/routers/pricing.py` — pure pricing calculator
11. `api/routers/upload.py` — POST /upload/init, /upload/blob, /upload/finalize
12. `api/x402/handler.py` + `api/routers/sandbox.py` — x402-gated sandbox
13. `api/routers/verify.py` + `api/routers/decisions.py`
14. `runtime/vllm_client.py` — talks to RunPod
15. `storage/arweave.py` — Bundlr sidecar client
16. `jobs/queue.py` + `jobs/tasks.py` — arq job definitions
17. `workers/run.py` — main worker entrypoint
18. `indexer/run.py` + handlers — Solana log subscriber
19. WebSocket router (per doc 05)
20. `Dockerfile` + `railway.json`
21. Tests with pytest-asyncio

## Critical implementation notes
- Database is async-only — use AsyncSession everywhere, no sync calls
- All Solana RPC interactions go through a singleton AsyncClient
- USDC values are u64 micro-units (multiply human price by 1_000_000)
- Content hashes stored as bytes(32) in DB, hex-encoded only at API boundary
- The indexer must be idempotent — reprocessing the same event must not double-write
- Don't use Anchor-Py's high-level fetch_all if you have many accounts; use raw RPC `get_program_accounts` with proper filters

## Common pitfalls
- Forgetting to `await db.commit()` after writes
- WebSocket connections leaking when client disconnects (handle in finally block)
- Bundlr uploads timing out (default 30s is too short, use 300s)
- Solana WS subscriptions disconnect periodically — implement auto-reconnect
- Migrations run BEFORE app starts (sequence in Dockerfile CMD)

## Test it
After implementation:
```
uv run alembic upgrade head
uv run uvicorn api.main:app --reload
```
Visit `/docs` for the OpenAPI UI. Test each endpoint manually before writing pytest cases.

For local development without Railway:
```
docker run -p 6379:6379 redis:7
DATABASE_URL=... REDIS_URL=redis://localhost:6379 uv run uvicorn api.main:app --reload
```

Build it. Test it. Deploy to Railway.
````

---

## 16. Definition of done

- [ ] All 8 REST endpoints implemented and documented in OpenAPI
- [ ] Sandbox endpoint correctly handles x402 402 → payment → 200 flow
- [ ] WebSocket endpoint streams compression + upload progress
- [ ] Solana indexer running, listings appear in Supabase within 30s of on-chain confirmation
- [ ] Pricing endpoint returns correct USDC amounts for any size
- [ ] Bundlr/Irys upload working end-to-end (test upload + fetch round-trip)
- [ ] Arweave hash verification matches on-chain hash
- [ ] Compress job queue working (Redis → arq → worker dispatcher)
- [ ] Deployed to Railway with all env vars set
- [ ] Health check at `/health` returns 200
- [ ] Migrations applied to Supabase
- [ ] At least 5 manual smoke tests pass on devnet

When this list is checked, frontend and buyer agent can start consuming the API.

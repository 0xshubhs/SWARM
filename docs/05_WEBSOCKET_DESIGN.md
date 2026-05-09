# 05 — WebSocket Design

**Where:** Cross-cutting (server-side in `backend/api/routers/ws.py`, client-side in `frontend/lib/hooks/` and `cli/src/transport/`)
**Stack:** FastAPI WebSockets + Redis pub/sub + signed challenge auth
**Build alongside:** `02_BACKEND.md` (backend WS gateway) and `04_FRONTEND.md` (client hooks)

---

## 1. What this document is for

Three components need realtime push from the backend:

| Consumer | What it needs to know about |
|---|---|
| **Frontend listing flow** (seller's `/list` page) | Compression %, Arweave upload %, on-chain confirmation |
| **Frontend agent demo** (`/agent` page) | Buyer agent reasoning events as they happen |
| **CLI** (when used as seller tool) | Same as frontend listing — compression, upload, confirmation |

Polling sucks for these — events are bursty and the UI needs to feel live. WebSockets are the right tool.

This doc specifies:
- The channel naming convention (so all consumers agree)
- The message schemas (so types are shared)
- The auth model (so randos can't subscribe to your channels)
- The fanout architecture (Redis pub/sub between API and worker processes)
- Reconnect logic (browsers and CLI both lose connections; this must be graceful)

---

## 2. Architecture

```
┌────────────────────┐      ┌────────────────────┐
│ Frontend / CLI     │      │ Worker process     │
│                    │      │ (compress, upload) │
└────────┬───────────┘      └────────┬───────────┘
         │ WSS                        │
         │                            │ PUBLISH "events:upload:{id}"
         ▼                            ▼
   ┌────────────────────────────────────────┐
   │      FastAPI backend (Railway)         │
   │                                        │
   │  ┌─────────────┐    ┌──────────────┐   │
   │  │ WS gateway  │◄───┤  Redis P/S   │   │
   │  │ /v1/ws/...  │    │  subscriber  │   │
   │  └─────────────┘    └──────────────┘   │
   │                          ▲              │
   │  ┌──────────────────────┘              │
   │  │ HTTP/internal: PUBLISH events       │
   │  │ (indexer, x402 settle, etc.)        │
   └────────────────────────────────────────┘
                              │
                              ▼
                       ┌──────────────┐
                       │   Redis      │
                       │  (Railway)   │
                       └──────────────┘
```

### Why Redis pub/sub for fanout

The compression worker runs in a separate process (sometimes a separate machine — RunPod). It can't write directly to a WebSocket connection that's held by the API process. Redis pub/sub solves this:

1. Worker publishes to `events:upload:{upload_id}` channel
2. API process has a Redis subscriber
3. API process forwards messages to any WebSocket clients subscribed to that upload

This means workers can be horizontally scaled, and any API instance can serve any client.

---

## 3. Channel naming convention

```
/v1/ws/upload/{upload_id}            # Compression + upload progress
/v1/ws/listing/{listing_pda}         # Listing-level events (post-creation)
/v1/ws/agent/{run_id}                # Buyer agent reasoning stream
/v1/ws/user/{wallet_pubkey}          # User-level events (purchases, sales)
```

### Redis channel format

```
events:upload:{upload_id}            # Internal pub/sub
events:listing:{listing_pda}
events:agent:{run_id}
events:user:{wallet_pubkey}
```

API process subscribes to the matching `events:*` channel when a client opens a WS at the corresponding `/v1/ws/*` URL.

---

## 4. Message schemas

All messages are JSON. Top-level shape:

```typescript
interface WSMessage {
  type: string;          // discriminator
  ts: number;            // unix ms
  data: any;             // type-specific payload
}
```

Subtypes per channel below.

### 4.1 Upload channel (`/v1/ws/upload/{upload_id}`)

```typescript
type UploadMessage =
  | { type: "upload.received"; ts: number; data: { size_bytes: number } }
  | { type: "compress.started"; ts: number; data: { worker_id: string } }
  | { type: "compress.progress"; ts: number; data: { percent: number; current_layer: number; total_layers: number } }
  | { type: "compress.done"; ts: number; data: { compressed_size_bytes: number; ratio: number; content_hash_hex: string } }
  | { type: "arweave.upload.started"; ts: number; data: {} }
  | { type: "arweave.upload.progress"; ts: number; data: { percent: number; bytes_uploaded: number } }
  | { type: "arweave.upload.done"; ts: number; data: { arweave_tx: string } }
  | { type: "listing.pending"; ts: number; data: { instruction: SerializedInstruction } } // sent so frontend can sign
  | { type: "listing.confirmed"; ts: number; data: { listing_pda: string; tx_signature: string } }
  | { type: "error"; ts: number; data: { code: string; message: string; recoverable: boolean } };
```

### 4.2 Agent channel (`/v1/ws/agent/{run_id}`)

The buyer agent emits reasoning events as it runs. The frontend `/agent` page renders these in real time.

```typescript
type AgentMessage =
  | { type: "agent.start"; ts: number; data: { task: string; budget_usdc: number } }
  | { type: "agent.classify"; ts: number; data: { tags: string[]; reasoning: string } }
  | { type: "agent.discover"; ts: number; data: { candidates: ListingPreview[] } }
  | { type: "agent.sandbox.start"; ts: number; data: { listing_id: string; query: string } }
  | { type: "agent.sandbox.x402"; ts: number; data: { listing_id: string; tx_signature: string; amount_usdc: number } }
  | { type: "agent.sandbox.response"; ts: number; data: { listing_id: string; response: string; score: number } }
  | { type: "agent.decision"; ts: number; data: { winner_id: string; reasoning: string; score: number } }
  | { type: "agent.purchase.signing"; ts: number; data: { listing_id: string } }
  | { type: "agent.purchase.confirmed"; ts: number; data: { tx_signature: string; license_pda: string } }
  | { type: "agent.fetch.arweave"; ts: number; data: { arweave_tx: string; bytes: number } }
  | { type: "agent.verify.hash"; ts: number; data: { hash_hex: string; verified: boolean } }
  | { type: "agent.decompress"; ts: number; data: { decompressed_size_mb: number; load_time_ms: number } }
  | { type: "agent.execute.start"; ts: number; data: { prompt: string } }
  | { type: "agent.execute.token"; ts: number; data: { token: string } } // streaming output
  | { type: "agent.execute.done"; ts: number; data: { output: string; total_tokens: number } }
  | { type: "agent.complete"; ts: number; data: { total_cost_usdc: number; duration_ms: number } }
  | { type: "agent.error"; ts: number; data: { phase: string; error: string } };
```

### 4.3 Listing channel (`/v1/ws/listing/{listing_pda}`)

Live updates after a listing is created — purchases roll in, prices update, etc. Used by the seller's dashboard.

```typescript
type ListingMessage =
  | { type: "listing.purchase"; ts: number; data: { buyer: string; amount_usdc: number; tx: string } }
  | { type: "listing.sandbox"; ts: number; data: { buyer: string; queries_left: number } }
  | { type: "listing.price_update"; ts: number; data: { new_price: number; old_price: number } }
  | { type: "listing.delisted"; ts: number; data: {} };
```

### 4.4 User channel (`/v1/ws/user/{wallet_pubkey}`)

Aggregates all events relevant to a specific user. Used by header notification bell.

```typescript
type UserMessage =
  | { type: "user.sale"; ts: number; data: { listing_id: string; amount_usdc: number } }
  | { type: "user.purchase_confirmed"; ts: number; data: { listing_id: string } }
  | { type: "user.decision_anchored"; ts: number; data: { decision_pda: string } };
```

### 4.5 Shared types — share these between TS and Python

Generate from a single source of truth. Recommended approach:

```
shared/types/
├── ws-messages.ts           # TS source of truth
├── ws-messages.py           # Hand-maintained Python mirror (or Pydantic)
└── README.md                # "edit ts first, mirror to py"
```

Or (better) use [**Json Schema → both**] approach with `quicktype` / `datamodel-code-generator`. For hackathon, hand-maintain both and add a CI check that they're in sync.

---

## 5. Server-side: FastAPI WebSocket gateway

### 5.1 Connection lifecycle

```python
# api/routers/ws.py
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
from typing import Optional
from redis.asyncio import Redis
from .auth_ws import verify_ws_token
from ..config import settings

router = APIRouter()


@router.websocket("/v1/ws/upload/{upload_id}")
async def upload_ws(
    websocket: WebSocket,
    upload_id: str,
    token: str = Query(...),
):
    # 1. Authenticate (see section 6)
    try:
        claims = verify_ws_token(token, expected_subject=f"upload:{upload_id}")
    except Exception as e:
        await websocket.close(code=4001, reason=f"unauthorized: {e}")
        return

    await websocket.accept()

    # 2. Subscribe to Redis channel
    redis: Redis = websocket.app.state.redis
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"events:upload:{upload_id}")

    # 3. Send hello
    await websocket.send_json({
        "type": "ws.hello",
        "ts": now_ms(),
        "data": {"channel": f"upload:{upload_id}"},
    })

    # 4. Two-way pump: Redis → WS, and WS → ping/pong
    try:
        # Use asyncio.gather to run both directions
        recv_task = asyncio.create_task(_pump_redis_to_ws(pubsub, websocket))
        ping_task = asyncio.create_task(_pump_pings(websocket))

        done, pending = await asyncio.wait(
            [recv_task, ping_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()

    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(f"events:upload:{upload_id}")
        await pubsub.close()


async def _pump_redis_to_ws(pubsub, websocket: WebSocket):
    """Read from Redis pub/sub, forward to WebSocket."""
    async for message in pubsub.listen():
        if message["type"] != "message":
            continue
        try:
            await websocket.send_text(message["data"].decode() if isinstance(message["data"], bytes) else message["data"])
        except Exception:
            break


async def _pump_pings(websocket: WebSocket):
    """Send periodic pings; close on client disconnect."""
    while True:
        try:
            await asyncio.sleep(20)
            await websocket.send_json({"type": "ws.ping", "ts": now_ms(), "data": {}})
        except Exception:
            break


def now_ms() -> int:
    import time
    return int(time.time() * 1000)
```

The `/v1/ws/agent/{run_id}` and `/v1/ws/user/{pubkey}` endpoints follow the same pattern.

### 5.2 Publishing events from workers

Any code that wants to push an event publishes to the matching Redis channel:

```python
# jobs/tasks.py — runs in arq worker
from redis.asyncio import Redis
import json

async def publish_event(redis: Redis, channel: str, msg_type: str, data: dict):
    payload = {
        "type": msg_type,
        "ts": now_ms(),
        "data": data,
    }
    await redis.publish(channel, json.dumps(payload))


async def compress_and_upload(ctx, upload_id: str, raw_bytes: bytes, metadata: dict):
    redis = ctx["redis"]
    chan = f"events:upload:{upload_id}"

    await publish_event(redis, chan, "upload.received", {"size_bytes": len(raw_bytes)})

    # Send to TurboQuant worker
    await publish_event(redis, chan, "compress.started", {"worker_id": settings.WORKER_URL})
    compressed_blob, blob_metadata = await dispatch_compression(
        raw_bytes, metadata,
        progress_callback=lambda pct, layer, total: asyncio.ensure_future(
            publish_event(redis, chan, "compress.progress", {
                "percent": pct, "current_layer": layer, "total_layers": total,
            })
        ),
    )
    content_hash = hashlib.sha256(compressed_blob).digest()
    await publish_event(redis, chan, "compress.done", {
        "compressed_size_bytes": len(compressed_blob),
        "ratio": len(raw_bytes) / len(compressed_blob),
        "content_hash_hex": content_hash.hex(),
    })

    # Upload
    await publish_event(redis, chan, "arweave.upload.started", {})
    arweave_tx = await arweave_upload_with_progress(
        compressed_blob,
        progress_callback=lambda pct, bytes: asyncio.ensure_future(
            publish_event(redis, chan, "arweave.upload.progress", {
                "percent": pct, "bytes_uploaded": bytes,
            })
        ),
    )
    await publish_event(redis, chan, "arweave.upload.done", {"arweave_tx": arweave_tx})

    # Build the on-chain instruction and send it back so frontend can sign
    instruction = build_list_memory_instruction(...)
    await publish_event(redis, chan, "listing.pending", {
        "instruction": serialize_instruction(instruction),
    })
    # Then frontend signs+sends, indexer picks it up, indexer publishes "listing.confirmed"
```

### 5.3 The indexer publishes too

```python
# indexer/listings_indexer.py
async def handle_memory_purchased(event, db, redis):
    # ... save to DB ...

    # Publish to listing channel and user channel
    await publish_event(redis, f"events:listing:{event.listing}", "listing.purchase", {
        "buyer": str(event.buyer),
        "amount_usdc": event.price_usdc,
        "tx": event.tx_signature,
    })
    await publish_event(redis, f"events:user:{event.seller}", "user.sale", {
        "listing_id": str(event.listing),
        "amount_usdc": event.price_usdc,
    })
    await publish_event(redis, f"events:user:{event.buyer}", "user.purchase_confirmed", {
        "listing_id": str(event.listing),
    })
```

---

## 6. Authentication

WebSocket auth is tricky because browsers can't set arbitrary headers. We use **signed JWT tokens passed as query params**. Tokens are short-lived (5 min) and scoped to a specific channel.

### 6.1 Token issuance — REST endpoint

```python
# api/routers/ws_auth.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from jose import jwt
import nacl.signing, nacl.exceptions, base58
from datetime import datetime, timedelta

router = APIRouter()


class WSTokenRequest(BaseModel):
    channel: str                 # e.g. "upload:abc-123" or "user:pubkey"
    wallet_pubkey: str
    signature: str               # base58, signs the challenge
    challenge_ts: int            # unix ms — must be within last 60s


@router.post("/v1/ws/token")
async def issue_ws_token(req: WSTokenRequest):
    # 1. Verify challenge timestamp is fresh
    now = int(datetime.utcnow().timestamp() * 1000)
    if abs(now - req.challenge_ts) > 60_000:
        raise HTTPException(400, "stale challenge")

    # 2. Verify signature
    challenge = f"agentvault.ws:{req.channel}:{req.challenge_ts}"
    pk_bytes = base58.b58decode(req.wallet_pubkey)
    try:
        verify_key = nacl.signing.VerifyKey(pk_bytes)
        sig_bytes = base58.b58decode(req.signature)
        verify_key.verify(challenge.encode(), sig_bytes)
    except nacl.exceptions.BadSignatureError:
        raise HTTPException(401, "bad signature")

    # 3. Verify channel access (e.g., user channel must match wallet)
    if req.channel.startswith("user:"):
        if req.channel != f"user:{req.wallet_pubkey}":
            raise HTTPException(403, "wrong channel")
    # upload:* channels: any signer is allowed (server pairs upload_id ↔ wallet at creation)
    # agent:* channels: any signer (run_id is hard to guess)

    # 4. Issue token
    token = jwt.encode(
        {
            "sub": req.channel,
            "iat": now,
            "exp": now + 5 * 60_000,    # 5 minutes
        },
        settings.WS_TOKEN_SECRET,
        algorithm="HS256",
    )
    return {"token": token, "expires_in": 300}
```

### 6.2 Server-side verification

```python
# api/routers/auth_ws.py
from jose import jwt, JWTError

def verify_ws_token(token: str, expected_subject: str) -> dict:
    try:
        claims = jwt.decode(token, settings.WS_TOKEN_SECRET, algorithms=["HS256"])
    except JWTError as e:
        raise ValueError(f"invalid token: {e}")
    if claims.get("sub") != expected_subject:
        raise ValueError(f"channel mismatch: {claims.get('sub')} != {expected_subject}")
    return claims
```

### 6.3 Client flow (browser)

```typescript
// lib/ws-auth.ts
export async function getWSToken(channel: string, wallet: WalletContextState): Promise<string> {
  if (!wallet.publicKey || !wallet.signMessage) throw new Error("wallet not ready");

  const challengeTs = Date.now();
  const challenge = `agentvault.ws:${channel}:${challengeTs}`;
  const sigBytes = await wallet.signMessage(new TextEncoder().encode(challenge));
  const sigB58 = bs58.encode(sigBytes);

  const resp = await fetch(`${BACKEND_URL}/v1/ws/token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      channel,
      wallet_pubkey: wallet.publicKey.toBase58(),
      signature: sigB58,
      challenge_ts: challengeTs,
    }),
  });
  if (!resp.ok) throw new Error("token request failed");
  const { token } = await resp.json();
  return token;
}
```

For **upload channels**, the `upload_id` itself is unguessable (UUID v4 returned by `/v1/upload/init` to the authenticated seller), so we can skip signature challenge for those and just check that the requester is the original seller:

```typescript
// Simplified: backend issues token directly when /upload/init is called
// Client gets `{ upload_id, ws_token }` in one response, no second round-trip.
```

---

## 7. Client-side: React hook for upload

```typescript
// lib/hooks/useUploadProgress.ts
import { useEffect, useState, useRef } from "react";

export interface UploadProgress {
  phase: "queued" | "compressing" | "uploading" | "listing_pending" | "confirmed" | "error";
  compressPercent: number;
  uploadPercent: number;
  contentHash?: string;
  arweaveTx?: string;
  listingPda?: string;
  txSignature?: string;
  pendingInstruction?: SerializedInstruction;
  error?: string;
}

const INITIAL: UploadProgress = {
  phase: "queued",
  compressPercent: 0,
  uploadPercent: 0,
};

export function useUploadProgress(uploadId: string | null, wsToken: string | null): UploadProgress {
  const [progress, setProgress] = useState<UploadProgress>(INITIAL);
  const reconnectAttempts = useRef(0);

  useEffect(() => {
    if (!uploadId || !wsToken) return;
    let cancelled = false;
    let ws: WebSocket | null = null;
    let reconnectTimer: any;

    function connect() {
      if (cancelled) return;

      const url = `${process.env.NEXT_PUBLIC_BACKEND_WS_URL}/v1/ws/upload/${uploadId}?token=${wsToken}`;
      ws = new WebSocket(url);

      ws.onopen = () => {
        reconnectAttempts.current = 0;
      };

      ws.onmessage = (evt) => {
        const msg = JSON.parse(evt.data);
        applyMessage(msg, setProgress);
      };

      ws.onclose = (evt) => {
        if (cancelled) return;
        // Exponential backoff
        const delay = Math.min(30_000, 1000 * 2 ** reconnectAttempts.current);
        reconnectAttempts.current += 1;
        reconnectTimer = setTimeout(connect, delay);
      };

      ws.onerror = () => ws?.close();
    }

    connect();

    return () => {
      cancelled = true;
      clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, [uploadId, wsToken]);

  return progress;
}

function applyMessage(msg: any, set: (u: (p: UploadProgress) => UploadProgress) => void) {
  switch (msg.type) {
    case "upload.received":
      set((p) => ({ ...p, phase: "compressing" }));
      break;
    case "compress.progress":
      set((p) => ({ ...p, compressPercent: msg.data.percent }));
      break;
    case "compress.done":
      set((p) => ({ ...p, compressPercent: 100, contentHash: msg.data.content_hash_hex, phase: "uploading" }));
      break;
    case "arweave.upload.progress":
      set((p) => ({ ...p, uploadPercent: msg.data.percent }));
      break;
    case "arweave.upload.done":
      set((p) => ({ ...p, uploadPercent: 100, arweaveTx: msg.data.arweave_tx }));
      break;
    case "listing.pending":
      set((p) => ({ ...p, phase: "listing_pending", pendingInstruction: msg.data.instruction }));
      break;
    case "listing.confirmed":
      set((p) => ({ ...p, phase: "confirmed", listingPda: msg.data.listing_pda, txSignature: msg.data.tx_signature }));
      break;
    case "error":
      set((p) => ({ ...p, phase: "error", error: msg.data.message }));
      break;
  }
}
```

### Agent stream hook

```typescript
// lib/hooks/useAgentStream.ts
import { useEffect, useState } from "react";

export interface AgentEvent {
  ts: number;
  type: string;
  data: any;
}

export function useAgentStream(task: string | null, wsToken: string | null) {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [result, setResult] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!task || !wsToken) return;
    setEvents([]);
    setResult(null);
    setError(null);
    setRunning(true);

    // First, kick off the agent run via REST — it returns a run_id
    let cancelled = false;
    let ws: WebSocket | null = null;

    (async () => {
      const resp = await fetch(`${BACKEND_URL}/v1/agent/runs`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${wsToken}` },
        body: JSON.stringify({ task }),
      });
      const { run_id } = await resp.json();
      if (cancelled) return;

      const url = `${WS_URL}/v1/ws/agent/${run_id}?token=${wsToken}`;
      ws = new WebSocket(url);

      ws.onmessage = (evt) => {
        const msg = JSON.parse(evt.data);
        setEvents((prev) => [...prev, msg]);
        if (msg.type === "agent.execute.done") {
          setResult(msg.data.output);
        }
        if (msg.type === "agent.complete") {
          setRunning(false);
          ws?.close();
        }
        if (msg.type === "agent.error") {
          setError(msg.data.error);
          setRunning(false);
          ws?.close();
        }
      };
    })();

    return () => {
      cancelled = true;
      ws?.close();
      setRunning(false);
    };
  }, [task, wsToken]);

  return { events, result, running, error };
}
```

---

## 8. CLI client (Rust)

```rust
// cli/src/transport/ws_client.rs
use tokio_tungstenite::{connect_async, tungstenite::Message};
use futures::{SinkExt, StreamExt};
use serde::Deserialize;

#[derive(Deserialize, Debug)]
#[serde(tag = "type", content = "data")]
pub enum UploadEvent {
    #[serde(rename = "upload.received")]
    Received { size_bytes: u64 },
    #[serde(rename = "compress.progress")]
    CompressProgress { percent: f32, current_layer: u32, total_layers: u32 },
    #[serde(rename = "compress.done")]
    CompressDone { compressed_size_bytes: u64, ratio: f32, content_hash_hex: String },
    #[serde(rename = "arweave.upload.progress")]
    ArweaveProgress { percent: f32, bytes_uploaded: u64 },
    #[serde(rename = "arweave.upload.done")]
    ArweaveDone { arweave_tx: String },
    #[serde(rename = "listing.confirmed")]
    ListingConfirmed { listing_pda: String, tx_signature: String },
    #[serde(rename = "error")]
    Error { code: String, message: String, recoverable: bool },
}

pub async fn subscribe_upload(
    upload_id: &str,
    token: &str,
    on_event: impl Fn(UploadEvent),
) -> anyhow::Result<()> {
    let url = format!("wss://api.agentvault.xyz/v1/ws/upload/{upload_id}?token={token}");
    let (ws_stream, _) = connect_async(&url).await?;
    let (_, mut read) = ws_stream.split();

    while let Some(msg) = read.next().await {
        match msg? {
            Message::Text(text) => {
                let event: UploadEvent = serde_json::from_str(&text)?;
                on_event(event);
            }
            Message::Close(_) => break,
            _ => {}
        }
    }

    Ok(())
}
```

Used in the CLI's `list` command with indicatif progress bars driven by these events.

---

## 9. Reconnection strategy

WebSockets disconnect. Design for it.

| Scenario | Behavior |
|---|---|
| Normal close (1000) | Don't reconnect |
| Auth failure (4001) | Don't reconnect; show error |
| Server error (1011) | Exponential backoff: 1s → 2s → 4s → ... → max 30s |
| Network blip (1006) | Same exponential backoff |
| Token expired (mid-connection) | Server closes 4001; client requests new token + reconnects |

After 5 failed reconnects within 5 minutes, give up and show a "connection lost — refresh page" UX. Don't retry forever.

For the **upload channel specifically**, missed messages are recoverable: the client can poll `/v1/upload/{upload_id}/status` to get the current state and re-sync. This is the safety net.

---

## 10. Backpressure & rate limits

WebSockets can be flooded. Limits:

| Limit | Value | Why |
|---|---|---|
| Max messages per connection per second | 10 | Prevents flooding |
| Max payload size | 64 KB | TurboQuant blobs go via HTTP, not WS |
| Max concurrent connections per IP | 10 | Prevents resource exhaustion |
| Max connections per user (token) | 5 | Sane limit |

Implement via a small middleware that tracks counts per IP + per token in Redis with TTL.

The agent stream is one place where 10 msg/s might be too low — bump to 50/s for that channel only. Tokens have rapid `agent.execute.token` events.

---

## 11. Testing

```python
# tests/test_ws.py
import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient
from api.main import app

@pytest.mark.asyncio
async def test_upload_ws_unauthorized():
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect("/v1/ws/upload/test-id?token=invalid") as ws:
                ws.receive_json()
        assert exc.value.code == 4001


@pytest.mark.asyncio
async def test_upload_ws_publishes_through_redis(redis_client):
    # Get a valid token
    token = await mint_test_token("upload:test-id")

    with TestClient(app) as client:
        with client.websocket_connect(f"/v1/ws/upload/test-id?token={token}") as ws:
            # Skip the hello message
            hello = ws.receive_json()
            assert hello["type"] == "ws.hello"

            # Publish to Redis
            await redis_client.publish("events:upload:test-id", json.dumps({
                "type": "compress.progress",
                "ts": 12345,
                "data": {"percent": 50, "current_layer": 14, "total_layers": 28},
            }))

            # Should receive it
            msg = ws.receive_json()
            assert msg["type"] == "compress.progress"
            assert msg["data"]["percent"] == 50
```

---

## 12. Claude Code prompt — paste this verbatim

````
You are implementing the WebSocket layer for AgentVault. This connects: backend FastAPI, frontend React, and CLI Rust client. The full spec is in `docs/05_WEBSOCKET_DESIGN.md`.

## Read the spec
Read all of section 1-11 of the doc. The architecture, channel naming, message schemas, auth model, and reconnect strategy are all specified. Don't deviate.

## Hard requirements
- Channel naming: /v1/ws/upload/{id}, /v1/ws/agent/{run_id}, /v1/ws/listing/{pda}, /v1/ws/user/{pubkey}
- Auth via short-lived JWT in query param, signed challenge from wallet
- Redis pub/sub for fanout (channel format: events:{channel-name})
- All messages: { type: string, ts: number, data: {} }
- Heartbeat ping every 20s
- Exponential backoff reconnect on client side
- Token expiry: 5 minutes

## Build order

### Backend (Python)
1. `api/routers/ws_auth.py` — POST /v1/ws/token (signed challenge → JWT)
2. `api/routers/auth_ws.py` — verify_ws_token helper used by WS endpoints
3. `api/routers/ws.py` — the four WS endpoints (upload, agent, listing, user)
4. Helper: publish_event(redis, channel, type, data) for use in workers/indexer
5. Add `/v1/upload/init` to return both upload_id AND ws_token (so frontend doesn't need second round-trip for upload channel)
6. Update `jobs/tasks.py` (compress_and_upload) to publish events at each phase
7. Update `indexer/*.py` to publish listing.confirmed, listing.purchase, user.sale events
8. Tests with pytest-asyncio + fakeredis or real Redis

### Frontend (TypeScript)
1. `lib/ws-auth.ts` — getWSToken helper (signs challenge, fetches token)
2. `lib/hooks/useWebSocket.ts` — generic WS hook with auto-reconnect
3. `lib/hooks/useUploadProgress.ts` — typed wrapper specific to upload channel
4. `lib/hooks/useAgentStream.ts` — typed wrapper for agent channel
5. `lib/hooks/useUserNotifications.ts` — typed wrapper for user channel (header bell)

### CLI (Rust)
1. `cli/src/transport/ws_client.rs` — generic WS client with deserializer
2. Wire into `cli/src/commands/list.rs` — drive indicatif progress bars from upload events

## Critical implementation notes
- FastAPI WS endpoints must use `await websocket.accept()` BEFORE any send
- Redis subscribe in a separate task — use asyncio.gather with cancellation
- Always close pubsub in finally block (memory leaks otherwise)
- JWT secret must be from env, not hardcoded
- Frontend reconnect: ONLY retry on close codes that aren't 1000 (normal) or 4xxx (auth)
- Browser WebSocket can't set headers, so token MUST go in query string

## Common pitfalls
- "WebSocket is closed before connection established" — happens when token check fails BEFORE accept(); use `websocket.close(4001)` not raise
- Redis pubsub messages come as bytes — decode before json.loads
- React strict mode runs effects twice in dev — useEffect cleanup must cancel reconnect timers
- Worker process needs its own Redis pool — don't share with API process
- Token expires mid-connection: server should close with 4001 + a message indicating "token_expired"; client refreshes and reconnects

## Testing checklist
1. Start backend with Redis
2. POST /v1/ws/token with valid signature → get token
3. Connect to /v1/ws/upload/{id}?token=... → receive ws.hello
4. From another process, redis-cli PUBLISH events:upload:{id} '{"type":"compress.progress","ts":1,"data":{"percent":50}}' → should receive on WS
5. Wait 20 seconds → should receive ping
6. Pass invalid token → should close with 4001
7. Connect, kill server, restart → client should auto-reconnect within 5s

Build it. Test the end-to-end flow with curl + wscat before wiring frontend hooks.
````

---

## 13. Definition of done

- [ ] `/v1/ws/token` endpoint mints JWTs for valid signed challenges
- [ ] All 4 WS endpoints accept connections and verify tokens
- [ ] Redis pub/sub fanout works (publish in worker → receive in client)
- [ ] Heartbeat pings every 20s
- [ ] Token expiry triggers clean disconnect (4001)
- [ ] Frontend `useUploadProgress` hook displays compression + upload progress live
- [ ] Frontend `useAgentStream` hook streams agent reasoning events
- [ ] Auto-reconnect with exponential backoff working in browser
- [ ] CLI `transport::subscribe_upload` works with indicatif progress bars
- [ ] Rate limit middleware in place (10 msg/s, 5 conns/user)
- [ ] At least 7 of the test cases in section 11 pass
- [ ] Documentation: example frontend usage, example backend publish

When this list is checked, the realtime layer is solid and the listing flow + agent demo both feel live.

"""Compress + upload pipeline. Runs in the workers/ process."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import httpx
import redis.asyncio as aioredis
from sqlalchemy import update

from api.config import settings
from jobs.queue import publish_event
from storage.arweave import ArweaveClient
from storage.db import SessionLocal
from storage.models import CompressJob


async def dispatch_compression(
    raw: bytes, redis: aioredis.Redis, channel: str
) -> tuple[bytes, dict]:
    """Send raw KV cache to the GPU worker; receive compressed blob + metadata.

    For dev / hackathon mode (no GPU worker), we fall back to a no-op:
    the input is treated as already-compressed and metadata is empty.
    """
    if settings.WORKER_URL == "http://localhost:9000" or not settings.WORKER_URL:
        await publish_event(redis, channel, "compress.progress", {
            "percent": 100, "current_layer": 1, "total_layers": 1,
        })
        return raw, {"compression": "none", "model_id": "qwen2.5-7b-instruct"}

    # Worker's /compress is multipart/form-data with a `file` field
    # (see worker/worker/server/routes/compress.py).
    async with httpx.AsyncClient(timeout=600) as client:
        resp = await client.post(
            f"{settings.WORKER_URL.rstrip('/')}/compress",
            files={"file": ("kv.pt", raw, "application/octet-stream")},
            headers={"X-API-Key": settings.WORKER_API_KEY},
        )
        resp.raise_for_status()
        return resp.content, {"compression": "turboquant", "model_id": "qwen2.5-7b-instruct"}


async def compress_and_upload(
    upload_id: str,
    raw: bytes,
    redis: aioredis.Redis,
    arweave: ArweaveClient,
) -> None:
    chan = f"events:upload:{upload_id}"
    try:
        await publish_event(redis, chan, "upload.received", {"size_bytes": len(raw)})
        await publish_event(redis, chan, "compress.started", {"worker_id": settings.WORKER_URL})

        blob, _meta = await dispatch_compression(raw, redis, chan)
        content_hash = hashlib.sha256(blob).digest()
        await publish_event(redis, chan, "compress.done", {
            "compressed_size_bytes": len(blob),
            "ratio": (len(raw) / max(1, len(blob))),
            "content_hash_hex": content_hash.hex(),
        })

        await publish_event(redis, chan, "arweave.upload.started", {})
        arweave_tx = await arweave.upload(
            blob,
            tags=[
                {"name": "Content-Type", "value": "application/octet-stream"},
                {"name": "App", "value": "AgentVault"},
            ],
        )
        await publish_event(redis, chan, "arweave.upload.done", {"arweave_tx": arweave_tx})

        async with SessionLocal() as session:
            await session.execute(
                update(CompressJob)
                .where(CompressJob.id == upload_id)
                .values(
                    status="done",
                    output_size_bytes=len(blob),
                    content_hash=content_hash,
                    arweave_tx=arweave_tx,
                    completed_at=datetime.now(tz=timezone.utc),
                )
            )
            await session.commit()

        await publish_event(redis, chan, "listing.pending", {
            "instruction": {
                "program_id": settings.AGENTVAULT_PROGRAM_ID,
                "name": "listMemory",
                "content_hash": content_hash.hex(),
                "arweave_tx": arweave_tx,
            }
        })
    except Exception as e:  # noqa: BLE001
        await publish_event(redis, chan, "error", {
            "code": "compress_failed",
            "message": str(e),
            "recoverable": False,
        })
        async with SessionLocal() as session:
            await session.execute(
                update(CompressJob)
                .where(CompressJob.id == upload_id)
                .values(status="failed", error=str(e))
            )
            await session.commit()

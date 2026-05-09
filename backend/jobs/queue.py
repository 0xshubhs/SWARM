"""Redis-backed job queue. We use a thin LPUSH/BRPOP interface instead of a
heavier framework — keeps the worker process small and dependency-light.
"""
from __future__ import annotations

import base64
import json
from typing import Any

import redis.asyncio as aioredis

QUEUE_KEY = "agentvault:jobs:compress"


async def enqueue_compress(redis: aioredis.Redis, upload_id: str, raw: bytes) -> None:
    payload = json.dumps(
        {"upload_id": upload_id, "blob_b64": base64.b64encode(raw).decode()}
    )
    await redis.lpush(QUEUE_KEY, payload)


async def dequeue_compress(redis: aioredis.Redis) -> dict[str, Any] | None:
    raw = await redis.brpop([QUEUE_KEY], timeout=5)
    if not raw:
        return None
    _, value = raw
    msg = json.loads(value)
    msg["raw"] = base64.b64decode(msg.pop("blob_b64"))
    return msg


async def publish_event(
    redis: aioredis.Redis, channel: str, msg_type: str, data: dict[str, Any]
) -> None:
    import time

    await redis.publish(
        channel,
        json.dumps({"type": msg_type, "ts": int(time.time() * 1000), "data": data}),
    )

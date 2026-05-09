"""Solana log subscriber. Mirrors program events into Supabase + publishes
fan-out events for the WS gateway.

For the hackathon path we use websocket logsSubscribe. In prod, prefer
Helius webhooks (more reliable, replay-safe).
"""
from __future__ import annotations

import asyncio
import json
import logging
import time

import redis.asyncio as aioredis
import websockets
from websockets.exceptions import WebSocketException

from api.config import settings
from api.deps import make_redis
from indexer.handlers import handle_event
from chain.events import detect_events

log = logging.getLogger("agentvault.indexer")


async def _subscribe_loop(redis: aioredis.Redis) -> None:
    sub_msg = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "logsSubscribe",
        "params": [
            {"mentions": [settings.AGENTVAULT_PROGRAM_ID]},
            {"commitment": "confirmed"},
        ],
    }
    backoff = 1.0
    while True:
        try:
            async with websockets.connect(settings.SOLANA_WS_URL) as ws:
                log.info("connected to %s", settings.SOLANA_WS_URL)
                await ws.send(json.dumps(sub_msg))
                backoff = 1.0
                async for raw in ws:
                    msg = json.loads(raw)
                    params = msg.get("params", {})
                    value = params.get("result", {}).get("value")
                    if not value:
                        continue
                    logs = value.get("logs", [])
                    sig = value.get("signature", "")
                    slot = msg.get("params", {}).get("result", {}).get("context", {}).get("slot", 0)
                    for ev in detect_events(logs):
                        await handle_event(ev.name, logs, sig, slot, redis)
        except (WebSocketException, OSError) as e:
            log.warning("ws error: %s — reconnecting in %.1fs", e, backoff)
            await asyncio.sleep(backoff)
            backoff = min(30.0, backoff * 2)


async def main() -> None:
    logging.basicConfig(level=settings.LOG_LEVEL.upper())
    redis = make_redis()
    log.info("indexer booted: program=%s ws=%s", settings.AGENTVAULT_PROGRAM_ID, settings.SOLANA_WS_URL)
    await _subscribe_loop(redis)


if __name__ == "__main__":
    asyncio.run(main())

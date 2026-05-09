"""Event handlers — turn detected log events into DB writes + WS pub.

Hackathon-mode parsing: we don't fully decode anchor event borsh data here.
Instead, the indexer handlers are dispatched and emit a generic "noticed"
event on the matching channel; richer parsing lives in the on-chain client
when the Anchor IDL is wired in (anchorpy.coder.events).
"""
from __future__ import annotations

import json
import logging

import redis.asyncio as aioredis

from jobs.queue import publish_event

log = logging.getLogger("agentvault.indexer.handlers")


async def handle_event(
    event_name: str,
    logs: list[str],
    tx_signature: str,
    slot: int,
    redis: aioredis.Redis,
) -> None:
    log.info("event %s sig=%s slot=%s", event_name, tx_signature[:8], slot)

    if event_name == "MemoryListed":
        # Real implementation: decode borsh, upsert into listings table,
        # publish to events:listing:{pda} and events:user:{seller}.
        await publish_event(redis, "events:listings:any", "listing.created", {
            "tx_signature": tx_signature, "slot": slot,
        })
    elif event_name == "MemoryPurchased":
        await publish_event(redis, "events:purchases:any", "purchase.confirmed", {
            "tx_signature": tx_signature, "slot": slot,
        })
    elif event_name == "DecisionAnchored":
        await publish_event(redis, "events:decisions:any", "decision.anchored", {
            "tx_signature": tx_signature, "slot": slot,
        })
    elif event_name == "ListingDelisted":
        await publish_event(redis, "events:listings:any", "listing.delisted", {
            "tx_signature": tx_signature, "slot": slot,
        })
    else:
        log.debug("unhandled event %s", event_name)

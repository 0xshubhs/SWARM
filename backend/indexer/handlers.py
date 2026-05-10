"""Event handlers — turn decoded Anchor events into DB writes + WS pub.

The indexer detects a `Program data: ...` line, decodes the event via
`chain.events.detect_events`, then we upsert the relevant row(s) and publish
on the per-PDA / per-user WS channels that the gateway in `api/routers/ws.py`
exposes.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

import redis.asyncio as aioredis
from solders.pubkey import Pubkey
from sqlalchemy.dialects.postgresql import insert as pg_insert

from chain.accounts import fetch_decision, fetch_listing
from chain.client import get_rpc
from chain.events import DecodedEvent
from jobs.queue import publish_event
from storage.db import SessionLocal
from storage.models import Decision, Listing, Purchase

log = logging.getLogger("agentvault.indexer.handlers")


async def handle_event(
    event: DecodedEvent,
    tx_signature: str,
    slot: int,
    redis: aioredis.Redis,
) -> None:
    log.info("event %s sig=%s slot=%s", event.name, tx_signature[:8], slot)
    handler = _DISPATCH.get(event.name)
    if handler is None:
        log.debug("unhandled event %s", event.name)
        return
    try:
        await handler(event, tx_signature, slot, redis)
    except Exception as e:
        log.exception("handler for %s raised: %s", event.name, e)


# ---------------------------------------------------------------------------
# MemoryListed → upsert listings + WS publish

async def _on_memory_listed(
    event: DecodedEvent, tx_signature: str, slot: int, redis: aioredis.Redis
) -> None:
    f = event.fields
    listing_pda = f["listing"]
    seller = f["seller"]

    # Pull the full account so we can populate title/tags/sandbox_price/etc.
    rpc = get_rpc()
    try:
        decoded = await fetch_listing(rpc, Pubkey.from_string(listing_pda))
    finally:
        await rpc.close()

    if decoded is None:
        log.warning("listing %s account not yet visible — partial upsert", listing_pda)
        partial = {
            "id": listing_pda,
            "seller": seller,
            "title": "",
            "model_id": f["model_id"],
            "tags": [],
            "price_usdc": int(f["price_usdc"]),
            "sandbox_price_usdc": 0,
            "arweave_tx": "",
            "content_hash": bytes(f["content_hash"]),
            "quant_seed": 0,
            "bits_per_channel": 0,
            "seq_len": 0,
            "active": True,
            "purchases": 0,
            "created_at": datetime.now(tz=UTC),
            "indexed_at": datetime.now(tz=UTC),
            "on_chain_slot": int(slot),
        }
        row = partial
    else:
        row = {
            "id": listing_pda,
            "seller": decoded.seller,
            "title": decoded.title,
            "model_id": decoded.model_id,
            "tags": list(decoded.tags),
            "price_usdc": int(decoded.price_usdc),
            "sandbox_price_usdc": int(decoded.sandbox_price_usdc),
            "arweave_tx": decoded.arweave_tx,
            "content_hash": bytes(decoded.content_hash),
            "quant_seed": int(decoded.quant_seed),
            "bits_per_channel": int(decoded.bits_per_channel),
            "seq_len": int(decoded.seq_len),
            "active": bool(decoded.active),
            "purchases": int(decoded.purchases),
            "created_at": datetime.fromtimestamp(int(decoded.created_at), tz=UTC),
            "indexed_at": datetime.now(tz=UTC),
            "on_chain_slot": int(slot),
        }

    async with SessionLocal() as session:
        stmt = pg_insert(Listing).values(**row).on_conflict_do_update(
            index_elements=[Listing.id],
            set_={
                "title": row["title"],
                "model_id": row["model_id"],
                "tags": row["tags"],
                "price_usdc": row["price_usdc"],
                "sandbox_price_usdc": row["sandbox_price_usdc"],
                "arweave_tx": row["arweave_tx"],
                "content_hash": row["content_hash"],
                "quant_seed": row["quant_seed"],
                "bits_per_channel": row["bits_per_channel"],
                "seq_len": row["seq_len"],
                "active": row["active"],
                "indexed_at": row["indexed_at"],
                "on_chain_slot": row["on_chain_slot"],
            },
        )
        await session.execute(stmt)
        await session.commit()

    payload = {
        "listing_pda": listing_pda,
        "seller": seller,
        "tx_signature": tx_signature,
        "slot": int(slot),
        "price_usdc": int(f["price_usdc"]),
        "model_id": f["model_id"],
    }
    await publish_event(redis, f"events:listing:{listing_pda}", "listing.confirmed", payload)
    await publish_event(redis, f"events:user:{seller}", "user.listing.confirmed", payload)
    await publish_event(redis, "events:listings:any", "listing.created", payload)


# ---------------------------------------------------------------------------
# MemoryPurchased → insert purchases + bump listings.purchases + WS publish

async def _on_memory_purchased(
    event: DecodedEvent, tx_signature: str, slot: int, redis: aioredis.Redis
) -> None:
    f = event.fields
    listing_pda = f["listing"]
    buyer = f["buyer"]
    license_pda, _ = Pubkey.find_program_address(
        [b"license", bytes(Pubkey.from_string(buyer)), bytes(Pubkey.from_string(listing_pda))],
        Pubkey.from_string(_program_id_str()),
    )

    async with SessionLocal() as session:
        stmt = pg_insert(Purchase).values(
            license_pda=str(license_pda),
            buyer=buyer,
            listing_id=listing_pda,
            price_paid_usdc=int(f["price_usdc"]),
            tx_signature=tx_signature,
            purchased_at=datetime.fromtimestamp(int(f["timestamp"]), tz=UTC),
        ).on_conflict_do_nothing(index_elements=[Purchase.license_pda])
        await session.execute(stmt)

        # Bump purchase counter on the listing if it exists.
        listing = await session.get(Listing, listing_pda)
        if listing is not None:
            listing.purchases = (listing.purchases or 0) + 1
        await session.commit()

    seller = listing.seller if listing is not None else None
    payload = {
        "listing_pda": listing_pda,
        "buyer": buyer,
        "seller": seller,
        "tx_signature": tx_signature,
        "slot": int(slot),
        "price_usdc": int(f["price_usdc"]),
        "license_pda": str(license_pda),
    }
    await publish_event(redis, f"events:listing:{listing_pda}", "listing.purchase", payload)
    await publish_event(redis, f"events:user:{buyer}", "user.purchase", payload)
    if seller is not None:
        await publish_event(redis, f"events:user:{seller}", "user.sale", payload)
    await publish_event(redis, "events:purchases:any", "purchase.confirmed", payload)


# ---------------------------------------------------------------------------
# DecisionAnchored → insert decisions + WS publish

async def _on_decision_anchored(
    event: DecodedEvent, tx_signature: str, slot: int, redis: aioredis.Redis
) -> None:
    f = event.fields
    agent_id = f["agent_id"]
    timestamp = int(f["timestamp"])
    decision_pda, _ = Pubkey.find_program_address(
        [b"decision", bytes(Pubkey.from_string(agent_id)), timestamp.to_bytes(8, "little", signed=True)],
        Pubkey.from_string(_program_id_str()),
    )

    rpc = get_rpc()
    try:
        decoded = await fetch_decision(rpc, decision_pda)
    finally:
        await rpc.close()

    if decoded is None:
        log.warning("decision %s account not visible yet — skipping DB write", decision_pda)
        decision_data = b""
        arweave_tx = ""
    else:
        decision_data = bytes(decoded.decision_data)
        arweave_tx = decoded.arweave_tx

    async with SessionLocal() as session:
        stmt = pg_insert(Decision).values(
            id=str(decision_pda),
            agent_id=agent_id,
            decision_type=f["decision_type"],
            context_hash=bytes(f["context_hash"]),
            arweave_tx=arweave_tx,
            decision_data=decision_data,
            timestamp=datetime.fromtimestamp(timestamp, tz=UTC),
            on_chain_slot=int(f["slot"]),
        ).on_conflict_do_nothing(index_elements=[Decision.id])
        await session.execute(stmt)
        await session.commit()

    payload = {
        "decision_pda": str(decision_pda),
        "agent_id": agent_id,
        "decision_type": f["decision_type"],
        "tx_signature": tx_signature,
        "slot": int(f["slot"]),
        "timestamp": timestamp,
    }
    await publish_event(redis, f"events:user:{agent_id}", "user.decision", payload)
    await publish_event(redis, "events:decisions:any", "decision.anchored", payload)


# ---------------------------------------------------------------------------
# ListingDelisted → flip active=False + WS publish

async def _on_listing_delisted(
    event: DecodedEvent, tx_signature: str, slot: int, redis: aioredis.Redis
) -> None:
    f = event.fields
    listing_pda = f["listing"]
    seller = f["seller"]

    async with SessionLocal() as session:
        listing = await session.get(Listing, listing_pda)
        if listing is not None:
            listing.active = False
            listing.indexed_at = datetime.now(tz=UTC)
            listing.on_chain_slot = int(slot)
            await session.commit()

    payload = {
        "listing_pda": listing_pda,
        "seller": seller,
        "tx_signature": tx_signature,
        "slot": int(slot),
    }
    await publish_event(redis, f"events:listing:{listing_pda}", "listing.delisted", payload)
    await publish_event(redis, f"events:user:{seller}", "user.listing.delisted", payload)
    await publish_event(redis, "events:listings:any", "listing.delisted", payload)


# ---------------------------------------------------------------------------
# ListingPriceUpdated → patch listing prices + WS publish

async def _on_listing_price_updated(
    event: DecodedEvent, tx_signature: str, slot: int, redis: aioredis.Redis
) -> None:
    f = event.fields
    listing_pda = f["listing"]
    seller = f["seller"]

    async with SessionLocal() as session:
        listing = await session.get(Listing, listing_pda)
        if listing is not None:
            listing.price_usdc = int(f["new_price_usdc"])
            listing.sandbox_price_usdc = int(f["new_sandbox_price_usdc"])
            listing.indexed_at = datetime.now(tz=UTC)
            listing.on_chain_slot = int(slot)
            await session.commit()

    payload = {
        "listing_pda": listing_pda,
        "seller": seller,
        "tx_signature": tx_signature,
        "slot": int(slot),
        "new_price_usdc": int(f["new_price_usdc"]),
        "new_sandbox_price_usdc": int(f["new_sandbox_price_usdc"]),
    }
    await publish_event(redis, f"events:listing:{listing_pda}", "listing.price_updated", payload)
    await publish_event(redis, f"events:user:{seller}", "user.listing.price_updated", payload)


# ---------------------------------------------------------------------------
# SandboxAccessGranted → WS only (no schema row dedicated to it yet).

async def _on_sandbox_granted(
    event: DecodedEvent, tx_signature: str, slot: int, redis: aioredis.Redis
) -> None:
    f = event.fields
    payload = {
        "buyer": f["buyer"],
        "listing": f["listing"],
        "expires_at": int(f["expires_at"]),
        "tx_signature": tx_signature,
        "slot": int(slot),
    }
    await publish_event(redis, f"events:listing:{f['listing']}", "sandbox.granted", payload)
    await publish_event(redis, f"events:user:{f['buyer']}", "user.sandbox.granted", payload)


_DISPATCH = {
    "MemoryListed": _on_memory_listed,
    "MemoryPurchased": _on_memory_purchased,
    "DecisionAnchored": _on_decision_anchored,
    "ListingDelisted": _on_listing_delisted,
    "ListingPriceUpdated": _on_listing_price_updated,
    "SandboxAccessGranted": _on_sandbox_granted,
}


def _program_id_str() -> str:
    # Imported lazily so unit tests can run without backend settings loaded.
    from api.config import settings
    return settings.AGENTVAULT_PROGRAM_ID

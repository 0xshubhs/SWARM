"""Anchor event log parsing. Mirrors events.rs from the program.

Real Anchor events surface as `Program data: <base64>` log lines. The base64
payload is an 8-byte event discriminator (sha256("event:<EventName>")[:8])
followed by Borsh-serialised fields.

We decode them here by hand instead of pulling in anchorpy — keeps the indexer
small and lets it run without an IDL file present.
"""
from __future__ import annotations

import base64
import hashlib
import logging
from dataclasses import dataclass
from typing import Any

import base58

from chain.borsh import BorshError, Reader

log = logging.getLogger("agentvault.chain.events")

EVENT_NAMES: tuple[str, ...] = (
    "MemoryListed",
    "MemoryPurchased",
    "SandboxAccessGranted",
    "DecisionAnchored",
    "ListingDelisted",
    "ListingPriceUpdated",
)


def _disc(name: str) -> bytes:
    """Anchor event discriminator: first 8 bytes of sha256("event:<name>")."""
    return hashlib.sha256(f"event:{name}".encode()).digest()[:8]


_DISC_TO_NAME: dict[bytes, str] = {_disc(n): n for n in EVENT_NAMES}


def _b58(p: bytes) -> str:
    return base58.b58encode(p).decode()


def _decode_memory_listed(r: Reader) -> dict[str, Any]:
    listing = _b58(r.pubkey())
    seller = _b58(r.pubkey())
    content_hash = r.fixed(32)
    price_usdc = r.u64()
    model_id = r.string()
    return {
        "listing": listing,
        "seller": seller,
        "content_hash": content_hash,
        "price_usdc": price_usdc,
        "model_id": model_id,
    }


def _decode_memory_purchased(r: Reader) -> dict[str, Any]:
    return {
        "buyer": _b58(r.pubkey()),
        "listing": _b58(r.pubkey()),
        "arweave_tx": r.string(),
        "price_usdc": r.u64(),
        "timestamp": r.i64(),
    }


def _decode_sandbox_access_granted(r: Reader) -> dict[str, Any]:
    return {
        "buyer": _b58(r.pubkey()),
        "listing": _b58(r.pubkey()),
        "expires_at": r.i64(),
    }


def _decode_decision_anchored(r: Reader) -> dict[str, Any]:
    return {
        "agent_id": _b58(r.pubkey()),
        "decision_type": r.string(),
        "context_hash": r.fixed(32),
        "slot": r.u64(),
        "timestamp": r.i64(),
    }


def _decode_listing_delisted(r: Reader) -> dict[str, Any]:
    return {
        "listing": _b58(r.pubkey()),
        "seller": _b58(r.pubkey()),
    }


def _decode_listing_price_updated(r: Reader) -> dict[str, Any]:
    return {
        "listing": _b58(r.pubkey()),
        "seller": _b58(r.pubkey()),
        "new_price_usdc": r.u64(),
        "new_sandbox_price_usdc": r.u64(),
    }


_DECODERS = {
    "MemoryListed": _decode_memory_listed,
    "MemoryPurchased": _decode_memory_purchased,
    "SandboxAccessGranted": _decode_sandbox_access_granted,
    "DecisionAnchored": _decode_decision_anchored,
    "ListingDelisted": _decode_listing_delisted,
    "ListingPriceUpdated": _decode_listing_price_updated,
}


@dataclass(slots=True)
class DecodedEvent:
    name: str
    fields: dict[str, Any]


_PROGRAM_DATA_PREFIX = "Program data: "


def detect_events(logs: list[str]) -> list[DecodedEvent]:
    """Find and decode every Anchor event in a list of program logs.

    Anchor's `emit!` macro produces lines like:
        Program data: <base64 of [discriminator || borsh fields]>
    Anything else is ignored.
    """
    out: list[DecodedEvent] = []
    for line in logs:
        idx = line.find(_PROGRAM_DATA_PREFIX)
        if idx < 0:
            continue
        b64 = line[idx + len(_PROGRAM_DATA_PREFIX) :].strip()
        if not b64:
            continue
        try:
            raw = base64.b64decode(b64)
        except Exception:
            continue
        if len(raw) < 8:
            continue
        disc, body = raw[:8], raw[8:]
        name = _DISC_TO_NAME.get(disc)
        if name is None:
            continue
        decoder = _DECODERS[name]
        reader = Reader(body)
        try:
            fields = decoder(reader)
        except BorshError as e:
            log.warning("borsh decode failed for %s: %s", name, e)
            continue
        out.append(DecodedEvent(name=name, fields=fields))
    return out

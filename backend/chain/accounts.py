"""Anchor account decoders.

Anchor accounts are stored on-chain with an 8-byte discriminator
(sha256("account:<Name>")[:8]) followed by Borsh-serialised fields. The
indexer reads the account after a `MemoryListed` event so we can write a
full listings row to Postgres.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any

import base58
from solders.pubkey import Pubkey

from chain.borsh import BorshError, Reader

log = logging.getLogger("agentvault.chain.accounts")


def _account_disc(name: str) -> bytes:
    return hashlib.sha256(f"account:{name}".encode()).digest()[:8]


_LISTING_DISC = _account_disc("MemoryListing")
_LICENSE_DISC = _account_disc("MemoryLicense")
_SANDBOX_DISC = _account_disc("SandboxAccess")
_DECISION_DISC = _account_disc("DecisionRecord")


def _b58(p: bytes) -> str:
    return base58.b58encode(p).decode()


@dataclass(slots=True)
class DecodedListing:
    seller: str
    bump: int
    arweave_tx: str
    content_hash: bytes
    model_id: str
    quant_seed: int
    bits_per_channel: int
    seq_len: int
    price_usdc: int
    sandbox_price_usdc: int
    title: str
    tags: list[str]
    created_at: int
    active: bool
    purchases: int


def decode_listing(data: bytes) -> DecodedListing:
    if len(data) < 8 or data[:8] != _LISTING_DISC:
        raise BorshError("not a MemoryListing account (discriminator mismatch)")
    r = Reader(data[8:])
    seller = _b58(r.pubkey())
    bump = r.u8()
    arweave_tx = r.string()
    content_hash = r.fixed(32)
    model_id = r.string()
    quant_seed = r.u64()
    bits_per_channel = r.u8()
    seq_len = r.u32()
    price_usdc = r.u64()
    sandbox_price_usdc = r.u64()
    title = r.string()
    tags = r.vec_string()
    created_at = r.i64()
    active = r.bool()
    purchases = r.u64()
    return DecodedListing(
        seller=seller,
        bump=bump,
        arweave_tx=arweave_tx,
        content_hash=content_hash,
        model_id=model_id,
        quant_seed=quant_seed,
        bits_per_channel=bits_per_channel,
        seq_len=seq_len,
        price_usdc=price_usdc,
        sandbox_price_usdc=sandbox_price_usdc,
        title=title,
        tags=tags,
        created_at=created_at,
        active=active,
        purchases=purchases,
    )


@dataclass(slots=True)
class DecodedDecision:
    agent_id: str
    decision_type: str
    context_hash: bytes
    arweave_tx: str
    decision_data: bytes
    timestamp: int
    slot: int
    bump: int


def decode_decision(data: bytes) -> DecodedDecision:
    if len(data) < 8 or data[:8] != _DECISION_DISC:
        raise BorshError("not a DecisionRecord account (discriminator mismatch)")
    r = Reader(data[8:])
    agent_id = _b58(r.pubkey())
    decision_type = r.string()
    context_hash = r.fixed(32)
    arweave_tx = r.string()
    decision_data = r.vec_u8()
    timestamp = r.i64()
    slot = r.u64()
    bump = r.u8()
    return DecodedDecision(
        agent_id=agent_id,
        decision_type=decision_type,
        context_hash=context_hash,
        arweave_tx=arweave_tx,
        decision_data=decision_data,
        timestamp=timestamp,
        slot=slot,
        bump=bump,
    )


async def fetch_listing(rpc, pubkey: Pubkey) -> DecodedListing | None:
    """RPC-fetch a MemoryListing PDA and Borsh-decode it."""
    try:
        resp = await rpc.get_account_info(pubkey, commitment="confirmed")
    except Exception as e:
        log.warning("get_account_info(%s) failed: %s", pubkey, e)
        return None
    info = resp.value
    if info is None or not info.data:
        return None
    try:
        return decode_listing(bytes(info.data))
    except BorshError as e:
        log.warning("decode_listing(%s) failed: %s", pubkey, e)
        return None


async def fetch_decision(rpc, pubkey: Pubkey) -> DecodedDecision | None:
    try:
        resp = await rpc.get_account_info(pubkey, commitment="confirmed")
    except Exception as e:
        log.warning("get_account_info(%s) failed: %s", pubkey, e)
        return None
    info = resp.value
    if info is None or not info.data:
        return None
    try:
        return decode_decision(bytes(info.data))
    except BorshError as e:
        log.warning("decode_decision(%s) failed: %s", pubkey, e)
        return None

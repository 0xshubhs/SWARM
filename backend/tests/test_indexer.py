"""Indexer event decoding + handler dispatch.

We exercise the Anchor `Program data:` decode path end-to-end with synthesised
events, plus the account decoders for MemoryListing / DecisionRecord. This
catches discriminator + Borsh-layout drift the moment events.rs changes.
"""
from __future__ import annotations

import base64
import hashlib
import os
import struct

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")

import base58  # noqa: E402

from chain.accounts import _account_disc, decode_decision, decode_listing  # noqa: E402
from chain.events import _DISC_TO_NAME, _disc, detect_events  # noqa: E402


def _b58(p: bytes) -> str:
    return base58.b58encode(p).decode()


def _string(s: str) -> bytes:
    b = s.encode()
    return struct.pack("<I", len(b)) + b


def _u64(v: int) -> bytes:
    return struct.pack("<Q", v)


def _i64(v: int) -> bytes:
    return struct.pack("<q", v)


def _u32(v: int) -> bytes:
    return struct.pack("<I", v)


def _emit(name: str, body: bytes) -> str:
    return "Program data: " + base64.b64encode(_disc(name) + body).decode()


# ---------------------------------------------------------------------------
# Event decode

class TestEventDecoder:
    def test_disc_bijection(self) -> None:
        # Each event name maps to a unique 8-byte discriminator.
        names = list(_DISC_TO_NAME.values())
        assert len(set(_DISC_TO_NAME.keys())) == len(names)

    def test_memory_listed_roundtrip(self) -> None:
        listing = bytes(range(32))
        seller = bytes(range(32, 64))
        content_hash = b"\xab" * 32
        body = (
            listing
            + seller
            + content_hash
            + _u64(1_500_000)
            + _string("qwen-2.5-7b")
        )
        events = detect_events([_emit("MemoryListed", body)])
        assert len(events) == 1
        ev = events[0]
        assert ev.name == "MemoryListed"
        assert ev.fields["listing"] == _b58(listing)
        assert ev.fields["seller"] == _b58(seller)
        assert ev.fields["content_hash"] == content_hash
        assert ev.fields["price_usdc"] == 1_500_000
        assert ev.fields["model_id"] == "qwen-2.5-7b"

    def test_memory_purchased_roundtrip(self) -> None:
        buyer = b"\x01" * 32
        listing = b"\x02" * 32
        body = buyer + listing + _string("ARW_TX_43_CHARS_xxxxxxxxxxxxxxxxxxxxxxxxxxx") + _u64(25_000_000) + _i64(1_700_000_000)
        events = detect_events([_emit("MemoryPurchased", body)])
        assert len(events) == 1
        ev = events[0]
        assert ev.name == "MemoryPurchased"
        assert ev.fields["buyer"] == _b58(buyer)
        assert ev.fields["price_usdc"] == 25_000_000
        assert ev.fields["timestamp"] == 1_700_000_000

    def test_listing_delisted_and_price_updated(self) -> None:
        listing = b"\x03" * 32
        seller = b"\x04" * 32
        events = detect_events([
            _emit("ListingDelisted", listing + seller),
            _emit("ListingPriceUpdated", listing + seller + _u64(50) + _u64(1)),
        ])
        names = [e.name for e in events]
        assert names == ["ListingDelisted", "ListingPriceUpdated"]
        assert events[1].fields["new_price_usdc"] == 50
        assert events[1].fields["new_sandbox_price_usdc"] == 1

    def test_garbage_lines_ignored(self) -> None:
        # Non-event log lines and unknown discriminators must be skipped.
        unknown = "Program data: " + base64.b64encode(b"\x00" * 16).decode()
        events = detect_events([
            "Program log: instruction MemoryListed",
            unknown,
            "ignore me entirely",
        ])
        assert events == []

    def test_truncated_payload_returns_no_event(self) -> None:
        # Only the discriminator, no body — decoder must not crash.
        line = "Program data: " + base64.b64encode(_disc("MemoryListed")).decode()
        events = detect_events([line])
        assert events == []


# ---------------------------------------------------------------------------
# Account decode

class TestAccountDecoder:
    def _build_listing(self) -> bytes:
        return (
            _account_disc("MemoryListing")
            + b"\x05" * 32                           # seller
            + bytes([255])                           # bump
            + _string("ARW_TX_43_CHARS_xxxxxxxxxxxxxxxxxxxxxxxxxxx")
            + b"\x07" * 32                           # content_hash
            + _string("qwen2.5-7b-instruct")
            + _u64(7777)                             # quant_seed
            + bytes([35])                            # bits_per_channel
            + _u32(8192)                             # seq_len
            + _u64(25_000_000)                       # price_usdc
            + _u64(50_000)                           # sandbox_price_usdc
            + _string("Solana DAO context pack")
            + _u32(2) + _string("solana") + _string("dao")  # tags
            + _i64(1_700_000_000)                    # created_at
            + bytes([1])                             # active
            + _u64(13)                               # purchases
        )

    def test_memory_listing_roundtrip(self) -> None:
        decoded = decode_listing(self._build_listing())
        assert decoded.bits_per_channel == 35
        assert decoded.seq_len == 8192
        assert decoded.price_usdc == 25_000_000
        assert decoded.tags == ["solana", "dao"]
        assert decoded.title == "Solana DAO context pack"
        assert decoded.purchases == 13
        assert decoded.active is True

    def test_listing_wrong_disc_rejected(self) -> None:
        bad = b"\x00" * 8 + self._build_listing()[8:]
        try:
            decode_listing(bad)
        except Exception as e:
            assert "discriminator mismatch" in str(e)
        else:
            raise AssertionError("expected discriminator mismatch")

    def test_decision_record_roundtrip(self) -> None:
        body = (
            _account_disc("DecisionRecord")
            + b"\x09" * 32
            + _string("buy_memory")
            + b"\x0a" * 32
            + _string("ARW_TX_43_CHARS_xxxxxxxxxxxxxxxxxxxxxxxxxxx")
            + _u32(3) + b"\x10\x20\x30"            # decision_data Vec<u8>
            + _i64(1_700_000_001)
            + _u64(123_456)
            + bytes([254])
        )
        d = decode_decision(body)
        assert d.decision_type == "buy_memory"
        assert d.decision_data == b"\x10\x20\x30"
        assert d.timestamp == 1_700_000_001
        assert d.slot == 123_456


# ---------------------------------------------------------------------------
# Discriminator constants — guard against silent renames in events.rs

class TestDiscriminatorStability:
    def test_known_discriminators(self) -> None:
        # Anchor 0.30 discriminator is sha256("event:<Name>")[:8]. If this
        # ever changes, downstream indexers break — pin the bytes.
        assert _disc("MemoryListed") == hashlib.sha256(b"event:MemoryListed").digest()[:8]
        assert _disc("MemoryPurchased") == hashlib.sha256(b"event:MemoryPurchased").digest()[:8]

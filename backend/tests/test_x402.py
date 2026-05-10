"""x402 handler — payment requirements + facilitator verify/settle."""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")

import httpx  # noqa: E402

from api.x402.handler import X402Handler  # noqa: E402


TREASURY = "11111111111111111111111111111112"
USDC = "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU"


def _handler() -> X402Handler:
    return X402Handler(
        facilitator_url="https://facilitator.test",
        treasury_address=TREASURY,
        network="solana-devnet",
        usdc_mint=USDC,
    )


def test_payment_requirements_shape() -> None:
    h = _handler()
    req = h.create_payment_requirements(
        amount_usdc_micro=50_000,
        resource_url="https://api/test",
        description="sandbox query",
    )
    assert req["scheme"] == "exact"
    assert req["network"] == "solana-devnet"
    assert req["payTo"] == TREASURY
    assert req["asset"]["address"] == USDC
    assert req["maxAmountRequired"] == "50000"
    assert req["maxTimeoutSeconds"] == 60


def test_extract_payment_handles_either_case() -> None:
    assert X402Handler.extract_payment({"x-payment": "abc"}) == "abc"
    # FastAPI lowercases, but be defensive against direct dict access too.
    assert X402Handler.extract_payment({"X-PAYMENT": "def"}) == "def"
    assert X402Handler.extract_payment({}) is None


async def test_verify_payment_handles_facilitator_error(monkeypatch) -> None:
    h = _handler()

    class _BadClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *_a, **_kw):
            raise httpx.ConnectError("boom")

    monkeypatch.setattr(httpx, "AsyncClient", _BadClient)
    ok = await h.verify_payment("payload", {"a": 1})
    assert ok is False


async def test_verify_payment_returns_facilitator_decision(monkeypatch) -> None:
    h = _handler()

    class _Resp:
        status_code = 200
        def json(self): return {"isValid": True}

    class _OkClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *_a, **_kw): return _Resp()

    monkeypatch.setattr(httpx, "AsyncClient", _OkClient)
    assert await h.verify_payment("p", {}) is True


async def test_settle_returns_tx_signature(monkeypatch) -> None:
    h = _handler()

    class _Resp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"tx_signature": "sig123"}

    class _Client:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *_a, **_kw): return _Resp()

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    sig = await h.settle_payment("p", {})
    assert sig == "sig123"

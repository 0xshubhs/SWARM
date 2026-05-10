"""WS auth: signed-challenge → JWT → verify."""
from __future__ import annotations

import os
import time

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("WS_TOKEN_SECRET", "test-secret")

import base58  # noqa: E402
import nacl.signing  # noqa: E402
import pytest  # noqa: E402
from fastapi import HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402
from api.routers.ws_auth import verify_ws_token  # noqa: E402


def _now_ms() -> int:
    return int(time.time() * 1000)


def _signing_pair():
    sk = nacl.signing.SigningKey.generate()
    pubkey_b58 = base58.b58encode(sk.verify_key.encode()).decode()
    return sk, pubkey_b58


def _sign_challenge(sk: nacl.signing.SigningKey, channel: str, ts: int) -> str:
    msg = f"agentvault.ws:{channel}:{ts}".encode()
    return base58.b58encode(sk.sign(msg).signature).decode()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_token_issued_for_valid_signature(client: TestClient) -> None:
    sk, pubkey = _signing_pair()
    ts = _now_ms()
    channel = f"user:{pubkey}"
    r = client.post(
        "/v1/ws/token",
        json={
            "channel": channel,
            "wallet_pubkey": pubkey,
            "signature": _sign_challenge(sk, channel, ts),
            "challenge_ts": ts,
        },
    )
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    claims = verify_ws_token(token, expected_subject=channel)
    assert claims["sub"] == channel


def test_stale_challenge_rejected(client: TestClient) -> None:
    sk, pubkey = _signing_pair()
    stale = _now_ms() - 5 * 60_000
    r = client.post(
        "/v1/ws/token",
        json={
            "channel": f"user:{pubkey}",
            "wallet_pubkey": pubkey,
            "signature": _sign_challenge(sk, f"user:{pubkey}", stale),
            "challenge_ts": stale,
        },
    )
    assert r.status_code == 400
    assert "stale" in r.json()["detail"].lower()


def test_bad_signature_rejected(client: TestClient) -> None:
    _, pubkey = _signing_pair()
    other_sk, _ = _signing_pair()
    ts = _now_ms()
    r = client.post(
        "/v1/ws/token",
        json={
            "channel": f"user:{pubkey}",
            "wallet_pubkey": pubkey,
            "signature": _sign_challenge(other_sk, f"user:{pubkey}", ts),
            "challenge_ts": ts,
        },
    )
    assert r.status_code == 401


def test_user_channel_must_match_wallet(client: TestClient) -> None:
    sk, pubkey = _signing_pair()
    ts = _now_ms()
    channel = "user:11111111111111111111111111111112"  # different wallet
    r = client.post(
        "/v1/ws/token",
        json={
            "channel": channel,
            "wallet_pubkey": pubkey,
            "signature": _sign_challenge(sk, channel, ts),
            "challenge_ts": ts,
        },
    )
    assert r.status_code == 403


def test_verify_token_rejects_channel_mismatch() -> None:
    from jose import jwt

    from api.config import settings
    token = jwt.encode(
        {"sub": "listing:abc", "iat": _now_ms(), "exp": _now_ms() + 60_000},
        settings.WS_TOKEN_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(ValueError, match="channel mismatch"):
        verify_ws_token(token, expected_subject="listing:xyz")


def test_verify_token_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        verify_ws_token("not.a.token", expected_subject="x")

"""POST /v1/ws/token — issues a short-lived JWT bound to a channel."""
from __future__ import annotations

from datetime import datetime, timezone

import base58
import nacl.exceptions
import nacl.signing
from fastapi import APIRouter, HTTPException
from jose import jwt
from pydantic import BaseModel

from api.config import settings

router = APIRouter(prefix="/v1/ws", tags=["ws-auth"])


class WSTokenRequest(BaseModel):
    channel: str
    wallet_pubkey: str
    signature: str  # base58
    challenge_ts: int  # unix ms — must be within last 60s


class WSTokenResponse(BaseModel):
    token: str
    expires_in: int


@router.post("/token", response_model=WSTokenResponse)
async def issue_ws_token(req: WSTokenRequest) -> WSTokenResponse:
    now = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    if abs(now - req.challenge_ts) > 60_000:
        raise HTTPException(400, "stale challenge")

    challenge = f"agentvault.ws:{req.channel}:{req.challenge_ts}".encode()
    try:
        verify_key = nacl.signing.VerifyKey(base58.b58decode(req.wallet_pubkey))
        sig_bytes = base58.b58decode(req.signature)
        verify_key.verify(challenge, sig_bytes)
    except (nacl.exceptions.BadSignatureError, ValueError) as e:
        raise HTTPException(401, f"bad signature: {e}")

    if req.channel.startswith("user:"):
        if req.channel != f"user:{req.wallet_pubkey}":
            raise HTTPException(403, "channel does not match wallet")

    token = jwt.encode(
        {"sub": req.channel, "iat": now, "exp": now + 5 * 60_000},
        settings.WS_TOKEN_SECRET,
        algorithm="HS256",
    )
    return WSTokenResponse(token=token, expires_in=300)


def verify_ws_token(token: str, expected_subject: str) -> dict:
    """Used by ws.py to authenticate every WS connection."""
    try:
        claims = jwt.decode(token, settings.WS_TOKEN_SECRET, algorithms=["HS256"])
    except Exception as e:
        raise ValueError(f"invalid token: {e}")
    if claims.get("sub") != expected_subject:
        raise ValueError(
            f"channel mismatch: {claims.get('sub')} != {expected_subject}"
        )
    return claims

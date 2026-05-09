"""Internal endpoints used by trusted services (workers, buyer-agent narrator).

Authorization is a shared bearer token. NOT for public exposure.
"""
from __future__ import annotations

import json
import time
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from api.config import settings
from api.deps import get_redis

router = APIRouter(prefix="/internal", tags=["internal"])


class PublishRequest(BaseModel):
    channel: str  # e.g. "events:agent:{run_id}"
    type: str
    data: dict


def _check_auth(authorization: str | None) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    if token != settings.WS_TOKEN_SECRET:
        raise HTTPException(401, "bad bearer token")


@router.post("/publish")
async def internal_publish(
    body: PublishRequest,
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    _check_auth(authorization)
    if not body.channel.startswith("events:"):
        raise HTTPException(400, "channel must start with 'events:'")

    payload = {
        "type": body.type,
        "ts": int(time.time() * 1000),
        "data": body.data,
    }
    await redis.publish(body.channel, json.dumps(payload))
    return {"ok": True}

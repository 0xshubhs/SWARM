"""WebSocket gateway. Every connection subscribes to a Redis channel and
forwards messages to the client. Authentication is via a JWT in `?token=...`.
"""
from __future__ import annotations

import asyncio
import json
import time

import redis.asyncio as aioredis
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from api.routers.ws_auth import verify_ws_token

router = APIRouter(tags=["ws"])


def _now_ms() -> int:
    return int(time.time() * 1000)


async def _pump_redis_to_ws(pubsub: aioredis.client.PubSub, websocket: WebSocket) -> None:
    async for message in pubsub.listen():
        if message.get("type") != "message":
            continue
        data = message["data"]
        if isinstance(data, bytes):
            data = data.decode()
        try:
            await websocket.send_text(data)
        except Exception:
            return


async def _pump_pings(websocket: WebSocket) -> None:
    while True:
        try:
            await asyncio.sleep(20)
            await websocket.send_json({"type": "ws.ping", "ts": _now_ms(), "data": {}})
        except Exception:
            return


async def _serve_channel(
    websocket: WebSocket,
    redis: aioredis.Redis,
    redis_channel: str,
    expected_subject: str,
    token: str,
) -> None:
    try:
        verify_ws_token(token, expected_subject=expected_subject)
    except Exception as e:
        await websocket.close(code=4001, reason=f"unauthorized: {e}")
        return

    await websocket.accept()
    await websocket.send_json(
        {"type": "ws.hello", "ts": _now_ms(), "data": {"channel": expected_subject}}
    )

    pubsub = redis.pubsub()
    await pubsub.subscribe(redis_channel)
    recv_task = asyncio.create_task(_pump_redis_to_ws(pubsub, websocket))
    ping_task = asyncio.create_task(_pump_pings(websocket))

    try:
        await asyncio.wait(
            [recv_task, ping_task], return_when=asyncio.FIRST_COMPLETED
        )
    except WebSocketDisconnect:
        pass
    finally:
        for t in (recv_task, ping_task):
            if not t.done():
                t.cancel()
        try:
            await pubsub.unsubscribe(redis_channel)
            await pubsub.close()
        except Exception:
            pass


@router.websocket("/v1/ws/upload/{upload_id}")
async def upload_ws(
    websocket: WebSocket,
    upload_id: str,
    token: str = Query(...),
) -> None:
    redis: aioredis.Redis = websocket.app.state.redis
    await _serve_channel(
        websocket,
        redis,
        f"events:upload:{upload_id}",
        f"upload:{upload_id}",
        token,
    )


@router.websocket("/v1/ws/agent/{run_id}")
async def agent_ws(
    websocket: WebSocket,
    run_id: str,
    token: str = Query(...),
) -> None:
    redis: aioredis.Redis = websocket.app.state.redis
    await _serve_channel(
        websocket,
        redis,
        f"events:agent:{run_id}",
        f"agent:{run_id}",
        token,
    )


@router.websocket("/v1/ws/listing/{listing_pda}")
async def listing_ws(
    websocket: WebSocket,
    listing_pda: str,
    token: str = Query(...),
) -> None:
    redis: aioredis.Redis = websocket.app.state.redis
    await _serve_channel(
        websocket,
        redis,
        f"events:listing:{listing_pda}",
        f"listing:{listing_pda}",
        token,
    )


@router.websocket("/v1/ws/user/{wallet_pubkey}")
async def user_ws(
    websocket: WebSocket,
    wallet_pubkey: str,
    token: str = Query(...),
) -> None:
    redis: aioredis.Redis = websocket.app.state.redis
    await _serve_channel(
        websocket,
        redis,
        f"events:user:{wallet_pubkey}",
        f"user:{wallet_pubkey}",
        token,
    )


# Internal HTTP publish lives in api/routers/internal.py — see /internal/publish.

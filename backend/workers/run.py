"""Worker process. Drains the compress queue and runs the pipeline."""
from __future__ import annotations

import asyncio
import logging

import redis.asyncio as aioredis

from api.config import settings
from api.deps import make_redis
from jobs.queue import dequeue_compress
from jobs.tasks import compress_and_upload
from storage.arweave import ArweaveClient

log = logging.getLogger("agentvault.worker")


async def main() -> None:
    logging.basicConfig(level=settings.LOG_LEVEL.upper())
    redis: aioredis.Redis = make_redis()
    arweave = ArweaveClient(sidecar_url=settings.IRYS_SIDECAR_URL)
    log.info(
        "worker booted: redis=%s sidecar=%s",
        settings.REDIS_URL,
        settings.IRYS_SIDECAR_URL,
    )

    while True:
        msg = await dequeue_compress(redis)
        if not msg:
            continue
        upload_id = msg["upload_id"]
        raw: bytes = msg["raw"]
        log.info("picked up job %s (%d bytes)", upload_id, len(raw))
        try:
            await compress_and_upload(upload_id, raw, redis, arweave)
        except Exception:
            log.exception("job %s crashed", upload_id)


if __name__ == "__main__":
    asyncio.run(main())

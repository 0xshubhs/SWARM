"""POST /inference — fetch from Arweave, decompress, query vLLM."""
from __future__ import annotations

import hashlib

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class InferenceRequest(BaseModel):
    arweave_tx: str
    content_hash_hex: str
    query: str
    max_tokens: int = 200


class InferenceResponse(BaseModel):
    response: str
    quality_score: float


@router.post("/inference")
async def inference_endpoint(
    req: InferenceRequest,
) -> InferenceResponse:
    """Full inference pipeline: Arweave fetch → decompress → vLLM query."""
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(f"https://arweave.net/{req.arweave_tx}")
            resp.raise_for_status()
            blob = resp.content
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Arweave fetch failed: {e}")

    actual_hash = hashlib.sha256(blob).hexdigest()
    if actual_hash != req.content_hash_hex:
        raise HTTPException(400, "Hash mismatch — possible tampering")

    try:
        from worker.turboquant.compress import decompress
        kv_cache = decompress(blob)
    except Exception as e:
        raise HTTPException(422, f"Decompression failed: {e}")

    try:
        from runtime.cache_loader import load_into_vllm
        from runtime.vllm_bridge import vllm_complete
        cache_id = await load_into_vllm(kv_cache, f"arweave-{req.arweave_tx}")
        response = await vllm_complete(
            prompt=req.query,
            kv_cache_id=cache_id,
            max_tokens=req.max_tokens,
        )
    except ImportError:
        raise HTTPException(503, "Runtime integration not available (run with --extra gpu)")
    except Exception as e:
        raise HTTPException(500, f"Inference failed: {e}")

    quality = min(1.0, len(response.split()) / 100.0)
    return InferenceResponse(response=response, quality_score=quality)
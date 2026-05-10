"""POST /load — load decompressed KV cache into vLLM via LMCache."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

router = APIRouter()


class LoadResponse(BaseModel):
    cache_id: str
    shape: list[int]
    dtype: str


@router.post("/load")
async def load_endpoint(
    file: UploadFile = File(...),
    cache_id: str = Form(...),
) -> LoadResponse:
    """Decompress blob and load into vLLM via LMCache."""
    try:
        contents = await file.read()
        from worker.turboquant.compress import decompress
        kv_cache = decompress(contents)
    except Exception as e:
        raise HTTPException(400, f"Decompression failed: {e}")

    try:
        from runtime.cache_loader import load_into_vllm
        cache_key = await load_into_vllm(kv_cache, cache_id)
    except ImportError:
        raise HTTPException(503, "Runtime integration not available (run with --extra gpu)")
    except Exception as e:
        raise HTTPException(500, f"vLLM load failed: {e}")

    return LoadResponse(
        cache_id=cache_key,
        shape=list(kv_cache.shape),
        dtype=str(kv_cache.dtype),
    )
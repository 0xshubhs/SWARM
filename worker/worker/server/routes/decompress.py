"""POST /decompress — decompress TurboQuant blob back to KV cache tensor."""
from __future__ import annotations

import io

import torch
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile

from worker.turboquant.compress import decompress

from ..auth import require_api_key

router = APIRouter()


@router.post("/decompress")
async def decompress_endpoint(
    file: UploadFile = File(...),
    _api_key: str = Depends(require_api_key),
) -> Response:
    """Decompress a TurboQuant blob back to a torch.Tensor KV cache."""
    try:
        contents = await file.read()
        kv_cache = decompress(contents)
    except Exception as e:
        raise HTTPException(400, f"Decompression failed: {e}")

    buf = io.BytesIO()
    torch.save(kv_cache, buf)
    return Response(
        content=buf.getvalue(),
        media_type="application/octet-stream",
        headers={
            "X-Shape": str(list(kv_cache.shape)),
            "X-Dtype": str(kv_cache.dtype),
        },
    )
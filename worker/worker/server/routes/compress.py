"""POST /compress — compress a KV cache tensor to TurboQuant blob."""
from __future__ import annotations

import io
import json

import torch
from fastapi import APIRouter, File, HTTPException, Query, Response, UploadFile

from worker.turboquant.compress import compress

router = APIRouter()


@router.post("/compress")
async def compress_endpoint(
    file: UploadFile = File(...),
    bits: float = Query(default=3.5, ge=1.0, le=8.0),
    seed: int = Query(default=42, ge=0),
) -> Response:
    """Compress a KV cache tensor to TurboQuant blob.

    Upload raw torch.Tensor bytes saved via torch.save().
    Query params: bits (default 3.5), seed (default 42)
    """
    try:
        contents = await file.read()
        buf = io.BytesIO(contents)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        kv_cache = torch.load(buf, map_location=device)
    except Exception as e:
        raise HTTPException(400, f"Failed to load tensor: {e}")

    if not isinstance(kv_cache, torch.Tensor):
        raise HTTPException(400, "Uploaded file is not a torch.Tensor")

    try:
        result = compress(kv_cache, bits=bits, seed=seed)
    except Exception as e:
        raise HTTPException(500, f"Compression failed: {e}")

    original_size = kv_cache.numel() * kv_cache.element_size()
    compression_ratio = original_size / len(result.blob)

    return Response(
        content=result.blob,
        media_type="application/octet-stream",
        headers={
            "X-Original-Size": str(original_size),
            "X-Compressed-Size": str(len(result.blob)),
            "X-Compression-Ratio": f"{compression_ratio:.2f}",
            "X-Metadata": json.dumps(result.metadata),
        },
    )
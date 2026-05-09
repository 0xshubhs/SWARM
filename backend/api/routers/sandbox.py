"""x402-gated sandbox preview.

Flow:
  1. POST /v1/sandbox/{listing_id} with no header → 402 + payment requirements
  2. Client signs the payment, retries with X-PAYMENT
  3. Backend verifies via facilitator, settles, runs inference, returns result
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.deps import get_arweave, get_db, get_runtime, get_x402
from api.x402.handler import X402Handler
from runtime.vllm_client import VLLMClient
from storage.arweave import ArweaveClient
from storage.models import Listing, SandboxQuery as SandboxQueryRow

router = APIRouter(prefix="/v1/sandbox", tags=["sandbox"])


@router.post("/{listing_id}")
async def sandbox_query(
    listing_id: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    x402: Annotated[X402Handler, Depends(get_x402)],
    runtime: Annotated[VLLMClient, Depends(get_runtime)],
    arweave: Annotated[ArweaveClient, Depends(get_arweave)],
):
    listing = await db.get(Listing, listing_id)
    if listing is None or not listing.active:
        raise HTTPException(404, "Listing not found")

    requirements = x402.create_payment_requirements(
        amount_usdc_micro=listing.sandbox_price_usdc,
        resource_url=f"{settings.BASE_URL}/v1/sandbox/{listing_id}",
        description=f"Sandbox preview: {listing.title}",
    )

    payment = X402Handler.extract_payment({k.lower(): v for k, v in request.headers.items()})
    if not payment:
        return JSONResponse(
            status_code=402,
            content={"x402Version": 1, "accepts": [requirements]},
            headers={"X-PAYMENT-REQUIREMENTS": json.dumps(requirements)},
        )

    if not await x402.verify_payment(payment, requirements):
        raise HTTPException(402, "Invalid payment proof")

    tx_sig = await x402.settle_payment(payment, requirements)

    body = await request.json()
    query = body.get("query", "").strip()
    if not query:
        raise HTTPException(400, "missing 'query' in request body")

    response = await runtime.run_with_memory(
        listing=listing,
        query=query,
        max_tokens=200,
        arweave=arweave,
    )

    db.add(
        SandboxQueryRow(
            id=str(uuid.uuid4()),
            buyer=requirements.get("payer", "unknown"),
            listing_id=listing_id,
            query=query,
            response=response.text,
            quality_score=response.quality_score,
            payment_tx=tx_sig,
            created_at=datetime.now(tz=timezone.utc),
        )
    )
    await db.commit()

    return {
        "response": response.text,
        "quality_score": response.quality_score,
        "queries_remaining": response.queries_remaining,
        "tx_signature": tx_sig,
    }

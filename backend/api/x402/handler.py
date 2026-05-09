"""x402 protocol handler — talks to a PayAI-style facilitator.

The facilitator does the heavy lifting (verifies signatures, optionally
settles on-chain). Backend's job is to:
  1. Build payment requirements when no `X-PAYMENT` header is present
  2. Forward the payment payload to the facilitator for verify+settle
  3. Treat the returned tx signature as proof
"""
from __future__ import annotations

from typing import Any

import httpx


class X402Handler:
    def __init__(
        self,
        facilitator_url: str,
        treasury_address: str,
        network: str,
        usdc_mint: str,
    ) -> None:
        self.facilitator_url = facilitator_url.rstrip("/")
        self.treasury = treasury_address
        self.network = network
        self.usdc_mint = usdc_mint

    def create_payment_requirements(
        self,
        amount_usdc_micro: int,
        resource_url: str,
        description: str,
        timeout_seconds: int = 60,
    ) -> dict[str, Any]:
        return {
            "scheme": "exact",
            "network": self.network,
            "maxAmountRequired": str(amount_usdc_micro),
            "resource": resource_url,
            "description": description,
            "mimeType": "application/json",
            "payTo": self.treasury,
            "asset": {"address": self.usdc_mint},
            "maxTimeoutSeconds": timeout_seconds,
        }

    @staticmethod
    def extract_payment(headers: dict[str, str]) -> str | None:
        # Headers come lowercased from FastAPI
        return headers.get("x-payment") or headers.get("X-PAYMENT")

    async def verify_payment(
        self, payment_b64: str, requirements: dict[str, Any]
    ) -> bool:
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.post(
                    f"{self.facilitator_url}/verify",
                    json={
                        "paymentPayload": payment_b64,
                        "paymentRequirements": requirements,
                    },
                )
            except httpx.HTTPError:
                return False
            if resp.status_code != 200:
                return False
            data = resp.json()
            return bool(data.get("isValid", False))

    async def settle_payment(
        self, payment_b64: str, requirements: dict[str, Any]
    ) -> str:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.facilitator_url}/settle",
                json={
                    "paymentPayload": payment_b64,
                    "paymentRequirements": requirements,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("transaction") or data.get("tx_signature", "")

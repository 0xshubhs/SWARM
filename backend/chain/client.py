"""Thin async wrapper around the Solana RPC for the program.

We deliberately avoid AnchorPy's high-level fetch_all when we have many
listings — backend reads from the indexed Postgres mirror. The on-chain
client here is for: building tx instructions for the frontend to sign,
and double-checking state during webhooks.
"""
from __future__ import annotations

from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey

from api.config import settings


def program_id() -> Pubkey:
    return Pubkey.from_string(settings.AGENTVAULT_PROGRAM_ID)


def usdc_mint() -> Pubkey:
    return Pubkey.from_string(settings.USDC_MINT)


def treasury() -> Pubkey:
    return Pubkey.from_string(settings.PLATFORM_TREASURY)


def get_rpc() -> AsyncClient:
    return AsyncClient(settings.SOLANA_RPC_URL, commitment="confirmed")

"""Pricing is the simplest pure function — pin its math."""
from __future__ import annotations

from api.routers.pricing import calculate_fee


def test_pricing_is_deterministic() -> None:
    fee = calculate_fee(220_358_912)  # ~210 MB
    assert fee.base_usdc == 500_000
    assert fee.compute_usdc > 0
    assert fee.storage_usdc > 0
    assert fee.total_usdc == fee.base_usdc + fee.compute_usdc + fee.storage_usdc
    assert fee.decimals == 6


def test_zero_size_returns_only_base() -> None:
    fee = calculate_fee(0)
    assert fee.compute_usdc == 0
    assert fee.storage_usdc == 0
    assert fee.total_usdc == fee.base_usdc

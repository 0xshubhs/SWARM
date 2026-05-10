"""Tests for turboquant/quantizer.py — Phase 2."""
from __future__ import annotations

import numpy as np
import pytest
import torch

from worker.turboquant.quantizer import (
    PRECOMPUTED_PATH,
    BetaQuantizer,
    lloyd_max,
    precompute_all_levels,
)


class TestLloydMax:
    def test_converges(self):
        levels = lloyd_max(num_levels=8, alpha=32, beta_param=32, num_iterations=50)
        assert len(levels) == 8
        assert np.all(levels[:-1] < levels[1:])

    def test_levels_in_order(self):
        for num_levels in [4, 8, 16]:
            levels = lloyd_max(num_levels=num_levels, alpha=64, beta_param=64)
            assert len(levels) == num_levels
            for i in range(num_levels - 1):
                assert levels[i] < levels[i + 1]


class TestBetaQuantizer:
    def test_encode_decode_roundtrip(self):
        q = BetaQuantizer(head_dim=128, bits=3.5)
        x = torch.randn(1000, 128) * 0.3
        codes = q.encode(x)
        x_rec = q.decode(codes)
        assert x_rec.shape == x.shape
        assert codes.dtype == torch.int32

    def test_encode_bounds(self):
        q = BetaQuantizer(head_dim=128, bits=3.5)
        x = torch.randn(100, 128)
        codes = q.encode(x)
        assert codes.min() >= 0
        assert codes.max() < q.num_levels

    def test_decode_uses_levels(self):
        q = BetaQuantizer(head_dim=128, bits=3.5)
        codes = torch.tensor([0, q.num_levels // 2, q.num_levels - 1])
        decoded = q.decode(codes)
        assert torch.equal(decoded[0], q.levels[0])
        assert torch.equal(decoded[1], q.levels[q.num_levels // 2])
        assert torch.equal(decoded[2], q.levels[-1])

    def test_different_bits_different_quantizer(self):
        q35 = BetaQuantizer(head_dim=128, bits=3.5)
        q40 = BetaQuantizer(head_dim=128, bits=4.0)
        x = torch.randn(10, 128)
        codes35 = q35.encode(x)
        codes40 = q40.encode(x)
        assert not torch.equal(codes35, codes40)

    def test_head_dim_64(self):
        q = BetaQuantizer(head_dim=64, bits=3.5)
        x = torch.randn(100, 64)
        codes = q.encode(x)
        x_rec = q.decode(codes)
        assert x_rec.shape == x.shape

    def test_precomputed_file_exists(self):
        assert PRECOMPUTED_PATH.exists()

    def test_cuda_if_available(self):
        if not torch.cuda.is_available():
            pytest.skip("CUDA not available")
        q = BetaQuantizer(head_dim=128, bits=3.5)
        # Quantizer is built for unit-norm / post-Hadamard data, not raw N(0,1).
        x = torch.randn(10, 128, device="cuda")
        x = x / x.norm(dim=-1, keepdim=True)
        codes = q.encode(x)
        x_rec = q.decode(codes)
        assert x_rec.device.type == "cuda"
        assert x_rec.shape == x.shape


class TestPrecomputeAllLevels:
    def test_produces_valid_json(self):
        data = precompute_all_levels()
        assert "64" in data
        assert "128" in data
        for bits in ["2.5", "3.0", "3.5", "4.0", "5.0", "6.0"]:
            assert bits in data["64"]
            assert bits in data["128"]

    def test_levels_strictly_increasing(self):
        data = precompute_all_levels()
        for hd in ["64", "128"]:
            for bits in data[hd]:
                levels = data[hd][bits]
                for i in range(len(levels) - 1):
                    assert levels[i] < levels[i + 1]
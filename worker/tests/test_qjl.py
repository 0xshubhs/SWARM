"""Tests for turboquant/qjl.py — Phase 3."""
from __future__ import annotations

import numpy as np
import pytest
import torch

from worker.turboquant.qjl import (
    make_qjl_matrix,
    qjl_decode_to_residual,
    qjl_encode,
)


class TestMakeQJLMatrix:
    def test_shape(self):
        W = make_qjl_matrix(d=128, proj_dim=16, seed=42)
        assert W.shape == (128, 16)

    def test_deterministic(self):
        W1 = make_qjl_matrix(d=128, proj_dim=16, seed=42)
        W2 = make_qjl_matrix(d=128, proj_dim=16, seed=42)
        assert torch.equal(W1, W2)

    def test_different_seeds_different_matrix(self):
        W1 = make_qjl_matrix(d=128, proj_dim=16, seed=42)
        W2 = make_qjl_matrix(d=128, proj_dim=16, seed=99)
        assert not torch.equal(W1, W2)

    def test_orthonormal_columns(self):
        """Columns should be approximately unit vectors."""
        W = make_qjl_matrix(d=128, proj_dim=16, seed=42)
        col_norms = torch.norm(W, dim=0)
        assert col_norms.min() > 0.5, "Column norms too small"
        assert col_norms.max() < 2.0, "Column norms too large"


class TestQJLEncode:
    def test_output_shape(self):
        d, proj_dim = 128, 16
        W = make_qjl_matrix(d, proj_dim, seed=42)
        residual = torch.randn(100, d)
        bits = qjl_encode(residual, W)
        assert bits.shape == (100, proj_dim)
        assert bits.dtype == torch.bool

    def test_output_is_bool(self):
        W = make_qjl_matrix(128, 16, seed=42)
        bits = qjl_encode(torch.randn(10, 128), W)
        assert bits.dtype == torch.bool

    def test_deterministic(self):
        W = make_qjl_matrix(128, 16, seed=42)
        residual = torch.randn(10, 128)
        bits1 = qjl_encode(residual, W)
        bits2 = qjl_encode(residual, W)
        assert torch.equal(bits1, bits2)


class TestQJLDecodeToResidual:
    def test_output_shape(self):
        d, proj_dim = 128, 16
        W = make_qjl_matrix(d, proj_dim, seed=42)
        bits = torch.randint(0, 2, (100, proj_dim), dtype=torch.bool)
        rec = qjl_decode_to_residual(bits, W)
        assert rec.shape == (100, d)

    def test_round_trip_shape(self):
        d, proj_dim = 128, 16
        W = make_qjl_matrix(d, proj_dim, seed=42)
        residual = torch.randn(100, d)
        bits = qjl_encode(residual, W)
        rec = qjl_decode_to_residual(bits, W)
        assert rec.shape == residual.shape


class TestQJLInnerProductPreservation:
    def test_inner_products_preserved_better_than_random(self):
        """
        QJL should preserve relative ordering of inner products better than random.
        """
        d, proj_dim = 128, 64
        W = make_qjl_matrix(d, proj_dim, seed=42)
        residual = torch.randn(100, d)
        bits = qjl_encode(residual, W)
        rec = qjl_decode_to_residual(bits, W)

        orig_ips = []
        rec_ips = []
        for i in range(min(20, len(residual))):
            for j in range(i + 1, min(20, len(residual))):
                orig_ips.append((residual[i] @ residual[j]).item())
                rec_ips.append((rec[i] @ rec[j]).item())

        orig_ips = np.array(orig_ips)
        rec_ips = np.array(rec_ips)

        correlation = np.corrcoef(orig_ips, rec_ips)[0, 1]
        assert correlation > 0.2, \
            f"QJL correlation {correlation:.3f} too low — QJL not capturing inner-product structure"

    def test_reconstruction_approximately_retrieves_residual(self):
        """
        QJL reconstruction should retrieve the residual with some fidelity.
        We test mean squared error of reconstruction vs original.
        """
        d, proj_dim = 128, 64
        W = make_qjl_matrix(d, proj_dim, seed=42)
        residual = torch.randn(50, d)
        bits = qjl_encode(residual, W)
        rec = qjl_decode_to_residual(bits, W)

        mse = torch.nn.functional.mse_loss(rec, residual).item()
        orig_var = residual.var().item()
        r2 = 1 - mse / orig_var
        assert r2 > 0.0, f"QJL reconstruction R2 {r2:.3f} — reconstruction worse than trivial"

    def test_batch_processing(self):
        """QJL encode/decode should handle arbitrary batch dims."""
        d, proj_dim = 128, 16
        W = make_qjl_matrix(d, proj_dim, seed=42)
        residual = torch.randn(3, 5, 7, d)
        bits = qjl_encode(residual, W)
        assert bits.shape == (3, 5, 7, proj_dim)
        rec = qjl_decode_to_residual(bits, W)
        assert rec.shape == residual.shape

    def test_cuda_if_available(self):
        if not torch.cuda.is_available():
            pytest.skip("CUDA not available")
        W = make_qjl_matrix(128, 16, seed=42).cuda()
        residual = torch.randn(10, 128, device="cuda")
        bits = qjl_encode(residual, W)
        rec = qjl_decode_to_residual(bits, W)
        assert rec.device.type == "cuda"
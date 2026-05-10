"""Tests for server routes — Phase 7."""
from __future__ import annotations

import io

import torch
from fastapi.testclient import TestClient

from worker.main import app
from worker.server.config import settings

client = TestClient(app, headers={"X-API-Key": settings.WORKER_API_KEY})


class TestHealth:
    def test_healthz_returns_ok(self):
        r = client.get("/healthz")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        assert "cuda_available" in r.json()


class TestCompress:
    def test_compress_invalid_tensor(self):
        buf = io.BytesIO(b"not a torch tensor")
        r = client.post("/compress", files={"file": ("tensor.bin", buf, "application/octet-stream")})
        assert r.status_code == 400

    def test_compress_valid_kv_cache(self):
        kv = torch.randn(28, 2, 4, 128, 128, dtype=torch.float32)
        buf = io.BytesIO()
        torch.save(kv, buf)
        buf.seek(0)
        r = client.post("/compress", files={"file": ("kv.bin", buf, "application/octet-stream")})
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/octet-stream"
        assert "X-Compression-Ratio" in r.headers
        assert float(r.headers["X-Compression-Ratio"]) > 1.0

    def test_compress_small_kv_cache(self):
        kv = torch.randn(4, 2, 2, 16, 64, dtype=torch.float32)
        buf = io.BytesIO()
        torch.save(kv, buf)
        buf.seek(0)
        r = client.post("/compress", files={"file": ("kv.bin", buf, "application/octet-stream")})
        assert r.status_code == 200
        ratio = float(r.headers["X-Compression-Ratio"])
        assert ratio > 1.0

    def test_compress_with_bits_param(self):
        kv = torch.randn(4, 2, 2, 16, 64, dtype=torch.float32)
        buf = io.BytesIO()
        torch.save(kv, buf)
        buf.seek(0)
        r = client.post(
            "/compress",
            files={"file": ("kv.bin", buf, "application/octet-stream")},
            params={"bits": 4.0, "seed": 99},
        )
        assert r.status_code == 200

    def test_compress_unknown_tensor_format(self):
        buf = io.BytesIO(b"\x00\x01\x02\x03 corrupted")
        r = client.post("/compress", files={"file": ("bad.bin", buf, "application/octet-stream")})
        assert r.status_code == 400


class TestDecompress:
    def test_decompress_valid_blob(self):
        kv = torch.randn(28, 2, 4, 128, 128, dtype=torch.float32)
        buf = io.BytesIO()
        torch.save(kv, buf)
        buf.seek(0)
        compress_resp = client.post("/compress", files={"file": ("kv.bin", buf, "application/octet-stream")})
        blob = compress_resp.content

        buf2 = io.BytesIO(blob)
        r = client.post("/decompress", files={"file": ("blob.tqnt", buf2, "application/octet-stream")})
        assert r.status_code == 200
        assert "X-Shape" in r.headers

    def test_decompress_invalid_blob(self):
        buf = io.BytesIO(b"garbage")
        r = client.post("/decompress", files={"file": ("bad.tqnt", buf, "application/octet-stream")})
        assert r.status_code == 400


class TestLoad:
    def test_load_without_runtime(self):
        kv = torch.randn(28, 2, 4, 128, 128, dtype=torch.float32)
        buf = io.BytesIO()
        torch.save(kv, buf)
        buf.seek(0)
        compress_resp = client.post("/compress", files={"file": ("kv.bin", buf, "application/octet-stream")})
        blob = compress_resp.content

        buf2 = io.BytesIO(blob)
        r = client.post("/load", files={"file": ("blob.tqnt", buf2, "application/octet-stream")}, data={"cache_id": "test-123"})
        assert r.status_code == 503


class TestInference:
    def test_inference_arweave_fetch_fails(self):
        r = client.post("/inference", json={
            "arweave_tx": "nonexistent-tx-123",
            "content_hash_hex": "deadbeef",
            "query": "Hello",
        })
        assert r.status_code in (400, 502)


class TestBenchmark:
    def test_benchmark_with_auth_no_transformers(self):
        r = client.post("/benchmark")
        assert r.status_code == 503
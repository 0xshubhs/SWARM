# 03 — TurboQuant Worker (GPU compression service)

**Where:** `worker/`
**Stack:** Python 3.12 + PyTorch 2.4+ + CUDA 12.1
**Deploy target:** RunPod (GPU) for production / Railway (CPU) for dev mocking
**Build first or in parallel:** Yes — this is the load-bearing technical claim. **De-risk in week 1.**

---

## 1. Why this is the most critical document

If TurboQuant doesn't actually achieve quality-neutral compression at 3.5 bits/channel on Qwen 2.5 7B's KV cache, the entire pitch falls apart. **Verify this on Day 1.** Everything else is engineering — this is research-validation engineering.

The paper claims:
- 3.5 bits/channel: absolute quality neutrality (i.e., output indistinguishable from full-precision)
- 2.5 bits/channel: marginal degradation
- Algorithm is data-oblivious (no calibration data needed)

If these claims hold on Qwen, you have a product. If they don't, pivot to FP8-only compression and accept the 2× ratio (still useful, less of a wow factor).

---

## 2. Responsibilities

The worker is a **stateless compression+inference service**. It exposes HTTP endpoints that:
1. **Compress**: take raw KV cache bytes → return TurboQuant blob + metadata
2. **Decompress**: take TurboQuant blob + metadata → return raw KV cache bytes
3. **Benchmark**: measure quality at different bit rates on a test prompt
4. **Inference with memory**: load a compressed cache, run a query, return response (this is what the sandbox endpoint calls into)

The worker does **not**:
- Touch the database
- Talk to Solana
- Manage user identities
- Persist anything between requests (except cached model weights)

---

## 3. Architecture

```
┌────────────────────────────────────────────────────────┐
│  RunPod A10G instance ($0.40/hr)                       │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │  vLLM (port 8000)                                │  │
│  │  Qwen/Qwen2.5-7B-Instruct                        │  │
│  │  - kv-cache-dtype: fp8                           │  │
│  │  - max-model-len: 8192                           │  │
│  │  - LMCache plugin enabled                        │  │
│  └────────────────┬─────────────────────────────────┘  │
│                   │                                     │
│                   │ shared GPU memory                   │
│                   ▼                                     │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Worker (FastAPI, port 8001)                     │  │
│  │                                                   │  │
│  │  - /compress    → TurboQuant.compress()          │  │
│  │  - /decompress  → TurboQuant.decompress()        │  │
│  │  - /load        → into vLLM via LMCache         │  │
│  │  - /inference   → query w/ loaded memory         │  │
│  │  - /benchmark   → quality measurement            │  │
│  │                                                   │  │
│  │  CUDA tensors stay on GPU — no copy to CPU       │  │
│  │  except when serializing to bytes for transport  │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
                       │
                       │ HTTPS
                       ▼
            ┌─────────────────────┐
            │  Backend (Railway)  │
            └─────────────────────┘
```

### Why this layout
- vLLM and worker share GPU memory (zero-copy cache loading)
- Worker handles compression at API boundary (CPU-bound serialization)
- Backend doesn't need GPU access at all — clean separation

---

## 4. The TurboQuant algorithm — implementation detail

### Input
KV cache tensor of shape `[num_layers, 2, num_heads, seq_len, head_dim]`.
For Qwen 2.5 7B: `[28, 2, 4, seq_len, 128]` (using GQA with 4 KV heads).

### Algorithm

```
For each layer l in 0..L:
  For each head h in 0..H:
    For each token t in 0..seq_len:
      Extract vector v ∈ R^d (d = head_dim = 128)

      # Step 1: Random rotation (Hadamard with random sign flips)
      v' = U(seed) * v
        where U is a randomized Hadamard transform

      # Step 2: Per-coordinate scalar quantization
      For each coordinate i in 0..d:
        Apply Beta-optimal quantizer at target bits b
        codes[l, h, t, i] = Q_b(v'[i])

      # Step 3: 1-bit QJL residual (for inner-product fidelity)
      residual = v' - Q_b^-1(codes[l, h, t, :])
      proj_dim = d / 8 = 16
      sketch = sign(W * residual)  where W ∈ R^{d × proj_dim}, gaussian
      qjl_bits[l, h, t, :] = sketch

Output:
  blob = pack(codes) + pack(qjl_bits) + metadata_header
  metadata = { shape, bits, seed, qjl_dim, quantizer_levels }
```

### Why each step

- **Random rotation**: After Hadamard rotation, vector coordinates become approximately Beta-distributed, which has a known optimal quantizer with fewer levels per bit. This is the key insight — instead of designing custom quantizers per data distribution, we *force* the data into a friendly distribution.
- **Per-coordinate quantizer**: Pre-computed via Lloyd-Max algorithm assuming Beta(d/2, d/2). Cached as JSON.
- **1-bit QJL residual**: Captures inner-product structure that scalar quantization loses. Stored as packed bits (1 bit per dimension of the projection).

### Compression math

For Qwen 2.5 7B, 4096 tokens, 28 layers, 4 KV heads, head_dim 128:
- Original (fp16): 28 × 2 × 4 × 4096 × 128 × 2 bytes = **234 MB**
- Codes at 3.5 bits/channel: 234 / (16/3.5) = **51 MB**
- QJL residual at d/8 = 16 dims, 1 bit each: 28 × 2 × 4 × 4096 × 16 / 8 = **1.7 MB**
- **Total compressed: ~53 MB (4.4× compression)**

For longer sequences, the ratio holds.

---

## 5. File structure

```
worker/
├── pyproject.toml
├── Dockerfile
├── runpod_template.json              # RunPod deployment template
├── README.md
│
├── server/
│   ├── __init__.py
│   ├── main.py                       # FastAPI app
│   ├── config.py
│   ├── auth.py                       # API key middleware
│   └── routes/
│       ├── compress.py
│       ├── decompress.py
│       ├── inference.py
│       ├── benchmark.py
│       └── health.py
│
├── turboquant/                       # The actual algorithm
│   ├── __init__.py
│   ├── compress.py                   # Main compress() function
│   ├── decompress.py                 # Main decompress() function
│   ├── hadamard.py                   # Fast Walsh-Hadamard transform
│   ├── quantizer.py                  # Beta-optimal scalar quantizer
│   ├── qjl.py                        # 1-bit Quantized JL projection
│   ├── serde.py                      # Binary blob format
│   └── precomputed/
│       └── beta_levels.json          # Lloyd-Max output for various bit-rates
│
├── runtime/
│   ├── __init__.py
│   ├── vllm_bridge.py                # Talk to vLLM API
│   ├── lmcache_serde.py              # Custom LMCache serializer
│   └── cache_loader.py               # Load decompressed tensor into vLLM cache
│
├── benchmarks/
│   ├── __init__.py
│   ├── quality.py                    # Perplexity + token-match measurements
│   ├── benchmark_runner.py           # Run full eval matrix
│   └── prompts/
│       └── eval_prompts.txt          # Standard eval set
│
└── tests/
    ├── test_hadamard.py              # Round-trip determinism
    ├── test_quantizer.py             # Lloyd-Max correctness
    ├── test_qjl.py                   # JL projection properties
    ├── test_compress.py              # End-to-end round-trip
    └── test_benchmark.py             # Quality measurement on synthetic data
```

---

## 6. Dependencies

```toml
# pyproject.toml
[project]
name = "agentvault-worker"
version = "0.1.0"
requires-python = ">=3.12"

dependencies = [
    # PyTorch (use CUDA 12.1 wheel from index)
    "torch>=2.4.0",
    "torchvision>=0.19.0",

    # vLLM + LMCache
    "vllm>=0.6.0",
    "lmcache>=0.2.0",

    # Transformers (for tokenizer + reference model loading)
    "transformers>=4.45",
    "accelerate>=1.0",
    "huggingface-hub>=0.26",

    # FastAPI server
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "pydantic>=2.9",
    "pydantic-settings>=2.6",
    "python-multipart>=0.0.12",
    "httpx>=0.27",

    # Math
    "numpy>=1.26",
    "scipy>=1.14",
    "pandas>=2.2",

    # Misc
    "structlog>=24.4",
]
```

For PyTorch with CUDA 12.1:
```
[tool.uv.sources]
torch = { url = "https://download.pytorch.org/whl/cu121/torch-2.4.0+cu121-cp312-cp312-linux_x86_64.whl" }
```

---

## 7. Hadamard transform — `turboquant/hadamard.py`

```python
"""
Fast Walsh-Hadamard Transform with random sign flips.

For a vector x of length d (must be power of 2):
  HxS x  where H is Hadamard matrix, S is diagonal random sign matrix

The transform makes the components of any input vector
approximately iid (after sign assignment), bringing them
closer to a Beta-distributed shape that's easy to quantize.
"""
import torch
import numpy as np


def next_power_of_2(n: int) -> int:
    return 1 << (n - 1).bit_length()


def random_signs(d: int, seed: int) -> torch.Tensor:
    """Generate a deterministic ±1 vector for given dimension and seed."""
    rng = np.random.default_rng(seed)
    return torch.tensor(rng.choice([-1.0, 1.0], size=d), dtype=torch.float32)


def fwht(x: torch.Tensor) -> torch.Tensor:
    """
    Fast Walsh-Hadamard Transform, in-place.
    Input x must have last dim a power of 2.
    Operates on the last dimension.
    """
    *batch, d = x.shape
    assert (d & (d - 1)) == 0, f"d={d} must be power of 2"
    h = 1
    while h < d:
        # Reshape and butterfly
        x = x.view(*batch, d // (2 * h), 2, h).contiguous()
        a = x[..., 0, :].clone()
        b = x[..., 1, :].clone()
        x[..., 0, :] = a + b
        x[..., 1, :] = a - b
        x = x.view(*batch, d)
        h *= 2
    return x / (d ** 0.5)  # Normalize


def hadamard_rotate(x: torch.Tensor, seed: int) -> torch.Tensor:
    """
    Apply randomized Hadamard rotation: H S x where S is random ±1 diagonal.
    Pads to next power of 2 if needed (truncated on inverse).
    """
    *batch, d = x.shape
    target_d = next_power_of_2(d)

    if target_d != d:
        padding = torch.zeros(*batch, target_d - d, device=x.device, dtype=x.dtype)
        x = torch.cat([x, padding], dim=-1)

    signs = random_signs(target_d, seed).to(x.device)
    x = x * signs
    x = fwht(x)
    return x


def hadamard_inverse(x: torch.Tensor, seed: int, original_d: int) -> torch.Tensor:
    """Inverse Hadamard rotation. Truncates back to original_d."""
    target_d = x.shape[-1]
    x = fwht(x)  # Hadamard is self-inverse
    signs = random_signs(target_d, seed).to(x.device)
    x = x * signs
    return x[..., :original_d]
```

---

## 8. Beta-optimal quantizer — `turboquant/quantizer.py`

```python
"""
Per-coordinate scalar quantizer optimized for Beta-distributed inputs.

After Hadamard rotation of a unit-norm vector, each coordinate is
approximately Beta(d/2, d/2) distributed. The Lloyd-Max algorithm
gives optimal quantization levels for this distribution.

Levels are precomputed and cached in beta_levels.json.
"""
import json
import torch
import numpy as np
from pathlib import Path
from scipy.stats import beta as beta_dist


PRECOMPUTED_PATH = Path(__file__).parent / "precomputed" / "beta_levels.json"


def lloyd_max(num_levels: int, alpha: float = 64, beta: float = 64,
              num_iterations: int = 100, num_samples: int = 100_000) -> np.ndarray:
    """
    Lloyd-Max algorithm: iteratively find optimal quantizer levels
    for a Beta(alpha, beta) distribution. (alpha=beta=d/2 for d=128)
    """
    # Sample from Beta then shift to [-1, 1]
    samples = beta_dist.rvs(alpha, beta, size=num_samples) * 2 - 1
    samples = np.sort(samples)

    # Initialize levels uniformly
    levels = np.linspace(samples.min(), samples.max(), num_levels)

    for _ in range(num_iterations):
        # Step 1: assign samples to nearest level (compute boundaries)
        boundaries = (levels[:-1] + levels[1:]) / 2
        assignments = np.searchsorted(boundaries, samples)

        # Step 2: update levels to centroid of assigned samples
        new_levels = np.array([
            samples[assignments == i].mean() if (assignments == i).any() else levels[i]
            for i in range(num_levels)
        ])

        if np.allclose(levels, new_levels, atol=1e-6):
            break
        levels = new_levels

    return levels


def precompute_all_levels():
    """Precompute and save levels for all bit-rates we support."""
    bit_rates = [2.5, 3.0, 3.5, 4.0, 5.0, 6.0]
    head_dims = [64, 128]  # Common sizes

    output = {}
    for d in head_dims:
        output[str(d)] = {}
        for bits in bit_rates:
            num_levels = round(2 ** bits)
            levels = lloyd_max(num_levels, alpha=d/2, beta=d/2)
            output[str(d)][str(bits)] = levels.tolist()

    with PRECOMPUTED_PATH.open("w") as f:
        json.dump(output, f)
    print(f"Saved precomputed levels to {PRECOMPUTED_PATH}")


class BetaQuantizer:
    """Encode/decode using precomputed levels."""

    def __init__(self, head_dim: int, bits: float):
        with PRECOMPUTED_PATH.open() as f:
            data = json.load(f)
        levels_list = data[str(head_dim)][str(bits)]
        self.levels = torch.tensor(levels_list, dtype=torch.float32)
        self.num_levels = len(self.levels)
        self.bits = bits

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        """Map x to nearest level index. Returns int32 codes."""
        # Compute distance to each level
        # x: [..., d], self.levels: [num_levels]
        x_unsq = x.unsqueeze(-1)  # [..., d, 1]
        levels = self.levels.to(x.device)  # [num_levels]
        distances = (x_unsq - levels).abs()  # [..., d, num_levels]
        codes = distances.argmin(dim=-1)  # [..., d]
        return codes.to(torch.int32)

    def decode(self, codes: torch.Tensor) -> torch.Tensor:
        """Map indices back to levels."""
        return self.levels.to(codes.device)[codes]
```

When you first set up the worker, run `python -m turboquant.quantizer` once to populate `beta_levels.json`.

---

## 9. QJL residual — `turboquant/qjl.py`

```python
"""
1-bit Quantized Johnson-Lindenstrauss projection.

The scalar quantizer captures coordinate-level information.
But for KV cache, attention computes inner products — and small
errors in coordinates can compound. The 1-bit QJL residual is
a low-overhead "second pass" that captures inner-product structure.

We project the residual through a Gaussian random matrix of
dimension d × (d/8), then store only the sign bit of each
projection coordinate.
"""
import torch
import numpy as np


def make_qjl_matrix(d: int, proj_dim: int, seed: int) -> torch.Tensor:
    """Gaussian random projection matrix W: R^d → R^proj_dim"""
    rng = np.random.default_rng(seed + 1)  # Different seed than Hadamard
    W = rng.standard_normal((d, proj_dim)) / np.sqrt(proj_dim)
    return torch.tensor(W, dtype=torch.float32)


def qjl_encode(residual: torch.Tensor, W: torch.Tensor) -> torch.Tensor:
    """
    Project residual and store sign bits.
    residual: [..., d], W: [d, proj_dim]
    Returns: bool tensor [..., proj_dim]
    """
    projected = residual @ W  # [..., proj_dim]
    return projected > 0


def qjl_decode_to_residual(qjl_bits: torch.Tensor, W: torch.Tensor) -> torch.Tensor:
    """
    Approximate the residual from sign bits.
    qjl_bits: [..., proj_dim] bool
    Returns approximated residual: [..., d]

    This is lossy — we use pseudo-inverse of W applied to
    a {-1, +1} vector reconstructed from sign bits.
    """
    signs = qjl_bits.float() * 2 - 1  # [..., proj_dim] in {-1, 1}
    # Pseudo-inverse: W^T @ (W @ W^T)^-1
    # For projection W with proj_dim < d, this gives least-squares estimate
    W_pinv = torch.linalg.pinv(W)  # [proj_dim, d]
    residual_approx = signs @ W_pinv  # [..., d]
    return residual_approx
```

---

## 10. Main compress/decompress — `turboquant/compress.py`

```python
"""
End-to-end TurboQuant compress and decompress.
"""
import torch
import numpy as np
import struct
import hashlib
from typing import NamedTuple
from .hadamard import hadamard_rotate, hadamard_inverse, next_power_of_2
from .quantizer import BetaQuantizer
from .qjl import make_qjl_matrix, qjl_encode, qjl_decode_to_residual
from .serde import serialize_blob, deserialize_blob


class CompressResult(NamedTuple):
    blob: bytes
    metadata: dict


def compress(
    kv_cache: torch.Tensor,    # [L, 2, H, S, D]
    bits: float = 3.5,
    seed: int = 42,
    qjl_ratio: float = 0.125,  # proj_dim / d
) -> CompressResult:
    """
    Compress a KV cache using TurboQuant.
    """
    L, two, H, S, D = kv_cache.shape
    assert two == 2, "KV cache must have keys and values"
    target_d = next_power_of_2(D)
    proj_dim = max(8, int(D * qjl_ratio))

    # Reshape to per-vector: [N, D] where N = L*2*H*S
    vectors = kv_cache.reshape(-1, D).float()
    if vectors.is_cuda:
        # Process on GPU
        device = vectors.device
    else:
        device = torch.device("cpu")

    # Step 1: Random Hadamard rotation
    rotated = hadamard_rotate(vectors, seed=seed)  # [N, target_d]

    # Step 2: Per-coordinate quantization
    # Note: rotated values are in roughly [-1, 1] range after normalization
    quantizer = BetaQuantizer(head_dim=target_d, bits=bits)
    codes = quantizer.encode(rotated)  # [N, target_d] int32

    # Step 3: QJL residual
    decoded = quantizer.decode(codes)
    residual = rotated - decoded
    W = make_qjl_matrix(target_d, proj_dim, seed=seed).to(device)
    qjl_bits = qjl_encode(residual, W)  # [N, proj_dim] bool

    # Pack everything
    metadata = {
        "shape": [L, two, H, S, D],
        "target_d": target_d,
        "bits": bits,
        "seed": seed,
        "proj_dim": proj_dim,
        "num_levels": quantizer.num_levels,
    }

    blob = serialize_blob(
        codes=codes.cpu().numpy().astype(np.int8),  # bits ≤ 8
        qjl_bits=qjl_bits.cpu().numpy(),
        metadata=metadata,
    )

    return CompressResult(blob=blob, metadata=metadata)


def decompress(blob: bytes) -> torch.Tensor:
    """
    Decompress a TurboQuant blob to KV cache tensor.
    """
    codes_np, qjl_bits_np, metadata = deserialize_blob(blob)
    L, two, H, S, D = metadata["shape"]
    target_d = metadata["target_d"]
    proj_dim = metadata["proj_dim"]
    seed = metadata["seed"]
    bits = metadata["bits"]

    codes = torch.tensor(codes_np, dtype=torch.int32)
    qjl_bits = torch.tensor(qjl_bits_np, dtype=torch.bool)

    quantizer = BetaQuantizer(head_dim=target_d, bits=bits)
    decoded = quantizer.decode(codes)  # [N, target_d]

    W = make_qjl_matrix(target_d, proj_dim, seed=seed)
    residual_approx = qjl_decode_to_residual(qjl_bits, W)

    rotated_approx = decoded + residual_approx
    vectors = hadamard_inverse(rotated_approx, seed=seed, original_d=D)  # [N, D]

    return vectors.reshape(L, two, H, S, D)
```

---

## 11. Serialization — `turboquant/serde.py`

```python
"""
Binary blob format:

[magic 4B "TQNT"]
[version 4B u32]
[metadata_len 4B u32]
[metadata JSON bytes]
[codes_len 8B u64]
[codes bytes (np.int8 packed)]
[qjl_len 8B u64]
[qjl bytes (np.uint8 packed bits)]
[sha256 32B]
"""
import json
import struct
import hashlib
import numpy as np

MAGIC = b"TQNT"
VERSION = 1


def serialize_blob(codes: np.ndarray, qjl_bits: np.ndarray, metadata: dict) -> bytes:
    metadata_json = json.dumps(metadata, separators=(",", ":")).encode()

    # Pack QJL bits (currently bool, pack to bytes)
    qjl_packed = np.packbits(qjl_bits.flatten(), axis=0)

    # Serialize codes (assume int8 codes for ≤8-bit quantization)
    codes_bytes = codes.tobytes()

    parts = [
        MAGIC,
        struct.pack("<I", VERSION),
        struct.pack("<I", len(metadata_json)),
        metadata_json,
        struct.pack("<Q", len(codes_bytes)),
        codes_bytes,
        struct.pack("<Q", len(qjl_packed.tobytes())),
        qjl_packed.tobytes(),
    ]
    body = b"".join(parts)

    # Append checksum
    checksum = hashlib.sha256(body).digest()
    return body + checksum


def deserialize_blob(blob: bytes) -> tuple[np.ndarray, np.ndarray, dict]:
    body = blob[:-32]
    expected_checksum = blob[-32:]
    actual_checksum = hashlib.sha256(body).digest()
    if expected_checksum != actual_checksum:
        raise ValueError("Blob checksum mismatch — corrupted data")

    pos = 0
    assert body[pos:pos+4] == MAGIC, "Invalid magic"
    pos += 4

    version = struct.unpack("<I", body[pos:pos+4])[0]
    pos += 4
    if version != VERSION:
        raise ValueError(f"Unsupported version {version}")

    metadata_len = struct.unpack("<I", body[pos:pos+4])[0]
    pos += 4
    metadata = json.loads(body[pos:pos+metadata_len])
    pos += metadata_len

    codes_len = struct.unpack("<Q", body[pos:pos+8])[0]
    pos += 8
    codes_bytes = body[pos:pos+codes_len]
    pos += codes_len

    qjl_len = struct.unpack("<Q", body[pos:pos+8])[0]
    pos += 8
    qjl_bytes = body[pos:pos+qjl_len]

    # Reconstruct numpy arrays
    L, two, H, S, D = metadata["shape"]
    target_d = metadata["target_d"]
    N = L * two * H * S
    codes = np.frombuffer(codes_bytes, dtype=np.int8).reshape(N, target_d)

    proj_dim = metadata["proj_dim"]
    qjl_packed = np.frombuffer(qjl_bytes, dtype=np.uint8)
    qjl_bits = np.unpackbits(qjl_packed)[:N * proj_dim].reshape(N, proj_dim).astype(bool)

    return codes, qjl_bits, metadata
```

---

## 12. Quality benchmark — `benchmarks/quality.py`

This is the **most important script in the project**. It empirically validates the load-bearing claim.

```python
"""
Run this on Day 1 to verify TurboQuant works on Qwen.

Usage:
  python -m benchmarks.benchmark_runner --model Qwen/Qwen2.5-7B-Instruct
"""
import argparse
import json
import torch
import pandas as pd
from transformers import AutoModelForCausalLM, AutoTokenizer
from turboquant.compress import compress, decompress


EVAL_PROMPTS = [
    "Write a production-grade Anchor program for a simple counter.",
    "Explain Solana's account model and how PDAs differ from regular accounts.",
    "Generate a TypeScript function that fetches all SPL token accounts for a wallet.",
    "What are the security considerations for upgradeable Solana programs?",
    "Write a Rust async function to query Jupiter's swap quote API.",
]


def run_with_kv_capture(model, tokenizer, prompt: str, max_new_tokens: int = 100):
    """
    Run inference, capture KV cache after the prompt is processed,
    then continue generation. Returns (kv_cache, generated_tokens).
    """
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

    with torch.no_grad():
        # First pass: process prompt, get cache
        outputs = model(**inputs, use_cache=True)
        kv_cache = outputs.past_key_values

        # Generate continuation
        generated = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            past_key_values=kv_cache,
            do_sample=False,  # Greedy for reproducibility
        )

    return kv_cache, generated[0][inputs["input_ids"].shape[1]:].cpu().tolist()


def kv_to_tensor(kv_cache):
    """Convert HF DynamicCache to [L, 2, H, S, D] tensor."""
    keys = torch.stack([layer[0] for layer in kv_cache])  # [L, batch, H, S, D]
    values = torch.stack([layer[1] for layer in kv_cache])
    # Stack k/v on dim 1: [L, 2, H, S, D] (assuming batch=1)
    stacked = torch.stack([keys, values], dim=1).squeeze(2)
    return stacked


def tensor_to_kv(tensor, num_layers: int):
    """Convert [L, 2, H, S, D] back to HF cache format."""
    cache = []
    for l in range(num_layers):
        k = tensor[l, 0].unsqueeze(0)
        v = tensor[l, 1].unsqueeze(0)
        cache.append((k, v))
    return cache


def benchmark_at_bits(model, tokenizer, prompt: str, bits: float, seed: int = 42):
    # Original run
    kv_orig, tokens_orig = run_with_kv_capture(model, tokenizer, prompt)
    kv_tensor = kv_to_tensor(kv_orig)

    # Compress + decompress
    result = compress(kv_tensor, bits=bits, seed=seed)
    blob_size = len(result.blob)
    original_size = kv_tensor.element_size() * kv_tensor.numel()

    kv_recon = decompress(result.blob)
    kv_recon_cache = tensor_to_kv(kv_recon, model.config.num_hidden_layers)

    # Run with reconstructed cache
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    with torch.no_grad():
        generated_recon = model.generate(
            **inputs,
            max_new_tokens=100,
            past_key_values=kv_recon_cache,
            do_sample=False,
        )
    tokens_recon = generated_recon[0][inputs["input_ids"].shape[1]:].cpu().tolist()

    # Metrics
    match_count = sum(1 for a, b in zip(tokens_orig, tokens_recon) if a == b)
    token_match_rate = match_count / len(tokens_orig)
    compression_ratio = original_size / blob_size

    return {
        "bits": bits,
        "compression_ratio": compression_ratio,
        "blob_size_mb": blob_size / (1024 * 1024),
        "original_size_mb": original_size / (1024 * 1024),
        "token_match_rate": token_match_rate,
        "first_50_match": sum(1 for a, b in zip(tokens_orig[:50], tokens_recon[:50]) if a == b) / 50,
    }


def main(model_name: str):
    print(f"Loading {model_name}...")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.float16,
        device_map="auto",
    )

    bit_rates = [2.5, 3.0, 3.5, 4.0]
    rows = []
    for prompt in EVAL_PROMPTS:
        print(f"\nPrompt: {prompt[:60]}...")
        for bits in bit_rates:
            result = benchmark_at_bits(model, tokenizer, prompt, bits)
            result["prompt"] = prompt[:60]
            rows.append(result)
            print(f"  {bits} bits: {result['compression_ratio']:.2f}x, "
                  f"first-50 match: {result['first_50_match']:.1%}")

    df = pd.DataFrame(rows)
    df.to_csv("benchmark_results.csv", index=False)
    summary = df.groupby("bits").agg({
        "compression_ratio": "mean",
        "first_50_match": "mean",
        "token_match_rate": "mean",
    })
    print("\n=== SUMMARY ===")
    print(summary)
    print(f"\nFull results saved to benchmark_results.csv")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    args = parser.parse_args()
    main(args.model)
```

### Expected results (Day 1 sanity check)

| Bits | Compression ratio | First-50 token match | Verdict |
|---|---|---|---|
| 2.5 | ~6.4× | >85% | Marginal — usable but lossy |
| 3.0 | ~5.3× | >92% | Good |
| **3.5** | **~4.6×** | **>97%** | **Production target** |
| 4.0 | ~4.0× | >98% | Conservative fallback |

**If you don't see >95% token match at 3.5 bits, debug.** Common issues:
1. Hadamard transform bug (verify round-trip identity at bits=∞ first)
2. Quantizer levels mismatch (ensure same bits used for encode/decode)
3. QJL pseudo-inverse numerically unstable at small proj_dim

---

## 13. FastAPI server — `server/main.py`

```python
from fastapi import FastAPI, UploadFile, File, Header, HTTPException
from contextlib import asynccontextmanager
import torch
import io
from .config import settings
from turboquant.compress import compress, decompress
from .routes import compress as compress_route
from .routes import decompress as decompress_route
from .routes import inference as inference_route
from .routes import benchmark as benchmark_route
from .routes import health


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-warm: ensure quantizer levels are loaded
    print("Worker starting up...")
    print(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"CUDA device: {torch.cuda.get_device_name()}")
    yield


app = FastAPI(title="AgentVault Worker", lifespan=lifespan)
app.include_router(health.router)
app.include_router(compress_route.router)
app.include_router(decompress_route.router)
app.include_router(inference_route.router)
app.include_router(benchmark_route.router)
```

### `/compress` endpoint

```python
# server/routes/compress.py
from fastapi import APIRouter, UploadFile, File, Form, Header, HTTPException
from fastapi.responses import Response
import torch
from turboquant.compress import compress

router = APIRouter()


@router.post("/compress")
async def compress_endpoint(
    file: UploadFile = File(...),
    bits: float = Form(3.5),
    seed: int = Form(42),
    api_key: str = Header(..., alias="X-API-Key"),
):
    if api_key != settings.WORKER_API_KEY:
        raise HTTPException(401, "Invalid API key")

    raw = await file.read()
    # Assumes raw is a PyTorch saved tensor of shape [L, 2, H, S, D]
    buf = io.BytesIO(raw)
    kv_cache = torch.load(buf, map_location="cuda" if torch.cuda.is_available() else "cpu")

    result = compress(kv_cache, bits=bits, seed=seed)

    return Response(
        content=result.blob,
        media_type="application/octet-stream",
        headers={
            "X-Original-Size": str(kv_cache.element_size() * kv_cache.numel()),
            "X-Compressed-Size": str(len(result.blob)),
            "X-Compression-Ratio": f"{(kv_cache.element_size() * kv_cache.numel()) / len(result.blob):.2f}",
            "X-Metadata": json.dumps(result.metadata),
        },
    )
```

### `/inference` endpoint (the sandbox-serving one)

```python
# server/routes/inference.py
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from turboquant.compress import decompress
from runtime.cache_loader import load_into_vllm
from runtime.vllm_bridge import vllm_complete
import httpx


class InferenceRequest(BaseModel):
    arweave_tx: str
    content_hash_hex: str
    metadata: dict
    query: str
    max_tokens: int = 200


router = APIRouter()


@router.post("/inference")
async def inference_endpoint(
    req: InferenceRequest,
    api_key: str = Header(..., alias="X-API-Key"),
):
    if api_key != settings.WORKER_API_KEY:
        raise HTTPException(401, "Invalid API key")

    # Step 1: Fetch blob from Arweave
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(f"https://arweave.net/{req.arweave_tx}")
        resp.raise_for_status()
        blob = resp.content

    # Step 2: Verify hash
    import hashlib
    actual = hashlib.sha256(blob).hexdigest()
    if actual != req.content_hash_hex:
        raise HTTPException(400, "Hash mismatch — possible tampering")

    # Step 3: Decompress
    cache_tensor = decompress(blob)

    # Step 4: Load into vLLM
    cache_id = await load_into_vllm(cache_tensor)

    # Step 5: Inference
    response = await vllm_complete(
        prompt=req.query,
        kv_cache_id=cache_id,
        max_tokens=req.max_tokens,
    )

    # Step 6: Naive quality scoring (longer + more code-like = better, for demo)
    quality = min(1.0, len(response.split()) / 100.0)

    return {
        "response": response,
        "quality_score": quality,
    }
```

---

## 14. RunPod deployment

### `Dockerfile`

```dockerfile
FROM pytorch/pytorch:2.4.0-cuda12.1-cudnn9-runtime

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy and install
COPY pyproject.toml ./
RUN uv pip install --system -e .

# Install vLLM with LMCache
RUN pip install vllm lmcache

# Copy code
COPY . .

# Expose worker + vLLM ports
EXPOSE 8001 8000

# Start both vLLM and worker
CMD ["bash", "-c", \
     "vllm serve Qwen/Qwen2.5-7B-Instruct \
       --kv-cache-dtype fp8 \
       --max-model-len 8192 \
       --gpu-memory-utilization 0.7 \
       --port 8000 & \
      sleep 60 && \
      uvicorn server.main:app --host 0.0.0.0 --port 8001"]
```

### RunPod template

In the RunPod console:
- **Container Image**: build from your Dockerfile and push to Docker Hub or use RunPod's registry
- **GPU**: A10G (24GB VRAM)
- **Container Disk**: 50GB (for model weights + cache)
- **Volume Disk**: 0GB (stateless service)
- **Expose**: HTTP port 8001 (worker), HTTP port 8000 (vLLM internal only — don't expose)
- **Environment**:
  ```
  WORKER_API_KEY=<random secret>
  HF_TOKEN=<your huggingface token>
  ```

Get the public URL from RunPod → set as `WORKER_URL` in backend's env.

### Cost estimate

A10G is ~$0.40/hr on RunPod. For the hackathon:
- Demo prep + testing: ~30 hours = $12
- Live demo + buffer: ~10 hours = $4
- **Total: ~$16-20**

You can pause the pod between development sessions to save money.

---

## 15. Claude Code prompt — paste this verbatim

````
You are implementing TurboQuant — extreme KV cache quantization that achieves 3.5 bits/channel with quality neutrality on Qwen 2.5 7B. This is the load-bearing technical claim of the AgentVault project.

## Read the spec
Open `docs/03_TURBOQUANT_WORKER.md` and read everything carefully. The algorithm details, expected compression ratios, and quality targets are all specified.

The reference paper is "Beyond Distortion-Rate Optimal: TurboQuant" (Zandieh, Daliri, Hadian, Mirrokni — Google Research, April 2025), arxiv.org/abs/2504.19874.

## Hard requirements
- Python 3.12, PyTorch 2.4+, CUDA 12.1
- Implement the exact 3-step algorithm: Hadamard rotation → Beta-optimal scalar quantizer → 1-bit QJL residual
- Round-trip determinism: compress(x) → decompress() must give bit-identical results given same seed
- Serialization format must match the spec in section 11 (binary blob with magic, version, metadata JSON, codes, QJL bits, SHA-256 checksum)
- FastAPI server with the 5 endpoints specified

## Build order (CRITICAL)
1. `turboquant/hadamard.py` — implement and unit-test fast Walsh-Hadamard transform with random sign flips. Test: hadamard_inverse(hadamard_rotate(x, seed), seed) == x for any x.
2. `turboquant/quantizer.py` — Lloyd-Max algorithm + BetaQuantizer class. Run `python -m turboquant.quantizer` to generate `precomputed/beta_levels.json`.
3. `turboquant/qjl.py` — QJL projection encoder/decoder.
4. `turboquant/serde.py` — binary blob format. Round-trip test on synthetic data.
5. `turboquant/compress.py` — full compress/decompress pipeline. Test: round-trip a real KV cache from a small Qwen model.
6. `benchmarks/quality.py` and `benchmarks/benchmark_runner.py` — Day 1 validation script.
7. `server/main.py` and routes — FastAPI server.
8. `runtime/vllm_bridge.py` and `runtime/cache_loader.py` — vLLM integration via LMCache.
9. `Dockerfile` and `runpod_template.json` — deployment artifacts.

## Day 1 validation (DO THIS FIRST AFTER STEP 5)
Run the benchmark script on Qwen 2.5 7B. Expected output at 3.5 bits:
- Compression ratio: 4.4-4.8x
- First-50 token match: >95%
- Token match rate: >90% over 100 tokens

If this fails, debug before continuing. Common issues:
- Hadamard not actually self-inverse (verify with `hadamard_inverse(hadamard_rotate(x, 42), 42, len(x)) ≈ x`)
- Quantizer level boundaries off-by-one
- QJL pseudo-inverse numerical instability (try larger proj_dim if needed)

## Common pitfalls
- Don't .cpu() in the compression hot path — use GPU end-to-end
- The HF DynamicCache format ≠ tuple of (key, value) tensors — convert carefully (see kv_to_tensor function in benchmark)
- Serialize codes as int8 (works for ≤8-bit quantization; assert in serde.py)
- QJL bits MUST be packed (np.packbits) for storage efficiency
- The metadata.seed must be the same on encode and decode

## Tests
- `tests/test_hadamard.py` — round-trip identity, orthogonality
- `tests/test_quantizer.py` — Lloyd-Max convergence, encode/decode bijection
- `tests/test_qjl.py` — preserves inner products approximately
- `tests/test_compress.py` — synthetic KV cache round-trip

## Stretch goals (only after core works)
- GPU-accelerated Lloyd-Max with batched updates
- Adaptive bit allocation per-layer (some layers tolerate more compression)
- Streaming compression for very large caches that don't fit in VRAM

Build it. Validate on Qwen 2.5 7B. The benchmark numbers are the ground truth — they tell you whether the project is viable.
````

---

## 16. Definition of done

- [ ] Hadamard round-trip identity verified (compress(decompress(x, seed)) ≈ x)
- [ ] Lloyd-Max precomputed levels saved for bits ∈ {2.5, 3.0, 3.5, 4.0} × head_dim ∈ {64, 128}
- [ ] Full compress/decompress pipeline works on synthetic data
- [ ] **Benchmark on Qwen 2.5 7B shows >95% first-50 token match at 3.5 bits**
- [ ] Compression ratio ≥4× achieved
- [ ] Worker FastAPI server starts cleanly
- [ ] All 5 endpoints respond correctly
- [ ] Docker image builds (test locally with `docker build .`)
- [ ] Deployed to RunPod, public URL accessible
- [ ] Backend can call worker `/compress` and get valid output
- [ ] vLLM + LMCache integration loads decompressed cache successfully

When this list is checked, the project's load-bearing technical claim is validated. Everything else is integration work.

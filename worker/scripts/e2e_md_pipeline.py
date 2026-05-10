"""
Behavioral E2E: drive a real markdown memory through the live worker and
verify the recovered cache produces the same next-token distribution in Qwen.

Why distributional, not greedy match: tiny KV perturbations cascade through
24 layers of attention, so greedy decoding diverges even at cosine 0.999.
What matters is whether the cache makes the model assign the same probability
mass to the same candidate tokens.

  curl-equivalent: POST /compress (KV bytes) → blob → POST /decompress → bytes
                   then load both into Qwen as past_key_values and diff logits.
"""
from __future__ import annotations

import hashlib
import io
import sys
import time

import httpx
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, DynamicCache

WORKER = "http://127.0.0.1:8002"
HEADERS = {"X-API-Key": "dev-secret-change-me"}
MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
BITS = 6.0
MAX_NEW_TOKENS = 50

MEMORY_MD = """# Solana program audit notes — AgentVault v0.1

The MemoryListing PDA is seeded with `[b"listing", seller.key, content_hash]`.
This makes content_hash uniqueness collision-free across sellers but means a
seller cannot list the same blob twice; if they need to, they must mutate at
least one byte first.

The buy_memory CPI splits 90% to the seller and 10% to the platform treasury
in a single instruction so partial failures are impossible. Both transfers
go through anchor-spl::token::transfer with the buyer as authority.

Sandbox access expires in 24 hours by default and is capped at 100 queries.
"""

QUESTION = "\n\nQ: Why can't a seller list the same blob twice on AgentVault?\nA:"


def kv_to_tensor(past) -> torch.Tensor:
    keys, values = [], []
    layers = past.layers if hasattr(past, "layers") else list(past)
    for layer in layers:
        if hasattr(layer, "keys") and hasattr(layer, "values"):
            k, v = layer.keys, layer.values
        else:
            k, v = layer
        keys.append(k.squeeze(0))
        values.append(v.squeeze(0))
    return torch.stack([torch.stack(keys, 0), torch.stack(values, 0)], dim=1)


def tensor_to_kv(t: torch.Tensor) -> DynamicCache:
    cache = DynamicCache()
    for layer_idx in range(t.shape[0]):
        cache.update(t[layer_idx, 0].unsqueeze(0), t[layer_idx, 1].unsqueeze(0), layer_idx)
    return cache


def main() -> int:
    print(f"[e2e] loading {MODEL}...")
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32)
    model.eval()

    prompt = MEMORY_MD + QUESTION
    inputs = tok(prompt, return_tensors="pt")
    seq_len = inputs.input_ids.shape[1]
    print(f"[e2e] prompt {seq_len} tokens, capturing KV...")

    with torch.no_grad():
        out = model(**inputs, use_cache=True)
    kv = kv_to_tensor(out.past_key_values)
    print(f"[e2e] KV {tuple(kv.shape)} {kv.numel()*4/1024:.0f} KB")

    buf = io.BytesIO()
    torch.save(kv, buf)
    raw = buf.getvalue()
    print(f"[e2e] sha256={hashlib.sha256(raw).hexdigest()[:16]}…")

    print(f"[e2e] POST /compress (bits={BITS})")
    t0 = time.time()
    r = httpx.post(
        f"{WORKER}/compress",
        headers=HEADERS,
        files={"file": ("kv.bin", raw, "application/octet-stream")},
        params={"bits": BITS, "seed": 42},
        timeout=120,
    )
    r.raise_for_status()
    blob = r.content
    ratio = float(r.headers["X-Compression-Ratio"])
    print(f"[e2e]   ratio={ratio:.2f}x  size={len(blob)}  t={time.time()-t0:.2f}s")

    print("[e2e] POST /decompress")
    t0 = time.time()
    r2 = httpx.post(
        f"{WORKER}/decompress",
        headers=HEADERS,
        files={"file": ("blob.tqnt", blob, "application/octet-stream")},
        timeout=120,
    )
    r2.raise_for_status()
    kv_recon = torch.load(io.BytesIO(r2.content), map_location="cpu", weights_only=True)
    print(f"[e2e]   t={time.time()-t0:.2f}s")

    flat_o = kv.reshape(-1, kv.shape[-1]).float()
    flat_r = kv_recon.reshape(-1, kv_recon.shape[-1]).float()
    cos_mean = torch.nn.functional.cosine_similarity(flat_o, flat_r, dim=-1).mean().item()

    # Behavioural: run a single forward step with each cache and compare logits.
    def step_logits(past_kv: torch.Tensor) -> torch.Tensor:
        cache = tensor_to_kv(past_kv)
        last = inputs.input_ids[:, -1:]
        with torch.no_grad():
            return model(input_ids=last, past_key_values=cache, use_cache=False).logits[0, -1]

    print("[e2e] computing next-token distributions on both caches...")
    p_orig = torch.softmax(step_logits(kv.clone()), dim=-1)
    p_rec = torch.softmax(step_logits(kv_recon), dim=-1)

    kl = torch.sum(p_orig * (torch.log(p_orig + 1e-12) - torch.log(p_rec + 1e-12))).item()
    top10_o = set(torch.topk(p_orig, 10).indices.tolist())
    top10_r = set(torch.topk(p_rec, 10).indices.tolist())
    overlap = len(top10_o & top10_r) / 10
    top1_match = torch.argmax(p_orig).item() == torch.argmax(p_rec).item()
    mass_kept = p_rec[list(top10_o)].sum().item()
    mass_orig = p_orig[list(top10_o)].sum().item()

    # Greedy generations for the human to read.
    with torch.no_grad():
        gen_o = model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS, past_key_values=tensor_to_kv(kv.clone()), do_sample=False)[0, seq_len:].tolist()
        gen_r = model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS, past_key_values=tensor_to_kv(kv_recon), do_sample=False)[0, seq_len:].tolist()

    print()
    print("=" * 70)
    print(f"  Compression ratio          : {ratio:.2f}x  ({len(raw)} → {len(blob)} bytes)")
    print(f"  Cache cosine similarity    : {cos_mean:.4f}")
    print(f"  Next-token KL divergence   : {kl:.4f}  (< 0.1 ≈ near-identical)")
    print(f"  Top-1 token match          : {top1_match}")
    print(f"  Top-10 overlap             : {overlap:.0%}")
    print(f"  Top-10 mass kept           : {mass_kept:.3f} / {mass_orig:.3f}")
    print(f"  Greedy 50-token match      : {sum(1 for a, b in zip(gen_o, gen_r) if a == b)}/50")
    print("=" * 70)
    print(f"  decoded original  : {tok.decode(gen_o)!r}")
    print(f"  decoded recovered : {tok.decode(gen_r)!r}")

    ok = cos_mean >= 0.95 and kl < 1.0 and overlap >= 0.5
    print(f"\n[e2e] {'PASS' if ok else 'FAIL'} — cache produces {'similar' if ok else 'divergent'} next-token distributions")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

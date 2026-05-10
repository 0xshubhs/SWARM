"""
Quality benchmark for TurboQuant.

Validates the load-bearing claim: 3.5 bits/channel achieves quality neutrality
on Qwen 2.5 7B's KV cache.

This is the most important script in the project — if TurboQuant doesn't hit
>95% first-50 token match at 3.5 bits on Qwen, the pitch falls apart.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import torch

try:
    from transformers import AutoModelForCausalLM, AutoTokenizer, DynamicCache
except ImportError:
    raise ImportError("transformers required: pip install transformers")

from worker.turboquant.compress import compress, decompress

EVAL_PROMPTS = [
    "Write a production-grade Anchor program for a simple counter.",
    "Explain Solana's account model and how PDAs differ from regular accounts.",
    "Generate a TypeScript function that fetches all SPL token accounts for a wallet.",
    "What are the security considerations for upgradeable Solana programs?",
    "Write a Rust async function to query Jupiter's swap quote API.",
    "Implement a Python async generator that yields prime numbers.",
    "Explain the difference between async/await and coroutines in Python.",
    "Write a SQL query that finds duplicate records in a users table.",
    "Describe how a merkle tree is used for proving membership.",
    "Implement a basic rate limiter using a token bucket algorithm.",
]


def load_prompts(path: str | Path | None = None) -> list[str]:
    """Load eval prompts from file or use default list."""
    if path and Path(path).exists():
        return Path(path).read_text().strip().split("\n")
    return EVAL_PROMPTS


def kv_cache_to_tensor(kv_cache: DynamicCache) -> torch.Tensor:
    """
    Convert HuggingFace DynamicCache to [L, 2, H, S, D] tensor.

    For Qwen2.5-7B-Instruct with GQA: num_key_value_heads=4
    """
    keys = []
    values = []
    for layer_kv in kv_cache:
        k, v = layer_kv
        keys.append(k)
        values.append(v)

    keys_t = torch.stack([k.squeeze(0) for k in keys], dim=0)
    values_t = torch.stack([v.squeeze(0) for v in values], dim=0)

    _L, _H, _S, _D = keys_t.shape
    return torch.stack([keys_t, values_t], dim=1)


def tensor_to_kv_cache(tensor: torch.Tensor, model_config: Any) -> DynamicCache:
    """Convert [L, 2, H, S, D] tensor back to DynamicCache format."""
    L, _two, _H, _S, _D = tensor.shape
    cache = DynamicCache()
    for l in range(L):
        k = tensor[l, 0].unsqueeze(0)
        v = tensor[l, 1].unsqueeze(0)
        cache.update(k, v, l)
    return cache


def run_with_kv_capture(
    model: Any,
    tokenizer: Any,
    prompt: str,
    max_new_tokens: int = 100,
) -> tuple[DynamicCache, list[int]]:
    """
    Run inference, capture KV cache after prompt is processed,
    then continue generation. Returns (kv_cache, generated_tokens).
    """
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model(**inputs, use_cache=True)
        kv_cache = outputs.past_key_values

        generated = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            past_key_values=kv_cache,
            do_sample=False,
        )

    return kv_cache, generated[0][inputs["input_ids"].shape[1] :].cpu().tolist()


def benchmark_at_bits(
    model: Any,
    tokenizer: Any,
    prompt: str,
    bits: float,
    seed: int = 42,
    max_new_tokens: int = 100,
) -> dict[str, Any]:
    """
    Benchmark TurboQuant at a specific bit rate for a single prompt.

    Returns metrics dict with compression ratio, token match rate, etc.
    """
    kv_orig, tokens_orig = run_with_kv_capture(model, tokenizer, prompt, max_new_tokens)
    kv_tensor = kv_cache_to_tensor(kv_orig)

    result = compress(kv_tensor, bits=bits, seed=seed)
    blob_size = len(result.blob)
    original_size = kv_tensor.element_size() * kv_tensor.numel()

    kv_recon = decompress(result.blob)
    kv_recon_cache = tensor_to_kv_cache(kv_recon, model.config)

    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    with torch.no_grad():
        generated_recon = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            past_key_values=kv_recon_cache,
            do_sample=False,
        )
    tokens_recon = generated_recon[0][inputs["input_ids"].shape[1] :].cpu().tolist()

    match_count = sum(1 for a, b in zip(tokens_orig, tokens_recon, strict=False) if a == b)
    n = len(tokens_orig)
    token_match_rate = match_count / n if n > 0 else 0.0

    compression_ratio = original_size / blob_size

    return {
        "bits": bits,
        "prompt": prompt[:80],
        "compression_ratio": compression_ratio,
        "blob_size_mb": blob_size / (1024 * 1024),
        "original_size_mb": original_size / (1024 * 1024),
        "token_match_rate": token_match_rate,
        "first_50_match": sum(1 for a, b in zip(tokens_orig[:50], tokens_recon[:50], strict=False) if a == b) / min(50, len(tokens_orig)),
        "num_tokens": n,
    }


def main(model_name: str, output_csv: str | None = None, prompts_path: str | Path | None = None) -> None:
    """Run full benchmark matrix on Qwen model."""
    print(f"Loading {model_name}...")
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )

    prompts = load_prompts(prompts_path)
    bit_rates = [2.5, 3.0, 3.5, 4.0]
    rows = []

    print(f"\nRunning benchmark on {len(prompts)} prompts × {len(bit_rates)} bit rates\n")

    for prompt in prompts:
        print(f"Prompt: {prompt[:60]}...")
        for bits in bit_rates:
            result = benchmark_at_bits(model, tokenizer, prompt, bits)
            rows.append(result)
            status = "PASS" if result["first_50_match"] > 0.95 else "WARN"
            print(
                f"  {bits} bits: {result['compression_ratio']:.1f}x, "
                f"first-50: {result['first_50_match']:.1%}, "
                f"tokens: {result['token_match_rate']:.1%} [{status}]"
            )

    try:
        import pandas as pd
        df = pd.DataFrame(rows)
        summary = df.groupby("bits").agg({
            "compression_ratio": "mean",
            "first_50_match": "mean",
            "token_match_rate": "mean",
        }).round(3)
        print("\n=== SUMMARY ===")
        print(summary.to_string())

        if output_csv:
            df.to_csv(output_csv, index=False)
            print(f"\nFull results saved to {output_csv}")

        target_row = summary.loc[3.5]
        if target_row["first_50_match"] < 0.95:
            print(f"\n!!! BENCHMARK FAILED: 3.5 bits first-50 match = {target_row['first_50_match']:.1%} < 95%")
            print("Debug: Hadamard, quantizer, QJL — in that order.")
        else:
            print(f"\nBENCHMARK PASSED: 3.5 bits first-50 match = {target_row['first_50_match']:.1%} >= 95%")

    except ImportError:
        print("\npandas not installed — skipping summary")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TurboQuant quality benchmark")
    parser.add_argument(
        "--model",
        default="Qwen/Qwen2.5-7B-Instruct",
        help="Model to benchmark against",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="CSV output path for full results",
    )
    args = parser.parse_args()
    main(args.model, args.output)
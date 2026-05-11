# TurboQuant compatibility verdict — laptop / RTX 4050

**Tested:** 2026-05-10. Ubuntu 24.04, RTX 4050 Laptop (6 GB VRAM), CUDA 12.0 toolkit, NVIDIA driver 580.142.

## TL;DR

**The hardware works. The runtime works. LMCache integration is gated on a vLLM upgrade.** TurboQuant itself doesn't exist as code — that's separate engineering work, ~3 days per `docs/03_TURBOQUANT_WORKER.md`.

| Component | Status |
|---|---|
| vLLM 0.6.6 boots on RTX 4050 | ✅ |
| Qwen 2.5 0.5B-Instruct serves chat completions | ✅ |
| Cloudflare quick tunnel (free, no domain) | ✅ exposes a public `*.trycloudflare.com` URL |
| Public `/v1/chat/completions` works through tunnel | ✅ |
| LMCache 0.4.4 imports | ✅ (Python fallback — C++ binding ABI mismatch with torch 2.5) |
| LMCache wired into vLLM via `--kv-transfer-config` | ❌ — `LMCacheConnectorV1` requires vLLM ≥ 0.7 |
| TurboQuant serde plugin | ❌ — does not yet exist as code |

## What's running right now

```
laptop:8000  ← vLLM (Qwen 2.5 0.5B, bf16, 2k ctx)
                                   │
                cloudflared        │  pid: cat .run/vllm.pid
                quick tunnel       │  log: logs/vllm.log
                                   ▼
   https://dir-export-remarks-karen.trycloudflare.com
```

(URL rotates every restart — current one in `.run/tunnel.url`.)

Smoke test result:

```bash
$ curl -s http://127.0.0.1:8000/v1/chat/completions \
    -H 'Content-Type: application/json' \
    -d '{"model":"Qwen/Qwen2.5-0.5B-Instruct","messages":[{"role":"user","content":"Reply with exactly the word OK."}],"max_tokens":8}'
{"choices":[{"message":{"role":"assistant","content":"OK."}}], ... }
```

Same call through the public tunnel returns the same payload. ✓

## What broke and why

### 1. vLLM 0.6.6 ↔ LMCache version gap

```python
>>> KVTransferConfig.from_cli('{"kv_connector":"LMCacheConnectorV1","kv_role":"kv_both"}')
ValidationError: Unsupported kv_connector: LMCacheConnectorV1.
                  Supported connectors are ['PyNcclConnector', 'MooncakeConnector'].
```

`LMCacheConnectorV1` was added in vLLM's V1 engine path (≥ 0.7). LMCache 0.4.4 only knows how to integrate via that connector. So **with vLLM 0.6.6 + LMCache 0.4.4 you cannot wire LMCache as a vLLM connector at all** — they don't share an API.

### 2. transformers 5.x broke vLLM 0.6.6

uv defaulted to `transformers==5.8.0` which removed `Qwen2Tokenizer.all_special_tokens_extended`. Pinned back to `transformers==4.57.6`. Locked in `runbook/install.sh`.

### 3. HF Xet downloader stalls

The new HF Xet protocol hung partway through downloading `model.safetensors`. Disabled with `HF_HUB_DISABLE_XET=1`. Locked into the runbook env.

### 4. Zombie GPU processes after a crashed vLLM

When vLLM dies mid-init the engine subprocess can outlive the parent and pin GPU memory. Caused a 298 MB OOM on retry. Fix: `nvidia-smi --query-compute-apps=pid` + kill. Added to `stop.sh` and documented in README troubleshooting.

## To make TurboQuant actually run, you need

**1. Upgrade vLLM to ≥ 0.7.x.** This is the gating dependency. Pin transformers explicitly to whatever vllm 0.7 wants, not latest.

```bash
uv pip install --python .venv/bin/python "vllm>=0.7,<0.8" "transformers<5"
```

Test that Qwen still serves on the 4050 — vLLM 0.7 changed the engine architecture and may want different memory tuning.

**2. Re-enable the LMCache connector.** Once on vLLM 0.7, set `ENABLE_LMCACHE=1` in `env.sh` and `start_vllm.sh` will pass `--kv-transfer-config` again.

**3. Write the TurboQuant serde plugin.** This is the actual research/engineering work. Outline:

  - Subclass LMCache's serde interface (`compress` and `decompress` methods on KV tensors)
  - Implement TurboQuant vector quantization (paper: Google Research 2024)
  - Register the plugin name in `lmcache.yaml`: `remote_serde: "turboquant"`
  - Plug-in entry point: `lmcache_serde.turboquant:TurboQuantSerde`

Realistic budget: 3-5 days of focused work + 1 day of tuning quality vs. bit-rate.

## Honest hackathon recommendation

For demo day, **don't fight the version pinning**. The flow that works today on free infra:

1. Use this laptop's vLLM as the demo runtime — exposed via Cloudflare tunnel
2. Treat "memory" as gzipped prompt + context bundle (Pivot 1 from earlier)
3. Mention TurboQuant as a v0.2 roadmap item with the architecture from `docs/03`
4. If you want a credibility boost, do **one** offline TurboQuant validation run on Colab T4 with Qwen 7B and paste the numbers in your README

This buys you a working demo with $0 cost, no GPU rental, and an honest narrative.

## Files in this folder

```
.venv/             # 6.3 GB, gitignored. Holds vllm 0.6.6 + lmcache 0.4.4.
logs/
  vllm.log         # current
  vllm.attempt*.log# previous boot attempts (kept for debugging)
  tunnel.log
.run/
  vllm.pid
  tunnel.pid
  tunnel.url       # current trycloudflare.com URL (rotates per restart)
```

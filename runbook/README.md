# runbook/ — local GPU runtime for AgentVault

This folder is **not in version control** (see root `.gitignore`). It contains everything needed to bring up a vLLM + LMCache endpoint on this laptop and expose it publicly via Cloudflare. Use it as the `VLLM_ENDPOINT` (and the future `WORKER_URL`) for the rest of the SWARM project.

## What runs

```
laptop:8000  ── vLLM (Qwen 2.5 1.5B-Instruct) ──┐
                + LMCache connector              │  → cloudflared quick tunnel
                  (TurboQuant slot-in point)    ─┘     → https://*.trycloudflare.com
```

## First-time setup

```bash
cd runbook
./install.sh        # ~10 min, ~5 GB download
```

## Daily / after-sleep workflow

The laptop suspending or rebooting kills both processes. Bring them back with:

```bash
./start.sh          # starts vllm + tunnel, prints the public URL
./status.sh         # any time, to see state
./test.sh           # confirm /v1/models works locally and through the tunnel
./stop.sh           # tear down
```

The Cloudflare quick-tunnel URL **rotates on every restart**. Read the new one from `./status.sh` or `cat .run/tunnel.url`, and update `VLLM_ENDPOINT` in your `.env` files.

## Why this folder exists

The TurboQuant story needs vLLM + LMCache running where you can iterate on the cache pipeline. RunPod's hosted endpoint is a black box (`/v1/chat/completions` only — no cache hooks). Running vLLM yourself on the 4050 puts you one serde plugin away from real TurboQuant compression.

## TurboQuant slot-in point

Once you write the TurboQuant serde plugin (see `docs/03_TURBOQUANT_WORKER.md`):

1. Install your plugin into `.venv` (e.g. `uv pip install -e ../worker`)
2. In `lmcache.yaml`, change `remote_serde: "naive"` → `remote_serde: "turboquant"`
3. In `lmcache.yaml`, set `remote_url: "lm://localhost:65432"` and stand up the remote store
4. `./stop.sh && ./start.sh`

LMCache will then route every KV cache transfer through your compress/decompress functions.

## Files

| File | Purpose |
|---|---|
| `install.sh`     | One-time install of uv, cloudflared, vllm, lmcache |
| `env.sh`         | Sourced by every script; sets paths, ports, model id |
| `lmcache.yaml`   | LMCache config — the TurboQuant slot-in point |
| `start.sh`       | Bring up vllm + tunnel |
| `start_vllm.sh`  | vllm only |
| `start_tunnel.sh`| cloudflared only |
| `stop.sh`        | Kill both |
| `status.sh`      | Show pids, GPU, endpoints |
| `test.sh`        | Smoke-test the local + public endpoints |
| `.venv/`         | Python deps (gitignored, ~5 GB) |
| `logs/`          | vllm + tunnel logs (gitignored) |
| `.run/`          | pidfiles + current tunnel URL (gitignored) |

## Troubleshooting

- **OOM on vLLM start.** Drop `MAX_MODEL_LEN=2048` in `env.sh`, or switch `MODEL_ID=Qwen/Qwen2.5-0.5B-Instruct`.
- **Tunnel URL is missing after start.** Look at `logs/tunnel.log` — Cloudflare's edge sometimes takes 30 s. Re-run `./start_tunnel.sh`.
- **Suspend/resume hung the GPU.** `sudo nvidia-smi --gpu-reset` (rarely needed); usually `./stop.sh && ./start.sh` is enough.
- **vLLM dies with CUDA mismatch.** Make sure the venv's torch version matches the system driver. `uv pip install --python .venv/bin/python torch --index-url https://download.pytorch.org/whl/cu121`.

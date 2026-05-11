#!/usr/bin/env bash
# Idempotent installer: uv, cloudflared, vLLM, LMCache. Safe to re-run.
set -euo pipefail

cd "$(dirname "$0")"

# uv
if ! command -v uv >/dev/null && [[ ! -x "$HOME/.local/bin/uv" ]]; then
  echo "[install] uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"

# cloudflared
if ! command -v cloudflared >/dev/null; then
  echo "[install] cloudflared"
  curl -sSL --max-time 60 -o /tmp/cloudflared \
    https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
  chmod +x /tmp/cloudflared
  mkdir -p "$HOME/.local/bin"
  mv /tmp/cloudflared "$HOME/.local/bin/cloudflared"
fi

# venv
if [[ ! -d .venv ]]; then
  echo "[install] python venv (3.12)"
  uv venv --python 3.12 .venv
fi
export VIRTUAL_ENV="$(pwd)/.venv"

# vLLM + LMCache + transformers (pinned to vllm-compatible 4.x — vllm 0.6.6 breaks on transformers 5)
echo "[install] vllm + lmcache (this can take 5-10 min on first run)"
uv pip install --python .venv/bin/python \
  "vllm==0.6.6.post1" \
  "lmcache>=0.2.0" \
  "transformers>=4.45,<5"

echo "[install] done. next:  ./start.sh"

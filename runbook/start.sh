#!/usr/bin/env bash
# One-command boot: vLLM (with LMCache) → Cloudflare tunnel.
# Use this every time the laptop wakes from sleep or reboots.
set -euo pipefail
cd "$(dirname "$0")"

./start_vllm.sh
./start_tunnel.sh
./status.sh

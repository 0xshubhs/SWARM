#!/usr/bin/env bash
# RunPod GPU box bootstrap for the worker. Run this on a fresh A10G pod.
set -euo pipefail

echo "→ Installing system deps"
apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates python3.12 python3-pip

echo "→ Installing uv"
curl -LsSf https://astral.sh/uv/install.sh | sh

echo "→ Syncing worker dependencies (GPU extras)"
cd /workspace/worker
uv sync --extra gpu

echo "✓ Worker ready. Start with: uv run uvicorn worker.main:app --host 0.0.0.0 --port 8001"

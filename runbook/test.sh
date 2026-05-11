#!/usr/bin/env bash
# Smoke test: hit /v1/models, run a chat completion, check LMCache logs.
set -euo pipefail

cd "$(dirname "$0")"
source ./env.sh

echo "=== /v1/models (local) ==="
curl -sf "http://127.0.0.1:$VLLM_PORT/v1/models" | head -c 400 ; echo

if [[ -f "$TUNNEL_URL_FILE" ]]; then
  url=$(cat "$TUNNEL_URL_FILE")
  echo
  echo "=== /v1/models (public via $url) ==="
  curl -sf "$url/v1/models" | head -c 400 ; echo
fi

echo
echo "=== chat completion ==="
curl -s "http://127.0.0.1:$VLLM_PORT/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"$MODEL_ID\",
    \"messages\": [{\"role\":\"user\",\"content\":\"Reply with exactly the word OK.\"}],
    \"max_tokens\": 8,
    \"temperature\": 0
  }" | head -c 500 ; echo

echo
echo "=== LMCache evidence (last 30 log lines mentioning lmcache) ==="
grep -i lmcache "$VLLM_LOG" | tail -30 || echo "(no lmcache mentions yet)"

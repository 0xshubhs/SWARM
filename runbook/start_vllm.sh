#!/usr/bin/env bash
# Boot vLLM with the LMCache connector enabled. Idempotent: if a vllm pid is
# already running, do nothing.
set -euo pipefail

cd "$(dirname "$0")"
source ./env.sh

if [[ -f "$VLLM_PIDFILE" ]] && kill -0 "$(cat "$VLLM_PIDFILE")" 2>/dev/null; then
  echo "[vllm] already running (pid $(cat "$VLLM_PIDFILE"))"
  exit 0
fi

if ! command -v vllm >/dev/null; then
  echo "[vllm] vllm not installed in $VIRTUAL_ENV — run ./install.sh first" >&2
  exit 1
fi

echo "[vllm] starting $MODEL_ID on port $VLLM_PORT (kv-cache-dtype=$KV_CACHE_DTYPE, max-model-len=$MAX_MODEL_LEN)"

# NOTE: vLLM 0.6.6 only supports PyNcclConnector / MooncakeConnector via
# --kv-transfer-config. LMCacheConnectorV1 requires vLLM >= 0.7 (V1 engine).
# We boot plain vLLM here; LMCache integration is gated on a vllm upgrade.
# See README.md "TurboQuant slot-in point" for the upgrade path.
EXTRA_ARGS=()
if [[ "${ENABLE_LMCACHE:-0}" == "1" ]]; then
  EXTRA_ARGS+=(--kv-transfer-config '{"kv_connector":"LMCacheConnectorV1","kv_role":"kv_both"}')
fi

nohup vllm serve "$MODEL_ID" \
  --port "$VLLM_PORT" \
  --max-model-len "$MAX_MODEL_LEN" \
  --kv-cache-dtype "$KV_CACHE_DTYPE" \
  --gpu-memory-utilization "$GPU_MEM_UTIL" \
  --enforce-eager \
  --disable-log-requests \
  --disable-frontend-multiprocessing \
  "${EXTRA_ARGS[@]}" \
  > "$VLLM_LOG" 2>&1 &

echo $! > "$VLLM_PIDFILE"
echo "[vllm] pid $(cat "$VLLM_PIDFILE") — tailing for readiness (Ctrl-C to detach)"

# Wait until /v1/models responds or the process dies
for i in $(seq 1 120); do
  if ! kill -0 "$(cat "$VLLM_PIDFILE")" 2>/dev/null; then
    echo "[vllm] process died — see $VLLM_LOG"
    exit 1
  fi
  if curl -sf "http://127.0.0.1:$VLLM_PORT/v1/models" >/dev/null 2>&1; then
    echo "[vllm] ready at http://127.0.0.1:$VLLM_PORT"
    exit 0
  fi
  sleep 2
done
echo "[vllm] timed out waiting for readiness — check $VLLM_LOG"
exit 1

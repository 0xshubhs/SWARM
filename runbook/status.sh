#!/usr/bin/env bash
# What's running, where to reach it, what the tunnel URL is.
set -euo pipefail

cd "$(dirname "$0")"
source ./env.sh

check() {
  local name="$1" pidfile="$2"
  if [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
    echo "  $name: ✓ running (pid $(cat "$pidfile"))"
  else
    echo "  $name: ✗ not running"
  fi
}

echo "Processes:"
check vllm   "$VLLM_PIDFILE"
check tunnel "$TUNNEL_PIDFILE"

echo
echo "Endpoints:"
echo "  local : http://127.0.0.1:$VLLM_PORT"
if [[ -f "$TUNNEL_URL_FILE" ]]; then
  echo "  public: $(cat "$TUNNEL_URL_FILE")"
else
  echo "  public: (no tunnel URL yet)"
fi

echo
echo "GPU:"
nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader 2>/dev/null \
  | sed 's/^/  /' || echo "  (nvidia-smi unavailable)"

echo
echo "Quick test:"
echo "  curl -sf http://127.0.0.1:$VLLM_PORT/v1/models | head -c 200"

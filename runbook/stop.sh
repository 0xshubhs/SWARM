#!/usr/bin/env bash
# Tear down vLLM and the tunnel. Safe to run repeatedly.
set -euo pipefail

cd "$(dirname "$0")"
source ./env.sh

stop_one() {
  local name="$1" pidfile="$2"
  if [[ -f "$pidfile" ]]; then
    local pid
    pid=$(cat "$pidfile")
    if kill -0 "$pid" 2>/dev/null; then
      echo "[$name] stopping pid $pid"
      kill "$pid" 2>/dev/null || true
      for _ in 1 2 3 4 5; do
        kill -0 "$pid" 2>/dev/null || break
        sleep 1
      done
      kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$pidfile"
  fi
}

stop_one tunnel "$TUNNEL_PIDFILE"
stop_one vllm   "$VLLM_PIDFILE"

# vllm sometimes leaves child workers behind
pkill -f "vllm serve" 2>/dev/null || true

# Zombie engine subprocesses can outlive the parent and pin GPU memory,
# causing OOM on the next boot. Clean them up.
if command -v nvidia-smi >/dev/null; then
  for pid in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null); do
    cmd=$(tr '\0' ' ' < /proc/$pid/cmdline 2>/dev/null)
    if [[ "$cmd" == *"$RUNBOOK_DIR/.venv"* ]] || [[ "$cmd" == *"vllm"* ]] || [[ "$cmd" == *"multiprocessing"* ]]; then
      echo "[stop] killing GPU zombie pid $pid"
      kill -9 "$pid" 2>/dev/null || true
    fi
  done
fi
echo "[stop] done"

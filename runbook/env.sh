# Source this file from any shell before running the other scripts.
# `source env.sh`
RUNBOOK_DIR="$( cd "$( dirname "${BASH_SOURCE[0]:-$0}" )" && pwd )"
export RUNBOOK_DIR
export PATH="$HOME/.local/bin:$RUNBOOK_DIR/.venv/bin:$PATH"
export VIRTUAL_ENV="$RUNBOOK_DIR/.venv"

# Model + serving config
export MODEL_ID="${MODEL_ID:-Qwen/Qwen2.5-0.5B-Instruct}"
export VLLM_PORT="${VLLM_PORT:-8000}"
export MAX_MODEL_LEN="${MAX_MODEL_LEN:-2048}"
export KV_CACHE_DTYPE="${KV_CACHE_DTYPE:-auto}"
export GPU_MEM_UTIL="${GPU_MEM_UTIL:-0.70}"

# LMCache (the connector that makes KV cache reachable for TurboQuant)
export LMCACHE_CONFIG_FILE="$RUNBOOK_DIR/lmcache.yaml"
export LMCACHE_USE_EXPERIMENTAL=True

# HF cache lives outside the runbook so it survives folder wipes
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"
# HF's Xet protocol stalled on this network during testing — use the legacy downloader.
export HF_HUB_DISABLE_XET=1

# Files
export VLLM_LOG="$RUNBOOK_DIR/logs/vllm.log"
export TUNNEL_LOG="$RUNBOOK_DIR/logs/tunnel.log"
export VLLM_PIDFILE="$RUNBOOK_DIR/.run/vllm.pid"
export TUNNEL_PIDFILE="$RUNBOOK_DIR/.run/tunnel.pid"
export TUNNEL_URL_FILE="$RUNBOOK_DIR/.run/tunnel.url"

mkdir -p "$RUNBOOK_DIR/logs" "$RUNBOOK_DIR/.run"

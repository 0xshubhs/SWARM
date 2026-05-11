#!/usr/bin/env bash
# Cloudflare quick tunnel — no login, no domain. The trycloudflare.com URL
# rotates on every restart, so this script captures it and writes it to a
# file the rest of the system can read.
set -euo pipefail

cd "$(dirname "$0")"
source ./env.sh

if [[ -f "$TUNNEL_PIDFILE" ]] && kill -0 "$(cat "$TUNNEL_PIDFILE")" 2>/dev/null; then
  echo "[tunnel] already running (pid $(cat "$TUNNEL_PIDFILE"))"
  [[ -f "$TUNNEL_URL_FILE" ]] && echo "[tunnel] url: $(cat "$TUNNEL_URL_FILE")"
  exit 0
fi

if ! command -v cloudflared >/dev/null; then
  echo "[tunnel] cloudflared not installed — run ./install.sh first" >&2
  exit 1
fi

echo "[tunnel] starting cloudflared quick tunnel → http://localhost:$VLLM_PORT"
nohup cloudflared tunnel --no-autoupdate --url "http://localhost:$VLLM_PORT" \
  > "$TUNNEL_LOG" 2>&1 &
echo $! > "$TUNNEL_PIDFILE"

# cloudflared prints the URL to its log within ~10 seconds
for i in $(seq 1 30); do
  url=$(grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" | head -1 || true)
  if [[ -n "$url" ]]; then
    echo "$url" > "$TUNNEL_URL_FILE"
    echo "[tunnel] ready: $url"
    echo "[tunnel] (URL also saved to $TUNNEL_URL_FILE)"
    exit 0
  fi
  sleep 1
done
echo "[tunnel] timed out — see $TUNNEL_LOG"
exit 1

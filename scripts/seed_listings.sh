#!/usr/bin/env bash
# Seed the marketplace with three demo listings used by the buyer-agent
# demo flow (anchor expert / defi specialist / dao governance).
#
# Backend must be running at $API_BASE_URL with a Postgres + Redis attached.
# This shell-only path uses curl to hit /v1/upload/init and /v1/upload/blob;
# the on-chain finalize step is left to the seller's wallet.
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
SELLER_PUBKEY="${SELLER_PUBKEY:-So11111111111111111111111111111111111111112}"

echo "→ Seeding demo listings against $API_BASE_URL"

post_listing() {
  local title="$1"
  local tags="$2"
  local price="$3"
  local sandbox="$4"
  local payload_size="${5:-1048576}"

  echo "  - $title (tags=$tags, $price USDC)"

  local tmp
  tmp=$(mktemp)
  head -c "$payload_size" /dev/urandom > "$tmp"

  local init
  init=$(curl -fsS -X POST "$API_BASE_URL/v1/upload/init" \
      -H "Content-Type: application/json" \
      -d "{\"seller_pubkey\":\"$SELLER_PUBKEY\",\"expected_size_bytes\":$payload_size}")
  local upload_id
  upload_id=$(echo "$init" | python3 -c "import json,sys; print(json.load(sys.stdin)['upload_id'])")
  echo "    upload_id: $upload_id"

  curl -fsS -X POST "$API_BASE_URL/v1/upload/blob/$upload_id" \
      -F "blob=@$tmp" >/dev/null

  rm -f "$tmp"

  curl -fsS -X POST "$API_BASE_URL/v1/upload/finalize" \
      -H "Content-Type: application/json" \
      -d "$(python3 -c "import json,sys; print(json.dumps({
        'upload_id': '$upload_id',
        'seller_pubkey': '$SELLER_PUBKEY',
        'title': '$title',
        'tags': '$tags'.split(','),
        'price_usdc': int($price * 1_000_000),
        'sandbox_price_usdc': int($sandbox * 1_000_000),
      }))")" >/dev/null
}

post_listing "Anchor Framework Senior Dev"      "anchor,solana,rust,pda"        25  0.05
post_listing "DeFi Slippage Specialist (Drift)" "drift,jupiter,defi,trading"    50  0.10
post_listing "Solana DAO Governance Expert"     "dao,governance,realms,voting"  15  0.05

echo "✓ Seeded. List with: curl $API_BASE_URL/v1/listings"

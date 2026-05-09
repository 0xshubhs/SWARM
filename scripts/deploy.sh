#!/usr/bin/env bash
# Deploy the Anchor program to the configured cluster, then sync the program ID
# into root .env and the generated IDL into shared/types.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "→ Building program..."
anchor build

echo "→ Deploying to $(solana config get | awk '/RPC URL/ {print $3}')"
anchor deploy

PROGRAM_ID=$(solana address -k target/deploy/agentvault-keypair.json)
echo "→ Program ID: $PROGRAM_ID"

if [ -f .env ]; then
  if grep -q '^AGENTVAULT_PROGRAM_ID=' .env; then
    sed -i.bak "s|^AGENTVAULT_PROGRAM_ID=.*|AGENTVAULT_PROGRAM_ID=$PROGRAM_ID|" .env
  else
    echo "AGENTVAULT_PROGRAM_ID=$PROGRAM_ID" >> .env
  fi
  echo "→ Updated .env"
fi

if [ -f target/idl/agentvault.json ]; then
  cp target/idl/agentvault.json shared/types/src/agentvault.idl.json
  echo "→ IDL copied to shared/types/src/agentvault.idl.json"
fi

echo "✓ Done."

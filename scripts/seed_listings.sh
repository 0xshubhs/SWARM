#!/usr/bin/env bash
# Seed the marketplace with demo listings. Requires backend + worker running.
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"

echo "→ Seeding demo listings against $API_BASE_URL"
echo "  TODO: implement (see docs/04_FRONTEND.md and docs/02_BACKEND.md for the upload flow)"

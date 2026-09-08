#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if command -v npm >/dev/null 2>&1; then
  npm run searxng:down
else
  echo "npm is not available; cannot stop Docker Compose services through project scripts."
fi

echo "If npm run dev is still open in another terminal, stop it with Ctrl+C."

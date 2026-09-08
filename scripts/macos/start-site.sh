#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

need_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1"
    exit 1
  fi
}

need_command node
need_command npm
need_command python3
need_command docker

if ! docker info >/dev/null 2>&1; then
  echo "Docker is installed, but Docker Desktop is not running."
  echo "Start Docker Desktop and run this script again."
  exit 1
fi

if [ ! -d "node_modules" ]; then
  npm install
fi

if [ ! -d "frontend/node_modules" ]; then
  npm --prefix frontend install
fi

if [ ! -x "backend/.venv/bin/python" ]; then
  python3 -m venv backend/.venv
fi

backend/.venv/bin/python -m pip install --upgrade pip
backend/.venv/bin/python -m pip install -e "backend[dev]"

npm run searxng:up
npm run searxng:check

echo "Starting Site Audit..."
echo "Frontend: http://127.0.0.1:${FRONTEND_PORT:-5173}"
echo "Stop with Ctrl+C, or run scripts/macos/stop-site.sh from another terminal."

npm run dev -- --with-worker --worker-autoscale=auto

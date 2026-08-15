#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PORT:-4171}"
HOST="${HOST:-0.0.0.0}"
LOG_FILE="${ROOT_DIR}/backend/reference-api.log"

cd "$ROOT_DIR"
mkdir -p "$(dirname "$LOG_FILE")"

nohup node backend/src/reference-search.mjs > "$LOG_FILE" 2>&1 &

echo "Reference API started in background."
echo "URL: http://${HOST}:${PORT}/health"
echo "Log: $LOG_FILE"

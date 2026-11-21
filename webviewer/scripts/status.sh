#!/usr/bin/env bash
# Report whether the background viewer server is running.
set -euo pipefail
WEBVIEWER_DIR="${WEBVIEWER_DIR:-$(git rev-parse --show-toplevel)/webviewer}"
source "$WEBVIEWER_DIR/scripts/paths.sh" || exit 1
PORT="${PORT:-4517}"
HOST="${HOST:-127.0.0.1}"
PID_FILE=".server.pid"

if [[ -f "$PID_FILE" ]] && [[ -d "/proc/$(cat "$PID_FILE")" ]]; then
  echo "running: pid $(cat "$PID_FILE"), http://${HOST}:${PORT}/"
  curl -fsS "http://${HOST}:${PORT}/api/health"
  echo
else
  echo "not running"
  exit 1
fi

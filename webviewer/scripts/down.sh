#!/usr/bin/env bash
# Stop the background viewer server started by up.sh.
set -euo pipefail
WEBVIEWER_DIR="${WEBVIEWER_DIR:-$(git rev-parse --show-toplevel)/webviewer}"
source "$WEBVIEWER_DIR/scripts/paths.sh" || exit 1
PID_FILE=".server.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo "not running (no pid file)"
  exit 0
fi
PID="$(cat "$PID_FILE")"
if [[ -n "$PID" && -d "/proc/$PID" ]]; then
  kill "$PID"
  echo "stopped: pid $PID"
else
  echo "not running (stale pid $PID)"
fi
rm -f "$PID_FILE"

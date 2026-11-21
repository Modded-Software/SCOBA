#!/usr/bin/env bash
# Start the viewer server in the background and wait until it answers.
set -uo pipefail
WEBVIEWER_DIR="${WEBVIEWER_DIR:-$(git rev-parse --show-toplevel)/webviewer}"
source "$WEBVIEWER_DIR/scripts/paths.sh" || exit 1
PORT="${PORT:-4517}"
HOST="${HOST:-127.0.0.1}"
URL="http://${HOST}:${PORT}"
PID_FILE=".server.pid"
LOG_FILE="server.log"

alive() { [[ -n "$1" && -d "/proc/$1" ]]; }

if [[ -f "$PID_FILE" ]] && alive "$(cat "$PID_FILE")"; then
  echo "already running: pid $(cat "$PID_FILE"), ${URL}/"
  exit 0
fi
if health="$(curl -sS "${URL}/api/health" 2>&1)"; then
  echo "ERROR: port ${PORT} is already served by another process: ${health}" >&2
  exit 1
fi

bash scripts/ref-setup.sh || exit 1
node tools/build-renderer.mjs || exit 1
bash scripts/catalog.sh --if-missing || exit 1

PORT="$PORT" HOST="$HOST" setsid nohup node server.mjs > "$LOG_FILE" 2>&1 &
PID="$!"
echo "$PID" > "$PID_FILE"

last=""
for _ in $(seq 1 100); do
  if last="$(curl -sS "${URL}/api/health" 2>&1)"; then
    echo "running: pid ${PID}, ${URL}/  ${last}"
    exit 0
  fi
  if ! alive "$PID"; then
    echo "ERROR: server exited. Log:" >&2
    cat "$LOG_FILE" >&2
    rm -f "$PID_FILE"
    exit 1
  fi
  sleep 0.2
done
echo "ERROR: server did not answer at ${URL}: ${last}. See ${LOG_FILE}" >&2
exit 1

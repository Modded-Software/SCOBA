#!/usr/bin/env bash
# Read the state of the viewer dev service. Read only: start, stop and
# restart go through Ansible (make viewer-start, viewer-stop, viewer-restart).
# Usage: scripts/service.sh status|logs
set -uo pipefail
UNIT="${VIEWER_UNIT:-sc2-viewer-dev}.service"
URL="http://${HOST:-127.0.0.1}:${PORT:-4517}"

if [[ -z "$(systemctl --user list-unit-files "$UNIT" --no-legend)" ]]; then
  echo "ERROR: $UNIT is not installed. Run: make viewer-provision" >&2
  exit 1
fi

case "${1:-}" in
  status)
    systemctl --user status "$UNIT" --no-pager --lines 0
    curl -fsS --max-time 5 "$URL/api/health" && echo
    ;;
  logs) journalctl --user -u "$UNIT" -n "${LINES:-100}" --no-pager ;;
  *)
    echo "usage: scripts/service.sh status|logs" >&2
    exit 2
    ;;
esac

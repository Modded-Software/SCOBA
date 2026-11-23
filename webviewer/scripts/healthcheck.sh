#!/usr/bin/env bash
# Liveness check for the viewer dev service (run by its systemd timer).
# The server must answer /api/health. When it does not, twice 5 s apart,
# the service is restarted. A server younger than GRACE seconds is still
# building and is left alone. Every outcome is logged; exit 1 on a restart.
set -uo pipefail
UNIT="${VIEWER_UNIT:-sc2-viewer-dev}.service"
URL="http://${HOST:-127.0.0.1}:${PORT:-4517}/api/health"
GRACE="${VIEWER_GRACE:-180}"

state="$(systemctl --user is-active "$UNIT")"
if [[ "$state" != active ]]; then
  echo "$UNIT is $state; systemd restarts it (Restart=always)"
  exit 0
fi
pid="$(systemctl --user show "$UNIT" -p MainPID --value)"
age="$(ps -o etimes= -p "$pid" | tr -d ' ')"
if [[ -z "$age" ]]; then
  echo "$UNIT has no live main process (pid $pid)"
elif (( age < GRACE )); then
  echo "$UNIT started ${age}s ago; still in its start grace (${GRACE}s)"
  exit 0
fi
for try in 1 2; do
  if answer="$(curl -fsS --max-time 10 "$URL" 2>&1)"; then
    echo "ok: $answer"
    exit 0
  fi
  echo "try $try: no answer from $URL: $answer"
  sleep 5
done
echo "restarting $UNIT"
systemctl --user restart "$UNIT"
exit 1

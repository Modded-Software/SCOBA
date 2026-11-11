#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
if [ ! -f "$ROOT_DIR/scripts/sc2-check-logs" ]; then
    ROOT_DIR="$(pwd)"
fi
if [ "${SC2_PLAYTEST_ACTIVE:-}" != "1" ]; then
    exec bash "$ROOT_DIR/scripts/playtest.sh" launch-check
fi
UV_BIN="${UV_BIN:-uv}"
if [ "${UV_BIN#/}" = "$UV_BIN" ]; then
    UV_BIN="$(command -v "$UV_BIN")" || {
        printf 'ERROR: uv not found\n' >&2
        exit 1
    }
fi
[ -x "$UV_BIN" ] || {
    printf 'ERROR: uv not executable: %s\n' "$UV_BIN" >&2
    exit 1
}
LOG_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/scoba"
mkdir -p "$LOG_DIR"

export SC2_BANK_SINCE="$(date +%s)"
export SC2_LOG_SINCE="$SC2_BANK_SINCE"
if [ -z "${SC2_MAP_SOURCE:-}" ] && [ -d "$ROOT_DIR/out/SCOBA256.SC2Map" ]; then
    export SC2_MAP_SOURCE="$ROOT_DIR/out/SCOBA256.SC2Map"
fi
nohup "$ROOT_DIR/scripts/launch-scoba.sh" >>"$LOG_DIR/launcher.log" 2>&1 &
sleep "${SC2_LOAD_DELAY:-18}"
if [ "${SC2_AUTO_START:-1}" = "1" ] && [ -f "$ROOT_DIR/scripts/input_inject.py" ]; then
    if ! "$UV_BIN" run python "$ROOT_DIR/scripts/input_inject.py" auto >>"$LOG_DIR/launcher.log" 2>&1; then
        printf 'warning: auto-start input failed\n' >>"$LOG_DIR/launcher.log"
    fi
    sleep 5
    if ! "$UV_BIN" run python "$ROOT_DIR/scripts/input_inject.py" auto >>"$LOG_DIR/launcher.log" 2>&1; then
        printf 'warning: auto-start input failed\n' >>"$LOG_DIR/launcher.log"
    fi
fi
sleep "${SC2_CHECK_DELAY:-25}"
exec "$ROOT_DIR/scripts/sc2-check-logs" --require-stamp
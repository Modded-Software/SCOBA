#!/usr/bin/env bash
set -euo pipefail

SCRIPT_PATH="$(readlink -f -- "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd -- "$(dirname -- "$SCRIPT_PATH")" && pwd)"
if [ -n "${SC2_PROJECT_ROOT:-}" ]; then
    ROOT_DIR="$SC2_PROJECT_ROOT"
elif [ -f "$SCRIPT_DIR/../pyproject.toml" ]; then
    ROOT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
else
    ROOT_DIR="$PWD"
fi

LOG_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/scoba"
mkdir -p "$LOG_DIR"
exec >>"$LOG_DIR/launcher.log" 2>&1

MAP_NAME="SCOBA.SC2Map"
MAP_SOURCE="${SC2_MAP_SOURCE:-$ROOT_DIR/src/$MAP_NAME}"
if [ ! -e "$MAP_SOURCE" ]; then
    MAP_SOURCE="$ROOT_DIR/$MAP_NAME"
fi

STEAM_ROOT="${STEAM_ROOT:-$HOME/.var/app/com.valvesoftware.Steam/data/Steam}"
BNET_PREFIX="${BNET_PREFIX:-$HOME/Games/battlenet-prefix}"
SC2_DIR="${SC2_DIR:-$BNET_PREFIX/pfx/drive_c/Program Files (x86)/StarCraft II}"
SC2_EXE="$SC2_DIR/StarCraft II.exe"
SC2_SWITCHER="$SC2_DIR/Support64/SC2Switcher_x64.exe"
MAP_DIR="$SC2_DIR/Maps"
MAP_TARGET="$MAP_DIR/$MAP_NAME"
SC2_LAUNCH_ARGS=(-run "$MAP_NAME" -displaymode "${SC2_DISPLAYMODE:-0}" -preload 1 -NoUserCheats -reloadcheck)

log() {
    printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

fail() {
    log "ERROR: $*" >&2
    exit 1
}

[ -e "$MAP_SOURCE" ] || fail "map not found: $MAP_SOURCE"
[ -f "$SC2_EXE" ] || fail "StarCraft II not found: $SC2_EXE"

GE_PROTON_DIR=""
for candidate in "$STEAM_ROOT"/compatibilitytools.d/GE-Proton*/; do
    if [ -x "$candidate/proton" ]; then
        GE_PROTON_DIR="${candidate%/}"
        break
    fi
done
[ -n "$GE_PROTON_DIR" ] || fail "GE-Proton not found under $STEAM_ROOT/compatibilitytools.d"

log "source: $MAP_SOURCE"
mkdir -p "$MAP_DIR"
python3 "$ROOT_DIR/scripts/stage-map.py" "$MAP_SOURCE" "$MAP_TARGET"

export STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_ROOT"
export STEAM_COMPAT_DATA_PATH="$BNET_PREFIX"
export WINE_SIMULATE_WRITECOPY=1
export PROTON_USE_NTSYNC=1

if [ "${DRY_RUN:-0}" = "1" ]; then
    log "map: $MAP_TARGET"
    log "proton: $GE_PROTON_DIR/proton"
    if [ -f "$SC2_SWITCHER" ]; then
        log "command: $SC2_SWITCHER ${SC2_LAUNCH_ARGS[*]}"
    else
        log "command: $SC2_EXE ${SC2_LAUNCH_ARGS[*]}"
    fi
    exit 0
fi

log "launching $MAP_NAME"
cd "$SC2_DIR"

if [ -f "$SC2_SWITCHER" ]; then
    exec "$GE_PROTON_DIR/proton" run "$SC2_SWITCHER" "${SC2_LAUNCH_ARGS[@]}"
fi

exec "$GE_PROTON_DIR/proton" run "$SC2_EXE" "${SC2_LAUNCH_ARGS[@]}"

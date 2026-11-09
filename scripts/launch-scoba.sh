#!/usr/bin/env bash
set -euo pipefail

resolve_root() {
    local cand
    for cand in \
        "${SC2_PROJECT_ROOT:-}" \
        "$(cd -- "$(dirname -- "${0:-.}")/.." && pwd)" \
        "$PWD" \
        "$(cd -- "$(dirname -- "${BASH_SOURCE[0]:-.}")/.." && pwd)"; do
        if [ -n "$cand" ] && [ -f "$cand/scripts/stage-map.py" ]; then
            printf '%s\n' "$cand"
            return 0
        fi
    done
    return 1
}
ROOT_DIR="$(resolve_root)" || { printf 'ERROR: cannot locate project root\n' >&2; exit 1; }

LOG_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/scoba"
mkdir -p "$LOG_DIR"
exec >>"$LOG_DIR/launcher.log" 2>&1

MAP_NAME="SCOBA.SC2Map"
MAP_SOURCE="${SC2_MAP_SOURCE:-$ROOT_DIR/out/SCOBA256.SC2Map}"
if [ ! -e "$MAP_SOURCE" ]; then
    MAP_SOURCE="$ROOT_DIR/src/$MAP_NAME"
fi
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
CACHE_DIR="${SC2_CACHE_DIR:-$BNET_PREFIX/pfx/drive_c/ProgramData/Blizzard Entertainment/StarCraft II/Maps/Cache/$MAP_NAME}"
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
if [ "${SC2_KEEP_RUNNING:-0}" != "1" ]; then
    uv run python "$ROOT_DIR/scripts/kill-sc2.py"
fi
if [ -e "$CACHE_DIR" ]; then
    log "clearing cache: $CACHE_DIR"
    rm -rf "$CACHE_DIR"
fi
mkdir -p "$MAP_DIR"
uv run python "$ROOT_DIR/scripts/stage-map.py" "$MAP_SOURCE" "$MAP_TARGET"
if [ -d "$MAP_SOURCE" ]; then
    diff -r "$MAP_SOURCE" "$MAP_TARGET" >"$LOG_DIR/stage-check.log" || fail "staged map does not match source"
elif ! cmp -s "$MAP_SOURCE" "$MAP_TARGET"; then
    fail "staged map does not match source"
fi
if [ -f "$MAP_TARGET/BuildStamp.txt" ]; then
    log "stamp: $(cat "$MAP_TARGET/BuildStamp.txt")"
fi

export STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_ROOT"
export STEAM_COMPAT_DATA_PATH="$BNET_PREFIX"
export WINE_SIMULATE_WRITECOPY=1
export PROTON_USE_NTSYNC=1
export SC2_WINDOW_WIDTH="${SC2_WINDOW_WIDTH:-1920}"
export SC2_WINDOW_HEIGHT="${SC2_WINDOW_HEIGHT:-1080}"

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

if ! uv run python "$ROOT_DIR/scripts/sc2-configure-window.py"; then
    log "warning: could not configure window size"
fi

if [ -f "$SC2_SWITCHER" ]; then
    exec "$GE_PROTON_DIR/proton" run "$SC2_SWITCHER" "${SC2_LAUNCH_ARGS[@]}"
fi

exec "$GE_PROTON_DIR/proton" run "$SC2_EXE" "${SC2_LAUNCH_ARGS[@]}"

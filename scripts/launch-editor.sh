#!/usr/bin/env bash
# Open the unpacked map folder in the StarCraft II editor.
# No build, no staging, and no running StarCraft II process is stopped.
set -euo pipefail

resolve_root() {
    local cand
    for cand in \
        "${SC2_PROJECT_ROOT:-}" \
        "$(cd -- "$(dirname -- "${0:-.}")/.." && pwd)" \
        "$PWD" \
        "$(cd -- "$(dirname -- "${BASH_SOURCE[0]:-.}")/.." && pwd)"; do
        if [ -n "$cand" ] && [ -f "$cand/scripts/launch-editor.sh" ]; then
            printf '%s\n' "$cand"
            return 0
        fi
    done
    return 1
}
ROOT_DIR="$(resolve_root)" || { printf 'ERROR: cannot locate project root\n' >&2; exit 1; }
# shellcheck source=paths.sh
source "$ROOT_DIR/scripts/paths.sh" || exit 1

if [ "${DRY_RUN:-0}" != "1" ]; then
    LOG_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/scoba"
    mkdir -p "$LOG_DIR"
    exec >>"$LOG_DIR/editor.log" 2>&1
fi

log() {
    printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

fail() {
    log "ERROR: $*" >&2
    exit 1
}

# The map the editor opens. The default is the built working map: the 256x256
# component folder with the generated models. src/ is the 128x128 source and
# looks like the original map in the editor.
# SC2_OUT is replaced by every build: editor saves there do not survive one.
MAP_SOURCE="${SC2_EDITOR_MAP:-$SC2_BUILT_MAP}"
[ -d "$MAP_SOURCE" ] || fail "unpacked map folder not found, run scripts/playtest.sh build: $MAP_SOURCE"
MAP_SOURCE="$(cd -- "$MAP_SOURCE" && pwd)"
COMPONENTS="$MAP_SOURCE/ComponentList.SC2Components"
[ -f "$COMPONENTS" ] || fail "not an unpacked map, no component list: $COMPONENTS"

STEAM_ROOT="${STEAM_ROOT:-$HOME/.var/app/com.valvesoftware.Steam/data/Steam}"
SC2_DIR="$SC2_INSTALL"
EDITOR_EXE="$SC2_DIR/Support64/SC2Editor_x64.exe"
[ -f "$EDITOR_EXE" ] || fail "StarCraft II editor not found: $EDITOR_EXE"

# The editor sees the Linux filesystem through the Z: drive of the prefix,
# beside its drive C.
Z_DRIVE="$(dirname -- "$BNET_PREFIX/$SC2_WINE_DRIVE")/dosdevices/z:"
[ -L "$Z_DRIVE" ] || fail "prefix has no Z: drive: $Z_DRIVE"
[ "$(readlink "$Z_DRIVE")" = "/" ] || fail "prefix Z: drive is not /: $(readlink "$Z_DRIVE")"
WIN_PATH="Z:${COMPONENTS//\//\\}"

GE_PROTON_DIR=""
for candidate in "$STEAM_ROOT"/compatibilitytools.d/GE-Proton*/; do
    if [ -x "$candidate/proton" ]; then
        GE_PROTON_DIR="${candidate%/}"
        break
    fi
done
[ -n "$GE_PROTON_DIR" ] || fail "GE-Proton not found under $STEAM_ROOT/compatibilitytools.d"

# The command the editor registers for ComponentList.SC2Components files.
EDITOR_ARGS=(-loadfile "$WIN_PATH" -product SC2)

export STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_ROOT"
export STEAM_COMPAT_DATA_PATH="$BNET_PREFIX"
export WINE_SIMULATE_WRITECOPY=1
export PROTON_USE_NTSYNC=1

log "map: $MAP_SOURCE"
log "proton: $GE_PROTON_DIR/proton"
log "command: $EDITOR_EXE ${EDITOR_ARGS[*]}"
if [ "${DRY_RUN:-0}" = "1" ]; then
    exit 0
fi

cd "$SC2_DIR"
exec "$GE_PROTON_DIR/proton" run "$EDITOR_EXE" "${EDITOR_ARGS[@]}"

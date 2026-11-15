#!/usr/bin/env bash
set -euo pipefail

resolve_root() {
    local cand
    for cand in \
        "${SC2_PROJECT_ROOT:-}" \
        "$(cd -- "$(dirname -- "${0:-.}")/.." && pwd)" \
        "$PWD" \
        "$(cd -- "$(dirname -- "${BASH_SOURCE[0]:-.}")/.." && pwd)"; do
        if [ -n "$cand" ] && [ -f "$cand/assets/scoba.png" ]; then
            printf '%s\n' "$cand"
            return 0
        fi
    done
    return 1
}
ROOT_DIR="$(resolve_root)" || { printf 'ERROR: cannot locate project root\n' >&2; exit 1; }

APP_ID="scoba.desktop"
APP_NAME="SCOBA"
ICON_NAME="scoba"
ICON_SOURCE="$ROOT_DIR/assets/scoba.png"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
APPS_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$APPS_DIR/$APP_ID"

log() {
    printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

fail() {
    log "ERROR: $*" >&2
    exit 1
}

[ -f "$ICON_SOURCE" ] || fail "icon not found: $ICON_SOURCE"
[ -x "$ROOT_DIR/scripts/playtest.sh" ] || fail "entrypoint not executable: $ROOT_DIR/scripts/playtest.sh"
if ! UV_BIN="$(command -v uv)"; then
    fail "uv not found"
fi
[ -x "$UV_BIN" ] || fail "uv not executable: $UV_BIN"

mkdir -p "$ICON_DIR" "$APPS_DIR"
cp -f "$ICON_SOURCE" "$ICON_DIR/$ICON_NAME.png"

# The launch command. $1 is the SC2_HD_TEXTURES value of the build; empty
# leaves it unset, so the build picks its default (Upscale 4x, or the
# built-in textures without a cache).
launch_exec() {
    local textures=""
    [ -z "$1" ] || textures="SC2_HD_TEXTURES=\"$1\" "
    printf 'env UV_BIN="%s" SC2_PROJECT_ROOT="%s" %sSC2_WINDOW_WIDTH="1920" SC2_WINDOW_HEIGHT="1080" bash "%s/scripts/playtest.sh" launch' \
        "$UV_BIN" "$ROOT_DIR" "$textures" "$ROOT_DIR"
}

# Right-click entries of the dock icon: action id, name, SC2_HD_TEXTURES value.
ACTIONS=(
    "original|Original Textures|off"
    "upscaled|Upscaled Textures|upscale"
    "hd|HD Textures|generative"
)

action_ids=""
action_names=""
for action in "${ACTIONS[@]}"; do
    action_ids="$action_ids${action%%|*};"
    IFS='|' read -r _id action_name _textures <<<"$action"
    action_names="${action_names:+$action_names, }$action_name"
done

# GNOME Shell keeps its cached app object while the name, comment, command,
# icon, and file stay the same (app_is_stale in shell-app-system.c). It does
# not compare Actions, so a change of the menu alone never shows. The
# comment names the menu entries, so a new menu makes the cache stale.
COMMENT="Launch the SCOBA StarCraft II custom map. Right-click: $action_names"

{
    printf '[Desktop Entry]\nName=%s\nComment=%s\nExec=%s\nPath=%s\nIcon=%s\nTerminal=false\nType=Application\nCategories=Game;StrategyGame;\nStartupNotify=true\nStartupWMClass=StarCraft II.exe\nActions=%s\n' \
        "$APP_NAME" \
        "$COMMENT" \
        "$(launch_exec "")" \
        "$ROOT_DIR" \
        "$ICON_NAME" \
        "$action_ids"
    for action in "${ACTIONS[@]}"; do
        IFS='|' read -r action_id action_name textures <<<"$action"
        printf '\n[Desktop Action %s]\nName=%s\nExec=%s\n' "$action_id" "$action_name" "$(launch_exec "$textures")"
    done
} > "$DESKTOP_FILE"

chmod +x "$DESKTOP_FILE"
if command -v desktop-file-validate; then
    if ! output="$(desktop-file-validate "$DESKTOP_FILE" 2>&1)"; then
        fail "invalid desktop entry: $output"
    fi
fi
if ! output="$(update-desktop-database "$APPS_DIR" 2>&1)"; then
    log "warning: update-desktop-database: $output"
fi
if ! output="$(gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>&1)"; then
    log "warning: gtk-update-icon-cache: $output"
fi

favorites="$(gsettings get org.gnome.shell favorite-apps)"
if [[ "$favorites" != *"'$APP_ID'"* ]]; then
    if [[ "$favorites" == "@as []" || "$favorites" == "[]" ]]; then
        favorites="['$APP_ID']"
    else
        favorites="${favorites%]}, '$APP_ID']"
    fi
    gsettings set org.gnome.shell favorite-apps "$favorites"
fi

log "installed $DESKTOP_FILE"
log "installed $ICON_DIR/$ICON_NAME.png"
log "added $APP_ID to GNOME favorites"

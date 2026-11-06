#!/usr/bin/env bash
set -euo pipefail

SCRIPT_PATH="$(readlink -f -- "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd -- "$(dirname -- "$SCRIPT_PATH")" && pwd)"
ROOT_DIR="${SC2_PROJECT_ROOT:-$(cd -- "$SCRIPT_DIR/.." && pwd)}"

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
[ -x "$ROOT_DIR/scripts/launch-scoba.sh" ] || fail "launcher not executable: $ROOT_DIR/scripts/launch-scoba.sh"

mkdir -p "$ICON_DIR" "$APPS_DIR"
cp -f "$ICON_SOURCE" "$ICON_DIR/$ICON_NAME.png"

printf '[Desktop Entry]\nName=%s\nComment=%s\nExec=env SC2_PROJECT_ROOT="%s" SC2_MAP_SOURCE="%s/out/SCOBA256.SC2Map" bash "%s/scripts/launch-scoba.sh"\nIcon=%s\nTerminal=false\nType=Application\nCategories=Game;StrategyGame;\nStartupNotify=true\nStartupWMClass=StarCraft II.exe\n' \
    "$APP_NAME" \
    "Launch the SCOBA StarCraft II custom map" \
    "$ROOT_DIR" \
    "$ROOT_DIR" \
    "$ROOT_DIR" \
    "$ICON_NAME" > "$DESKTOP_FILE"

chmod +x "$DESKTOP_FILE"
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

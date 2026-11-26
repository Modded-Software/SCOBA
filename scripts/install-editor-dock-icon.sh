#!/usr/bin/env bash
# Install a GNOME dock icon that opens the unpacked map in the StarCraft II editor.
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

APP_ID="scoba-editor.desktop"
APP_NAME="SCOBA Editor"
ICON_NAME="scoba-editor"
ICON_SIZE=256
ICON_DIR="$HOME/.local/share/icons/hicolor/${ICON_SIZE}x${ICON_SIZE}/apps"
APPS_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$APPS_DIR/$APP_ID"
LAUNCHER="$ROOT_DIR/scripts/launch-editor.sh"
# The launch dialog (REQ-LAUNCH-DIALOG) runs the launcher and shows its log.
DIALOG="$ROOT_DIR/scripts/launch-dialog.sh"

# shellcheck source=paths.sh
source "$ROOT_DIR/scripts/paths.sh" || exit 1
# The icon comes from the installed editor. It is not stored in the repository.
ICON_EXE="$SC2_INSTALL/StarCraft II Editor_x64.exe"
ICON_GROUP=101

log() {
    printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

fail() {
    log "ERROR: $*" >&2
    exit 1
}

[ -f "$LAUNCHER" ] || fail "launcher not found: $LAUNCHER"
[ -f "$DIALOG" ] || fail "launch dialog not found: $DIALOG"
[ -f "$ICON_EXE" ] || fail "StarCraft II editor not found: $ICON_EXE"
for tool in wrestool icotool gsettings; do
    if ! tool_path="$(command -v "$tool")"; then
        fail "$tool not found"
    fi
    [ -x "$tool_path" ] || fail "$tool not executable: $tool_path"
done

# Fail here, not on the first click, when the launcher cannot resolve its paths.
if ! output="$(DRY_RUN=1 SC2_PROJECT_ROOT="$ROOT_DIR" bash "$LAUNCHER" 2>&1)"; then
    fail "launcher dry run failed: $output"
fi
if ! output="$(SC2_PROJECT_ROOT="$ROOT_DIR" bash "$DIALOG" --check 2>&1)"; then
    fail "launch dialog cannot start: $output"
fi

WORK_DIR="$(mktemp -d -p "$SC2_TMP")"
cleanup() {
    rm -rf "$WORK_DIR"
}
trap cleanup EXIT

if ! output="$(wrestool -x -t 14 -n "$ICON_GROUP" -o "$WORK_DIR/editor.ico" "$ICON_EXE" 2>&1)"; then
    fail "cannot read the editor icon: $output"
fi
if ! output="$(icotool -x --width="$ICON_SIZE" --height="$ICON_SIZE" -o "$WORK_DIR" "$WORK_DIR/editor.ico" 2>&1)"; then
    fail "cannot convert the editor icon: $output"
fi
ICON_SOURCE=""
for candidate in "$WORK_DIR"/*.png; do
    if [ -f "$candidate" ]; then
        ICON_SOURCE="$candidate"
        break
    fi
done
[ -n "$ICON_SOURCE" ] || fail "editor icon has no ${ICON_SIZE}x${ICON_SIZE} image"

mkdir -p "$ICON_DIR" "$APPS_DIR"
cp -f "$ICON_SOURCE" "$ICON_DIR/$ICON_NAME.png"

printf '[Desktop Entry]\nName=%s\nComment=%s\nExec=env SC2_PROJECT_ROOT="%s" bash "%s" editor\nPath=%s\nIcon=%s\nTerminal=false\nType=Application\nCategories=Development;\nStartupNotify=true\nStartupWMClass=sc2editor_x64.exe\n' \
    "$APP_NAME" \
    "Open the unpacked SCOBA map in the StarCraft II editor" \
    "$ROOT_DIR" \
    "$DIALOG" \
    "$ROOT_DIR" \
    "$ICON_NAME" > "$DESKTOP_FILE"

chmod +x "$DESKTOP_FILE"
if validator="$(command -v desktop-file-validate)"; then
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

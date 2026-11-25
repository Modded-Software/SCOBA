#!/usr/bin/env bash
# Provision the SCOBA and SCOBA FG GNOME desktop entries.
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
# shellcheck source=env/gpu-env.sh
source "$ROOT_DIR/env/gpu-env.sh" || exit 1  # the shell names the cause

APP_ID="scoba.desktop"
FG_APP_ID="scoba-fg.desktop"
APP_NAME="SCOBA"
FG_APP_NAME="SCOBA FG"
ICON_NAME="scoba"
ICON_SOURCE="$ROOT_DIR/assets/scoba.png"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
APPS_DIR="$HOME/.local/share/applications"
GAME_GPU="${SCOBA_GAME_GPU:-$SC2_DEFAULT_GAME_GPU}"
FG_GPU="${SCOBA_FG_GPU:-$SC2_DEFAULT_FG_GPU}"
GAME_DRI="$(sc2_dri_prime_for_pci "$GAME_GPU")"
DRM_BY_PATH="${SCOBA_DRM_BY_PATH:-/dev/dri/by-path}"
VULKAN_LAYER_DIR="${SCOBA_VULKAN_LAYER_DIR:-$HOME/.local/share/vulkan/implicit_layer.d}"
LSFG_LIB="${SCOBA_LSFG_LIB:-$HOME/.local/lib/liblsfg-vk-layer.so}"

log() {
    printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

fail() {
    log "ERROR: $*" >&2
    exit 1
}

[ -f "$ICON_SOURCE" ] || fail "icon not found: $ICON_SOURCE"
[ -x "$ROOT_DIR/scripts/playtest.sh" ] || fail "entrypoint not executable: $ROOT_DIR/scripts/playtest.sh"
[ "$GAME_GPU" != "$FG_GPU" ] || fail "game GPU and frame-generation GPU are both $GAME_GPU"
[ -e "$DRM_BY_PATH/pci-$GAME_GPU-render" ] || fail "game GPU render node not found: $DRM_BY_PATH/pci-$GAME_GPU-render"
[ -e "$DRM_BY_PATH/pci-$FG_GPU-render" ] || fail "frame-generation GPU render node not found: $DRM_BY_PATH/pci-$FG_GPU-render"
[ -f "$VULKAN_LAYER_DIR/VkLayer_LSFGVK_frame_generation.json" ] || fail "lsfg-vk layer not found: $VULKAN_LAYER_DIR/VkLayer_LSFGVK_frame_generation.json"
[ -f "$LSFG_LIB" ] || fail "lsfg-vk library not found: $LSFG_LIB"
if ! UV_BIN="$(command -v uv)"; then
    fail "uv not found"
fi
[ -x "$UV_BIN" ] || fail "uv not executable: $UV_BIN"
if ! command -v gsettings; then
    fail "gsettings not found"
fi

mkdir -p "$ICON_DIR" "$APPS_DIR"
cp -f "$ICON_SOURCE" "$ICON_DIR/$ICON_NAME.png"

# The launch command. $1 is the playtest.sh action. $2 is extra environment
# for this desktop entry. The textures of a build are the picks of the
# dataset `scoba` in the texture store, not a choice of the entry.
launch_exec() {
    local entry="$1"
    local extra="${2:-}"
    [ -z "$extra" ] || extra="$extra "
    printf 'env %sUV_BIN="%s" SC2_PROJECT_ROOT="%s" SC2_WINDOW_WIDTH="1920" SC2_WINDOW_HEIGHT="1080" bash "%s/scripts/playtest.sh" %s' \
        "$extra" "$UV_BIN" "$ROOT_DIR" "$ROOT_DIR" "$entry"
}

# Right-click entries of the dock icon: action id, name, playtest.sh action.
# `built` launches the map as it was last built, with no build step
# (operator 2026-11-20).
ACTIONS=(
    "built|Instant Launch (no build)|launch-built"
)

action_ids=""
action_names=""
for action in "${ACTIONS[@]}"; do
    action_ids="$action_ids${action%%|*};"
    IFS='|' read -r _id action_name _entry <<<"$action"
    action_names="${action_names:+$action_names, }$action_name"
done

# GNOME Shell keeps its cached app object while the name, comment, command,
# icon, and file stay the same (app_is_stale in shell-app-system.c). It does
# not compare Actions, so a change of the menu alone never shows. The
# comment names the menu entries, so a new menu makes the cache stale.
COMMENT="Launch the SCOBA StarCraft II custom map. Right-click: $action_names"
FG_COMMENT="Launch the SCOBA StarCraft II custom map with lsfg-vk frame generation (2x, performance mode, game on GPU $GAME_GPU, frame generation on GPU $FG_GPU). Right-click: $action_names"
GAME_ENV=""
[ -z "${SCOBA_GAME_GPU:-}" ] || GAME_ENV="SCOBA_GAME_GPU=\"$GAME_GPU\""
FG_ENV="LSFGVK_ENV=\"1\" LSFGVK_MULTIPLIER=\"2\" LSFGVK_PERFORMANCE_MODE=\"1\""
[ -z "${SCOBA_FG_GPU:-}" ] || FG_ENV="$FG_ENV SCOBA_FG_GPU=\"$FG_GPU\""
FG_ENV="${GAME_ENV:+$GAME_ENV }$FG_ENV"

write_desktop() {
    local app_id="$1"
    local app_name="$2"
    local comment="$3"
    local extra_env="$4"
    local file="$APPS_DIR/$app_id"

    {
        printf '[Desktop Entry]\nName=%s\nComment=%s\nExec=%s\nPath=%s\nIcon=%s\nTerminal=false\nType=Application\nCategories=Game;StrategyGame;\nStartupNotify=true\nStartupWMClass=StarCraft II.exe\nActions=%s\n' \
            "$app_name" \
            "$comment" \
            "$(launch_exec "launch" "$extra_env")" \
            "$ROOT_DIR" \
            "$ICON_NAME" \
            "$action_ids"
        for action in "${ACTIONS[@]}"; do
            IFS='|' read -r action_id action_name entry <<<"$action"
            printf '\n[Desktop Action %s]\nName=%s\nExec=%s\n' \
                "$action_id" \
                "$action_name" \
                "$(launch_exec "$entry" "$extra_env")"
        done
    } > "$file"

    chmod +x "$file"
}

write_desktop "$APP_ID" "$APP_NAME" "$COMMENT" "$GAME_ENV"
write_desktop "$FG_APP_ID" "$FG_APP_NAME" "$FG_COMMENT" "$FG_ENV"

if command -v desktop-file-validate; then
    for file in "$APPS_DIR/$APP_ID" "$APPS_DIR/$FG_APP_ID"; do
        if ! output="$(desktop-file-validate "$file" 2>&1)"; then
            fail "invalid desktop entry: $output"
        fi
    done
fi
if ! output="$(update-desktop-database "$APPS_DIR" 2>&1)"; then
    log "warning: update-desktop-database: $output"
fi
if ! output="$(gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>&1)"; then
    log "warning: gtk-update-icon-cache: $output"
fi

ensure_favorite() {
    local app_id="$1"
    local favorites
    favorites="$(gsettings get org.gnome.shell favorite-apps)"
    if [[ "$favorites" != *"'$app_id'"* ]]; then
        if [[ "$favorites" == "@as []" || "$favorites" == "[]" ]]; then
            favorites="['$app_id']"
        else
            favorites="${favorites%]}, '$app_id']"
        fi
        gsettings set org.gnome.shell favorite-apps "$favorites"
    fi
}

ensure_favorite "$APP_ID"
ensure_favorite "$FG_APP_ID"

log "installed $APPS_DIR/$APP_ID"
log "installed $APPS_DIR/$FG_APP_ID"
log "game GPU: $GAME_GPU ($GAME_DRI)"
log "frame-generation GPU: $FG_GPU"
log "installed $ICON_DIR/$ICON_NAME.png"
log "added $APP_ID and $FG_APP_ID to GNOME favorites"

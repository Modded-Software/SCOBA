#!/usr/bin/env bash
# The launch dialog of the dock icons (REQ-LAUNCH-DIALOG): progress, steps
# and the log of a build and launch. It stays open when the run shows an error.
#
# usage: launch-dialog.sh <launch|launch-built|editor>
#        launch-dialog.sh --check     load the toolkit, open nothing
set -euo pipefail

resolve_root() {
    local cand
    for cand in \
        "${SC2_PROJECT_ROOT:-}" \
        "$(cd -- "$(dirname -- "${0:-.}")/.." && pwd)" \
        "$PWD" \
        "$(cd -- "$(dirname -- "${BASH_SOURCE[0]:-.}")/.." && pwd)"; do
        if [ -n "$cand" ] && [ -f "$cand/scripts/launchui/main.js" ]; then
            printf '%s\n' "$cand"
            return 0
        fi
    done
    return 1
}
ROOT_DIR="$(resolve_root)" || { printf 'ERROR: cannot locate project root\n' >&2; exit 1; }
export SC2_PROJECT_ROOT="$ROOT_DIR"

fail() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

# The dialog is GNOME's own toolkit: gjs with GTK 4 and libadwaita.
GJS="$(command -v gjs)" || fail "gjs not found: the launch dialog needs gjs, GTK 4 and libadwaita"
[ -x "$GJS" ] || fail "gjs not executable: $GJS"
MAIN="$ROOT_DIR/scripts/launchui/main.js"

[ $# -eq 1 ] || fail "usage: launch-dialog.sh <launch|launch-built|editor> | --check"
if [ "$1" = "--check" ]; then
    exec "$GJS" -m "$MAIN" --check
fi
exec "$GJS" -m "$MAIN" --root "$ROOT_DIR" --action "$1"

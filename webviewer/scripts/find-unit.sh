#!/usr/bin/env bash
# Units whose name or id contains a text.
set -euo pipefail
WEBVIEWER_DIR="${WEBVIEWER_DIR:-$(git rev-parse --show-toplevel)/webviewer}"
source "$WEBVIEWER_DIR/scripts/paths.sh" || exit 1
node tools/find-unit.mjs "$WEBVIEWER_DATA" "$@"

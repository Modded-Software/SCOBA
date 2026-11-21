#!/usr/bin/env bash
# Print the standard materials and layers of one unit's model file.
set -euo pipefail
WEBVIEWER_DIR="${WEBVIEWER_DIR:-$(git rev-parse --show-toplevel)/webviewer}"
source "$WEBVIEWER_DIR/scripts/paths.sh" || exit 1
node tools/m3-materials.mjs "$WEBVIEWER_DATA" "$1"

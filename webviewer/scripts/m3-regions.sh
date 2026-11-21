#!/usr/bin/env bash
# Print the regions of one unit's model and flag indices past 65535.
set -euo pipefail
WEBVIEWER_DIR="${WEBVIEWER_DIR:-$(git rev-parse --show-toplevel)/webviewer}"
source "$WEBVIEWER_DIR/scripts/paths.sh" || exit 1
node tools/m3-regions.mjs "$WEBVIEWER_DATA" "$1"

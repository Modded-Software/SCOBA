#!/usr/bin/env bash
# Parse one unit's model file with the patched parser and show why it fails.
set -euo pipefail
WEBVIEWER_DIR="${WEBVIEWER_DIR:-$(git rev-parse --show-toplevel)/webviewer}"
source "$WEBVIEWER_DIR/scripts/paths.sh" || exit 1
node tools/parse-one.mjs "$WEBVIEWER_DATA" "$1"

#!/usr/bin/env bash
# Check vertex strides of unit models against the library and m3addon rules.
set -euo pipefail
WEBVIEWER_DIR="${WEBVIEWER_DIR:-$(git rev-parse --show-toplevel)/webviewer}"
source "$WEBVIEWER_DIR/scripts/paths.sh" || exit 1
node tools/vertex-survey.mjs "$WEBVIEWER_DATA" "$@"

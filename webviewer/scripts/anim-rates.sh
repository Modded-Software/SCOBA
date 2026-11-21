#!/usr/bin/env bash
# Units whose animation rate in data is not 1.
set -euo pipefail
WEBVIEWER_DIR="${WEBVIEWER_DIR:-$(git rev-parse --show-toplevel)/webviewer}"
source "$WEBVIEWER_DIR/scripts/paths.sh" || exit 1
node tools/anim-rates.mjs "$WEBVIEWER_DATA" "$@"

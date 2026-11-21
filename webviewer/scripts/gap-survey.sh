#!/usr/bin/env bash
# Renderer gap survey of unit models (docs/specifications/GAP-ANALYSIS-WEBVIEWER.md).
set -euo pipefail
WEBVIEWER_DIR="${WEBVIEWER_DIR:-$(git rev-parse --show-toplevel)/webviewer}"
# Reads build/m3parser.cjs, made by tools/build-renderer.mjs (scripts/test.sh runs it).
source "$WEBVIEWER_DIR/scripts/paths.sh" || exit 1
node tools/gap-survey.mjs "$WEBVIEWER_DATA" "$@"

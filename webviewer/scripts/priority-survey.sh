#!/usr/bin/env bash
# Models whose batch draw order differs from file order (gap G2).
set -euo pipefail
WEBVIEWER_DIR="${WEBVIEWER_DIR:-$(git rev-parse --show-toplevel)/webviewer}"
# Reads build/m3parser.cjs, made by tools/build-renderer.mjs (scripts/test.sh runs it).
source "$WEBVIEWER_DIR/scripts/paths.sh" || exit 1
node tools/priority-survey.mjs "$WEBVIEWER_DATA" "$@"

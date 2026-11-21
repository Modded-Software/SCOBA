#!/usr/bin/env bash
# Texture coordinate ranges of unit models: the old rule against the file's.
set -euo pipefail
WEBVIEWER_DIR="${WEBVIEWER_DIR:-$(git rev-parse --show-toplevel)/webviewer}"
# Reads build/m3parser.cjs, made by tools/build-renderer.mjs (scripts/test.sh runs it).
source "$WEBVIEWER_DIR/scripts/paths.sh" || exit 1
node tools/uv-survey.mjs "$WEBVIEWER_DATA" "$@"

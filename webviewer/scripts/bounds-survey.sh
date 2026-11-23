#!/usr/bin/env bash
# Check the culling bounds of unit models against their vertex positions.
set -euo pipefail
WEBVIEWER_DIR="${WEBVIEWER_DIR:-$(git rev-parse --show-toplevel)/webviewer}"
# Reads build/m3parser.cjs, made by src/tools/build.ts (scripts/test.sh runs it).
source "$WEBVIEWER_DIR/scripts/paths.sh" || exit 1
node tools/bounds-survey.mjs "$WEBVIEWER_DATA" "$@"

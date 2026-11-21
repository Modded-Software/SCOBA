#!/usr/bin/env bash
# Layers with sequence-driven UV offset, angle or tiling (gap A1).
set -euo pipefail
WEBVIEWER_DIR="${WEBVIEWER_DIR:-$(git rev-parse --show-toplevel)/webviewer}"
# Reads build/m3parser.cjs, made by tools/build-renderer.mjs (scripts/test.sh runs it).
source "$WEBVIEWER_DIR/scripts/paths.sh" || exit 1
node tools/uv-anim-survey.mjs "$WEBVIEWER_DATA" "$@"

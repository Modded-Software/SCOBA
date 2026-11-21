#!/usr/bin/env bash
# Two surveys of the unit model files:
# 1. the M3 struct versions the parser's size table (ref repo) does not list;
# 2. which files the parser actually parses.
set -euo pipefail
WEBVIEWER_DIR="${WEBVIEWER_DIR:-$(git rev-parse --show-toplevel)/webviewer}"
source "$WEBVIEWER_DIR/scripts/paths.sh" || exit 1
bash scripts/ref-setup.sh
cd "$REPO_ROOT/scripts"
PYTHONPATH="$REPO_ROOT/scripts:$REPO_ROOT/scripts/hdtex" uv run python ../webviewer/tools/m3_survey.py --data "$WEBVIEWER_DATA" \
  --parser "$WEBVIEWER_DIR/ref/mdx-m3-viewer/src/parsers/m3/indexentry.ts"
cd "$WEBVIEWER_DIR"
node tools/build-renderer.mjs
node tools/parse-survey.mjs "$WEBVIEWER_DATA"

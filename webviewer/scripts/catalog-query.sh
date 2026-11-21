#!/usr/bin/env bash
# Print catalog stats, "--modified" units, or the records of the given unit ids.
set -euo pipefail
WEBVIEWER_DIR="${WEBVIEWER_DIR:-$(git rev-parse --show-toplevel)/webviewer}"
source "$WEBVIEWER_DIR/scripts/paths.sh" || exit 1
cd "$REPO_ROOT/scripts"
uv run python ../webviewer/tools/catalog_query.py "$WEBVIEWER_DATA/catalog/units.json" "$@"

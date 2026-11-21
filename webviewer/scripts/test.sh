#!/usr/bin/env bash
# Run the Playwright integration tests. Arguments go to playwright.
# The renderer bundle and the unit catalog must exist first.
set -euo pipefail
WEBVIEWER_DIR="${WEBVIEWER_DIR:-$(git rev-parse --show-toplevel)/webviewer}"
source "$WEBVIEWER_DIR/scripts/paths.sh" || exit 1
bash scripts/ref-setup.sh
node tools/build-renderer.mjs
bash scripts/catalog.sh --if-missing
npx playwright test "$@"

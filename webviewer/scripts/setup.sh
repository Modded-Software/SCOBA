#!/usr/bin/env bash
# Install dependencies and the test browser, set up the patched renderer
# source, then build the renderer.
set -euo pipefail
WEBVIEWER_DIR="${WEBVIEWER_DIR:-$(git rev-parse --show-toplevel)/webviewer}"
source "$WEBVIEWER_DIR/scripts/paths.sh" || exit 1
pwd
npm install
npx playwright install chromium
bash scripts/ref-setup.sh
node tools/build-renderer.mjs

#!/usr/bin/env bash
# Start the viewer server in the foreground, with hot reload: a change under
# src/ rebuilds, a new build/server.js restarts the server (src/tools/dev.ts).
# PORT and HOST can be set in the environment.
set -euo pipefail
WEBVIEWER_DIR="${WEBVIEWER_DIR:-$(git rev-parse --show-toplevel)/webviewer}"
source "$WEBVIEWER_DIR/scripts/paths.sh" || exit 1
bash scripts/ref-setup.sh
bash scripts/tool.sh build
bash scripts/catalog.sh --if-missing
exec bash scripts/tool.sh dev

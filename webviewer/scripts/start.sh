#!/usr/bin/env bash
# Start the viewer server in the foreground. PORT and HOST can be set in the environment.
set -euo pipefail
WEBVIEWER_DIR="${WEBVIEWER_DIR:-$(git rev-parse --show-toplevel)/webviewer}"
source "$WEBVIEWER_DIR/scripts/paths.sh" || exit 1
bash scripts/ref-setup.sh
bash scripts/tool.sh build
bash scripts/catalog.sh --if-missing
exec node build/server.js

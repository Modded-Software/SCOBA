#!/usr/bin/env bash
# Bundle one Node tool from src/tools/<name>.ts into build/tools/<name>.js and run it.
# Usage: scripts/tool.sh <name> [arguments of the tool]
# The bundler does not check types; scripts/typecheck.sh does.
set -euo pipefail
WEBVIEWER_DIR="${WEBVIEWER_DIR:-$(git rev-parse --show-toplevel)/webviewer}"
source "$WEBVIEWER_DIR/scripts/paths.sh" || exit 1
if [[ $# -lt 1 ]]; then
  echo "usage: scripts/tool.sh <name> [arguments]" >&2
  exit 2
fi
NAME="$1"
shift
SOURCE="src/tools/${NAME}.ts"
if [[ ! -f "$SOURCE" ]]; then
  echo "ERROR: no tool $SOURCE" >&2
  exit 2
fi
node_modules/.bin/esbuild "$SOURCE" --bundle --platform=node --format=esm --target=node24 \
  --packages=external --log-level=warning --outfile="build/tools/${NAME}.js"
exec node "build/tools/${NAME}.js" "$@"

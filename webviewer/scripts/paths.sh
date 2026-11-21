# Paths for the viewer scripts. Sourced, not run.
#
# Every script starts with
#   WEBVIEWER_DIR="${WEBVIEWER_DIR:-$(git rev-parse --show-toplevel)/webviewer}"
#   source "$WEBVIEWER_DIR/scripts/paths.sh"
# because $0 and BASH_SOURCE can resolve under /proc in this environment.
#
# Machine settings (data folder, game install) go in webviewer/local.env,
# which is gitignored. Example:
#   WEBVIEWER_DATA=/mnt/ws-fast/sc2res/webviewer

REPO_ROOT="${REPO_ROOT:-$(cd "$WEBVIEWER_DIR/.." && pwd)}"
if [[ -f "$WEBVIEWER_DIR/local.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$WEBVIEWER_DIR/local.env" || return 1
  set +a
fi
# Extracted game files: model cache, stock game data, unit catalog. Gitignored.
WEBVIEWER_DATA="${WEBVIEWER_DATA:-$WEBVIEWER_DIR/data}"
SC2_PATH="${SC2_PATH:-$HOME/Games/battlenet-prefix/pfx/drive_c/Program Files (x86)/StarCraft II}"
STORMEX="${STORMEX:-$REPO_ROOT/tools/stormex}"
export WEBVIEWER_DIR REPO_ROOT WEBVIEWER_DATA SC2_PATH STORMEX
cd "$WEBVIEWER_DIR"

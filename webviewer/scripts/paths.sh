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
  # A setting given in the environment wins over local.env, empty included
  # (GHOST_PATH= runs a tool as if the game were not installed).
  declare -A _paths_env=()
  for _paths_name in WEBVIEWER_DATA SC2_PATH STORMEX GHOST_PATH; do
    [[ ! -v "$_paths_name" ]] || _paths_env[$_paths_name]="${!_paths_name}"
  done
  set -a
  # shellcheck source=/dev/null
  source "$WEBVIEWER_DIR/local.env" || return 1
  set +a
  for _paths_name in "${!_paths_env[@]}"; do
    printf -v "$_paths_name" '%s' "${_paths_env[$_paths_name]}"
  done
  unset _paths_env _paths_name
fi
# Extracted game files: model cache, stock game data, unit catalog. Gitignored.
WEBVIEWER_DATA="${WEBVIEWER_DATA:-$WEBVIEWER_DIR/data}"
SC2_PATH="${SC2_PATH:-$HOME/Games/battlenet-prefix/pfx/drive_c/Program Files (x86)/StarCraft II}"
STORMEX="${STORMEX:-$REPO_ROOT/tools/stormex}"
# The extracted StarCraft: Ghost build (SPEC-VIEWER-GHOST 3). No built-in value:
# unset, the game is not available and its tools stop with a message.
GHOST_PATH="${GHOST_PATH:-}"
export WEBVIEWER_DIR REPO_ROOT WEBVIEWER_DATA SC2_PATH STORMEX GHOST_PATH
cd "$WEBVIEWER_DIR"

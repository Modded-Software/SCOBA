# Paths for the viewer scripts. Sourced, not run.
#
# Every script starts with
#   WEBVIEWER_DIR="${WEBVIEWER_DIR:-$(git rev-parse --show-toplevel)/webviewer}"
#   source "$WEBVIEWER_DIR/scripts/paths.sh"
# because $0 and BASH_SOURCE can resolve under /proc in this environment.
#
# The project paths come from scripts/paths.sh (env/paths.conf, SPEC-PATHS).
# Viewer machine settings (data folder, Ghost build) go in webviewer/local.env,
# which is gitignored. Example:
#   WEBVIEWER_DATA=/mnt/ws-fast/sc2res/webviewer

REPO_ROOT="${REPO_ROOT:-$(cd "$WEBVIEWER_DIR/.." && pwd)}"
# The project's paths (SPEC-PATHS): work folders, texture store, game install.
# shellcheck source=../../scripts/paths.sh
ROOT_DIR="$REPO_ROOT"
source "$REPO_ROOT/scripts/paths.sh" || return 1
paths_check_device || return 1
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
# Extracted game files: model cache, stock game data, unit catalog.
WEBVIEWER_DATA="${WEBVIEWER_DATA:-$WEBVIEWER_WORK/data}"
SC2_PATH="${SC2_PATH:-$SC2_INSTALL}"
STORMEX="${STORMEX:-$REPO_ROOT/tools/stormex}"
# The extracted StarCraft: Ghost build (SPEC-VIEWER-GHOST 3). No built-in value:
# unset, the game is not available and its tools stop with a message.
GHOST_PATH="${GHOST_PATH:-}"
export WEBVIEWER_DIR REPO_ROOT WEBVIEWER_DATA SC2_PATH STORMEX GHOST_PATH

# The viewer's heavy folders live below WEBVIEWER_WORK, off the repo disk.
# The code names them below webviewer/; each is a link there. A real folder
# in their place is data still to move: stop and say so, move nothing.
# webviewer/ref stays a real folder in the repo (operator 2026-11-25).
VIEWER_WORK_FOLDERS=(build node_modules test-results)
if [[ -L "$WEBVIEWER_DIR/ref" ]]; then
  printf 'ERROR: %s is a link; the reference repos stay in the repo (SPEC-PATHS)\n' \
    "$WEBVIEWER_DIR/ref" >&2
  return 1
fi
for _paths_name in "${VIEWER_WORK_FOLDERS[@]}"; do
  _paths_link="$WEBVIEWER_DIR/$_paths_name"
  _paths_target="$WEBVIEWER_WORK/$_paths_name"
  if [[ -L "$_paths_link" ]]; then
    if [[ "$(readlink "$_paths_link")" != "$_paths_target" ]]; then
      ln -sfn "$_paths_target" "$_paths_link" || return 1
    fi
  elif [[ -e "$_paths_link" ]]; then
    printf 'ERROR: %s is a folder on the repo disk; move it to %s (SPEC-PATHS)\n' \
      "$_paths_link" "$_paths_target" >&2
    unset _paths_name _paths_link _paths_target
    return 1
  else
    ln -s "$_paths_target" "$_paths_link" || return 1
  fi
  mkdir -p "$_paths_target" || return 1
done
unset _paths_name _paths_link _paths_target

# npm install with node_modules below WEBVIEWER_WORK. npm replaces a linked
# node_modules with a real folder, so it runs in WEBVIEWER_WORK on a copy of
# package.json and the lock; the lock it writes comes back to the repo.
viewer_npm_install() {
  local name
  for name in package.json package-lock.json; do
    cp "$WEBVIEWER_DIR/$name" "$WEBVIEWER_WORK/$name" || return 1
  done
  npm install --prefix "$WEBVIEWER_WORK" "$@" || return 1
  cmp -s "$WEBVIEWER_WORK/package-lock.json" "$WEBVIEWER_DIR/package-lock.json" ||
    cp "$WEBVIEWER_WORK/package-lock.json" "$WEBVIEWER_DIR/package-lock.json" || return 1
  [[ -L "$WEBVIEWER_DIR/node_modules" ]] || {
    printf 'ERROR: npm replaced the link %s\n' "$WEBVIEWER_DIR/node_modules" >&2
    return 1
  }
}
cd "$WEBVIEWER_DIR"

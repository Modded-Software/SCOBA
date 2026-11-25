# Where the project writes (SPEC-PATHS). Sourced, not run; needs ROOT_DIR.
#
# The one resolver. It reads env/paths.conf, derives every path, checks it,
# makes the folders and exports the result. scripts/workpaths.py and the
# viewer only read what it exports. A variable already in the environment
# wins over the file and over the derivation.

_paths_config="$ROOT_DIR/env/paths.conf"
if [ ! -f "$_paths_config" ]; then
    printf 'ERROR: %s is missing (SPEC-PATHS)\n' "$_paths_config" >&2
    return 1
fi
while IFS= read -r _paths_line || [ -n "$_paths_line" ]; do
    case "$_paths_line" in
        ''|'#'*) continue ;;
    esac
    _paths_name="${_paths_line%%=*}"
    _paths_value="${_paths_line#*=}"
    _paths_value="${_paths_value//\$HOME/$HOME}"
    if [ -z "${!_paths_name+set}" ]; then
        printf -v "$_paths_name" '%s' "$_paths_value"
    fi
done < "$_paths_config"
unset _paths_config _paths_line _paths_name _paths_value
for _paths_name in SC2_WORK SC2RES BNET_PREFIX SC2_MAP_NAME SC2_WINE_DRIVE SC2_WINE_USER; do
    if [ -z "${!_paths_name// /}" ]; then
        printf 'ERROR: %s is not set: name it in env/paths.conf (SPEC-PATHS)\n' "$_paths_name" >&2
        unset _paths_name
        return 1
    fi
done

: "${SC2_OUT:=$SC2_WORK/out}"
: "${SC2_BUILD:=$SC2_WORK/build}"
: "${SC2_TEST_RUNS:=$SC2_WORK/test-runs}"
: "${SC2_TESTKIT:=$SC2_WORK/testkit}"
: "${SC2_TMP:=$SC2_WORK/tmp}"
: "${TEXTURE_STORE:=$SC2_BUILD/texture-store}"
: "${UV_PROJECT_ENVIRONMENT:=$SC2_WORK/venv}"
: "${WEBVIEWER_WORK:=$SC2_WORK/webviewer}"
: "${SC2_BUILT_MAP:=$SC2_OUT/$SC2_MAP_NAME}"
: "${SC2_BUILD_STAMP:=$SC2_OUT/.last-build-stamp}"
: "${SC2_INSTALL:=$BNET_PREFIX/$SC2_WINE_DRIVE/Program Files (x86)/StarCraft II}"
: "${SC2_DOCUMENTS:=$BNET_PREFIX/$SC2_WINE_DRIVE/users/$SC2_WINE_USER/Documents/StarCraft II}"
: "${SC2_MAP_CACHE:=$BNET_PREFIX/$SC2_WINE_DRIVE/ProgramData/Blizzard Entertainment/StarCraft II/Maps/Cache}"
TMPDIR="$SC2_TMP"

# Folders this file makes; paths_check_device keeps them off the repo disk.
PATHS_FOLDERS=(SC2_WORK SC2_OUT SC2_BUILD SC2_TEST_RUNS SC2_TESTKIT SC2_TMP SC2RES WEBVIEWER_WORK)
# Every path this file exports. scripts/workpaths.py NAMES lists the same.
PATHS_ALL=("${PATHS_FOLDERS[@]}" TEXTURE_STORE UV_PROJECT_ENVIRONMENT BNET_PREFIX
    SC2_BUILT_MAP SC2_BUILD_STAMP SC2_INSTALL SC2_DOCUMENTS SC2_MAP_CACHE)

for _paths_name in "${PATHS_ALL[@]}"; do
    case "${!_paths_name:-}" in
        /*) ;;
        *)
            printf 'ERROR: %s must be an absolute path, not "%s" (env/paths.conf, SPEC-PATHS)\n' \
                "$_paths_name" "${!_paths_name:-}" >&2
            unset _paths_name
            return 1
            ;;
    esac
done
for _paths_name in "${PATHS_FOLDERS[@]}"; do
    if ! mkdir -p "${!_paths_name}"; then
        printf 'ERROR: cannot make %s: %s\n' "$_paths_name" "${!_paths_name}" >&2
        unset _paths_name
        return 1
    fi
done
unset _paths_name
export "${PATHS_ALL[@]}" SC2_MAP_NAME SC2_WINE_DRIVE SC2_WINE_USER TMPDIR

# Refuse a work folder on the repository's disk: the reason for SPEC-PATHS.
paths_check_device() {
    local repo_dev name
    repo_dev="$(stat -c %d "$ROOT_DIR")"
    for name in "${PATHS_FOLDERS[@]}"; do
        if [ "$(stat -c %d "${!name}")" = "$repo_dev" ] && [ "${SC2_ALLOW_REPO_DISK:-0}" != 1 ]; then
            printf 'ERROR: %s=%s is on the disk of the repository; set SC2_WORK in env/paths.conf (SPEC-PATHS)\n' \
                "$name" "${!name}" >&2
            return 1
        fi
    done
}

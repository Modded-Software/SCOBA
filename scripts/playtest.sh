#!/usr/bin/env bash
set -euo pipefail

if [ -n "${SC2_PROJECT_ROOT:-}" ] && [ -f "$SC2_PROJECT_ROOT/scripts/playtest.sh" ]; then
    ROOT_DIR="$SC2_PROJECT_ROOT"
elif [ -f "$PWD/scripts/playtest.sh" ]; then
    ROOT_DIR="$PWD"
else
    ROOT_DIR="$(cd -- "$(dirname -- "$0")/.." && pwd)"
fi
export SC2_PROJECT_ROOT="$ROOT_DIR"
OUT_DIR="$ROOT_DIR/out"
FRESH_MAP="$OUT_DIR/SCOBA256.SC2Map"
PLAYTEST="$ROOT_DIR/scripts/playtest.sh"
UV_BIN="${UV_BIN:-uv}"
if [ "${UV_BIN#/}" = "$UV_BIN" ]; then
    UV_BIN="$(command -v "$UV_BIN")" || {
        printf 'ERROR: uv not found\n' >&2
        exit 1
    }
fi
[ -x "$UV_BIN" ] || {
    printf 'ERROR: uv not executable: %s\n' "$UV_BIN" >&2
    exit 1
}
export UV_BIN

log() {
    printf '%s\n' "$*"
}

fail() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

usage() {
    cat <<'EOF'
usage: scripts/playtest.sh <action>

actions:
  build                  rebuild out/SCOBA256.SC2Map and stop
  launch                 rebuild, then launch the fresh map
  launch-check           rebuild, launch, and check runtime logs
  combat                 rebuild, build combat test map, run combat profile
  aim                    rebuild, build aim test map, run aim profile
  motion                 rebuild, build motion test map, run motion profile
  controls               rebuild, build controls test map, run controls profile
  pitch                  rebuild, build pitch test map, run 10-second pitch playtest
  build-profile <name>   rebuild, build one profile map, stop
  run-profile <name>     rebuild, build one profile map, run it
EOF
}

run_python() {
    "$UV_BIN" run python "$@"
}

profile_timeout() {
    case "$1" in
        aim) printf '%s\n' "${SC2_CASE_TIMEOUT:-150}" ;;
        motion) printf '%s\n' "${SC2_CASE_TIMEOUT:-80}" ;;
        pitch) printf '%s\n' "${SC2_CASE_TIMEOUT:-18}" ;;
        *) printf '%s\n' "${SC2_CASE_TIMEOUT:-40}" ;;
    esac
}

fresh_build() {
    log "fresh build: $ROOT_DIR/src/SCOBA.SC2Map"
    SC2_PLAYTEST_ACTIVE=1 bash "$ROOT_DIR/scripts/build.sh"
    [ -f "$FRESH_MAP/BuildStamp.txt" ] || fail "fresh build missing BuildStamp.txt"
    [ -f "$OUT_DIR/.last-build-stamp" ] || fail "fresh build missing build stamp"
    log "fresh build stamp: $(cat "$OUT_DIR/.last-build-stamp")"
    if [ -f "$FRESH_MAP/BuildManifest.txt" ]; then
        log "fresh map manifest sha256: $(sha256sum "$FRESH_MAP/BuildManifest.txt" | cut -d' ' -f1)"
    fi
}

build_profile() {
    local profile="$1"
    case "$profile" in
        combat|aim|motion|controls|pitch) ;;
        *) fail "unknown profile: $profile" ;;
    esac
    log "building profile map: $profile"
    run_python "$ROOT_DIR/scripts/testmap.py" build "$profile"
}

run_profile() {
    local profile="$1"
    local timeout_s
    build_profile "$profile"
    timeout_s="$(profile_timeout "$profile")"
    launch_timeout_s="${SC2_LAUNCH_TIMEOUT:-60}"
    log "running profile: $profile (launch ${launch_timeout_s}s, case ${timeout_s}s)"
    SC2_CASE_TIMEOUT="$timeout_s" run_python "$ROOT_DIR/scripts/testmap.py" run "$profile" \
        --launch-timeout "$launch_timeout_s" \
        --case-timeout "$timeout_s"
}

ACTION="${1:-}"
if [ -z "$ACTION" ]; then
    usage >&2
    exit 2
fi
shift

export SC2_PLAYTEST_ACTIVE=1
fresh_build

case "$ACTION" in
    build)
        ;;
    launch)
        export SC2_MAP_SOURCE="$FRESH_MAP"
        exec bash "$ROOT_DIR/scripts/launch-scoba.sh"
        ;;
    launch-check)
        export SC2_MAP_SOURCE="$FRESH_MAP"
        exec bash "$ROOT_DIR/scripts/launch-and-check.sh"
        ;;
    combat|aim|motion|controls|pitch)
        run_profile "$ACTION"
        ;;
    build-profile)
        [ $# -ge 1 ] || fail "build-profile needs a profile"
        build_profile "$1"
        ;;
    run-profile)
        [ $# -ge 1 ] || fail "run-profile needs a profile"
        run_profile "$1"
        ;;
    *)
        usage >&2
        fail "unknown action: $ACTION"
        ;;
esac

log "done: $ACTION"

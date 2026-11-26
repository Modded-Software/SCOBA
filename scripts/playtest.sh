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
# Every path below comes from here (SPEC-PATHS).
# shellcheck source=paths.sh
source "$ROOT_DIR/scripts/paths.sh" || exit 1
paths_check_device
OUT_DIR="$SC2_OUT"
FRESH_MAP="$SC2_BUILT_MAP"
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
usage: scripts/playtest.sh <action> [group]

actions:
  build                  rebuild the map (SC2_BUILT_MAP) and stop
  host-tests             rebuild, then run the Python unittest suite for the tooling
  launch                 rebuild, then launch the fresh map
  launch-built           no build: launch the map as it was last built
  launch-check           rebuild, launch, and check runtime logs
  combat [group]         rebuild, build combat test map, run one scenario group
                         (idle, single, auto, cancel, wasd, hold, button, switch,
                         pose, kerrigan, camheight) or the full suite when no group is given
  tps [group]            rebuild, build tps test map, run one scenario group
                         (move, cursor, aim, head, target, pick, shot, hold, pose) or the full suite when no group is given
  jump [group]           rebuild, build jump test map, run one scenario group
                         (arc, body, hero) or the full suite when no group is given
  slowwalk [group]       rebuild, build slow walk test map, run one scenario group
                         (walk, mode, hero, jump) or the full suite when no group is given
  intro [group]          rebuild, build intro test map, run one scenario group
                         (boot, shots, wrap, gate, deploy; boot always runs) or the full suite
  herodrop [group]       rebuild, build hero drop test map, run one scenario group
                         (main, alive, loop, seat2, leave, wave) or all; only wave fires the real wave
  roster                 rebuild, build roster test map, run it (seats, owners, alliances)
  podbirth               rebuild, build pod Birth test map, run it
  aimdof                 rebuild, sweep 10 aim near-DOF datapoints (operator check)
  skyduel                rebuild, check the three MengskBC spots and heights, Leviathan hidden
  aircreep [group]       rebuild, build air creep test map, run one scenario group
                         (timer, wave, route, fight, ground, cap, balance) or the full suite
  ui                     rebuild, check stats and abilities panels stay open on XP
  baseai [group]         rebuild, build base AI test map, run one scenario group
                         (probe) or the full suite
  aim                    rebuild, build aim test map, run aim profile
  motion                 rebuild, build motion test map, run motion profile
  controls               rebuild, build controls test map, run controls profile
  pitch                  rebuild, build pitch test map, run 10-second pitch playtest
  aimfreeze              rebuild, build aim freeze test map, run 10-second hold test
  treepath               rebuild, build tree and spore pathing test map, run it
  fprot                  rebuild, build footprint rotation probe map, run it
  flora                  rebuild, build flora and lane hazard test map, run it
  crushtest              rebuild, build the grass crush test map, run it
  waterprobe             rebuild, build the water test probe map, run it
  ground                 rebuild, engine ground vs render ground, flyer over a
                         hill
  hdbake                 rebuild, then a map with a unit and an actor HD bake:
                         the made model entries in the game (SPEC-HD-TEXTURES E-1)
  loadwait               rebuild, then a map that keeps the wait for a key: no game
                         for 90 s with no input, the game after a key (about 2 min)
  waterfeat              rebuild, water features: carved ground, pool pathing,
                         a walk into each pool, the pipe unit
  dissolveview           rebuild, build the doodad physics view map, launch it
                         for manual viewing (bank SCOBADISSOLVE)
  dropview               rebuild, build the hero pod watch map, launch it: intro
                         deploy, hero killed, revive pod (operator judges)
  picklog                rebuild, build the pick log map, launch it for manual play;
                         the log goes to the SCOBAPNCPROBE bank, section picklog
  build-profile <name>   rebuild, build one profile map, stop
  run-profile <name>     rebuild, build one profile map, run it

environment:
  SC2_KEEP_OPEN=1        operator mode: check and write the summary as usual,
                         then leave StarCraft II running to play on
  paths                  env/paths.conf, read by scripts/paths.sh (SPEC-PATHS);
                         a variable set in the environment wins
EOF
}

run_python() {
    "$UV_BIN" run python "$@"
}

profile_timeout() {
    case "$1" in
        aim) printf '%s\n' "${SC2_CASE_TIMEOUT:-150}" ;;
        pncprobe) printf '%s\n' "${SC2_CASE_TIMEOUT:-180}" ;;
        treepath) printf '%s\n' "${SC2_CASE_TIMEOUT:-240}" ;;
        flora) printf '%s\n' "${SC2_CASE_TIMEOUT:-300}" ;;
        crushtest) printf '%s\n' "${SC2_CASE_TIMEOUT:-240}" ;;
        combat|tps)
            if [ "${SC2_TEST_GROUP:-all}" = all ]; then
                printf '%s\n' "${SC2_CASE_TIMEOUT:-420}"
            else
                printf '%s\n' "${SC2_CASE_TIMEOUT:-90}"
            fi
            ;;
        motion) printf '%s\n' "${SC2_CASE_TIMEOUT:-80}" ;;
        jump) printf '%s\n' "${SC2_CASE_TIMEOUT:-90}" ;;
        slowwalk) printf '%s\n' "${SC2_CASE_TIMEOUT:-120}" ;;
        herodrop) printf '%s\n' "${SC2_CASE_TIMEOUT:-170}" ;;
        roster) printf '%s\n' "${SC2_CASE_TIMEOUT:-90}" ;;
        waterfeat) printf '%s\n' "${SC2_CASE_TIMEOUT:-150}" ;;
        hdbake) printf '%s\n' "${SC2_CASE_TIMEOUT:-60}" ;;
        podbirth) printf '%s\n' "${SC2_CASE_TIMEOUT:-90}" ;;
        aimdof) printf '%s\n' "${SC2_CASE_TIMEOUT:-60}" ;;
        ui) printf '%s\n' "${SC2_CASE_TIMEOUT:-90}" ;;
        intro) printf '%s\n' "${SC2_CASE_TIMEOUT:-120}" ;;
        aircreep) printf '%s\n' "${SC2_CASE_TIMEOUT:-240}" ;;
        baseai) printf '%s\n' "${SC2_CASE_TIMEOUT:-300}" ;;
        pitch) printf '%s\n' "${SC2_CASE_TIMEOUT:-30}" ;;
        aimfreeze) printf '%s\n' "${SC2_CASE_TIMEOUT:-20}" ;;
        *) printf '%s\n' "${SC2_CASE_TIMEOUT:-40}" ;;
    esac
}

fresh_build() {
    log "fresh build: $ROOT_DIR/src/SCOBA.SC2Map"
    SC2_PLAYTEST_ACTIVE=1 bash "$ROOT_DIR/scripts/build.sh"
    [ -f "$FRESH_MAP/BuildStamp.txt" ] || fail "fresh build missing BuildStamp.txt"
    [ -f "$SC2_BUILD_STAMP" ] || fail "fresh build missing build stamp"
    log "fresh build stamp: $(cat "$SC2_BUILD_STAMP")"
    if [ -f "$FRESH_MAP/BuildManifest.txt" ]; then
        log "fresh map manifest sha256: $(sha256sum "$FRESH_MAP/BuildManifest.txt" | cut -d' ' -f1)"
    fi
}

build_profile() {
    local profile="$1"
    case "$profile" in
        combat|tps|jump|slowwalk|intro|aircreep|baseai|herodrop|podbirth|aimdof|skyduel|ui|aim|motion|controls|pitch|aimfreeze|rungun|pncprobe|treepath|fprot|flora|crushtest|waterprobe|roster|ground|waterfeat|hdbake|loadwait) ;;
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
# launch-built (operator 2026-11-20): launch the map as it was last built,
# with no build step. Nothing else skips the build.
if [ "$ACTION" = launch-built ]; then
    [ -f "$FRESH_MAP/BuildStamp.txt" ] || fail "no built map: $FRESH_MAP (run: scripts/playtest.sh build)"
    log "launching the built map, no build: stamp $(cat "$FRESH_MAP/BuildStamp.txt")"
    export SC2_MAP_SOURCE="$FRESH_MAP"
    exec bash "$ROOT_DIR/scripts/launch-scoba.sh"
fi
fresh_build

case "$ACTION" in
    build)
        ;;
    host-tests)
        PYTHONPATH="$ROOT_DIR/scripts" run_python -m unittest discover \
            -s "$ROOT_DIR/scripts/testkit/tests" -t "$ROOT_DIR/scripts" -v
        ;;
    launch)
        export SC2_MAP_SOURCE="$FRESH_MAP"
        exec bash "$ROOT_DIR/scripts/launch-scoba.sh"
        ;;
    launch-check)
        export SC2_MAP_SOURCE="$FRESH_MAP"
        exec bash "$ROOT_DIR/scripts/launch-and-check.sh"
        ;;
    combat|tps|jump|slowwalk|intro|aircreep|baseai|herodrop)
        export SC2_TEST_GROUP="${1:-all}"
        run_profile "$ACTION"
        ;;
    podbirth|aimdof|skyduel|ui|aim|motion|controls|pitch|aimfreeze|rungun|pncprobe|treepath|fprot|flora|crushtest|waterprobe|roster|ground|waterfeat|hdbake|loadwait)
        run_profile "$ACTION"
        ;;
    picklog)
        export SC2_TEST_GROUP=picklog
        build_profile pncprobe
        export SC2_MAP_SOURCE="$OUT_DIR/SCOBA256_pncprobe.SC2Map"
        exec bash "$ROOT_DIR/scripts/launch-scoba.sh"
        ;;
    dissolveview)
        PYTHONPATH="$ROOT_DIR/scripts" run_python -m testkit.profiles.dissolveview
        export SC2_MAP_SOURCE="$OUT_DIR/SCOBA256_dissolveview.SC2Map"
        exec bash "$ROOT_DIR/scripts/launch-scoba.sh"
        ;;
    dropview)
        PYTHONPATH="$ROOT_DIR/scripts" run_python -m testkit.profiles.dropview
        export SC2_MAP_SOURCE="$OUT_DIR/SCOBA256_dropview.SC2Map"
        exec bash "$ROOT_DIR/scripts/launch-scoba.sh"
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

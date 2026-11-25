#!/usr/bin/env bash
# Dependency provisioning for SCOBA. Every subcommand can run again safely.
#
#   venv     uv sync --frozen: the locked Python tooling environment.
#   stormex  build Talv/stormex at the pinned tag, with its dependencies at the
#            pinned tags in STORMEX_DEPS and the patches in
#            scripts/setup/patches/stormex/, and install it to tools/stormex
#            with the pins it was built from in tools/stormex.pins. Skipped
#            when the installed binary reports the pinned version and its
#            pins file matches the current pins.
#   upscale  clone upscale-on-arc next to this repo (if absent), check that it
#            holds the pinned commit, and run its `make install`.
#   nodsdk   build the parser library of the nodsdk-scghost checkout (the
#            StarCraft: Ghost formats; cloned at its pin by make viewer-install)
#            into WEBVIEWER_WORK/build/nodsdk. Needs the GLM headers: sudo
#            make init.
#   photocraft  build the PhotoCraft editor site and renderer at the pins
#            below and install them to PHOTOCRAFT_HOME. The steps are in
#            scripts/setup/photocraft.sh (SPEC-PHOTOCRAFT section 5). Skipped
#            when the install's pin record matches the current pins.
#   check    report every dependency as OK, MISSING or OPTIONAL. Exit 1 when a
#            required one is missing.
#
# make runs this with the paths of scripts/paths.sh (SPEC-PATHS): SC2_BUILD,
# WEBVIEWER_WORK, SC2_INSTALL, PHOTOCRAFT_HOME and UV_PROJECT_ENVIRONMENT
# come from there.
# Other settings:
#   SC2_PROJECT_ROOT  this repo (default: git top level of the working directory)
#   STORMEX           the stormex binary (default: tools/stormex)
#   STORMEX_SRC       the stormex source checkout (default: SC2_BUILD/deps/stormex)
#   STORMEX_PATH      PATH for the stormex build: the system compiler and linker
#                     (default: /usr/local/bin:/usr/bin:/bin)
#   UPSCALE_DIR       the upscale-on-arc checkout (default: ../upscale-on-arc)
#   NODSDK_SRC        the nodsdk-scghost checkout (default: webviewer/ref/nodsdk-scghost)
#   NODSDK_BUILD      its build folder (default: WEBVIEWER_WORK/build/nodsdk)
#   STEAM_ROOT        as in scripts/launch-scoba.sh
set -euo pipefail

STORMEX_REPO="https://github.com/Talv/stormex.git"
STORMEX_TAG="v2.2.0"
STORMEX_COMMIT="1e931794583869bd8f4de9c18a3292a6715034ed"
# stormex is unmaintained (last commit 2019). Its v2.2.0 gitlink for CascLib
# (b2bd4c8) exists in no public repository, so the submodules are not taken
# from the gitlinks. Each one is the latest stable tag of its maintained
# upstream: <path> <url> <tag> <commit the tag names>.
STORMEX_DEPS=(
    "CascLib https://github.com/ladislav-zezula/CascLib.git 3.0 4971d363e665551ac4142f541e5f2d71f1cda653"
    "cxxopts https://github.com/jarro2783/cxxopts.git v3.3.1 44380e5a44706ab7347f400698c703eb2a196202"
    "plog https://github.com/SergiusTheBest/plog.git 1.1.11 e5c033e317a01b2703d13aab42288d09b2efdafc"
)
# PhotoCraft (SPEC-PHOTOCRAFT 5.1): the source, the build's own Rust, Trunk
# by the sha256 of its release archive, and how the renderer is built.
PHOTOCRAFT_REPO="https://github.com/storytold/photocraft.git"
PHOTOCRAFT_TAG="v0.23.1"
PHOTOCRAFT_COMMIT="45066c48292e92229ada3459a83453439514c83d"
PHOTOCRAFT_RUST="1.96.1"
PHOTOCRAFT_HOST="x86_64-unknown-linux-gnu"
PHOTOCRAFT_TRUNK="0.21.14"
PHOTOCRAFT_TRUNK_URL="https://github.com/trunk-rs/trunk/releases/download/v$PHOTOCRAFT_TRUNK/trunk-$PHOTOCRAFT_HOST.tar.gz"
PHOTOCRAFT_TRUNK_SHA256="f2b4680cd239693a646a2795e4633c625328d7b2a044fbe749fa3a2fe9e7036b"
# No default features: the renderer is built without its GPU code (R-PC-59).
PHOTOCRAFT_CLI_BUILD="--release --locked -p photocraft-cli --no-default-features"
UPSCALE_REPO="git@github.com:Modded-Software/upscale-on-arc.git"
# First commit on the remote, 2026-11-22. A checkout must contain it.
UPSCALE_COMMIT="b35fa0784ab610946a239e7a634f4735eac10998"

ROOT_DIR="${SC2_PROJECT_ROOT:-$(git rev-parse --show-toplevel)}"
STORMEX="${STORMEX:-$ROOT_DIR/tools/stormex}"
: "${SC2_BUILD:?SC2_BUILD is not set: run this through make (SPEC-PATHS)}"
: "${WEBVIEWER_WORK:?WEBVIEWER_WORK is not set: run this through make (SPEC-PATHS)}"
: "${SC2_INSTALL:?SC2_INSTALL is not set: run this through make (SPEC-PATHS)}"
: "${PHOTOCRAFT_HOME:?PHOTOCRAFT_HOME is not set: run this through make (SPEC-PATHS)}"
STORMEX_SRC="${STORMEX_SRC:-$SC2_BUILD/deps/stormex}"
STORMEX_PATH="${STORMEX_PATH:-/usr/local/bin:/usr/bin:/bin}"
STORMEX_PATCHES="$ROOT_DIR/scripts/setup/patches/stormex"
UPSCALE_DIR="${UPSCALE_DIR:-$(dirname "$ROOT_DIR")/upscale-on-arc}"
NODSDK_SRC="${NODSDK_SRC:-$ROOT_DIR/webviewer/ref/nodsdk-scghost}"
NODSDK_BUILD="${NODSDK_BUILD:-$WEBVIEWER_WORK/build/nodsdk}"
NODSDK_LIB="$NODSDK_BUILD/cmake/libasset_parsers.a"
NODSDK_SURVEY="$NODSDK_BUILD/cmake/NODSurvey"
NODSDK_EXPORT="$NODSDK_BUILD/cmake/NODExport"
GLM_HEADER=/usr/include/glm/glm.hpp
STEAM_ROOT="${STEAM_ROOT:-$HOME/.var/app/com.valvesoftware.Steam/data/Steam}"
SC2_DIR="$SC2_INSTALL"
LSFG_LAYER="$HOME/.local/share/vulkan/implicit_layer.d/VkLayer_LSFGVK_frame_generation.json"

die() {
    printf 'deps: error: %s\n' "$*" >&2
    exit 1
}

say() {
    printf 'deps: %s\n' "$*"
}

# True when $1 is an executable stormex that reports the pinned version.
stormex_reports_tag() {
    local out
    [[ -x "$1" ]] || return 1
    out="$("$1" --version 2>&1)" || return 1
    [[ "$out" == "stormex $STORMEX_TAG |"* ]]
}

# The pins a stormex build comes from: the stormex commit, every dependency,
# and the sha256 of every patch. deps.sh writes them to $STORMEX.pins.
stormex_pins() {
    local entry patch
    printf 'stormex %s %s\n' "$STORMEX_TAG" "$STORMEX_COMMIT"
    for entry in "${STORMEX_DEPS[@]}"; do
        printf '%s\n' "$entry"
    done
    for patch in "$STORMEX_PATCHES"/*.patch; do
        [[ -f "$patch" ]] || continue
        printf 'patch %s %s\n' "$(basename "$patch")" "$(sha256sum "$patch" | cut -d' ' -f1)"
    done
}

# True when $STORMEX reports the pinned version and was built from the
# current pins. Both builds report "v2.2.0 | CascLib v3.0", so only the pins
# file tells a build from other dependency commits apart.
stormex_is_pinned() {
    stormex_reports_tag "$STORMEX" || return 1
    [[ -f "$STORMEX.pins" ]] || return 1
    [[ "$(<"$STORMEX.pins")" == "$(stormex_pins)" ]]
}

cmd_venv() {
    local uv
    uv="$(command -v uv)" || die "uv is not installed; see https://docs.astral.sh/uv/"
    "$uv" sync --frozen --project "$ROOT_DIR"
}

# Clone each stormex dependency (STORMEX_DEPS) into the checkout at its pinned
# tag, and check the tag still names the pinned commit. This does not use
# `git submodule`, which the workspace shell guard reserves for root.
fetch_stormex_deps() {
    local entry path url tag want have
    for entry in "${STORMEX_DEPS[@]}"; do
        read -r path url tag want <<<"$entry"
        if [[ ! -d "$STORMEX_SRC/$path/.git" ]]; then
            say "cloning $url $tag into $path"
            rm -rf "${STORMEX_SRC:?}/$path"
            git -c advice.detachedHead=false clone --depth 1 --branch "$tag" "$url" "$STORMEX_SRC/$path"
        fi
        have="$(git -C "$STORMEX_SRC/$path" rev-parse HEAD)"
        [[ "$have" == "$want" ]] || die "$path is at $have, not $tag ($want); move it away and run again"
    done
}

# Apply every scripts/setup/patches/stormex/*.patch to the checkout, in name
# order. A patch that is already applied is skipped; one that fits neither way
# stops the build.
apply_stormex_patches() {
    local patch name reverse
    for patch in "$STORMEX_PATCHES"/*.patch; do
        [[ -f "$patch" ]] || continue
        name="$(basename "$patch")"
        if reverse="$(git -C "$STORMEX_SRC" apply --check --reverse "$patch" 2>&1)"; then
            say "patch already applied: $name"
        elif git -C "$STORMEX_SRC" apply "$patch"; then
            say "applied patch: $name"
        else
            die "patch $name does not apply to $STORMEX_SRC (reverse check: $reverse); move the checkout away and run again"
        fi
    done
}

cmd_stormex() {
    if stormex_is_pinned; then
        say "stormex $STORMEX_TAG already installed: $STORMEX"
        return 0
    fi
    local cmake
    cmake="$(command -v cmake)" || die "cmake is not installed"
    pkg-config --exists fuse || die "FUSE 2 headers missing (Ubuntu: libfuse-dev)"
    if [[ ! -d "$STORMEX_SRC/.git" ]]; then
        say "cloning $STORMEX_REPO $STORMEX_TAG into $STORMEX_SRC"
        mkdir -p "$(dirname "$STORMEX_SRC")"
        git clone --branch "$STORMEX_TAG" "$STORMEX_REPO" "$STORMEX_SRC"
    fi
    local head
    head="$(git -C "$STORMEX_SRC" rev-parse HEAD)"
    [[ "$head" == "$STORMEX_COMMIT" ]] \
        || die "$STORMEX_SRC is at $head, not $STORMEX_TAG ($STORMEX_COMMIT); move it away and run again"
    fetch_stormex_deps
    apply_stormex_patches
    # Upstream declares cmake_minimum_required(2.6); CMake 3.27+ needs a floor of 3.5 to configure it.
    # stormex links the system libfuse and zlib, so compiler and linker come
    # from STORMEX_PATH, not from whatever toolchain is first on PATH.
    PATH="$STORMEX_PATH" "$cmake" -S "$STORMEX_SRC" -B "$STORMEX_SRC/build" \
        -DCMAKE_BUILD_TYPE=Release -DCMAKE_POLICY_VERSION_MINIMUM=3.5
    PATH="$STORMEX_PATH" "$cmake" --build "$STORMEX_SRC/build" --parallel "$(nproc)"
    local built="$STORMEX_SRC/build/bin/stormex"
    stormex_reports_tag "$built" || die "the build at $built does not report stormex $STORMEX_TAG"
    mkdir -p "$(dirname "$STORMEX")"
    install -m 755 "$built" "$STORMEX"
    stormex_pins >"$STORMEX.pins"
    say "installed stormex $STORMEX_TAG: $STORMEX"
}

cmd_upscale() {
    if [[ ! -d "$UPSCALE_DIR/.git" ]]; then
        [[ ! -e "$UPSCALE_DIR" ]] || die "$UPSCALE_DIR exists but is not a git checkout"
        say "cloning $UPSCALE_REPO into $UPSCALE_DIR"
        git clone "$UPSCALE_REPO" "$UPSCALE_DIR"
    fi
    git -C "$UPSCALE_DIR" merge-base --is-ancestor "$UPSCALE_COMMIT" HEAD \
        || die "$UPSCALE_DIR does not contain the pinned commit ${UPSCALE_COMMIT:0:8}; pull it"
    make -C "$UPSCALE_DIR" install
}

# The parser library only: no viewer, no editors, no tests. The compiler
# and linker come from STORMEX_PATH, as for stormex: GLM is a system package.
cmd_nodsdk() {
    local cmake
    cmake="$(command -v cmake)" || die "cmake is not installed"
    [[ -d "$NODSDK_SRC/.git" ]] || die "no nodsdk-scghost checkout at $NODSDK_SRC; run: make viewer-install"
    [[ -f "$GLM_HEADER" ]] || die "GLM headers missing ($GLM_HEADER); run: sudo make init"
    PATH="$STORMEX_PATH" "$cmake" -S "$NODSDK_SRC" -B "$NODSDK_BUILD" -DCMAKE_BUILD_TYPE=Release \
        -DNODSDK_BUILD_VIEWER=OFF -DNODSDK_BUILD_EDITORS=OFF -DBUILD_TESTING=OFF
    PATH="$STORMEX_PATH" "$cmake" --build "$NODSDK_BUILD" --target asset_parsers NODSurvey NODExport --parallel "$(nproc)"
    [[ -f "$NODSDK_LIB" ]] || die "the build did not write $NODSDK_LIB"
    [[ -x "$NODSDK_SURVEY" ]] || die "the build did not write $NODSDK_SURVEY"
    [[ -x "$NODSDK_EXPORT" ]] || die "the build did not write $NODSDK_EXPORT"
    say "built the nodsdk parser library, NODSurvey and NODExport: $NODSDK_BUILD/cmake"
}

# cmd_photocraft and photocraft_report: the PhotoCraft steps. Found from the
# repo root: make starts this script through a guarded shell that hides the
# script's own path.
# shellcheck source=scripts/setup/photocraft.sh
source "$ROOT_DIR/scripts/setup/photocraft.sh" || exit 1

# --- check -------------------------------------------------------------------

MISSING=0

report() {  # report <OK|MISSING|OPTIONAL> <name> <detail>
    printf '%-9s %-14s %s\n' "$1" "$2" "$3"
    [[ "$1" != "MISSING" ]] || MISSING=$((MISSING + 1))
}

check_tool() {  # check_tool <required|optional> <name> <hint>
    local path
    if path="$(command -v "$2")"; then
        report OK "$2" "$path"
    elif [[ "$1" == "required" ]]; then
        report MISSING "$2" "$3"
    else
        report OPTIONAL "$2" "not found; $3"
    fi
}

cmd_check() {
    check_tool required git "install git"
    check_tool required uv "see https://docs.astral.sh/uv/"
    check_tool required node "needed by the model viewer (make viewer-install)"
    check_tool required npm "needed by the model viewer (make viewer-install)"
    check_tool required cmake "needed to build stormex"
    local cxx
    if cxx="$(PATH="$STORMEX_PATH" command -v c++)"; then
        report OK c++ "$cxx"
    else
        report MISSING c++ "no system C++ compiler on $STORMEX_PATH, needed to build stormex"
    fi
    if pkg-config --exists fuse; then
        report OK fuse "libfuse $(pkg-config --modversion fuse)"
    else
        report MISSING fuse "FUSE 2 headers, needed to build stormex (Ubuntu: libfuse-dev)"
    fi
    if stormex_is_pinned; then
        report OK stormex "$STORMEX ($STORMEX_TAG)"
    else
        report MISSING stormex "$STORMEX is absent, not $STORMEX_TAG, or not built from the current pins; run: make install-deps"
    fi
    if [[ -f "$GLM_HEADER" ]]; then
        report OK glm "$GLM_HEADER"
    else
        report MISSING glm "GLM headers, needed to build the nodsdk parsers; run: sudo make init"
    fi
    if [[ -f "$NODSDK_LIB" && -x "$NODSDK_SURVEY" && -x "$NODSDK_EXPORT" ]]; then
        report OK nodsdk "$NODSDK_BUILD/cmake"
    else
        report MISSING nodsdk "the nodsdk parser library is not built; run: make install-deps"
    fi
    if [[ -f "$SC2_DIR/StarCraft II.exe" ]]; then
        report OK starcraft2 "$SC2_DIR"
    else
        report MISSING starcraft2 "no StarCraft II.exe in $SC2_DIR; set BNET_PREFIX in env/paths.conf"
    fi
    local proton=""
    local candidate
    for candidate in "$STEAM_ROOT"/compatibilitytools.d/GE-Proton*/; do
        [[ -x "$candidate/proton" ]] && { proton="${candidate%/}"; break; }
    done
    if [[ -n "$proton" ]]; then
        report OK ge-proton "$proton"
    else
        report MISSING ge-proton "no GE-Proton under $STEAM_ROOT/compatibilitytools.d"
    fi
    if [[ -f "$LSFG_LAYER" ]]; then
        report OK lsfg-vk "$LSFG_LAYER"
    else
        report OPTIONAL lsfg-vk "layer not installed; only the SCOBA FG entry needs it"
    fi
    if [[ -x "$UPSCALE_DIR/arc-upscale" ]]; then
        report OK upscale-on-arc "$UPSCALE_DIR"
    else
        report OPTIONAL upscale-on-arc "not at $UPSCALE_DIR; only a texture request needs it (make install-hdtex)"
    fi
    photocraft_report
    if [[ "$MISSING" -gt 0 ]]; then
        say "$MISSING required dependencies missing"
        return 1
    fi
    say "all required dependencies present"
}

case "${1:-}" in
    venv) cmd_venv ;;
    stormex) cmd_stormex ;;
    upscale) cmd_upscale ;;
    nodsdk) cmd_nodsdk ;;
    photocraft) cmd_photocraft ;;
    check) cmd_check ;;
    *) die "usage: deps.sh venv|stormex|upscale|nodsdk|photocraft|check" ;;
esac

# PhotoCraft provisioning (SPEC-PHOTOCRAFT section 5). Sourced by deps.sh, not run.
#
# Builds the editor site (WebAssembly, with Trunk) and the renderer
# (photocraft-cli, for this machine) from one clone at the pinned commit,
# with the patches of scripts/setup/patches/photocraft/, and installs both
# to PHOTOCRAFT_HOME with the pins they were built from.
#
# Each build makes a fresh build tree: a local git clone of the first clone,
# at the pinned tag, checked against the pinned commit. The patches are
# applied to that tree with git, inside a work tree, as the workspace's git
# guard asks. The first clone's HEAD and its working files are not read, so
# a pull or an edit there changes no build. These steps write nothing into
# the first clone after the clone step. They do not stop anyone else from
# changing it; a first clone that lost the tag or the commit is an error.
#
# From deps.sh: die, say, ROOT_DIR, SC2_BUILD, PHOTOCRAFT_HOME and the pins
# PHOTOCRAFT_REPO, _TAG, _COMMIT, _RUST, _HOST, _TRUNK, _TRUNK_URL,
# _TRUNK_SHA256 and _CLI_BUILD.
# Other settings:
#   PHOTOCRAFT_SRC     the clone (default: SC2_BUILD/deps/photocraft)
#   PHOTOCRAFT_TREE    the build tree (default: SC2_BUILD/deps/photocraft-tree)
#   PHOTOCRAFT_TOOLS   the build's own Rust toolchain, Cargo home, Trunk and
#                      Trunk's tools (default: SC2_BUILD/deps/photocraft-tools)
#   PHOTOCRAFT_TARGET  Cargo's build folder (default: SC2_BUILD/deps/photocraft-target)
#   PHOTOCRAFT_LOGS    one log per step (default: SC2_BUILD/deps/photocraft-logs)
#   PHOTOCRAFT_PATH    PATH of the system tools the build needs: git, curl,
#                      tar, and the system cc and ld that link the build
#                      scripts (default: /usr/local/bin:/usr/bin:/bin). Not
#                      the caller's PATH: a cc found there first linked
#                      against another libc and failed.
#   PHOTOCRAFT_RUSTUP  the rustup that installs the build's own toolchain
#                      (default: the rustup on PATH)

PHOTOCRAFT_SRC="${PHOTOCRAFT_SRC:-$SC2_BUILD/deps/photocraft}"
PHOTOCRAFT_TREE="${PHOTOCRAFT_TREE:-$SC2_BUILD/deps/photocraft-tree}"
PHOTOCRAFT_TOOLS="${PHOTOCRAFT_TOOLS:-$SC2_BUILD/deps/photocraft-tools}"
PHOTOCRAFT_TARGET="${PHOTOCRAFT_TARGET:-$SC2_BUILD/deps/photocraft-target}"
PHOTOCRAFT_LOGS="${PHOTOCRAFT_LOGS:-$SC2_BUILD/deps/photocraft-logs}"
PHOTOCRAFT_PATH="${PHOTOCRAFT_PATH:-/usr/local/bin:/usr/bin:/bin}"
PHOTOCRAFT_RUSTUP="${PHOTOCRAFT_RUSTUP:-rustup}"
PHOTOCRAFT_PATCHES="$ROOT_DIR/scripts/setup/patches/photocraft"
PHOTOCRAFT_RUST_BIN="$PHOTOCRAFT_TOOLS/rustup/toolchains/$PHOTOCRAFT_RUST-$PHOTOCRAFT_HOST/bin"
PHOTOCRAFT_DIST="$PHOTOCRAFT_TREE/dist/web"
PHOTOCRAFT_BUILT_CLI="$PHOTOCRAFT_TARGET/release/photocraft-cli"
# Upstream's licence, notice and attribution files, installed with the site.
PHOTOCRAFT_LICENCES=(LICENSE-APACHE LICENSE-MIT NOTICE ATTRIBUTION.md)
# The site asks for fonts/manifest.txt at each start. Upstream takes a 404
# as "no fonts", and the browser logs it as an error. The install holds a
# manifest of this one comment line instead: no fonts are served.
PHOTOCRAFT_FONTS="# No fonts are served with this install (SPEC-PHOTOCRAFT)."

# The pins an install comes from. deps.sh writes them to photocraft.pins.
photocraft_pins() {
    local patch
    printf 'photocraft %s %s\n' "$PHOTOCRAFT_TAG" "$PHOTOCRAFT_COMMIT"
    printf 'rust %s %s wasm32-unknown-unknown\n' "$PHOTOCRAFT_RUST" "$PHOTOCRAFT_HOST"
    printf 'trunk %s %s\n' "$PHOTOCRAFT_TRUNK" "$PHOTOCRAFT_TRUNK_SHA256"
    printf 'renderer %s\n' "$PHOTOCRAFT_CLI_BUILD"
    printf 'fonts none\n'
    for patch in "$PHOTOCRAFT_PATCHES"/*.patch; do
        [[ -f "$patch" ]] || continue
        printf 'patch %s %s\n' "$(basename "$patch")" "$(sha256sum "$patch" | cut -d' ' -f1)"
    done
}

# Prints the state of the install: "absent", "pinned", or "stale: <what differs>".
photocraft_state() {
    local record="$PHOTOCRAFT_HOME/photocraft.pins" want have line
    if [[ ! -f "$record" || ! -f "$PHOTOCRAFT_HOME/site/index.html" || ! -x "$PHOTOCRAFT_HOME/bin/photocraft-cli" ]]; then
        printf 'absent\n'
        return 0
    fi
    want="$(photocraft_pins)"
    have="$(<"$record")"
    if [[ "$have" == "$want" ]]; then
        printf 'pinned\n'
        return 0
    fi
    while IFS= read -r line; do
        if [[ $'\n'"$have"$'\n' != *$'\n'"$line"$'\n'* ]]; then
            printf 'stale: built without the pin "%s"\n' "$line"
            return 0
        fi
    done <<<"$want"
    printf 'stale: built with a pin that is gone\n'
}

# A command with the build's own toolchain and caches, and nothing of the
# shared ones: the Rust of PHOTOCRAFT_TOOLS first on PATH.
photocraft_env() {
    env RUSTUP_HOME="$PHOTOCRAFT_TOOLS/rustup" CARGO_HOME="$PHOTOCRAFT_TOOLS/cargo" \
        CARGO_TARGET_DIR="$PHOTOCRAFT_TARGET" XDG_CACHE_HOME="$PHOTOCRAFT_TOOLS/cache" \
        PATH="$PHOTOCRAFT_TOOLS/bin:$PHOTOCRAFT_RUST_BIN:$PHOTOCRAFT_PATH" "$@"
}

# One step with its own log. A failed step stops the command and names both.
# The step runs inside `if`, where `set -e` is off: each step returns 1 itself.
photocraft_step() {  # photocraft_step <name> <function>
    local name="$1" log="$PHOTOCRAFT_LOGS/$1.log" started=$SECONDS
    say "photocraft: $name"
    if ! "$2" >"$log" 2>&1; then
        die "photocraft: step '$name' failed; log: $log"
    fi
    say "photocraft: $name done in $((SECONDS - started)) s"
}

photocraft_toolchain() {
    local rustup
    rustup="$(command -v "$PHOTOCRAFT_RUSTUP")" || { echo "rustup is not installed: $PHOTOCRAFT_RUSTUP"; return 1; }
    RUSTUP_HOME="$PHOTOCRAFT_TOOLS/rustup" CARGO_HOME="$PHOTOCRAFT_TOOLS/cargo" PATH="$PHOTOCRAFT_PATH" \
        "$rustup" toolchain install "$PHOTOCRAFT_RUST" --profile minimal \
        --target wasm32-unknown-unknown --no-self-update || return 1
    [[ -x "$PHOTOCRAFT_RUST_BIN/cargo" ]] || { echo "rustup left no cargo at $PHOTOCRAFT_RUST_BIN"; return 1; }
}

photocraft_trunk() {
    local archive="$PHOTOCRAFT_TOOLS/trunk-$PHOTOCRAFT_TRUNK.tar.gz" have
    mkdir -p "$PHOTOCRAFT_TOOLS/bin" || return 1
    if [[ ! -f "$archive" ]]; then
        PATH="$PHOTOCRAFT_PATH" curl -fsSL -o "$archive.part" "$PHOTOCRAFT_TRUNK_URL" || return 1
        mv "$archive.part" "$archive" || return 1
    fi
    # The hash is the first word sha256sum prints.
    have="$(sha256sum "$archive")" || return 1
    have="${have%% *}"
    if [[ "$have" != "$PHOTOCRAFT_TRUNK_SHA256" ]]; then
        echo "the Trunk archive has sha256 $have, not $PHOTOCRAFT_TRUNK_SHA256; delete $archive and run again"
        return 1
    fi
    PATH="$PHOTOCRAFT_PATH" tar -xzf "$archive" -C "$PHOTOCRAFT_TOOLS/bin" trunk || return 1
}

# The clone must hold the pinned commit. Its HEAD is not asked: the build
# exports the commit by its id. A tag that upstream moved gives a clone
# without the commit, and that is an error.
photocraft_clone() {
    if [[ ! -d "$PHOTOCRAFT_SRC/.git" ]]; then
        mkdir -p "$(dirname "$PHOTOCRAFT_SRC")" || return 1
        PATH="$PHOTOCRAFT_PATH" git -c advice.detachedHead=false clone --depth 1 \
            --branch "$PHOTOCRAFT_TAG" "$PHOTOCRAFT_REPO" "$PHOTOCRAFT_SRC" || return 1
    fi
    if ! PATH="$PHOTOCRAFT_PATH" git -C "$PHOTOCRAFT_SRC" cat-file -e "$PHOTOCRAFT_COMMIT^{commit}"; then
        echo "$PHOTOCRAFT_SRC does not hold $PHOTOCRAFT_TAG ($PHOTOCRAFT_COMMIT); move it away and run again"
        return 1
    fi
}

# A fresh build tree: a local clone of the first clone at the pinned tag,
# then every patch in name order. The old tree is deleted whole: it is this
# script's own output. A tag that names another commit is an error.
photocraft_tree() {
    local patch head
    rm -rf "$PHOTOCRAFT_TREE" || return 1
    PATH="$PHOTOCRAFT_PATH" git -c advice.detachedHead=false clone --depth 1 \
        --branch "$PHOTOCRAFT_TAG" "file://$PHOTOCRAFT_SRC" "$PHOTOCRAFT_TREE" || return 1
    head="$(PATH="$PHOTOCRAFT_PATH" git -C "$PHOTOCRAFT_TREE" rev-parse HEAD)" || return 1
    if [[ "$head" != "$PHOTOCRAFT_COMMIT" ]]; then
        echo "$PHOTOCRAFT_TAG in $PHOTOCRAFT_SRC names $head, not $PHOTOCRAFT_COMMIT; move the clone away and run again"
        return 1
    fi
    for patch in "$PHOTOCRAFT_PATCHES"/*.patch; do
        [[ -f "$patch" ]] || continue
        if ! PATH="$PHOTOCRAFT_PATH" git -C "$PHOTOCRAFT_TREE" apply "$patch"; then
            echo "patch $(basename "$patch") does not apply to $PHOTOCRAFT_TAG"
            return 1
        fi
        echo "applied patch: $(basename "$patch")"
    done
}

photocraft_build_site() {
    rm -rf "$PHOTOCRAFT_DIST" || return 1
    (cd "$PHOTOCRAFT_TREE/apps/photocraft-web" && photocraft_env trunk build --release --locked) || return 1
}

photocraft_build_cli() {
    local -a build
    read -r -a build <<<"$PHOTOCRAFT_CLI_BUILD"
    (cd "$PHOTOCRAFT_TREE" && photocraft_env cargo build "${build[@]}") || return 1
}

photocraft_check_site() {
    local page file size
    local -a scripts modules
    [[ -f "$PHOTOCRAFT_DIST/index.html" ]] || { echo "the build left no $PHOTOCRAFT_DIST/index.html"; return 1; }
    scripts=("$PHOTOCRAFT_DIST"/*.js)
    modules=("$PHOTOCRAFT_DIST"/*.wasm)
    [[ -f "${scripts[0]}" ]] || { echo "the build left no script in $PHOTOCRAFT_DIST"; return 1; }
    if [[ "${#modules[@]}" -ne 1 || ! -f "${modules[0]}" ]]; then
        echo "the build left ${#modules[@]} .wasm files in $PHOTOCRAFT_DIST, not one"
        return 1
    fi
    size="$(stat -c %s "${modules[0]}")" || return 1
    if [[ "$size" -le 1048576 ]]; then
        echo "${modules[0]} has $size bytes: too small for the editor"
        return 1
    fi
    page="$(<"$PHOTOCRAFT_DIST/index.html")"
    if [[ "$page" == *'src="/'* || "$page" == *'href="/'* ]]; then
        echo "index.html names an address that starts at the root: the site would not work below a path"
        return 1
    fi
    for file in "${PHOTOCRAFT_LICENCES[@]}"; do
        [[ -f "$PHOTOCRAFT_TREE/$file" ]] || { echo "the pinned commit has no $file"; return 1; }
    done
    echo "site: ${modules[0]} $size bytes"
}

# The renderer does what the pipeline needs of it (SPEC-PHOTOCRAFT section 10):
# two pictures become two named groups of one PSD, and each group is written
# back as its own picture. The pixels are compared by the host tests.
photocraft_check_cli() {
    local cli="$PHOTOCRAFT_BUILT_CLI" work="$PHOTOCRAFT_TARGET/renderer-check"
    [[ -x "$cli" ]] || { echo "the build left no $cli"; return 1; }
    "$cli" --version || return 1
    rm -rf "$work" || return 1
    mkdir -p "$work/planes" || return 1
    "$cli" run --new '{"width":8,"height":8,"background":"#ff0000"}' --out "$work/a.png" --no-gpu || return 1
    "$cli" run --new '{"width":8,"height":8,"background":"#0000ff"}' --out "$work/b.png" --no-gpu || return 1
    "$cli" run --new '{"width":1,"height":1}' \
        --cmd file.scripts.loadFilesIntoStack --params "{\"paths\":[\"$work/a.png\",\"$work/b.png\"]}" \
        --cmd layer.select --params '{"name":"a.png"}' --cmd layer.groupLayers --params '{"name":"a"}' \
        --cmd layer.select --params '{"name":"b.png"}' --cmd layer.groupLayers --params '{"name":"b"}' \
        --out "$work/check.psd" --no-gpu || return 1
    "$cli" run "$work/check.psd" --cmd file.export.layersToFiles \
        --params "{\"dir\":\"$work/planes\",\"format\":\"png\",\"visibleOnly\":false,\"prefix\":\"plane\"}" \
        --no-gpu || return 1
    if [[ ! -f "$work/planes/plane_0000_b.png" || ! -f "$work/planes/plane_0001_a.png" ]]; then
        echo "the renderer did not write one picture per group into $work/planes"
        return 1
    fi
}

# Both results into a new folder, then swapped in by rename. A step that
# failed before this one leaves the old install as it is.
photocraft_install() {
    local new="$PHOTOCRAFT_HOME.new" old="$PHOTOCRAFT_HOME.old" file
    rm -rf "$new" "$old" || return 1
    mkdir -p "$new/bin" || return 1
    cp -r "$PHOTOCRAFT_DIST" "$new/site" || return 1
    for file in "${PHOTOCRAFT_LICENCES[@]}"; do
        cp "$PHOTOCRAFT_TREE/$file" "$new/site/$file" || return 1
    done
    mkdir -p "$new/site/fonts" || return 1
    printf '%s\n' "$PHOTOCRAFT_FONTS" >"$new/site/fonts/manifest.txt" || return 1
    install -m 755 "$PHOTOCRAFT_BUILT_CLI" "$new/bin/photocraft-cli" || return 1
    photocraft_pins >"$new/photocraft.pins" || return 1
    if [[ -e "$PHOTOCRAFT_HOME" ]]; then
        mv "$PHOTOCRAFT_HOME" "$old" || return 1
    fi
    mv "$new" "$PHOTOCRAFT_HOME" || return 1
    rm -rf "$old" || return 1
}

cmd_photocraft() {
    if [[ "$(photocraft_state)" == "pinned" ]]; then
        say "photocraft present: $PHOTOCRAFT_HOME ($PHOTOCRAFT_TAG)"
        return 0
    fi
    mkdir -p "$PHOTOCRAFT_LOGS" "$PHOTOCRAFT_TOOLS"
    photocraft_step toolchain photocraft_toolchain
    photocraft_step trunk photocraft_trunk
    photocraft_step clone photocraft_clone
    photocraft_step tree photocraft_tree
    photocraft_step build-site photocraft_build_site
    photocraft_step build-renderer photocraft_build_cli
    photocraft_step check-site photocraft_check_site
    photocraft_step check-renderer photocraft_check_cli
    photocraft_step install photocraft_install
    say "installed photocraft $PHOTOCRAFT_TAG: $PHOTOCRAFT_HOME"
}

# For deps.sh check: installs nothing.
photocraft_report() {
    local state
    state="$(photocraft_state)"
    case "$state" in
        pinned) report OK photocraft "$PHOTOCRAFT_HOME ($PHOTOCRAFT_TAG)" ;;
        absent) report OPTIONAL photocraft "not installed; only texture editing needs it (make install-photocraft)" ;;
        *) report OPTIONAL photocraft "$state; run: make install-photocraft" ;;
    esac
}

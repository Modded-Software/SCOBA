#!/usr/bin/env bash
set -euo pipefail

if [ -n "${SC2_PROJECT_ROOT:-}" ] && [ -f "$SC2_PROJECT_ROOT/scripts/build.sh" ]; then
    ROOT_DIR="$SC2_PROJECT_ROOT"
elif [ -f "$PWD/scripts/build.sh" ]; then
    ROOT_DIR="$PWD"
else
    ROOT_DIR="$(cd -- "$(dirname -- "$0")/.." && pwd)"
fi
if [ "${SC2_PLAYTEST_ACTIVE:-}" != "1" ]; then
    exec bash "$ROOT_DIR/scripts/playtest.sh" build
fi
# shellcheck source=paths.sh
source "$ROOT_DIR/scripts/paths.sh" || exit 1
paths_check_device
OUT_DIR="$SC2_OUT"
FINAL="$SC2_BUILT_MAP"
TMP="$OUT_DIR/.build-tmp"
OLD="$OUT_DIR/.build-old"
cd "$ROOT_DIR"

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

py() {
    "$UV_BIN" run python "$@"
}

log() {
    printf '%s\n' "$*"
}

fail() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

BOOTSTRAP="$ROOT_DIR/src/SCOBA.SC2Map/MapScript.galaxy"
grep -q 'include "scripts/app/main"' "$BOOTSTRAP" \
    || fail "$BOOTSTRAP lost its scripts/app/main include; restore it from git"

mkdir -p "$OUT_DIR"
exec 9>"$OUT_DIR/.build.lock"
if ! flock -n 9; then
    fail "another build is running"
fi

cleanup() {
    rm -rf "$TMP"
}
trap cleanup EXIT

rm -rf "$TMP" "$OLD"
log "expanding map"
py "$ROOT_DIR/scripts/expand_map.py" --out "$TMP"

log "normalizing line endings"
while IFS= read -r -d '' file; do
    py "$ROOT_DIR/scripts/normalize_eol.py" "$file" crlf >>"$OUT_DIR/.build.log"
done < <(find "$TMP" -type f \( -name '*.xml' -o -name '*.galaxy' -o -name '*.SC2Layout' -o -name '*.SC2Style' -o -name '*.txt' \) -print0)

log "writing build stamp"
STAMP="$(py "$ROOT_DIR/scripts/build-stamp.py" "$ROOT_DIR/src/SCOBA.SC2Map" "$TMP")"
log "stamp: $STAMP"

log "writing manifest"
: >"$TMP/BuildManifest.txt"
while IFS= read -r -d '' file; do
    rel="${file#"$TMP"/}"
    (cd "$TMP" && sha256sum "$rel") >>"$TMP/BuildManifest.txt"
# Byte order, so the manifest and its hash do not depend on the disk's
# directory order (the same map gave two hashes on two disks).
done < <(find "$TMP" -type f ! -name 'BuildManifest.txt' -print0 | LC_ALL=C sort -z)

log "validating map"
py "$ROOT_DIR/scripts/validate-map.py" "$TMP"

if [ -e "$FINAL" ]; then
    mv "$FINAL" "$OLD"
fi
mv "$TMP" "$FINAL"
rm -rf "$OLD"
trap - EXIT

log "OK: $FINAL"
printf '%s\n' "$STAMP" >"$SC2_BUILD_STAMP"
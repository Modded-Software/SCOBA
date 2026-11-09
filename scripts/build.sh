#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$PWD"
if [ ! -f "$ROOT_DIR/scripts/build.sh" ]; then
    ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
fi
OUT_DIR="$ROOT_DIR/out"
FINAL="$OUT_DIR/SCOBA256.SC2Map"
TMP="$OUT_DIR/.build-tmp"
OLD="$OUT_DIR/.build-old"
cd "$ROOT_DIR"

py() {
    uv run python "$@"
}

log() {
    printf '%s\n' "$*"
}

fail() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

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
done < <(find "$TMP" -type f ! -name 'BuildManifest.txt' -print0)

log "validating map"
py "$ROOT_DIR/scripts/validate-map.py" "$TMP"

if [ -e "$FINAL" ]; then
    mv "$FINAL" "$OLD"
fi
mv "$TMP" "$FINAL"
rm -rf "$OLD"
trap - EXIT

log "OK: $FINAL"
printf '%s\n' "$STAMP" >"$OUT_DIR/.last-build-stamp"
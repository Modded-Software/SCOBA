#!/usr/bin/env bash
# Checks NODExport (our nodsdk-scghost fork) on the StarCraft: Ghost build:
# every model and clip exports, the binary sizes match their description,
# every material name resolves, and changed files are refused with a
# message (SPEC-VIEWER-GHOST 7). Exports go to build/exports/. Exit 0 only
# when every check holds.
set -euo pipefail
WEBVIEWER_DIR="${WEBVIEWER_DIR:-$(git rev-parse --show-toplevel)/webviewer}"
source "$WEBVIEWER_DIR/scripts/paths.sh" || exit 1

if [[ -z "$GHOST_PATH" ]]; then
  echo "ERROR: GHOST_PATH is not set; set it in webviewer/local.env" >&2
  exit 1
fi
if [[ ! -d "$GHOST_PATH/3D/Models" || ! -d "$GHOST_PATH/3D/Anims" ]]; then
  echo "ERROR: GHOST_PATH ($GHOST_PATH) has no 3D/Models or 3D/Anims" >&2
  exit 1
fi
EXPORT="$WEBVIEWER_DIR/build/nodsdk/cmake/NODExport"
if [[ ! -x "$EXPORT" ]]; then
  echo "ERROR: $EXPORT is not built; run: make install-deps" >&2
  exit 1
fi
OUT="$WEBVIEWER_DIR/build/exports"
rm -rf "$OUT"
mkdir -p "$OUT/nod" "$OUT/nad" "$OUT/bad"

failures=0
ok() { echo "ok    $1"; }
fail() { echo "FAIL  $1"; failures=$((failures + 1)); }
check() {  # check <true|false> <what it states>
  if [[ "$1" == "true" ]]; then ok "$2"; else fail "$2"; fi
}
holds() {  # holds <what it states> <command...>: the command's exit decides
  local what="$1"
  shift
  if "$@"; then ok "$what"; else fail "$what"; fi
}

# The parsers log each file to the console; that goes to a log file.
nodRefused=0
for f in "$GHOST_PATH"/3D/Models/*.nod; do
  b="$(basename "$f" .nod)"
  "$EXPORT" nod "$f" "$OUT/nod/$b.json" "$OUT/nod/$b.bin" >> "$OUT/nod.log" 2>&1 || nodRefused=$((nodRefused + 1))
done
nadRefused=0
for f in "$GHOST_PATH"/3D/Anims/*.nad; do
  b="$(basename "$f" .nad)"
  "$EXPORT" nad "$f" "$OUT/nad/$b.json" >> "$OUT/nad.log" 2>&1 || nadRefused=$((nadRefused + 1))
done
holds "all 1401 models export ($nodRefused refused)" test "$nodRefused" -eq 0
holds "all 1551 clips export ($nadRefused refused)" test "$nadRefused" -eq 0

# Every binary is vertexCount x 52 bytes of vertices, then indexCount x 4.
badSize=0
for j in "$OUT"/nod/*.json; do
  want="$(jq '.vertexCount * .vertexStride + .indexCount * 4' "$j")"
  got="$(stat -c %s "${j%.json}.bin")"
  [[ "$want" == "$got" ]] || badSize=$((badSize + 1))
done
holds "every model binary has the size its description gives ($badSize differ)" test "$badSize" -eq 0
check "$(jq -s '[.[] | .groups[] | select(.firstIndex + .indexCount > 0)] | length > 0' "$OUT"/nod/crate.json)" "crate.nod has triangles"
check "$(jq '.groups | length == 1 and .[0].bones == [0] and .[0].indexCount % 3 == 0' "$OUT/nod/crate.json")" "crate.nod: one rigid group on bone 0, whole triangles"
check "$(jq '(.bones | length) == 32 and ([.groups[].vertexType] | sort) == [0, 1, 1, 2]' "$OUT/nod/zergling.json")" "zergling.nod: 32 bones; groups on vertex types 0, 1, 1, 2"
check "$(jq '.length == 59 and (.tracks | length) == 40 and ([.tracks[].keys[-1][7]] | all(. == null))' "$OUT/nad/zergling_stand.json")" "zergling_stand.nad: 59 frames, 40 tracks, last keys end the curve"

# Materials: every model material name gets a lookup step.
jq -r '.materials[]' "$OUT"/nod/*.json | sort -u > "$OUT/names.txt"
"$EXPORT" materials "$GHOST_PATH" "$OUT/names.txt" "$OUT/materials.json" >> "$OUT/materials.log" 2>&1 || fail "materials export exit $?"
check "$(jq --argjson n "$(wc -l < "$OUT/names.txt")" '(.materials | length) == $n' "$OUT/materials.json")" "every model material name is in the materials export"
check "$(jq '[.materials[] | select(.name == "zergling" or .name == "chestCrate2") | .step] == ["texture", "texture"]' "$OUT/materials.json")" "zergling and chestCrate2 resolve to a texture of the same name"
check "$(jq '[.materials[] | select(.name == "collide") | .step] == ["none"]' "$OUT/materials.json")" "collide resolves to nothing"
check "$(jq '[.materials[] | select(.step == "archive") | .source | startswith("Materials/")] | all' "$OUT/materials.json")" "every archive material names its archive file"

# Catalog: templates, motion sets and model headers of the whole build.
"$EXPORT" catalog "$GHOST_PATH" "$OUT/catalog.json" >> "$OUT/catalog.log" 2>&1 || fail "catalog export exit $?"
cat="$OUT/catalog.json"
check "$(jq '(.templates | length) == 1223 and [.refusedTemplates[].name] == ["scourge_track"]' "$cat")" "catalog: 1223 templates; scourge_track refused"
check "$(jq '[.templates[] | select(.model)] | length == 858' "$cat")" "catalog: 858 templates with a model"
check "$(jq '([.templates[] | select(.motionSet)] | length) == 426 and ([.templates[] | select(.motionSet and (.model | not))] | length) == 0' "$cat")" "catalog: 426 templates with a motion set, all with a model"
check "$(jq '(.motionSets | length) == 163 and ([.motionSets[].entries[]] | length) == 2027 and (.refusedMotionSets | length) == 0' "$cat")" "catalog: 163 motion sets, 2027 entries"
check "$(jq '(.models | length) == 1401 and (.refusedModels | length) == 0' "$cat")" "catalog: 1401 models, none refused"
check "$(jq '[.models[] | select(.file == "zergling.nod")][0] | .bones == 32 and .groups == 4 and .vertexTypes == [0, 1, 2]' "$cat")" "catalog: zergling.nod header counts"
check "$(jq '[.models[] | select(.file == "crate.nod")][0] | .vertexTypes == [0]' "$cat")" "catalog: crate.nod is rigid only"
mkdir -p "$OUT/bad/nomodels"
code=0
"$EXPORT" catalog "$OUT/bad/nomodels" "$OUT/bad/catalog.json" > "$OUT/bad/catalog.log" 2>&1 || code=$?
catalogRefused() { [[ $code -eq 1 ]] && jq -e '.error | contains("no 3D/Models")' "$OUT/bad/catalog.json" > "$OUT/bad/catalog.check"; }
holds "refused: catalog of a folder without 3D/Models" catalogRefused

# Refusals: a changed copy of a real file is refused, with a message.
refused() {  # refused <name> <file> <expected message part> <mode args...>
  local name="$1" file="$2" want="$3"
  shift 3
  local code=0
  "$EXPORT" "$@" > "$OUT/bad/$name.log" 2>&1 || code=$?
  if [[ "$code" -eq 1 ]] && jq -e --arg w "$want" '.error | contains($w)' "$file" > "$OUT/bad/$name.check"; then
    ok "refused: $name ($(jq -r .error "$file"))"
  else
    fail "refused: $name (exit $code, $(cat "$file"))"
  fi
}
crate="$GHOST_PATH/3D/Models/crate.nod"
cp "$crate" "$OUT/bad/version.nod"
printf '\x09' | dd of="$OUT/bad/version.nod" bs=1 seek=0 conv=notrunc status=none
refused version "$OUT/bad/version.json" "version 9" nod "$OUT/bad/version.nod" "$OUT/bad/version.json" "$OUT/bad/version.bin"
cp "$crate" "$OUT/bad/vtype.nod"
printf '\x06' | dd of="$OUT/bad/vtype.nod" bs=1 seek=36 conv=notrunc status=none
refused vertex-type "$OUT/bad/vtype.json" "vertex type" nod "$OUT/bad/vtype.nod" "$OUT/bad/vtype.json" "$OUT/bad/vtype.bin"
dd if="$crate" of="$OUT/bad/cut.nod" bs=1 count=3000 status=none
refused cut-model "$OUT/bad/cut.json" "Truncated" nod "$OUT/bad/cut.nod" "$OUT/bad/cut.json" "$OUT/bad/cut.bin"
cp "$crate" "$OUT/bad/extra.nod"
printf 'XXXX' >> "$OUT/bad/extra.nod"
refused extra-bytes "$OUT/bad/extra.json" "bytes the layout does not explain" nod "$OUT/bad/extra.nod" "$OUT/bad/extra.json" "$OUT/bad/extra.bin"
noBinary() { [[ ! -e "$OUT/bad/version.bin" && ! -e "$OUT/bad/cut.bin" ]]; }
holds "a refused model writes no binary" noBinary
clip="$GHOST_PATH/3D/Anims/zergling_stand.nad"
cp "$clip" "$OUT/bad/version.nad"
printf '\x03' | dd of="$OUT/bad/version.nad" bs=1 seek=0 conv=notrunc status=none
refused clip-version "$OUT/bad/version-nad.json" "version 3" nad "$OUT/bad/version.nad" "$OUT/bad/version-nad.json"
cp "$clip" "$OUT/bad/extra.nad"
printf 'XXXX' >> "$OUT/bad/extra.nad"
refused clip-extra-bytes "$OUT/bad/extra-nad.json" "bytes the layout does not explain" nad "$OUT/bad/extra.nad" "$OUT/bad/extra-nad.json"

echo "failures: $failures"
[[ "$failures" -eq 0 ]]

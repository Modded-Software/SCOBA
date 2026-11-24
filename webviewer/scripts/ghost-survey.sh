#!/usr/bin/env bash
# The StarCraft: Ghost surveys (SPEC-VIEWER-GHOST 9): every .nod of 3D/Models
# and every .nad of 3D/Anims, the materials, motion sets, templates and textures, read by
# NODSurvey (our nodsdk-scghost fork, built by scripts/setup/deps.sh nodsdk).
# The reports go to build/surveys/{nod,nad,nsa,nms,not,dds}.json; the facts of SPEC-VIEWER-GHOST 3 and 4 are
# then asserted on them. Exit 0 only when every assertion holds.
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
SURVEY="$WEBVIEWER_DIR/build/nodsdk/cmake/NODSurvey"
if [[ ! -x "$SURVEY" ]]; then
  echo "ERROR: $SURVEY is not built; run: make install-deps" >&2
  exit 1
fi
OUT="$WEBVIEWER_DIR/build/surveys"
mkdir -p "$OUT"

# The survey exits 1 when a file is refused or leaves bytes over; the
# assertions below name what failed, so its code is kept, not stopped on.
code=0
"$SURVEY" nod "$GHOST_PATH/3D/Models" "$OUT/nod.json" > "$OUT/nod.log" 2>&1 || code=$?
echo "nod survey exit $code"
code=0
"$SURVEY" nad "$GHOST_PATH/3D/Anims" "$OUT/nad.json" > "$OUT/nad.log" 2>&1 || code=$?
echo "nad survey exit $code"
code=0
"$SURVEY" nsa "$GHOST_PATH" "$OUT/nsa.json" > "$OUT/nsa.log" 2>&1 || code=$?
echo "nsa survey exit $code"
code=0
"$SURVEY" nms "$GHOST_PATH" "$OUT/nms.json" > "$OUT/nms.log" 2>&1 || code=$?
echo "nms survey exit $code"
code=0
"$SURVEY" not "$GHOST_PATH" "$OUT/not.json" > "$OUT/not.log" 2>&1 || code=$?
echo "not survey exit $code"
code=0
"$SURVEY" dds "$GHOST_PATH" "$OUT/dds.json" > "$OUT/dds.log" 2>&1 || code=$?
echo "dds survey exit $code"

failures=0
check() {  # check <report> <jq expression that must be true> <what it states>
  local got
  got="$(jq -r "$2" "$OUT/$1.json")"
  if [[ "$got" == "true" ]]; then
    echo "ok    $1: $3"
  else
    echo "FAIL  $1: $3"
    failures=$((failures + 1))
  fi
}

# 4.1 NOD
check nod '.files == 1401 and .read == 1401' 'all 1401 models read'
check nod '.refused == [] and .leftover == []' 'every model read to its last byte'
check nod '.versions == {"10": 1401}' 'version 10 in every model'
check nod '[.vertexTypes | keys[] | tonumber] | all(. <= 5)' 'vertex types 0 to 5 only'
check nod '.faults == []' 'bone parents earlier, palettes in range, rigid groups on rigid vertices, indices and vertices sum per group'
check nod '[.groupBones | keys[] | tonumber] | all(. <= 20)' 'at most 20 bones per group'
check nod '.groupByte1F == {"0": .groups} and .groupByte37 == {"0": .groups}' 'group bytes 0x1F and 0x37 are always 0'
check nod '.withBlendData == 0' 'no model has blend data'
# 4.2 NAD
check nad '.files == 1551 and .read == 1551' 'all 1551 clips read'
check nad '.refused == [] and .leftover == []' 'every clip read to its last byte'
check nad '.versions == {"4": 1551}' 'version 4 in every clip'
check nad '[.kinds | keys[]] == ["0", "1"]' 'track kinds 0 (turn) and 1 (position) only'
check nad '.lastKeyNaN == .tracks' 'the last key of every track holds not-a-number'
check nad '.frameOrder == 0 and .frameRange == 0' 'keys in frame order, inside the clip length'
check nad '.withShapeTracks == []' 'no clip has shape tracks'
check nad '.joinsTurn.frames.within > 0.99 * .joinsTurn.frames.joins and .joinsTurn.frames.within > .joinsTurn.unit.within' 't is in frames: turn keys join'
check nad '.joinsPosition.frames.within > 0.99 * .joinsPosition.frames.joins and .joinsPosition.frames.within > .joinsPosition.unit.within' 't is in frames: position keys join'

# 4.4 NSA
check nsa '.archives == 52 and .listed == 11 and .missingArchives == ["organic", "wood"]' '52 archives, 11 of the 13 listed exist (no organic, no wood)'
check nsa '.archiveOrder[0:11] == ["common.nsa", "effects.nsa", "metal.nsa", "radiant.nsa", "shaders.nsa", "lights.nsa", "glass.nsa", "stone.nsa", "skies.nsa", "3dMaterials.nsa", "constraints.nsa"]' 'listed archives read in shaderlist.txt order'
check nsa '.unclosed == [] and .strayClose == [] and .openBraces == .closeBraces' 'every block closes'
check nsa '.commentLines == 689' '689 comment lines skipped'
check nsa '.droppedDrawn == 0 and ([.droppedAt[].shader] | unique) == ["dynamic"]' 'only dynamic materials have more than 32 properties'
check nsa '.nestedShaders == {"dynamic": .withNestedBlocks}' 'nested blocks only in dynamic materials'
check nsa '(.shaders | length) == 64' '64 shader values'
check nsa '.missingFolders == ["Materials\\Radiant"] and (.duplicateTextures | length) == 8' 'Materials\Radiant missing; 8 textures in two folders'
check nsa '.materialNames == 1340 and .materialSlots == 4922' '1340 material names in 4922 slots of the models'
check nsa '.lookup.archive.names + .lookup.nas.names + .lookup.texture.names + .lookup.none.names == .materialNames' 'every material name takes exactly one lookup step'

# 4.3 NMS
check nms '.files == 163 and .read == 163 and .refused == []' 'all 163 motion sets read'
check nms '.shortLines == 0 and .droppedFlags == 0' 'every entry names a clip; no entry has more than 8 flags'
check nms '.entries == 2027 and .entriesExact + .entriesByCase + .entriesByAddedExt + .entriesMissing == .entries' '2027 entries; each takes exactly one clip match class'
check nms '.entriesExact == 1073 and .entriesByCase == 676 and .entriesByAddedExt == 216' 'clip match: 1073 exact, 676 without case, 216 with .nad appended'
check nms '.entriesMissing == 62 and .missingClipCount == 20' '62 entries name 20 clips that are not in 3D/Anims'
check nms '.clipCaseTwins == []' 'no two clips differ only by case'
check nms '(.flags | keys) == ["add", "endpause", "endtag", "fidget", "lowpriority", "lowpriotity", "mix", "movespeed", "nofadein", "nofadeout", "noframereset", "noloop", "resetmotion", "variable"]' '14 flag spellings, lowpriotity once'

# 4.5 NOT
check not '.archives == 1 and .templates == 1224 and .shadowed == 0' 'Global.not alone: 1224 templates, none shadowed'
check not '.incomplete == 0 and .badStrings == []' 'every property decoded at full width; every model and motion set name is text'
check not '.resolve == {"ok": 1223, "missing_template": 1} and .refused == ["scourge_track: Missing template: "]' '1223 templates resolve; scourge_track has an empty basedon'
check not '.unknownIds == 90 and ([.ownIds | keys[] | tonumber | select(. >= 177)] == [177, 178, 179, 180, 181, 182, 183, 184])' '90 properties use ids 177 to 184, past the 177-entry engine table'
check not '.withModel == 858 and .models.templates == {"exact": 757, "case": 49, "addedExt": 12, "missing": 40}' 'models: 858 templates; 757 exact, 49 without case, 12 with .nod appended, 40 missing'
check not '.withMotionSet == 426 and .motionSetWithoutModel == 0 and .motionSets.templates == {"exact": 361, "case": 9, "addedExt": 34, "missing": 22}' 'motion sets: 426 templates, all with a model; 361 exact, 9 without case, 34 with .nms appended, 22 missing'

# 4.6 DDS
check dds '.files == 2275 and .read == 2275 and .refused == [] and .unsized == []' 'all 2275 textures read and sized'
check dds '(.formats | keys) == ["DXT1", "DXT2", "DXT3", "DXT5", "bits32 flags41 rFF0000 gFF00 bFF aFF000000"]' 'formats: DXT1, DXT2, DXT3, DXT5 and 32-bit ARGB only'
check dds '.notPowerOfTwo == 0 and .partialCubes == 0 and .cubes == 39 and .volumes == 2' 'power-of-two sides; 39 full cube maps; 2 volumes'
check dds '.short == [] and .sizeExact + (.over | length) == .read' 'no texture is shorter than its levels'
check dds '(.over | length) == 540 and .overBytes["8"] == 263 and .overBytes["16"] == 212' '540 textures have bytes over, most one block (8 or 16)'

echo "failures: $failures"
[[ "$failures" -eq 0 ]]

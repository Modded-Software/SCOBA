#!/usr/bin/env bash
# Make the datasets the tests use, in the folder $WEBVIEWER_DATASETS (set by
# test.sh; never the operator's own datasets folder):
#
#   fx   the stock data, with a map layer that makes the Marine twice its
#        size (actor Scale 2) and gives it the Zealot's skin
#        (Assets/Textures/marine_diffuse_blood.dds, the stock Marine
#        model's skin, is the Zealot texture)
#
# The files get a fixed change time, so the dataset's fingerprint is the
# same on every run and its catalog is rebuilt only when it is stale.
set -euo pipefail
WEBVIEWER_DIR="${WEBVIEWER_DIR:-$(git rev-parse --show-toplevel)/webviewer}"
source "$WEBVIEWER_DIR/scripts/paths.sh" || exit 1
: "${WEBVIEWER_DATASETS:?test-fixture.sh: WEBVIEWER_DATASETS is not set (test.sh sets it)}"
STOCK="${WEBVIEWER_STOCK:-$WEBVIEWER_DATA/stock}"
STAMP="2026-01-01T00:00:00"
ZEALOT='mods\liberty.sc2mod\base.sc2assets\assets\textures\zealot_diffuse.dds'
LARGE='mods\liberty.sc2mod\base.sc2assets\assets\textures\commandcenter_remastered_diff.dds'

if [[ ! -d "$STOCK/mods" ]]; then
  echo "ERROR: no stock data at $STOCK; run scripts/catalog.sh first" >&2
  exit 1
fi

fx="$WEBVIEWER_DATASETS/fx"
mkdir -p "$fx"
rm -rf "$fx/mods" "$fx/campaigns" "$fx/map"
cp -r "$STOCK/mods" "$STOCK/campaigns" "$fx/"
mkdir -p "$fx/map/Base.SC2Data/GameData" "$fx/map/Assets/Textures"
printf '%s\n' \
  '<?xml version="1.0" encoding="utf-8"?>' \
  '<Catalog>' \
  '    <CActorUnit id="Marine">' \
  '        <Scale value="2.000000"/>' \
  '    </CActorUnit>' \
  '</Catalog>' > "$fx/map/Base.SC2Data/GameData/ActorData.xml"
work="$fx/.work"
rm -rf "$work"
mkdir -p "$work"
"$STORMEX" -S "$SC2_PATH" -X "$ZEALOT" -o "$work"
zealot="$work/mods/liberty.sc2mod/base.sc2assets/assets/textures/zealot_diffuse.dds"
if [[ ! -f "$zealot" ]]; then
  echo "ERROR: stormex did not extract $ZEALOT" >&2
  exit 1
fi
cp "$zealot" "$fx/map/Assets/Textures/marine_diffuse_blood.dds"
# A 2048 texture, for the tests' upscaled model textures (tools/hdtex-fixture.mjs).
"$STORMEX" -S "$SC2_PATH" -X "$LARGE" -o "$work"
large="$work/mods/liberty.sc2mod/base.sc2assets/assets/textures/commandcenter_remastered_diff.dds"
if [[ ! -f "$large" ]]; then
  echo "ERROR: stormex did not extract $LARGE" >&2
  exit 1
fi
mkdir -p "$WEBVIEWER_DATA/test-hdtex-src"
cp "$large" "$WEBVIEWER_DATA/test-hdtex-src/large.dds"
rm -rf "$work"
printf '{ "label": "Test fixture" }\n' > "$fx/dataset.json"
find "$fx/mods" "$fx/campaigns" "$fx/map" -exec touch -d "$STAMP" {} +

bash scripts/catalog.sh --if-stale --dataset fx

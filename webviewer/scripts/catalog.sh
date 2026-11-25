#!/usr/bin/env bash
# Build the catalogs of the datasets from their game data: units (units.json
# and PNG icons) and doodads (doodads.json). Datasets: src/games/sc2/server/datasets.ts.
#
#   catalog.sh [--if-missing | --if-stale] [--extract] [--dataset ID]
#
# --if-missing  leave a dataset alone when its catalog is already there
# --if-stale    leave a dataset alone when its catalog is there and was
#               built from the sources as they are now
# --extract     extract the shared stock data from the game again (after a
#               game patch); without it, only when it is missing
# --dataset ID  build that dataset only
#
# Beside each catalog goes signature.txt: the fingerprint of the files it
# was built from. The server compares it to tell when a dataset changed.
set -euo pipefail
WEBVIEWER_DIR="${WEBVIEWER_DIR:-$(git rev-parse --show-toplevel)/webviewer}"
source "$WEBVIEWER_DIR/scripts/paths.sh" || exit 1
STOCK="${WEBVIEWER_STOCK:-$WEBVIEWER_DATA/stock}"

if_missing=0
if_stale=0
extract=0
only=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --if-missing) if_missing=1 ;;
    --if-stale) if_stale=1 ;;
    --extract) extract=1 ;;
    --dataset)
      [[ $# -ge 2 ]] || { echo "ERROR: --dataset needs an id" >&2; exit 2; }
      only="$2"
      shift
      ;;
    *) echo "ERROR: unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done

# Unit names are in gamestrings.txt, doodad (actor) names in objectstrings.txt.
if [[ "$extract" -eq 1 || ! -d "$STOCK/mods" ]]; then
  mkdir -p "$STOCK"
  "$STORMEX" -S "$SC2_PATH" \
    -I '^(mods|campaigns)\\(core|liberty|swarm|void|libertystory|swarmstory|voidstory)\.sc2(mod|campaign)\\(base\.sc2data\\gamedata\\(unitdata|actordata|modeldata)\.xml|enus\.sc2data\\localizeddata\\(gamestrings|objectstrings)\.txt)$' \
    -x -o "$STOCK"
fi

listing="$(bash scripts/tool.sh datasets list)"
if [[ -n "$only" ]] && ! grep -q "^${only}	" <<< "$listing"; then
  echo "ERROR: no dataset \"$only\". Datasets:" >&2
  cut -f1 <<< "$listing" >&2
  exit 1
fi

export PYTHONPATH="$REPO_ROOT/scripts"
while IFS=$'\t' read -r id stock map out; do
  [[ -z "$only" || "$only" == "$id" ]] || continue
  present=0
  [[ -f "$out/units.json" && -f "$out/doodads.json" && -f "$out/signature.txt" ]] && present=1
  if [[ "$if_missing" -eq 1 && "$present" -eq 1 ]]; then
    echo "catalog present: $id ($out)"
    continue
  fi
  # The fingerprint of the sources as they are now, before they are read.
  built_from="$(bash "$WEBVIEWER_DIR/scripts/tool.sh" datasets signature "$id")"
  if [[ "$if_stale" -eq 1 && "$present" -eq 1 && "$(cat "$out/signature.txt")" == "$built_from" ]]; then
    echo "catalog up to date: $id ($out)"
    continue
  fi
  echo "building catalog: $id (stock $stock, map $map)"
  mkdir -p "$out"
  # Icon textures extracted from the game before may be outdated after a patch.
  if [[ "$extract" -eq 1 ]]; then
    rm -rf "$out/raw" "$out/icons"
  fi
  rm -f "$out/signature.txt"
  (
    cd "$REPO_ROOT/scripts"
    uv run python ../webviewer/tools/build_catalog.py --stock "$stock" --map "$map" --out "$out"
    uv run python ../webviewer/tools/build_doodads.py --stock "$stock" --map "$map" --out "$out"
  )
  printf '%s\n' "$built_from" > "$out/signature.txt"
done <<< "$listing"

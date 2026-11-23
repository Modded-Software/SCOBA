#!/usr/bin/env bash
# Make a new dataset: the game's full stock data (every game data XML and
# every enUS string file of the data stack), extracted into its own folder
# to be edited there, and its catalog.
#
#   dataset-new.sh ID [--with-map]
#
# ID          lower case letters, digits, "-", "_"; not "stock" or "scoba"
# --with-map  also copy this repo's map layer (game data, strings, Assets)
#             into the dataset's map/ folder
#
# The dataset lands in the datasets folder (default $WEBVIEWER_DATA/datasets,
# gitignored). Layout and rules: src/games/sc2/server/datasets.ts. A map layer can be
# added later by hand: <dataset>/map/Base.SC2Data/GameData/*.xml,
# <dataset>/map/Assets/...
set -euo pipefail
WEBVIEWER_DIR="${WEBVIEWER_DIR:-$(git rev-parse --show-toplevel)/webviewer}"
source "$WEBVIEWER_DIR/scripts/paths.sh" || exit 1

id="${1:-}"
with_map=0
if [[ "${2:-}" == "--with-map" ]]; then
  with_map=1
elif [[ -n "${2:-}" ]]; then
  echo "ERROR: unknown argument: $2" >&2
  exit 2
fi
if [[ ! "$id" =~ ^[a-z0-9][a-z0-9_-]{0,39}$ || "$id" == "stock" || "$id" == "scoba" ]]; then
  echo "ERROR: usage: dataset-new.sh ID [--with-map]; ID is lower case letters, digits, \"-\", \"_\", and not \"stock\" or \"scoba\" (got \"$id\")" >&2
  exit 2
fi

root="$(bash scripts/tool.sh datasets dir)"
target="$root/$id"
if [[ -e "$target" ]]; then
  echo "ERROR: $target exists already" >&2
  exit 1
fi
mkdir -p "$target"

"$STORMEX" -S "$SC2_PATH" \
  -I '^(mods|campaigns)\\(core|liberty|swarm|void|libertystory|swarmstory|voidstory)\.sc2(mod|campaign)\\(base\.sc2data\\gamedata\\.*\.xml|enus\.sc2data\\localizeddata\\.*\.txt)$' \
  -x -o "$target"
if [[ ! -d "$target/mods" ]]; then
  echo "ERROR: stormex extracted no stock data into $target" >&2
  exit 1
fi

if [[ "$with_map" -eq 1 ]]; then
  map="${WEBVIEWER_MAP:-$REPO_ROOT/src/SCOBA.SC2Map}"
  mkdir -p "$target/map"
  for part in Base.SC2Data enUS.SC2Data Assets; do
    cp -r "$map/$part" "$target/map/$part"
  done
fi

printf '{ "label": "%s" }\n' "$id" > "$target/dataset.json"
bash scripts/catalog.sh --dataset "$id"
echo "dataset ready: $target"
echo "restart the viewer (make viewer-restart) to list it"

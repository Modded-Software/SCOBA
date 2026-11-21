#!/usr/bin/env bash
# Build the unit catalog (units.json and PNG icons) from the game data.
# With "--if-missing" it does nothing when the catalog is already there.
set -euo pipefail
WEBVIEWER_DIR="${WEBVIEWER_DIR:-$(git rev-parse --show-toplevel)/webviewer}"
source "$WEBVIEWER_DIR/scripts/paths.sh" || exit 1
STOCK="$WEBVIEWER_DATA/stock"
OUT="$WEBVIEWER_DATA/catalog"

if [[ "${1:-}" == "--if-missing" && -f "$OUT/units.json" ]]; then
  echo "catalog present: $OUT/units.json"
  exit 0
fi

mkdir -p "$STOCK" "$OUT"
"$STORMEX" -S "$SC2_PATH" \
  -I '^(mods|campaigns)\\(core|liberty|swarm|void|libertystory|swarmstory|voidstory)\.sc2(mod|campaign)\\(base\.sc2data\\gamedata\\(unitdata|actordata|modeldata)\.xml|enus\.sc2data\\localizeddata\\gamestrings\.txt)$' \
  -x -o "$STOCK"

cd "$REPO_ROOT/scripts"
PYTHONPATH="$REPO_ROOT/scripts:$REPO_ROOT/scripts/hdtex" uv run python ../webviewer/tools/build_catalog.py --stock "$STOCK" --out "$OUT"

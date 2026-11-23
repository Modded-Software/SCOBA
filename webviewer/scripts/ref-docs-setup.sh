#!/usr/bin/env bash
# Set up the StarCraft: Ghost reference repos under ref/ (gitignored):
# - ref/scghost-rev: NOD engine reverse-engineering notes and code.
# - ref/nodsdk-docs: NOD engine asset format docs (.nod, .nad, .nmb, .nsa, ...).
# They are reading material for the viewer's Ghost format support. Neither
# repo has a license, so nothing from them is copied into this repo.
#
# Each repo is pinned to one commit.
# - Missing: clone it. A fresh clone's HEAD must be the pin; when upstream
#   has moved on, the script stops: check out the pin by hand.
# - Present: its HEAD must be the pin. To move a pin, update it here.
#
# REF_ROOT overrides where the repos go (default: ref/).
set -euo pipefail
WEBVIEWER_DIR="${WEBVIEWER_DIR:-$(git rev-parse --show-toplevel)/webviewer}"
source "$WEBVIEWER_DIR/scripts/paths.sh" || exit 1

ROOT="${REF_ROOT:-$WEBVIEWER_DIR/ref}"
# name url commit
REPOS=(
  "scghost-rev https://github.com/aknavj/scghost-rev.git 4f1fd24381edf00e20dff9c0352ead3ef16d1473"
  "nodsdk-docs https://github.com/aknavj/nodsdk-docs.git f2110b37d04135a5b7c1d4605e764de49736d512"
)

failed=0
for entry in "${REPOS[@]}"; do
  read -r name url pin <<<"$entry"
  dir="$ROOT/$name"
  if [[ ! -d "$dir/.git" ]]; then
    echo "cloning $url into $dir"
    mkdir -p "$ROOT"
    git clone "$url" "$dir"
  fi
  head="$(git -C "$dir" rev-parse HEAD)"
  if [[ "$head" != "$pin" ]]; then
    echo "ERROR: $dir is at ${head:0:8}, the pin is ${pin:0:8}." >&2
    echo "Check out the pin there, or move the pin in scripts/ref-docs-setup.sh." >&2
    failed=1
    continue
  fi
  echo "$name ok at ${pin:0:8}"
done
exit "$failed"

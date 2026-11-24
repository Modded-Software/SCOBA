#!/usr/bin/env bash
# Set up the StarCraft: Ghost reference repos under ref/ (gitignored):
# - ref/scghost-rev: NOD engine reverse-engineering notes and code.
# - ref/nodsdk-docs: NOD engine asset format docs (.nod, .nad, .nmb, .nsa, ...).
# - ref/nodsdk-scghost: the OpenNOD SDK parsers (C++17, GPL v3), from our
#   fork Modded-Software/nodsdk-scghost (origin; aknavj's repo is upstream).
#   The viewer's tools are built in the fork and run as separate programs
#   (scripts/setup/deps.sh nodsdk); no SDK code is copied into this repo.
# - ref/nodsdk-radiant: the SDK's GtkRadiant fork (BSD, LGPL, GPL by file).
#   Reading material for the level formats only.
# scghost-rev and nodsdk-docs state no license: they are read, not copied.
#
# Each repo is pinned to one commit.
# - Missing: clone it. A fresh clone's HEAD must be the pin; when upstream
#   has moved on, the script stops: check out the pin by hand.
# - Present: its HEAD must be the pin, and its origin the url. To move a
#   pin (a new commit in our fork), update it here.
# - A fork has a fourth field, the repo it was forked from: a fresh clone
#   gets it as the remote "upstream".
#
# REF_ROOT overrides where the repos go (default: ref/).
set -euo pipefail
WEBVIEWER_DIR="${WEBVIEWER_DIR:-$(git rev-parse --show-toplevel)/webviewer}"
source "$WEBVIEWER_DIR/scripts/paths.sh" || exit 1

ROOT="${REF_ROOT:-$WEBVIEWER_DIR/ref}"
# name url commit [upstream url]
REPOS=(
  "scghost-rev https://github.com/aknavj/scghost-rev.git 4f1fd24381edf00e20dff9c0352ead3ef16d1473"
  "nodsdk-docs https://github.com/aknavj/nodsdk-docs.git f2110b37d04135a5b7c1d4605e764de49736d512"
  "nodsdk-scghost git@github.com:Modded-Software/nodsdk-scghost.git f3d434cdece987ce6b8d1ebb3309c7a8b40c1df0 https://github.com/aknavj/nodsdk-scghost.git"
  "nodsdk-radiant https://github.com/aknavj/nodsdk-radiant.git a660bef1c7f3f537d01495d207439622d6d257ef"
)

failed=0
for entry in "${REPOS[@]}"; do
  read -r name url pin upstream <<<"$entry"
  dir="$ROOT/$name"
  if [[ ! -d "$dir/.git" ]]; then
    echo "cloning $url into $dir"
    mkdir -p "$ROOT"
    git clone "$url" "$dir"
    [[ -z "$upstream" ]] || git -C "$dir" remote add upstream "$upstream"
  fi
  origin="$(git -C "$dir" remote get-url origin)"
  # A trailing .git names the same repo.
  if [[ "${origin%.git}" != "${url%.git}" ]]; then
    echo "ERROR: $dir has origin $origin, not $url." >&2
    echo "Set it there: git remote set-url origin $url" >&2
    failed=1
    continue
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

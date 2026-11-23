#!/usr/bin/env bash
# Set up ref/mdx-m3-viewer: the upstream renderer source at its base commit
# with patches/*.patch applied as commits. ref/ is gitignored; patches/ is
# the tracked record of every change we made to the library.
#
# - No ref repo: clone upstream, reset to the base, apply the patches.
# - A ref repo: check that patches/ is the start of its commits on the base.
#   Extra local commits are fine (the next build exports them to patches/).
#   A patch the ref repo lacks is an error: the ref repo is behind patches/.
#   Move it away (or delete it) and run this again to rebuild it.
#
# REF_DIR overrides where the repo goes (default: ref/mdx-m3-viewer).
set -euo pipefail
WEBVIEWER_DIR="${WEBVIEWER_DIR:-$(git rev-parse --show-toplevel)/webviewer}"
source "$WEBVIEWER_DIR/scripts/paths.sh" || exit 1

UPSTREAM="https://github.com/flowtsohg/mdx-m3-viewer.git"
# Upstream master, 2025-08-27. Keep in sync with BASE in src/tools/build.ts.
BASE="2ff0bc00c6363f425016e23d88c0fb2929d3b3cc"
REF="${REF_DIR:-$WEBVIEWER_DIR/ref/mdx-m3-viewer}"
PATCHES=("$WEBVIEWER_DIR"/patches/*.patch)

if [[ ! -d "$REF/.git" ]]; then
  echo "cloning $UPSTREAM into $REF"
  mkdir -p "$(dirname "$REF")"
  git clone "$UPSTREAM" "$REF"
  # Upstream is unmaintained; its master is the base. Should it ever move,
  # stop rather than patch a different tree.
  head="$(git -C "$REF" rev-parse HEAD)"
  if [[ "$head" != "$BASE" ]]; then
    echo "ERROR: upstream master is $head, not the base $BASE." >&2
    echo "Check out the base in $REF by hand, then run this script again." >&2
    exit 1
  fi
  # git am records the user's git identity as committer.
  git -C "$REF" am "${PATCHES[@]}"
  echo "ref repo ready: $(git -C "$REF" rev-parse --short HEAD), ${#PATCHES[@]} patches on ${BASE:0:8}"
  exit 0
fi

if ! git -C "$REF" merge-base --is-ancestor "$BASE" HEAD; then
  echo "ERROR: $REF does not build on the base ${BASE:0:8}" >&2
  exit 1
fi

# Compare by patch id, which ignores commit hashes and dates.
want="$(cat "${PATCHES[@]}" | git patch-id --stable | cut -d' ' -f1)"
have="$(git -C "$REF" log --reverse -p "$BASE..HEAD" | git patch-id --stable | cut -d' ' -f1)"
want_count="$(printf '%s\n' "$want" | grep -c .)"
have_prefix="$(printf '%s\n' "$have" | sed -n "1,${want_count}p")"
if [[ "$want" != "$have_prefix" ]]; then
  echo "ERROR: $REF does not hold patches/ as its first commits on ${BASE:0:8}." >&2
  echo "patches/: $want_count patches; ref repo: $(printf '%s\n' "$have" | grep -c .) commits." >&2
  echo "Move the ref repo away and run this script again to rebuild it from patches/." >&2
  exit 1
fi
echo "ref repo ok: $(git -C "$REF" rev-parse --short HEAD), holds all ${want_count} patches"

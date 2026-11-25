#!/usr/bin/env bash
# Test helper for test_workpaths.py: source scripts/paths.sh, print each
# exported path as NAME=VALUE, then run the device check when asked.
set -euo pipefail
ROOT_DIR="${SC2_PROJECT_ROOT:?SC2_PROJECT_ROOT names the repository}"
# shellcheck source=../../paths.sh
source "$ROOT_DIR/scripts/paths.sh" || exit 1
for name in "${PATHS_ALL[@]}" TMPDIR; do
    printf '%s=%s\n' "$name" "${!name}"
done
if [ "${1:-}" = --device ]; then
    paths_check_device
fi

#!/usr/bin/env bash
# Run the Playwright integration tests. Arguments go to playwright.
# The run keeps the machine usable: lowest CPU priority, and only the cores in
# WEBVIEWER_TEST_CPUS (default 0-23, 24 cores; operator 2026-11-22). The browsers draw
# WebGL in software, so they take every core they are given; 16 cores starved 4 workers.
# Other knobs (playwright.config.mjs): WEBVIEWER_TEST_WORKERS (4),
# WEBVIEWER_TEST_ALL=1 (the @slow surveys too), WEBVIEWER_TEST_MAX_FAILURES (0: no limit).
# The renderer bundle and the catalogs must exist first.
# The tests get their own datasets folder (scripts/test-fixture.sh), so
# they never see or touch the operator's datasets. The same for the HD
# texture viewer (WEBVIEWER_HDTEX, tools/hdtex-fixture.mjs).
set -euo pipefail
WEBVIEWER_DIR="${WEBVIEWER_DIR:-$(git rev-parse --show-toplevel)/webviewer}"
source "$WEBVIEWER_DIR/scripts/paths.sh" || exit 1
export WEBVIEWER_DATASETS="$WEBVIEWER_DATA/test-datasets"
bash scripts/ref-setup.sh
# A type error ends the run before any test starts (R-VIEW-13).
bash scripts/typecheck.sh
bash scripts/tool.sh build
bash scripts/catalog.sh --if-missing
bash scripts/test-fixture.sh
# The texture viewer the tests open: the real page template with four entries.
export WEBVIEWER_HDTEX="$WEBVIEWER_DATA/test-hdtex"
# The upscaled model textures the view shows: the Zergling's skin (the Zealot's picture, not
# larger than the standard one) and the Roach's skin (a 2048 picture).
export WEBVIEWER_HDTEX_MODELS="$WEBVIEWER_DATA/test-hdtex-models"
node tools/hdtex-fixture.mjs "$REPO_ROOT/scripts/hdtex/compare.html" "$WEBVIEWER_DATA/catalog/icons" "$WEBVIEWER_HDTEX" \
  "$WEBVIEWER_HDTEX_MODELS" "$WEBVIEWER_DATASETS/fx/map/Assets/Textures/marine_diffuse_blood.dds" "$WEBVIEWER_DATA/test-hdtex-src/large.dds"
CPUS="${WEBVIEWER_TEST_CPUS:-0-23}"
exec taskset -c "$CPUS" nice -n 19 npx playwright test "$@"

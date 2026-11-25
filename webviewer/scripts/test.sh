#!/usr/bin/env bash
# Run the Playwright tests. Arguments go to playwright: --project=unit (no
# browser) or --project=e2e (the page in a browser); none runs both.
# The run keeps the machine usable: lowest CPU priority, and only the cores in
# WEBVIEWER_TEST_CPUS (default 0-23, 24 cores; operator 2026-11-22). The browsers draw
# WebGL on the GPU: ANGLE on Vulkan, Mesa's Intel driver only (playwright.config.mjs).
# Other knobs (playwright.config.mjs): WEBVIEWER_TEST_WORKERS (4),
# WEBVIEWER_TEST_ALL=1 (the @slow surveys too), WEBVIEWER_TEST_MAX_FAILURES (0: no limit).
# The renderer bundle and the catalogs must exist first.
# The tests get their own datasets folder (scripts/test-fixture.sh), so
# they never see or touch the operator's datasets. The same for the
# texture store: their own, with the upscaler that needs no GPU
# (SPEC-VIEWER 17.8: HDTEX_RUNNER=repeat, scripts/hdtex/core/repeat.py).
# These two are the base: each Playwright worker copies them and starts its
# own server on them (tests/fixtures.mjs, SPEC-VIEWER 11.1). Global setup
# makes the base state index first, once (tests/global-setup.mjs).
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
export TEXTURE_STORE="$WEBVIEWER_DATA/test-texture-store"
export HDTEX_RUNNER=repeat
# The base store is built once and kept (operator 2026-11-25): its state
# index and each game's index/ are made only when missing (global setup's
# server start). No test writes to it: each worker copies it
# (tests/fixtures.mjs). To build it again, delete $TEXTURE_STORE.
shopt -s nullglob
# A store of layout 1 (variants came after it) is moved once, emptied, while
# its state index is still there: the move reads it (SPEC-HD-TEXTURES 7).
for game in "$TEXTURE_STORE"/*/; do
  if [ -f "$TEXTURE_STORE/format" ] && [ "$(cat "$TEXTURE_STORE/format")" = 1 ]; then
    uv --project "$WEBVIEWER_DIR/.." run python "$WEBVIEWER_DIR/../scripts/hd_textures.py" move --game "$(basename "$game")"
  fi
done
shopt -u nullglob
# The workers' folders of the last run.
rm -rf "$WEBVIEWER_WORK/test-workers"
# The Intel Vulkan driver alone: with every driver listed, the loader can pick lavapipe (software).
export VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/intel_icd.json
CPUS="${WEBVIEWER_TEST_CPUS:-0-23}"
exec taskset -c "$CPUS" nice -n 19 npx playwright test "$@"

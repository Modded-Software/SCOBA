#!/usr/bin/env bash
# Type-check the viewer's TypeScript and its import rule. A type error or a
# forbidden import ends with exit 1. Every check runs, so one report shows every error.
# 1. The renderer library in the ref repo, by tsconfig.lib.json (its own flags). This
#    writes its declarations to build/lib-types/, which our code is checked against.
# 2. Our code, by tsconfig.json (strict, noUncheckedIndexedAccess): tools, server
#    and code shared with Node. Then the page code by tsconfig.page.json: the same
#    flags without the Node types, so page code cannot use Node globals.
# 3. The import rule of SPEC-VIEWER section 3, over src/ (src/tools/import-rule.ts).
# Arguments: other settings files to check instead of the two (the tests use this).
set -uo pipefail
WEBVIEWER_DIR="${WEBVIEWER_DIR:-$(git rev-parse --show-toplevel)/webviewer}"
source "$WEBVIEWER_DIR/scripts/paths.sh" || exit 1
TSC="node_modules/.bin/tsc"
if [[ ! -x "$TSC" ]]; then
  echo "ERROR: $TSC is missing. Run: make viewer-install" >&2
  exit 1
fi
echo "node $(node --version), compiler $("$TSC" --version)"
projects=("$@")
if [[ ${#projects[@]} -eq 0 ]]; then
  rm -rf build/lib-types
  projects=(tsconfig.lib.json tsconfig.json tsconfig.page.json)
fi
failed=0
for project in "${projects[@]}"; do
  # Plain output, one line per error: the same with or without a terminal.
  if "$TSC" -p "$project" --pretty false; then
    echo "types ok: $project"
  else
    echo "ERROR: type errors in $project" >&2
    failed=1
  fi
done
if [[ $# -eq 0 ]]; then
  if bash scripts/tool.sh import-rule src; then
    echo "imports ok: src"
  else
    echo "ERROR: forbidden imports in src" >&2
    failed=1
  fi
fi
exit "$failed"

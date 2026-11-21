#!/usr/bin/env bash
# Report the toolchain the viewer needs.
set -euo pipefail
command -v node
node -v
command -v npm
npm -v

# Agent Guidelines

## Procedural map changes

- Every procedural modification to the map must live in a persistent script in `scripts/`.
- Wire each modification into the build pipeline (`scripts/expand_map.py`) so rebuilding reproduces the map.
- Scripts must be idempotent: running them again on the same target must not double-apply.
- Scripts must be reversible when possible:
  - Preferred: `out/SCOBA256.SC2Map` is derived from `src/SCOBA.SC2Map`; rebuilding reverts everything.
  - Provide `--revert` or document the revert command in the script.
- Never hand-edit generated files in `out/` without a corresponding script.
- Keep scripts deterministic (fixed seeds) so rebuilds are stable.

## Verification

- Rebuild with `python scripts/expand_map.py`.
- Confirm idempotency (run twice, compare hashes).
- Launch via the `scoba.desktop` shortcut to check in game.

## Existing procedural scripts

- `scripts/expand_map.py` — 128→256 upscale pipeline.
- `scripts/doodad_occlusion.py` — disable doodad auto-transparency (idempotent, wired into the pipeline).
- `scripts/props_expand.py` — 1.5× trees, 2× fluff, tree scale remapped to max 8 (idempotent, reversible, wired into the pipeline).
- `scripts/spore_scale.py` — scale SporeCannon/SporeCrawler units 3× and projectile speed 1.5× (idempotent, reversible, wired into the pipeline).

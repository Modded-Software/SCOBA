# Agent Guidelines

## Procedural map changes

- Every procedural modification to the map must live in a persistent script in `scripts/`.
- Wire each modification into the build pipeline (`scripts/expand_map.py`) so rebuilding reproduces the map.
- Scripts must be idempotent: running them again on the same target must not double-apply.
- Scripts must be reversible when possible:
  - Preferred: `out/SCOBA256.SC2Map` is derived from `src/SCOBA.SC2Map`; rebuilding reverts everything.
  - The original packed baseline is `original/SCOBA.SC2Map`.
  - Provide `--revert` or document the revert command in the script.
- Never hand-edit generated files in `out/` without a corresponding script.
- Keep scripts deterministic (fixed seeds) so rebuilds are stable.

## Verification

- Rebuild with `uv run python scripts/expand_map.py`.
- Confirm idempotency (run twice, compare hashes).
- Launch via the `scoba.desktop` shortcut to check in game.

## Existing procedural scripts

- `scripts/expand_map.py` — 128→256 upscale pipeline.
- `scripts/doodad_occlusion.py` — disable doodad auto-transparency (idempotent, wired into the pipeline).
- `scripts/props_expand.py` — 1.5× trees, 2× fluff, tree scale remapped to max 8 (idempotent, reversible, wired into the pipeline).
- `scripts/spore_scale.py` — scale SporeCannon/SporeCrawler units 3× and projectile speed 1.5× (idempotent, reversible, wired into the pipeline).
- `scripts/bootstrap_galaxy.py` — write the minimal `MapScript.galaxy` bootstrap (idempotent, wired into the pipeline).
- `scripts/strip_gui_triggers.py` — replace the GUI trigger graph with one empty category (idempotent, reversible from git, wired into the pipeline).
- `scripts/migrate_galaxy_modules.py` — one-time generator for `scripts/app/`; it refuses to run after the source monoliths are removed.

## Project docs

- `docs/requirements/REQ-COMBAT-CONTROLS.md` — binding combat control requirements.
- `docs/specifications/SPEC-COMBAT-CONTROLS.md` — combat FSM implementation specification.
- `docs/requirements/REQ-MOUSE-CONTROLS.md` — binding mouse control requirements.
- `docs/specifications/SPEC-MOUSE-CONTROLS.md` — mouse control implementation specification.
- `docs/AUDIT.md` — full audit of command-card and repository changes.
- `docs/REMEDIATION.md` — phased remediation plan and test matrix.
- `docs/PIPELINE_AUDIT.md` — build, staging, cache, and launch audit.
- `docs/PIPELINE_REMEDIATION.md` — pipeline remediation plan.

## Build pipeline

- `scripts/build.sh` — canonical atomic build, normalization, stamping, validation.
- `scripts/validate-map.py` — required-file, XML, dimension, catalog, and stamp checks.
- `scripts/kill-sc2.py` — stop old SC2 processes before staging.
- `scripts/launch-scoba.sh` — clears cache, stages `out/SCOBA256.SC2Map`, verifies copy, launches.
- `scripts/launch-and-check.sh` — launches and verifies runtime stamp and logs.
- Never launch `src/SCOBA.SC2Map` for gameplay tests. Launch the built map.

## Command card

- Auto-attack state lives only in `SCOBAAutoAttackBehavior`.
- Chase state lives only in `SCOBARightClickStandBehavior`.
- Read state with `UnitHasBehavior`. Do not add boolean mirrors.
- Do not register toggle handlers with `c_unitAbilStageAll`.
- `tools/stormex` is a local helper and is ignored by git.
- `scripts/sc2res*` and `scripts/sc2-check-logs*` are optional project tools.
- Launch with `scripts/launch-and-check.sh` to include log checks.

## Resource tools

- `tools/stormex` - CASC reader. Supports SC2, name search, list, extract, and regex filters.
- `scripts/sc2res` - project CLI for SC2 resources.

Examples:

```bash
bash scripts/sc2res paths
bash scripts/sc2res list btn-command --ext dds
bash scripts/sc2res list "ability.*blink" --regex --ext dds
bash scripts/sc2res extract "mods\\liberty.sc2mod\\base.sc2assets\\assets\\textures\\btn-command-move.dds" --out /mnt/ws-fast/sc2res/icons --exact
bash scripts/sc2res preview btn-command-holdposition --out /mnt/ws-fast/sc2res/icons --html
```

Overrides: `SC2_PATH` for the install directory, `STORMEX` for the reader binary.

Default output root: `/mnt/ws-fast/sc2res` (preview, extract, tmp).

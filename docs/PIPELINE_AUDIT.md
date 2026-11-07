# SCOBA Build Pipeline Audit

Status: active  
Scope: build, staging, cache, launch, logging, and verification for `out/SCOBA256.SC2Map`.  
Baseline: `scripts/expand_map.py`, `scripts/stage-map.py`, `scripts/launch-scoba.sh`, `scripts/launch-and-check.sh`, `scripts/sc2-check-logs.py`, `scripts/run-map-test.py`.

## Severity legend

- **S1**: can silently run stale or broken map code.
- **S2**: causes unreliable builds or launches.
- **S3**: maintainability or documentation defect.
- **S4**: cosmetic.

## Findings

### P01 - Build success does not prove the game runs the new map

Severity: **S1**

Evidence:
- Staged `scripts/combat.galaxy` contains debug bank writes.
- `SCOBA.SC2Bank` contains no `Debug` section after launch.
- Build printed success.

Impact:
- The pipeline can report success while the game runs older code.
- No build stamp exists to distinguish builds.

Status: open.

### P02 - Production launch does not clear the SC2 map cache

Severity: **S1**

Cache path:
`ProgramData/Blizzard Entertainment/StarCraft II/Maps/Cache/SCOBA.SC2Map`

Evidence:
- `run-map-test.py` explicitly removes this cache.
- `launch-scoba.sh` and `launch-and-check.sh` do not.
- Cached `hardTile.bin` exists.

Impact:
- Stale terrain and hard-tile data can be reused.
- `-reloadcheck` does not guarantee cache invalidation.

Status: open.

### P03 - No compile validation before launch

Severity: **S1**

Evidence:
- `expand_map.py` copies and edits files only.
- Galaxy syntax errors are detected only after SC2 loads the map.
- `sc2-check-logs` runs only after launch.

Impact:
- Broken scripts reach the game.
- Build success is misleading.

Status: open.

### P04 - No build stamp or content hash in the map

Severity: **S1**

Evidence:
- No generated stamp file.
- No Galaxy constant.
- No runtime bank key.
- `Build.txt` is copied unchanged.

Impact:
- Cannot prove which source revision produced a running map.
- Impossible to distinguish stale execution from logic bugs.

Status: open.

### P05 - Staging can run while SC2 is using the map

Severity: **S1**

Evidence:
- `stage-map.py` deletes the destination directory before copying.
- `launch-scoba.sh` does not stop a running SC2 process.
- Only `/tmp/opencode/launch_sc2.sh` kills the game.

Impact:
- Locked or partially deleted map.
- Race between staging and game load.

Status: open.

### P06 - Staging is not verified

Severity: **S2**

Evidence:
- `stage-map.py` returns success after copy.
- No hash comparison or `diff -r`.
- No file count check.

Impact:
- Partial copies and permission failures can go unnoticed.

Status: open.

### P07 - Build is not atomic

Severity: **S2**

Evidence:
- `expand_map.py` does `rmtree(out)` then `copytree(src)`.
- Transforms run directly in the live output directory.

Impact:
- Interrupted build leaves a broken `out/`.
- A failed transform leaves a half-built map.

Status: open.

### P08 - No build lock

Severity: **S2**

Evidence:
- No lock file or process guard.
- Multiple builds can run concurrently.

Impact:
- Concurrent builds corrupt `out/`.

Status: open.

### P09 - Line endings are inconsistent

Severity: **S2**

Evidence:
- Source files are CRLF.
- `read_text` / `write_text` writes LF.
- Copied files keep CRLF.
- `out/` ends with mixed endings.

Impact:
- Noisy diffs.
- Editors can corrupt files further.
- Tools that assume one EOL behave inconsistently.

Status: open.

### P10 - `normalize_eol.py` is not wired into the pipeline

Severity: **S3**

Evidence:
- Script exists.
- No build or launch step calls it.

Impact:
- Normalization is manual and easy to forget.

Status: open.

### P11 - Exact-string terrain replacements are fragile

Severity: **S2**

File: `scripts/expand_map.py`

Evidence:
- `dim="129 129 "`
- `blockTextureSetList num="256"`
- `cliffCellList num="4096" numOccupied="547"`

Impact:
- A harmless formatting change silently skips the resize.
- Resulting map can have mixed dimensions.

Status: open.

### P12 - XML edits use regex instead of an XML parser

Severity: **S3**

Files:
- `scale_xml_objects`
- `scale_xml_regions`

Impact:
- Formatting-sensitive.
- Can rewrite unrelated attributes if patterns collide.

Status: open.

### P13 - `doodad_occlusion.py` rewrites `ModelData.xml` with ElementTree

Severity: **S3**

Evidence:
- Parses and writes the full file.
- Removes comments and original formatting.
- Creates `CModel` entries for unknown doodad types.

Impact:
- Large noisy output.
- Possible invalid model entries.

Status: open.

### P14 - Props and spore markers are meaningless in a full rebuild

Severity: **S3**

Evidence:
- Pipeline deletes `out/` before every build.
- `.props_expanded` and `.spore_scaled` are recreated from scratch.

Impact:
- Markers only guard direct script runs, not the pipeline.
- Idempotency is accidental, not enforced.

Status: open.

### P15 - Spore projectile factor contradicts documentation

Severity: **S2**

Evidence:
- `AGENTS.md` says projectile speed **1.5×**.
- `spore_scale.py` uses `PROJECTILE_FACTOR = 2.0`.

Impact:
- Gameplay does not match documented behavior.

Status: open.

### P16 - `spore_scale.py` scales every `MissileDefault` mover

Severity: **S2**

Evidence:
- `MOVER_ID = "MissileDefault"`.
- All `CMoverMissile` entries with that ID are modified.

Impact:
- Unrelated missiles change speed.

Status: open.

### P17 - Revert flags are coupled

Severity: **S2**

Evidence:
- `props_expand.py --revert` sets `SC2_NO_PROPS=1`.
- `spore_scale.py --revert` also sets `SC2_NO_PROPS=1`.
- `expand_map.py` skips both props and spores when `SC2_NO_PROPS=1`.

Impact:
- Reverting spores also disables props.
- No independent revert path.

Status: open.

### P18 - Launch script does not kill the old game

Severity: **S2**

Evidence:
- `launch-scoba.sh` stages and launches directly.
- No process check.
- README tells users to run it directly.

Impact:
- Staging while game is running.
- New launch may race with old process.

Status: open.

### P19 - Staged map name is hardcoded

Severity: **S3**

Evidence:
- `MAP_NAME="SCOBA.SC2Map"`.
- `SC2_MAP_SOURCE` may point to a different map.

Impact:
- Staged file name and internal map name can diverge.
- Test variants are forced into the same name.

Status: open.

### P20 - `launch-and-check.sh` uses a fixed wait

Severity: **S2**

Evidence:
- `sleep "${SC2_CHECK_DELAY:-25}"`.
- No check for map load, process health, or build stamp.

Impact:
- Log check may run before the map loads.
- Check may pass with no map activity.

Status: open.

### P21 - `launch-and-check.sh` root discovery is fragile

Severity: **S3**

Evidence:
- Uses `$PWD` first.
- Falls back to `$0` path.
- Wrapper execution can supply `/proc/self/fd/*`.

Impact:
- Wrong root under launchers and shells.

Status: open.

### P22 - Log checker wrapper hardcodes absolute paths

Severity: **S3**

Evidence:
- `/home/agent/WORKSPACE-VM/projects/SC2/.venv/bin/python3`
- `/home/agent/WORKSPACE-VM/projects/SC2/scripts/sc2-check-logs.py`

Impact:
- Breaks if the project moves.
- Breaks in other users' environments.

Status: open.

### P23 - Log checker scans stale logs

Severity: **S2**

Evidence:
- `MAX_AGE` default 180 seconds.
- Scans all recent `*.txt`.
- No launch timestamp or build ID.

Impact:
- Old errors can fail a good launch.
- A missing map load can pass.

Status: open.

### P24 - Log checker ignores important failures

Severity: **S2**

Evidence:
- Only checks `ScriptError` and `Alerts`.
- Ignores `TextError`.
- Ignores map load and cache failures.

Impact:
- Invalid UI styles and load failures are missed.

Status: open.

### P25 - `run-map-test.py` hardcodes paths

Severity: **S3**

Evidence:
- Absolute `DOCS` path.
- Absolute cache path.
- Direct `pgrep` / `kill` calls.

Impact:
- Not portable.
- Duplicates launch policy.

Status: open.

### P26 - Test harness is not wired into the build

Severity: **S3**

Evidence:
- `build-test-map.py` and `run-map-test.py` exist.
- No canonical command runs them.
- No CI target.

Impact:
- Tests are manual and easy to skip.

Status: open.

### P27 - Build metadata is stale

Severity: **S3**

Evidence:
- `Build.txt` says `Map Came From Build Server`.
- `DocumentHeader` keeps the original build ID and dependencies.
- `ComponentList.SC2Components` is copied unchanged.

Impact:
- Map metadata does not describe the expanded build.
- Editor and debugging tools see misleading data.

Status: open.

### P28 - Out directory contains stale variants

Severity: **S3**

Evidence:
- `out/SCOBA256_dbg.SC2Map`
- `out/SCOBA256_hud.SC2Map`
- `out/SCOBA256_test.SC2Map`

Impact:
- Stale maps can be staged or tested by mistake.

Status: open.

### P29 - No canonical build entrypoint in the repo

Severity: **S2**

Evidence:
- Agent uses `/tmp/opencode/build_sc2.sh`.
- README documents only `launch-scoba.sh`.
- AGENTS documents `python scripts/expand_map.py`.

Impact:
- Different build paths produce different results.
- Temp scripts are lost.

Status: open.

### P30 - No dependency-aware build

Severity: **S3**

Evidence:
- `pyproject.toml` contains `mpyq` and `pillow`.
- Build scripts use system `python3`.
- Some scripts use `.venv/bin/python3`.

Impact:
- Different interpreters and packages.
- Non-reproducible behavior.

Status: open.

### P31 - Untracked tools and scripts

Severity: **S3**

Evidence:
- `tools/stormex`
- `scripts/sc2res`
- `scripts/sc2res.py`
- `scripts/sc2-check-logs`
- `scripts/sc2-check-logs.py`

Impact:
- Unclear ownership.
- CI cannot reproduce local tooling.

Status: open.

### P32 - No runtime assertion for toggles or behaviors

Severity: **S1**

Evidence:
- Behavior presence is not verified.
- Auto-attack and Stand/Walk failures look identical to stale builds.
- Debug bank output did not appear.

Impact:
- Cannot separate data failure from stale execution.

Status: open.

### P33 - Cache path is not documented

Severity: **S3**

Evidence:
- Only `run-map-test.py` knows the cache path.
- AGENTS and README omit it.

Impact:
- Manual debugging misses the cache.

Status: open.

### P34 - No staging manifest

Severity: **S3**

Evidence:
- No list of staged files and hashes.
- No comparison between `out/` and staged map.

Impact:
- Hard to audit what the game actually loaded.

Status: open.

### P35 - Build stamp cannot be checked after launch

Severity: **S1**

Evidence:
- No bank key, no log line, no UI message.
- No launch-side assertion.

Impact:
- The pipeline cannot prove the running map is the built map.

Status: open.

## Most likely cause of the last failed test

1. Cache was not cleared.
2. The old game process may have influenced staging or launch.
3. No stamp proved which code loaded.
4. No runtime behavior assertion existed.
5. Debug bank writing failed or the old code ran.

## Required outcome

- A build that is atomic, validated, stamped, and reproducible.
- A launch that kills old game, clears cache, stages, verifies, and checks the stamp.
- Logs that fail on script, catalog, UI, cache, and map-load errors.
- A runtime probe that reports auto and stand behavior counts.
- No gameplay testing until the build identity is proven.
# SPEC-BUILD-ENTRYPOINT

Status: implementing
Companion requirement: `docs/requirements/REQ-BUILD-ENTRYPOINT.md`

## 1. Canonical entrypoint

`scripts/playtest.sh` is the only user-facing command.

Usage:

```bash
scripts/playtest.sh build
scripts/playtest.sh launch
scripts/playtest.sh combat
scripts/playtest.sh aim
scripts/playtest.sh motion
scripts/playtest.sh controls
```

Every action starts with:

```bash
SC2_PLAYTEST_ACTIVE=1 bash scripts/build.sh
```

The build step is unconditional.
No action may skip it.
No action may read a pre-existing `out/SCOBA256.SC2Map` before this step.

## 2. Actions

| Action | After fresh build |
| --- | --- |
| `build` | Stop. Report the stamp and map hash. |
| `launch` | Run `launch-scoba.sh` with the fresh map. |
| `combat` | Build `SCOBA256_combattest.SC2Map`, then run the combat profile. |
| `aim` | Build `SCOBA256_aimtest.SC2Map`, then run the aim profile. |
| `motion` | Build `SCOBA256_motiontest.SC2Map`, then run the motion profile. |
| `controls` | Build `SCOBA256_controlstest.SC2Map`, then run the controls profile. |

Profile builds and runs call `scripts/testmap.py`.
They do not call the thin wrapper scripts.

## 3. Reentrancy guard

Wrappers check `SC2_PLAYTEST_ACTIVE`.

If the variable is unset, a wrapper re-executes `scripts/playtest.sh` with the
matching action.
If the variable is `1`, the wrapper executes its low-level work.

The entrypoint exports `SC2_PLAYTEST_ACTIVE=1` for every child process.

This prevents recursion:

```text
playtest -> testmap -> wrapper -> playtest -> testmap
```

The protected wrappers are:

- `scripts/build.sh`
- `scripts/build-test-map.py`
- `scripts/build-aim-test-map.py`
- `scripts/build-controls-test-map.py`
- `scripts/build-motion-test-map.py`
- `scripts/run-map-test.py`
- `scripts/run-aim-test.py`
- `scripts/run-controls-test.py`
- `scripts/run-motion-test.py`
- `scripts/testmap.py`
- `scripts/launch-scoba.sh`
- `scripts/launch-and-check.sh`

## 4. Freshness proof

`build.sh` writes `out/.last-build-stamp`.
It also writes `out/SCOBA256.SC2Map/BuildStamp.txt`.

The entrypoint prints both after every build:

```text
fresh build stamp: <stamp>
fresh map: <path>
```

Tests and launches then use that map path.

## 5. Make targets

The project Makefile adds:

| Target | Command |
| --- | --- |
| `map-build` | `scripts/playtest.sh build` |
| `map-launch` | `scripts/playtest.sh launch` |
| `combat` | `scripts/playtest.sh combat` |
| `aim` | `scripts/playtest.sh aim` |
| `motion` | `scripts/playtest.sh motion` |
| `controls` | `scripts/playtest.sh controls` |

These names do not replace CI targets.

## 6. Desktop entry

`scripts/install-dock-icon.sh` writes an Exec line shaped like:

```text
bash <root>/scripts/playtest.sh launch
```

It sets the project root as the desktop `Path`.
It does not set `SC2_MAP_SOURCE`.
The entrypoint chooses the fresh map.
The installer validates the desktop entry and exports an absolute `UV_BIN`.
The entrypoint exports `UV_BIN` to every child process.

## 7. Failure behavior

The entrypoint stops on the first failure.
It does not launch a test or game after a failed build.
It does not use `src/` when the build fails.
It does not use a previously built map.
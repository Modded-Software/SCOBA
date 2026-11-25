# SPEC-PATHS: Where the Project Writes

**Date:** 2026-11-25
**Status:** Built. The data move of section 7 is an operator step.
**Owner:** operator decision 2026-11-25

## 1. Purpose

The repository disk is encrypted (LUKS). Heavy writes there starve the
desktop: a texture bake run wrote 18 GB and 100,000 files and froze it.
The repository therefore holds source only. Everything the tools make or
extract goes to a work root on the fast, unencrypted disk.

## 2. Rules

| Id | Rule |
| --- | --- |
| P-1 | One file names the places: `env/paths.conf`. It is committed. |
| P-2 | One resolver reads it: `scripts/paths.sh`. It derives every path, checks it, makes the folders and exports the result. |
| P-3 | Every other script only reads the exported variables. Python reads them through `scripts/workpaths.py`; the viewer through `requiredPath` in `webviewer/src/server/core/settings.ts`. |
| P-4 | A reader guesses nothing. An unset, blank or relative value is an error that names `make` and `scripts/playtest.sh`. |
| P-5 | A variable already set in the environment wins over `env/paths.conf` and over the derived value. |
| P-6 | No work folder may lie on the repository's disk. `paths_check_device` refuses it. `SC2_ALLOW_REPO_DISK=1` allows it for one run. |
| P-7 | No module reads a path when it is imported. A path is read when the code runs. |
| P-8 | The entrypoints are `make` and `scripts/playtest.sh`. The viewer scripts, the launchers and the editor icon source the resolver themselves. Single tool scripts are not entrypoints. |
| P-9 | Temporary files go to `SC2_TMP`. The resolver exports it as `TMPDIR`, so `tempfile` and `mktemp` use it. |

## 3. Settings in env/paths.conf

| Name | Meaning |
| --- | --- |
| `SC2_WORK` | The work root. Today `/mnt/ws-fast/sc2work`. |
| `SC2RES` | Extracted game resources (`scripts/sc2res.py`). |
| `SC2_MAP_NAME` | The file name of the built map below `SC2_OUT`. |
| `BNET_PREFIX` | The Wine prefix of the game. |
| `SC2_WINE_DRIVE` | Drive C below the prefix: `pfx/drive_c` for a Proton prefix, `drive_c` for plain Wine. |
| `SC2_WINE_USER` | The Windows user of the prefix. |

A value may name `$HOME` and nothing else.

## 4. Derived paths

| Variable | Default | Holds |
| --- | --- | --- |
| `SC2_OUT` | `SC2_WORK/out` | The built map, profile maps, build log and lock. |
| `SC2_BUILT_MAP` | `SC2_OUT/SC2_MAP_NAME` | The built map. |
| `SC2_BUILD_STAMP` | `SC2_OUT/.last-build-stamp` | The stamp of the last build. |
| `SC2_BUILD` | `SC2_WORK/build` | Tool builds and caches: the stormex checkout (`deps/stormex`), the old texture caches (`hdtex`). |
| `TEXTURE_STORE` | `SC2_BUILD/texture-store` | The texture store (SPEC-HD-TEXTURES). |
| `SC2_TEST_RUNS` | `SC2_WORK/test-runs` | In-game test runs: `<profile>/<run>/summary.txt`. |
| `SC2_TESTKIT` | `SC2_WORK/testkit` | Files the test profiles generate, such as the hdbake store and map. |
| `SC2_TMP` | `SC2_WORK/tmp` | Temporary files; exported as `TMPDIR`. |
| `UV_PROJECT_ENVIRONMENT` | `SC2_WORK/venv` | The Python environment uv makes. |
| `WEBVIEWER_WORK` | `SC2_WORK/webviewer` | The viewer's `build`, `node_modules`, `test-results` and default data. |
| `SC2_INSTALL` | `BNET_PREFIX/SC2_WINE_DRIVE/Program Files (x86)/StarCraft II` | The game install. |
| `SC2_DOCUMENTS` | `BNET_PREFIX/SC2_WINE_DRIVE/users/SC2_WINE_USER/Documents/StarCraft II` | Banks, logs and `Variables.txt`. |
| `SC2_MAP_CACHE` | `BNET_PREFIX/SC2_WINE_DRIVE/ProgramData/Blizzard Entertainment/StarCraft II/Maps/Cache` | The game's map cache, cleared before each launch. |

`scripts/workpaths.py` lists the same names in `NAMES`. A host test checks
that the two lists agree.

## 5. The viewer

`webviewer/scripts/paths.sh` sources the resolver, runs the device check,
and sets `SC2_PATH` from `SC2_INSTALL` and `WEBVIEWER_DATA` from
`webviewer/local.env` or `WEBVIEWER_WORK/data`.

The viewer code names `build/`, `node_modules/` and `test-results/` below
`webviewer/`. Each of them is a link into `WEBVIEWER_WORK`. The script
makes a missing link. A real folder in its place is data that has not
moved: the script stops with an error and moves nothing.

`webviewer/ref/`, the reference repos, stays a real folder in the repo
(operator 2026-11-25). The script stops with an error when it is a link.

A plain `npm install` replaces the `node_modules` link with a real folder.
So `viewer_npm_install` in `webviewer/scripts/paths.sh` runs npm in
`WEBVIEWER_WORK` on a copy of `package.json` and the lock. It copies a
changed lock back to the repo, and stops with an error if the link is gone.
`make viewer-install` and the service setup use it.

The service runs `webviewer/scripts/start.sh`, so it gets the same paths.
The server stops at start when `TEXTURE_STORE`, `SC2_PATH` or
`WEBVIEWER_DATA` is unset.

## 6. Guards

The host test `scripts/testkit/tests/test_workpaths.py` checks:

- the resolver exports exactly the names of `NAMES`, all absolute, and the
  derived folders exist;
- the environment wins; a blank or relative value is refused; a folder on
  the repository disk is refused unless `SC2_ALLOW_REPO_DISK=1`;
- `workpaths.path` raises `PathsError` for an unknown, unset, blank or
  relative name, and for a file where a folder belongs;
- no Python module under `scripts/` reads a path at import;
- no script hard-codes the repository's `out` or `build` (joined to the
  root, or as a relative `Path("out/...")`), the system `/tmp`, the game
  prefix or the Wine prefix layout;
- no Python reads a path variable from the environment past `workpaths`.

`scripts/testkit/tests/deps/test_deps.py` checks that `deps.sh` refuses to
run without the paths `make` passes.

`scripts/build.sh` writes `BuildManifest.txt` in byte order of the file
names, so the manifest hash does not depend on the disk.
`scripts/testkit/tests/test_build_manifest.py` checks the order, one line
per file with its hash, and no line for the manifest itself.

## 7. Moving the data

The operator stops the viewer service, any test run and the game, then
copies each old folder to its new place with its hard links kept, checks
file counts and checksums, and rebuilds. The repository copies are
deleted only after that check passes. The game prefix moves as a whole;
`BNET_PREFIX` then names its new place.

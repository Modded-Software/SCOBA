# SCOBA

SCOBA is an old-school battle arena that builds upon the core StarCraft
gameloop and mechanics.

## Key Features

- Command individual units in third-person, first-person and VR, with support
  for KBM and gamepad controls.
- Procedural map generation and cross-match account progression inside a
  persistent MMO world.
- Real-time planet-scale combat, multi-map base expansion, and live
  territorial contention.
- P2P play, AI automation (including offline base defense), and more.

## Visuals & Environment

- Realistic visual scaling of units, buildings and environments.
- High-resolution terrain and skybox textures.
- Terrain deformation, destructible props, and physics-based platforming
  mechanics.
- Hydraulic surface erosion, dynamic skylight and weather simulation.

## Matchmaking

- Self-hosted realms and servers through aiarena, up to 8 players per match.
  A public IP address or a VPN is required.
- Custom SCOBA Link launcher app and a managed VPN service. Both are available
  on self-hosted realms and on scoba.link as a public service.

## State Of This Repository

The list above is the project goal. This repository holds the StarCraft II map
and its tooling. Work in progress:

- Third-person hero control with two modes: `WASD / Point & Click` and
  `WASD / TPS`.
- Two heroes, hero switch, order mode, HUD, and the character animation layer.
- A deterministic map build and an in-game test kit.
- Terrain and model textures upscaled four times per side, kept in a texture
  store. A selection picks a result and a size per texture. The map build
  packages the selection of the dataset `scoba`:
  [REQ-HD-TEXTURES](docs/requirements/REQ-HD-TEXTURES.md),
  [SPEC-HD-TEXTURES](docs/specifications/SPEC-HD-TEXTURES.md)

Two control modes have a contract and a state document:

- `WASD / Point & Click`:
  [REQ-POINT-AND-CLICK](docs/requirements/REQ-POINT-AND-CLICK.md),
  [SPEC-POINT-AND-CLICK](docs/specifications/SPEC-POINT-AND-CLICK.md)
- `WASD / TPS`, current phase, design only:
  [REQ-TPS](docs/requirements/REQ-TPS.md),
  [SPEC-TPS](docs/specifications/SPEC-TPS.md)

## Layout

| Path | Content |
| --- | --- |
| `src/SCOBA.SC2Map/` | The map source: game data XML, Galaxy script, assets. |
| `src/SCOBA.SC2Map/scripts/app/` | Galaxy modules. |
| `scripts/` | Build, validation, launch, and test tooling. |
| `scripts/testkit/` | In-game test harness and profiles. |
| `scripts/setup/deps.sh` | Dependency checks and installs behind `make deps-check`, `install-deps`, `install-hdtex`. |
| `deploy/ansible/` | Ansible playbook for the model viewer dev server (systemd user service). |
| `scripts/setup/patches/stormex/` | Patches `deps.sh` applies to the stormex source before it builds. |
| `tools/stormex`, `tools/stormex.pins` | The CASC extractor and the pins it was built from, written by `make install-deps`. Not in git. |
| `scripts/hdtex/core/`, `scripts/hd_textures.py` | Texture upscaling for any game: store, steps, selection, requests, package. |
| `scripts/hdtex/sc2/` | The StarCraft II adapter: textures of a dataset, model copies, map packaging. |
| `env/paths.conf`, `scripts/paths.sh` | Where the project writes, and the one resolver of those paths. See below. |
| `original/` | The untouched source map. |
| `docs/` | Requirements and specifications. |

### Work folders

The repository holds source only. Its disk is encrypted, and heavy writes
there freeze the desktop. Built maps, test runs, the texture store, extracted
game files, temp files and the Python and Node environments go below
`SC2_WORK` (`env/paths.conf`, today `/mnt/ws-fast/sc2work`).
[SPEC-PATHS](docs/specifications/SPEC-PATHS.md) lists every folder.

| Variable | Default | Holds |
| --- | --- | --- |
| `SC2_OUT` | `SC2_WORK/out` | The built map (`SC2_BUILT_MAP`) and the profile maps. Never edited by hand. |
| `SC2_TEST_RUNS` | `SC2_WORK/test-runs` | In-game test runs. |
| `TEXTURE_STORE` | `SC2_WORK/build/texture-store` | The texture store: results, selections, package records. |
| `SC2_BUILD` | `SC2_WORK/build` | The stormex source (`deps/stormex`), the caches of the earlier texture pipeline (`hdtex`). |
| `SC2_TMP` | `SC2_WORK/tmp` | Temp files (`TMPDIR`). |
| `UV_PROJECT_ENVIRONMENT` | `SC2_WORK/venv` | The Python environment. |
| `WEBVIEWER_WORK` | `SC2_WORK/webviewer` | The viewer's `build`, `node_modules`, `test-results`; `webviewer/` links to them. `webviewer/ref` stays in the repo. |

`make` and `scripts/playtest.sh` source `scripts/paths.sh`. It refuses a
work folder on the repository's disk. A variable set in the environment
wins over the file.

## Setup

| Command | Does |
| --- | --- |
| `sudo make init` | Root steps only, run first. Installs the system packages with apt (`SYSTEM_PACKAGES` in the Makefile: `libglm-dev`). Refuses to run as a user. |
| `make deps-check` | Report every dependency as `OK`, `MISSING` or `OPTIONAL`. Installs nothing. Exit 1 if a required one is missing. |
| `make install` | `make install-deps`. Git hooks are separate: `sudo make install-hooks`. |
| `make install-deps` | `uv sync --frozen`, build `tools/stormex`, `make viewer-install`, build the nodsdk parser library and its `NODExport` tool, then `make deps-check`. Needs `sudo make init` first. |
| `make install-hdtex` | Clone `../upscale-on-arc` if absent, check its pinned commit, run its `make install`. Only a texture request needs it. |

All steps are in `scripts/setup/deps.sh` and can run again safely.

- **stormex** is built from source: Talv/stormex (`github.com/Talv/stormex`)
  at `v2.2.0` (commit `1e93179`). Upstream ships only a Windows binary and has
  had no commit since 2019. Its tag pins a CascLib commit (`b2bd4c8`) that no
  public repository has, so the gitlinks are not used. Each dependency is the
  latest stable tag of its maintained upstream:

  | Dependency | Tag | Commit |
  | --- | --- | --- |
  | CascLib (`github.com/ladislav-zezula/CascLib`) | `3.0` | `4971d36` |
  | cxxopts (`github.com/jarro2783/cxxopts`) | `v3.3.1` | `44380e5` |
  | plog (`github.com/SergiusTheBest/plog`) | `1.1.11` | `e5c033e` |

  `scripts/setup/patches/stormex/` makes the 2019 source build against them.
  The source goes to `SC2_BUILD/deps/stormex`. The build uses the system compiler
  and linker (`STORMEX_PATH`, default `/usr/local/bin:/usr/bin:/bin`). The
  pins go to `tools/stormex.pins`. The build is skipped while
  `tools/stormex --version` reports `v2.2.0` and that file matches the current
  pins. Needs `cmake`, a system C++ compiler, and the FUSE 2 headers (Ubuntu:
  `libfuse-dev`).
- **upscale-on-arc** is
  Modded-Software/upscale-on-arc (`github.com/Modded-Software/upscale-on-arc`).
  A checkout must contain commit `b35fa07`.
- **Model viewer**: `make viewer-install` runs `npm install` (into
  `WEBVIEWER_WORK`), installs the Playwright browser, clones the pinned
  mdx-m3-viewer (`github.com/flowtsohg/mdx-m3-viewer`) into
  `webviewer/ref/` (a real folder in the repo) with `webviewer/patches/`
  applied, and builds the renderer.
- Not installed by any step: StarCraft II, GE-Proton, lsfg-vk. See
  [Requirements](#requirements).

`deps.sh` takes the work folders and the game install from `scripts/paths.sh`
and refuses to run without them. It reads `STORMEX`, `STORMEX_SRC`,
`STORMEX_PATH`, `UPSCALE_DIR`, `NODSDK_SRC`, `NODSDK_BUILD` and `STEAM_ROOT`
to override its own paths.

## Build And Test

`scripts/playtest.sh` and `make` are the only entry points. Every playtest
action rebuilds the map first.

| Command | Does |
| --- | --- |
| `scripts/playtest.sh build` | Rebuild and validate the map (`SC2_BUILT_MAP`). |
| `scripts/playtest.sh host-tests` | Rebuild, then run the Python `unittest` suite for the tooling. |
| `scripts/playtest.sh launch` | Rebuild, then launch the map. |
| `scripts/playtest.sh combat` | Run the full Point & Click suite, about three minutes. |
| `scripts/playtest.sh combat <group>` | Run one group, about one minute. Groups: `idle`, `single`, `auto`, `cancel`, `wasd`, `hold`, `button`, `switch`, `kerrigan`. |
| `scripts/playtest.sh pncprobe` | Run the engine probes. |
| `scripts/playtest.sh launch-check` | Rebuild, launch the map, and check the game logs. |
| `make host-tests` | The same as `scripts/playtest.sh host-tests`. |
| `make measure-hit-volumes`, `measure-footprints`, `measure-rim-falls`, `measure-water-features`, `classic-skins` | The measuring tools; they write the committed data under `scripts/data/` or `src/`. `ARGS=` passes options. |
| `make map-stage OUT=<folder>` | Expand the map into a folder without checks, to measure a changed map. |

The texture pipeline (`scripts/hd_textures.py`) runs from the viewer, which
gives it the paths. By hand: `make hd-textures ARGS="<command> ..."`. See [SPEC-HD-TEXTURES](docs/specifications/SPEC-HD-TEXTURES.md),
section 4.8.

The map build packages the picks of the dataset `scoba` as its last step. It
upscales nothing. It fails when a pick names a result that is missing, stale
or blocked. With no selection, the map keeps the built-in textures.

A test run stops any running StarCraft II process. Do not click in the game
window during a run: real mouse input makes the run invalid.

Results are written to `SC2_TEST_RUNS/<profile>/<run>/summary.txt`.

The testing rules for contributors and agents are in [AGENTS.md](AGENTS.md).

## Model Viewer Dev Server

The viewer runs as the systemd user service `sc2-viewer-dev` at
`http://127.0.0.1:4517/`. Ansible makes it: `deploy/ansible/viewer-dev.yml`,
role `viewer_dev`. It runs on this machine as the checkout's owner, with no
root. Every start, stop and restart goes through the playbook.

| Command | Does |
| --- | --- |
| `make viewer-provision` | Check linger, node 24 and `webviewer/local.env`; install the node packages; set up the renderer clone; build; make a missing catalog; write and enable the units; start; wait for `/api/health`; check that the port is held by the service. A second run changes nothing. `RESTART=1` restarts too. |
| `make viewer-start` | The same as `viewer-provision`. |
| `make viewer-restart` | Restart. A start rebuilds from the checkout. Not needed for code changes: the service hot reloads (a change under `webviewer/src/` rebuilds; a new `build/server.js` restarts the server). |
| `make viewer-stop` | Stop the server and its health check. Check that the port is free. The units stay. |
| `make viewer-unprovision` | Stop, disable and remove the units. |
| `make viewer-status`, `make viewer-logs` | Show the unit and the health answer; the last log lines (`LINES=n`). Read only. |
| `make viewer-serve` | The server in the foreground, for debugging. Beside the service it needs another `PORT`. |

- The service starts at boot (linger), and restarts 5 s after it exits. In a
  crash loop the wait grows to 60 s; it never gives up.
- The timer `sc2-viewer-dev-healthcheck.timer` runs
  `webviewer/scripts/healthcheck.sh` every 2 minutes. When the server does
  not answer twice, 5 s apart, it is restarted. A server younger than 180 s
  is still building and is left alone.
- The playbook refuses to start when another process holds the port. It
  names the pid and stops nothing.
- Each command the playbook runs writes its output to a step log in
  `~/.local/state/sc2-viewer-dev/steps/`, kept until the next run. The
  playbook shows each log after its step.
- Settings: `-e viewer_port=`, `viewer_host`, `viewer_node_bin`, in
  `deploy/ansible/roles/viewer_dev/defaults/main.yml`.
- The viewer shows two games: StarCraft II and StarCraft: Ghost. Ghost
  needs `GHOST_PATH` in `webviewer/local.env`, the folder of an unpacked
  build (with `3D/Models`), and `NODExport` built by `make install-deps`
  (`NODSDK_EXPORT` names another). Without them the Ghost tab is disabled
  and names the reason; StarCraft II still works.
- `make viewer-ghost-export-check` exports every Ghost model and clip
  through `NODExport` and checks the results and the refusals.

## Desktop Entries

`scripts/install-dock-icon.sh` provisions both the plain `SCOBA` entry and
`SCOBA FG`. Both put the game on GPU `0000:09:00.0` by default. The FG entry
also puts lsfg-vk frame generation on GPU `0000:03:00.0`.

Set `SCOBA_GAME_GPU` or `SCOBA_FG_GPU` to change either GPU. The launch
scripts read them at run time. The installer also reads them, writes them into
the entries when set, and validates the GPU render nodes and the installed
lsfg-vk layer. It does not install lsfg-vk.

`scripts/install-editor-dock-icon.sh` provisions `SCOBA Editor`.

Every entry starts through the launch dialog (`scripts/launch-dialog.sh`,
[REQ-LAUNCH-DIALOG](docs/requirements/REQ-LAUNCH-DIALOG.md)). It shows the
steps, the progress and the log of the build and the launch, and stays open
when the run shows an error. The log of the last run of each action is in
`~/.local/state/scoba/dialog-<action>.log`. Run both installers again after
a change to the entries.

## Requirements

- StarCraft II installed under a Wine or Proton prefix, launched with
  GE-Proton. `env/paths.conf` names the prefix (`BNET_PREFIX`), its drive C
  (`SC2_WINE_DRIVE`) and its Windows user (`SC2_WINE_USER`). GE-Proton is
  looked up under the Flatpak Steam's `compatibilitytools.d`.
- `uv` for the Python tooling.
- `git`, `node` and `npm`, `cmake`, a C++ compiler, and the FUSE 2 headers.
- The GLM headers, for the nodsdk parser library: `sudo make init`.
- Optional: lsfg-vk, for the `SCOBA FG` entry. An Intel Arc GPU, for
  texture requests. `gjs` with GTK 4 and libadwaita, for the launch dialog
  of the desktop entries (GNOME ships them).

`make deps-check` checks all of these.

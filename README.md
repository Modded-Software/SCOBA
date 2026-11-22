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
- Terrain textures upscaled four times per side, in two variants, `Upscale 4x`
  and `Generative 4x`. The map build applies one of them:
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
| `scripts/setup/deps.sh` | Dependency checks and installs behind `make init`, `install-deps`, `install-hdtex`. |
| `scripts/setup/patches/stormex/` | Patches `deps.sh` applies to the stormex source before it builds. |
| `.venv/src/stormex/` | The stormex source checkout built by setup. Not in git. |
| `tools/stormex`, `tools/stormex.pins` | The CASC extractor and the pins it was built from, written by `make install-deps`. Not in git. |
| `scripts/hdtex/`, `scripts/hd_textures.py` | Texture upscaling: extract, upscale, encode, inject. |
| `build/hdtex/` | Cache of upscaled textures, one folder per variant. Not in git. |
| `original/` | The untouched source map. |
| `out/` | Build output and test runs. Never edited by hand. |
| `docs/` | Requirements and specifications. |

## Setup

| Command | Does |
| --- | --- |
| `make init` | Report every dependency as `OK`, `MISSING` or `OPTIONAL`. Installs nothing. Exit 1 if a required one is missing. |
| `make install` | `make install-deps`. Git hooks are separate: `sudo make install-hooks`. |
| `make install-deps` | `uv sync --frozen`, build `tools/stormex`, `make viewer-install`, then `make init`. |
| `make install-hdtex` | Clone `../upscale-on-arc` if absent, check its pinned commit, run its `make install`. Only the HD texture cache build needs it. |

All steps are in `scripts/setup/deps.sh` and can run again safely.

- **stormex** is built from source: [Talv/stormex](https://github.com/Talv/stormex)
  at `v2.2.0` (commit `1e93179`). Upstream ships only a Windows binary and has
  had no commit since 2019. Its tag pins a CascLib commit (`b2bd4c8`) that no
  public repository has, so the gitlinks are not used. Each dependency is the
  latest stable tag of its maintained upstream:

  | Dependency | Tag | Commit |
  | --- | --- | --- |
  | [CascLib](https://github.com/ladislav-zezula/CascLib) | `3.0` | `4971d36` |
  | [cxxopts](https://github.com/jarro2783/cxxopts) | `v3.3.1` | `44380e5` |
  | [plog](https://github.com/SergiusTheBest/plog) | `1.1.11` | `e5c033e` |

  `scripts/setup/patches/stormex/` makes the 2019 source build against them.
  The source goes to `.venv/src/stormex`. The build uses the system compiler
  and linker (`STORMEX_PATH`, default `/usr/local/bin:/usr/bin:/bin`). The
  pins go to `tools/stormex.pins`. The build is skipped while
  `tools/stormex --version` reports `v2.2.0` and that file matches the current
  pins. Needs `cmake`, a system C++ compiler, and the FUSE 2 headers (Ubuntu:
  `libfuse-dev`).
- **upscale-on-arc** is
  [Modded-Software/upscale-on-arc](https://github.com/Modded-Software/upscale-on-arc).
  A checkout must contain commit `b35fa07`.
- **Model viewer**: `make viewer-install` runs `npm install`, installs the
  Playwright browser, clones the pinned
  [mdx-m3-viewer](https://github.com/flowtsohg/mdx-m3-viewer) into
  `webviewer/ref/` with `webviewer/patches/` applied, and builds the renderer.
- Not installed by any step: StarCraft II, GE-Proton, lsfg-vk. See
  [Requirements](#requirements).

`deps.sh` reads `STORMEX`, `STORMEX_SRC`, `STORMEX_PATH`, `UPSCALE_DIR`, `BNET_PREFIX`,
`SC2_DIR` and `STEAM_ROOT` to override its paths.

## Build And Test

`scripts/playtest.sh` is the only entry point. Every action rebuilds the map
first.

| Command | Does |
| --- | --- |
| `scripts/playtest.sh build` | Rebuild and validate `out/SCOBA256.SC2Map`. |
| `scripts/playtest.sh host-tests` | Rebuild, then run the Python `unittest` suite for the tooling. |
| `scripts/playtest.sh launch` | Rebuild, then launch the map. |
| `scripts/playtest.sh combat` | Run the full Point & Click suite, about three minutes. |
| `scripts/playtest.sh combat <group>` | Run one group, about one minute. Groups: `idle`, `single`, `auto`, `cancel`, `wasd`, `hold`, `button`, `switch`, `kerrigan`. |
| `scripts/playtest.sh pncprobe` | Run the engine probes. |
| `scripts/playtest.sh launch-check` | Rebuild, launch the map, and check the game logs. |
| `uv run python scripts/hd_textures.py build --gpu 1` | Fill the cache of the `Upscale 4x` textures. Needs `../upscale-on-arc` and a GPU. Run once; the map build applies the cache. |
| `uv run python scripts/hd_textures.py --variant generative build --gpu 1` | Fill the cache of the `Generative 4x` textures. Its input is the `Upscale 4x` colour at 2048, so build `Upscale 4x` first. |
| `uv run python scripts/hd_textures.py compare` | Write a web page that shows every texture as original, upscaled, and generative: `build/hdtex/compare/index.html`. |

`SC2_HD_TEXTURES` picks the terrain textures of a build:

| Value | The map gets |
| --- | --- |
| not set | `Upscale 4x`. Without its cache, the built-in textures. |
| `upscale` | `Upscale 4x`. The build fails without its cache. |
| `generative` | `Generative 4x`. The build fails without its cache. |
| `off` | The built-in textures. |

For example: `SC2_HD_TEXTURES=generative scripts/playtest.sh build`.

A test run stops any running StarCraft II process. Do not click in the game
window during a run: real mouse input makes the run invalid.

Results are written to `out/test-runs/<profile>/<run>/summary.txt`.

The testing rules for contributors and agents are in [AGENTS.md](AGENTS.md).

## Desktop Entries

`scripts/install-dock-icon.sh` provisions both the plain `SCOBA` entry and
`SCOBA FG`. Both put the game on GPU `0000:09:00.0` by default. The FG entry
also puts lsfg-vk frame generation on GPU `0000:03:00.0`.

Set `SCOBA_GAME_GPU` or `SCOBA_FG_GPU` to change either GPU. The launch
scripts read them at run time. The installer also reads them, writes them into
the entries when set, and validates the GPU render nodes and the installed
lsfg-vk layer. It does not install lsfg-vk.

## Requirements

- StarCraft II installed under a Proton prefix, launched with GE-Proton. The
  test runner reads `SC2_GAME_PREFIX`, default `~/Games/battlenet-prefix`.
  GE-Proton is looked up under the Flatpak Steam's `compatibilitytools.d`.
- `uv` for the Python tooling.
- `git`, `node` and `npm`, `cmake`, a C++ compiler, and the FUSE 2 headers.
- Optional: lsfg-vk, for the `SCOBA FG` entry. An Intel Arc GPU, for the HD
  texture cache build.

`make init` checks all of these.

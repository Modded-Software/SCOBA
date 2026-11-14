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

The current phase is `WASD / Point & Click`. Its contract and state are in:

- [REQ-POINT-AND-CLICK](docs/requirements/REQ-POINT-AND-CLICK.md)
- [SPEC-POINT-AND-CLICK](docs/specifications/SPEC-POINT-AND-CLICK.md)

## Layout

| Path | Content |
| --- | --- |
| `src/SCOBA.SC2Map/` | The map source: game data XML, Galaxy script, assets. |
| `src/SCOBA.SC2Map/scripts/app/` | Galaxy modules. |
| `scripts/` | Build, validation, launch, and test tooling. |
| `scripts/testkit/` | In-game test harness and profiles. |
| `original/` | The untouched source map. |
| `out/` | Build output and test runs. Never edited by hand. |
| `docs/` | Requirements and specifications. |

## Build And Test

`scripts/playtest.sh` is the only entry point. Every action rebuilds the map
first.

| Command | Does |
| --- | --- |
| `scripts/playtest.sh build` | Rebuild and validate `out/SCOBA256.SC2Map`. |
| `scripts/playtest.sh launch` | Rebuild, then launch the map. |
| `scripts/playtest.sh combat` | Run the full Point & Click suite, about three minutes. |
| `scripts/playtest.sh combat <group>` | Run one group, about one minute. Groups: `idle`, `single`, `auto`, `cancel`, `wasd`, `hold`, `button`, `switch`, `kerrigan`. |
| `scripts/playtest.sh pncprobe` | Run the engine probes. |

A test run stops any running StarCraft II process. Do not click in the game
window during a run: real mouse input makes the run invalid.

Results are written to `out/test-runs/<profile>/<run>/summary.txt`.

The testing rules for contributors and agents are in [AGENTS.md](AGENTS.md).

## Requirements

- StarCraft II installed under a Proton prefix, launched with GE-Proton. The
  test runner reads `SC2_GAME_PREFIX`, default `~/Games/battlenet-prefix`.
- `uv` for the Python tooling.

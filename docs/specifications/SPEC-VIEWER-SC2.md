# SPEC-VIEWER-SC2: StarCraft II in the Asset Viewer

**Date:** 2026-11-24
**Status:** Built as the game module `src/games/sc2/`. Sections 5.4 and
8.2 are not built.
**Requirements:** [REQ-VIEWER](../requirements/REQ-VIEWER.md)
**Core:** [SPEC-VIEWER](SPEC-VIEWER.md)

Related: [GAP-ANALYSIS-WEBVIEWER](GAP-ANALYSIS-WEBVIEWER.md), what the M3
renderer does not draw as the game does.
[SPEC-HD-TEXTURES](SPEC-HD-TEXTURES.md), how textures are upscaled, kept
and packaged.

## 1. Identity

| Field | Value |
| --- | --- |
| Game id | `sc2` |
| Label | StarCraft II |
| Tab text | SC2 |
| Formats | `m3` (models), with DDS and TGA textures |
| Default dataset | `scoba` |

## 2. Labels

- **[today]**: the code does it, and the named test files passed in a full
  run of SPEC-VIEWER section 13.
- **[plan]**: not in the code.

Unmarked text is [today].

## 3. Data on the machine

Settings are environment variables.

| What | Setting | When unset |
| --- | --- | --- |
| The installed game | `SC2_PATH` | `SC2_INSTALL` (SPEC-PATHS) |
| Storage reader | `STORMEX` | `tools/stormex` |
| Data folder, outside git | `WEBVIEWER_DATA` | `WEBVIEWER_WORK/data` |
| Stock game data | `WEBVIEWER_STOCK` | `<data>/stock` |
| Catalogs | `WEBVIEWER_CATALOG` | `<data>/catalog` |
| Cache of extracted files | `WEBVIEWER_CACHE` | `<data>/cache` |
| Custom datasets | `WEBVIEWER_DATASETS` | `<data>/datasets` |
| Map layer of `scoba` | `WEBVIEWER_MAP` | `src/SCOBA.SC2Map` |
| Texture store | `TEXTURE_STORE` | `SC2_BUILD/texture-store` (SPEC-PATHS) |

- `scripts/paths.sh` sources the project resolver (SPEC-PATHS), reads
  `webviewer/local.env` and sets the first three. The server stops at
  start when `SC2_PATH`, `WEBVIEWER_DATA` or `TEXTURE_STORE` is unset; it
  guesses no folder.
- `scripts/test.sh` points the datasets at fixtures and the texture store
  at its own, emptied each run but for the game's index, with
  `HDTEX_RUNNER=repeat` (SPEC-VIEWER 17.8). A test run never reads the
  operator's.
- At start the backend lists every `.m3`, `.dds` and `.tga` of the
  storage. A file is extracted on its first request and cached.
- A model is addressed by its storage path. A texture is addressed by the
  in-model path, lower case with backslashes.
- Without the storage or the catalogs the server does not start. A missing
  catalog is named. [plan] the game is listed as not available instead
  (R-VIEW-8).
- The dev server is the systemd user service `sc2-viewer-dev` on
  `127.0.0.1:4517`, run by Ansible (`make viewer-start`, `viewer-stop`,
  `viewer-restart`). Every start rebuilds from the checkout. It hot
  reloads: a source change rebuilds, a new `build/server.js` restarts the
  server (`src/tools/dev.ts`).

## 4. Datasets

A dataset is the stock data and, on top, an optional map layer: a folder
shaped like a map.

| Id | Content |
| --- | --- |
| `scoba` | stock data with this repository's map on top |
| `stock` | stock data alone |
| other | a folder under the datasets folder with its own stock data, an optional `map/` and an optional label. Made by `scripts/dataset-new.sh`. |

- An asset resolves in the map layer first, then in the game storage
  (R-VIEW-33).
- The signature is a hash over the path, size and change time of every
  source file. A dataset has changed when it differs from the one its
  catalog was built from (R-VIEW-34).
- A reload rebuilds the catalog when the sources changed, then loads the
  dataset again. One reload runs at a time.
- A folder that is not a dataset is listed as a problem, with the reason.

## 5. Categories

Catalogs are built from the game's XML by the Python tools under
`webviewer/tools/`, through `scripts/catalog.sh`.

### 5.1 `units`

- Filters: `race` (buttons), `kind` (select), `family` (select; "no
  family" is a value).
- Search: every word must be in the name or the id. Order: the whole name,
  a name that starts with the text, a word that starts with it, the id.
  Among equals: units of the map, then family `Melee`.
- A unit's model is the file its data names, or that name with `_00`. A
  unit whose model cannot be served is left out and counted.
- Record data: race, kind, family, in the map, model file, the scale
  fields, height, radius, tint, animation speed, time scale, speed, walk
  animation speed, skybox.
- Picture: the portrait, or the icon.

### 5.2 `doodads`

- Filters: `type`, `tileset` (the terrain sets that list the doodad).
- A doodad has one file per model variation.
- A doodad that draws nothing in game is listed with its editor model. One
  with no file is left out and counted.
- Record data: type, tilesets, in the map, editor only, editor model, auto
  rotate, footprint, scale range, and the scale, tint and speed fields of
  a unit.

### 5.3 `models`

- Every `.m3` file the dataset can serve, by path. Search only. No "add
  all".
- The tab asks for the first 60 matches of the typed text and shows
  nothing for an empty text (O-SC2-3).

### 5.4 `terrain`

R-VIEW-107. `server/terrain.ts`. No gallery tab: the ground button lists
these records (SPEC-VIEWER 17.7).

- One record per `CTerrainTex` entry of the dataset with a colour file,
  from the pipeline's listing of the kind `terrain` (699 in `scoba` on
  2026-11-24). The id and the name are the entry id.
- A ground category. Not placeable. No "add all". No filter.
- Search: every word must be in the id, the colour file or a terrain set.
- Record data: the colour file, the normal map, the terrain sets that name
  it, and its state: the terrain bake, the number of variants, whether
  packaged [plan for bake and variants].
- Picture: none today; [plan] a preview of the colour file (R-VIEW-124).
- Ground: the colour file, one repeat every 8 world units (O-SC2-4).
- A double-click opens the texture window on its colour file and normal
  map.
- [plan] Filters `set` and `state`; the editor icon; a count of entries
  left out.

## 6. From record to instance

| Rule | Detail |
| --- | --- |
| Scale | actor scale x model scale x creation scale, per axis. A model scale range and a doodad's random scale range are read at the pick. |
| Height | a unit's height; 0 for a doodad and a bare file |
| Tint | the record's tint, as the vertex colour |
| Variant | a doodad: random unless one is wished |
| Angle | a doodad: random, unless its data forbids it; a unit: 0 |
| Rest animation | the first whose name starts with `stand`; else the first; else none |
| Play rate | animation speed x time scale. A `walk` animation also runs at speed / walk animation speed, when both are above 0. |
| Backdrop | a unit marked skybox is not placed: it becomes the backdrop. "Add all" leaves it out as "skybox unit". |

A unit is marked skybox when its model lies in a skybox folder of the
game, or a model entry with parent `Skybox` names it.

Item options, kept in the scene document:

| Option | Values | Meaning |
| --- | --- | --- |
| `team` | 0 to 13 | team colour; not for doodads |
| `skin` | core's skin choice (SPEC-VIEWER 17.4) [plan] | |

SC2 has no option of its own. A stored `hd` or `textures` is dropped when
read [plan for `textures`].

## 7. Format `m3`

- Renderer: `mdx-m3-viewer` at upstream commit `2ff0bc00`, with this
  repository's 56 patches (SPEC-VIEWER section 9). `src/formats/m3/` is
  the adapter to the core interfaces. It does not hold the renderer.
- The library tells an M3 file by its bytes. Animations are in the model
  file.
- Texture readers: DDS (DXT1, DXT3, DXT5, ATI2, uncompressed) and TGA.
- Capabilities: `teamColor` with 14 colours, `tint`, `textureOverride`,
  `edges`.
- Post pass: displacement materials, drawn over a copy of the frame.
- Probes: particle emitters, billboards, ground lights, alpha tests,
  constant colour layers, the fresnel term, vertex and index layout, draw
  order.
- Survey tools (R-VIEW-92): `scripts/m3-survey.sh` and the other survey
  scripts under `webviewer/scripts/`.

## 8. Backdrops and textures

### 8.1 Backdrops

- Every model in the game's skybox folder, named from the model entry that
  points at it, or from its file name.
- They come from the default dataset, whatever dataset an instance uses
  (O-SC2-2).

### 8.2 Textures

SPEC-VIEWER section 17.

- The backend's texture service is core's service over the pipeline, for
  the game id `sc2`, with each dataset's map layer as `--layer`. SC2 adds
  no route of its own; it has no extension route.
- The service's name of a texture is its in-model path, lower case with
  backslashes (`page/textures/originals.ts`).
- The textures of a record or an instance are those its model file names.
  The textures of a `terrain` record are its colour file and normal map.
- Owners (SPEC-HD-TEXTURES 5.1) [plan]: a `units` record is
  `unit:<id>`, a `doodads` record `actor:<id>`, a `models` record
  `model:<path>`. A `terrain` record has no owner; it bakes per texture.
  An owner's skins name the textures of every model its actor shows
  (death, portrait). The texture window, where skins are edited, lists
  only the textures of the model file in the view (17.3 of SPEC-VIEWER).
- The grid glows blue around an instance whose largest shown texture is
  2048 or more on a side, green around the rest.

## 9. Module

| Part | Holds |
| --- | --- |
| `server/` | storage index, datasets, catalogs, units, doodads, skyboxes, terrain, and the backend |
| `page/` | placement and play rate, data scale, record checks, preview cards, landmark names, test members, the game's parts, and `textures/`: what the texture window opens on |
| `shared/` | the record types |
| `src/formats/m3/` | the adapter, the format module, the displacement pass, the probes |

- The summary holds the counts: models, files, units, units without a
  model file, skyboxes, doodads, doodads without a model file, datasets.
- Only the icons the dataset's catalog lists are served.

## 10. Tests

In `webviewer/tests/`.

| Area | Files |
| --- | --- |
| Backend | `server`, `units-api`, `doodads-api`, `datasets-api` |
| Datasets in the page | `datasets-ui`; `datasets-change` (unit) |
| Gallery | `units-ui`, `doodads-ui`, `paged-list`, `add-all`, `add-all-view` |
| Record to instance | `units-ui`, `doodads-ui`, `anim-speed` |
| Backdrops | `skyboxes`, `skybox-units`, `ground-sky` |
| Textures | `texture-window`, `texture-service`, `ground-texture`; [plan] `texture-variants`, `texture-skins`, `texture-bake` in place of `texture-sets` |
| Format `m3` | `geometry`, `shader`, `uv`, `uv-anim`, `bounds`, `draw-order`, `constant-color`, `wide-index`, `cutout`, `displacement`, `fresnel`, `ground-lights`, `billboards`, `particles`, `particle-materials`, `particle-motion`, `particle-ground`, `doodads-survey` |

Negative cases:

- An instance of another game has no team colour control and no skin
  choice (`ghost-mix.spec`).
- [plan] a doodad row has no team colour control; a unit row has no
  variation control.

## 11. Open points

| ID | Point |
| --- | --- |
| O-SC2-1 | The `models` category lists the files of every dataset together. As a category of one dataset it should list that dataset's only. |
| O-SC2-2 | Whether each dataset should offer its own backdrops is not decided. |
| O-SC2-3 | As a paged list like the others, the `models` tab would list every file. That follows from R-VIEW-40, not from a stated wish. |
| O-SC2-4 | The repeat length of a terrain texture is a guess: 8 world units. The only field found is `TilingFreq` 4.0 on the default terrain set of `core`. Its meaning is not known. |
| O-SC2-5 | 108 terrain texture entries name a `Heightmap` file. It is not listed and not upscaled. |

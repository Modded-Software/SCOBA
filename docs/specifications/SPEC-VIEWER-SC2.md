# SPEC-VIEWER-SC2: StarCraft II in the Asset Viewer

**Date:** 2026-11-23
**Status:** The behaviour in sections 3 to 8 is what the current viewer
does, written from its code and its test titles. No test run is named in
this document. Its form as a game module (section 9) is design, not built.
**Requirements:** [REQ-VIEWER](../requirements/REQ-VIEWER.md)
**Core:** [SPEC-VIEWER](SPEC-VIEWER.md)

Related:

- [GAP-ANALYSIS-WEBVIEWER](GAP-ANALYSIS-WEBVIEWER.md): what the M3 renderer
  does not draw as the game does.
- [SPEC-HD-TEXTURES](SPEC-HD-TEXTURES.md): the upscaled textures the viewer
  can show.

## 1. Identity

| Field | Value |
| --- | --- |
| Game id | `sc2` |
| Label | StarCraft II |
| Tab text | SC2 |
| Formats | `m3` (models), with DDS and TGA textures |
| Default dataset | `scoba` |

## 2. Labels

- **[today]**: the current code does it. The test files named cover it and
  passed in the baseline run `full85`
  ([SPEC-VIEWER](SPEC-VIEWER.md), section 13).
- **[plan]**: not in the code.

## 3. Data on the machine

| What | Setting | When unset |
| --- | --- | --- |
| Game storage, the installed game | `SC2_PATH`, else `SC2_INSTALL` | a path under the home folder |
| Storage reader | `STORMEX` | `tools/stormex` |
| Data folder, outside git | `WEBVIEWER_DATA` | `webviewer/data` |
| Stock game data | `WEBVIEWER_STOCK` | `<data>/stock` |
| Catalogs | `WEBVIEWER_CATALOG` | `<data>/catalog` |
| Cache of extracted files | `WEBVIEWER_CACHE` | `<data>/cache` |
| Custom datasets | `WEBVIEWER_DATASETS` | `<data>/datasets` |
| Map layer of `scoba` | `WEBVIEWER_MAP` | `src/SCOBA.SC2Map` |
| Texture compare page | `WEBVIEWER_HDTEX` | `build/hdtex/compare` |
| Upscaled model textures, with `manifest.json` | `WEBVIEWER_HDTEX_MODELS` | `build/hdtex/upscale/models` |

Settings are environment variables [today]. `scripts/paths.sh` reads
`webviewer/local.env` and sets the first three. The server sets the rest.
`scripts/test.sh` points the datasets and the two texture folders at test
fixtures, so a test run never reads the operator's.

Without the game storage or the catalogs the game is not available
(R-VIEW-8), with the missing part named [plan]. Today the server does not
start without them: the storage is listed and the catalogs are read
before it listens. A missing catalog is named in the error.

The dev server on this machine is the systemd user service
`sc2-viewer-dev` on `127.0.0.1:4517`, made and run by Ansible
(`deploy/ansible/viewer-dev.yml`, `make viewer-provision`, `viewer-start`,
`viewer-stop`, `viewer-restart`). Its unit runs `scripts/start.sh`, so every
start rebuilds from the checkout. The README section "Model Viewer Dev
Server" has the commands and checks.

- At start the backend lists every `.m3`, `.dds` and `.tga` of the storage.
- A file is extracted on its first request and kept in the cache.
- A model is addressed by its storage path. A texture is addressed by the
  in-model path the model names, lower case with backslashes.

## 4. Datasets

A dataset is the stock data and, on top, an optional map layer: a folder
shaped like a map (`Base.SC2Data`, `enUS.SC2Data`, `Assets`).

| Id | Content |
| --- | --- |
| `scoba` | stock data with this repository's map on top |
| `stock` | stock data alone |
| other | `<datasets>/<id>/`: its own stock data, optional `map/`, optional `dataset.json` with a label. Made by `scripts/dataset-new.sh`. |

- An asset reference resolves in the dataset's map layer first, then in the
  game storage (R-VIEW-33).
- The signature is a hash over the path, size and change time of every
  source file. A dataset has changed when its signature differs from the
  one its catalog was built from (R-VIEW-34).
- A reload rebuilds the catalog with `scripts/catalog.sh --dataset <id>`
  when the sources changed, then loads the dataset again. One reload runs
  at a time.
- A folder that is not a dataset is listed under `problems` with the reason.

## 5. Categories

Catalogs are built from the game's XML by `tools/build_catalog.py` (units,
icons) and `tools/build_doodads.py` (doodads).

### 5.1 `units`

- Filters: `race` (buttons), `kind` (select), `family` (select; "no family"
  is a value of its own).
- Search: every word must be in the name or the id. Order: the whole name,
  a name that starts with the text, a word that starts with it, the id.
  Among equals: units of the map, then family `Melee`, then the rest.
- A unit whose model file cannot be served is left out and counted.
- Record data: `race`, `kind`, `family`, `inMap`, `m3`, `actorScale`,
  `modelScaleMin`, `modelScaleMax`, `eventScale`, `height`, `radius`,
  `tint`, `animSpeed`, `timeScale`, `speed`, `walkAnimMoveSpeed`, `skybox`.
- Picture: the portrait, or the icon when there is none.

### 5.2 `doodads`

- Filters: `type`, `tileset` (the terrain sets that list the doodad).
- A doodad has one file per model variation: `name_00.m3` and up, or
  `name.m3` alone.
- A doodad that draws nothing in game is listed with its editor model and
  `editorOnly`. One with no file at all is left out and counted.
- Record data: `type`, `tilesets`, `inMap`, `editorOnly`, `editorModel`,
  `autoRotate`, `footprint`, `scaleRange`, the scale fields of a unit,
  `tint`, `animSpeed`, `timeScale`.

### 5.3 `models`

- Every `.m3` file the dataset can serve, by path. Search only; no filter.
- No "add all".
- Today the tab is not a paged list. It asks for the first 60 matches of
  the typed text and shows nothing for an empty text. The route itself
  pages. As a category it becomes a paged list like the others (R-VIEW-40,
  O-SC2-3).

## 6. From record to instance

The rules of `place` and `playRate` (R-VIEW-44):

| Rule | Detail |
| --- | --- |
| Scale | actor scale x model scale x creation scale, per axis. A model scale range is read at `pick`. A doodad's random scale range is read at `pick` too, the same on every axis. |
| Height | a unit's `height`; 0 for a doodad and for a bare file. |
| Tint | the record's `tint`, applied as the vertex colour. |
| Variant | a doodad: a random variation unless one is wished. |
| Angle | a doodad: random, unless its data forbids it (`autoRotate` off); then 0. A unit: 0. |
| Rest animation | the first whose name starts with `stand`; else the first; else none. |
| Play rate | `animSpeed` x `timeScale`. An animation whose name starts with `walk` also runs at `speed` / `walkAnimMoveSpeed`, when both are above 0. |
| Backdrop | a unit marked `skybox` is not placed: it becomes the backdrop. It is not placeable for "add all" and is named "skybox unit". |

A unit is marked `skybox` when its model lies in a skybox folder of the
game, or a model entry with parent `Skybox` names it.

Item options (written to the scene address under `o`):

| Option | Values | Meaning |
| --- | --- | --- |
| `team` | 0 to 13 | team colour; not for doodads |
| `hd` | boolean, absent means on | the upscaled texture set |

## 7. Format `m3`

- Renderer: `mdx-m3-viewer` at upstream commit `2ff0bc00`, with this
  repository's changes as commits in `webviewer/ref/mdx-m3-viewer`. The
  same commits are kept as files in `webviewer/patches/` (53 today).
  `scripts/ref-setup.sh` builds the ref repo from them.
- The M3 parser, model, instance and shaders stay in the ref repo. They
  are viewer code (operator 2026-11-23), checked by
  `webviewer/tsconfig.lib.json`, the library's flags restated for
  compiler 7.0.2 (core specification, 9). `src/formats/m3/` is the
  adapter to the core interfaces. It does not hold the renderer.
- An M3 file starts with a magic number. The library tells it by its
  bytes, as today. The format gives no `parse`.
- Animations are in the model file. The format takes no `clips`.
- Texture readers: DDS and TGA. The DDS reader takes DXT1, DXT3, DXT5,
  ATI2 and files without a compression code.
- Capabilities: `teamColor` (14 colours), `tint`, `textureOverride`.
- Post pass: displacement materials, drawn over a copy of the frame.
- Probes for tests: particle emitters, billboards, ground lights, alpha
  tests, constant colour layers, the fresnel term, vertex and index
  layout, draw order.
- Survey tools (R-VIEW-92): `scripts/m3-survey.sh` and the other survey
  scripts under `webviewer/scripts/`.
- What it does not draw as the game does: the gap analysis.

## 8. Backdrops and game-only features

### 8.1 Backdrops

- Every model in the game's skybox folder, named from the model entry that
  points at it, or from its file name.
- They come from the default dataset, whatever dataset an instance uses.

### 8.2 Upscaled textures

Routes below `/api/sc2/x/`:

| Route | Reply |
| --- | --- |
| `hd-textures` | the in-model paths that have an upscaled file |
| `hd-asset?path=` | the upscaled file |
| `textures` | whether the texture compare page is built, and the command that builds it |
| `textures/...` | the texture compare page and its images |

- A model "has both sets" when a layer names a texture with an upscaled
  file. Such an instance starts with the upscaled set.
- `Ctrl+H` switches the selected instances that have both sets. The
  animation menu has an "hd" box for such an instance, and none for others.
- The grid glows blue around an instance whose largest texture is 2048 or
  more on a side, standard or upscaled; green around the rest.
- A double-click on a record or an instance opens the texture window: the
  compare page for its textures, and the originals of the rest, decoded in
  the page.

## 9. As a game module

Design, [plan]. `src/games/sc2/`:

| Part | Holds | From |
| --- | --- | --- |
| `server/` | storage index, datasets, catalogs, backdrops, the `x/` routes | today in `src/games/sc2/server/` (steps 4a and 4b): `storage.ts`, `datasets.ts`, `loaded.ts`, `catalog.ts`, `units.ts`, `doodads.ts`, `skyboxes.ts`, `textures.ts`, and `index.ts`, the game's `GameBackend` |
| `page/` | `place`, `playRate`, `describe`, item options, the texture features | `page/core/rules.ts` (data rules), `page/core/scene.ts` (doodad rules), `features/hd`, `features/textures`, the preview cards of `ui/gallery/units.ts` and `doodads.ts` |
| `shared/` | the unit and doodad record types | `src/shared/records.ts` |
| `formats/m3/` | the adapter to the library's M3 handler, the capabilities, the post pass and the probes | today in `src/formats/m3/`: `particles.ts`, `emitters.ts`, `billboards.ts`, `displacement.ts`; and parts of `features/inspect` |

The "From" column names the step 3 and 4a modules (SPEC-VIEWER section
13); the JavaScript files they came from are gone.

As built (SPEC-VIEWER section 13, steps 5b and 5c): `page/` holds
`game.ts`, `rules.ts`, `records.ts`, `describe.ts`, `api.ts`,
`parts.ts`, `hd.ts`, `textures/` and `gallery/`; `shared/records.ts`
holds the record types. The "From" files are gone, except
`page/core/scene.ts`, which no longer holds doodad rules.

Step 6: `gallery/` is gone; core's gallery draws the SC2 tabs from the
categories, and `names.ts` keeps the landmark names. `parts.ts`
(`installSc2Page`) takes the FeatureContext (SPEC-VIEWER 6.6) and gives
its test members through `testApi`: the adds of `api.ts` on
`sc2viewer`; `textureWindow` and `hdAssets` on both; `filterName` on
`SC2App`.
`hd.ts` and `textures/` take the context, not a page object. The M3
probes are reached as `sc2viewer.probe('m3', name, ...)`.

Routes before step 4b, and in the protocol of the core specification.
Step 4b switched the server, the page and the tests to the right column.
The left column is gone: each of its routes answers 404 (`server.spec`).

| Before step 4b | Now |
| --- | --- |
| `/api/datasets`, `/api/dataset/reload?id=` | `/api/sc2/datasets`, `/api/sc2/datasets/<id>/reload` |
| `/api/facets` | `/api/sc2/categories` |
| `/api/units`, `/api/doodads`, `/api/models` | `/api/sc2/records/<category>` |
| `/api/unit`, `/api/doodad` | `/api/sc2/record/<category>` |
| `/file`, `/asset`, `/icon/<name>` | `/api/sc2/file`, `/api/sc2/asset`, `/api/sc2/icon/<name>` |
| `/api/skyboxes` | `/api/sc2/backdrops` |
| `/api/hd-textures`, `/hd-asset`, `/textures/` | `/api/sc2/x/...` |
| `/api/health`, the counts in it | `/api/sc2/summary` |

Before step 4b a request without a dataset read `scoba`. Now the dataset
is required: `400` without it (`datasets-api.spec`).

The summary holds the counts `/api/health` held before step 4b: `models`,
`files`, `units`, `unitsWithoutModelFile`, `skyboxes`, `doodads`,
`doodadsWithoutModelFile`, `datasets`.

The categories are `units`, `doodads` and `models`. The gallery filters
are their `filters`: `race`, `kind`, `family` for units; `type`, `tileset`
for doodads.

Other rules of the server that stay:

- a unit's model is the file its data names, or that name with `_00`
  before the extension;
- only the icons the dataset's catalog lists are served;
- a reload is a `POST`, for a known dataset.

## 10. Tests

[today], in `webviewer/tests/`. Titles were read. All passed in the
baseline run `full85` ([SPEC-VIEWER](SPEC-VIEWER.md), section 13).

| Area | Files |
| --- | --- |
| Backend | `server`, `units-api`, `doodads-api`, `datasets-api` |
| Datasets in the page | `datasets-ui`, `datasets-toast` |
| Gallery | `units-ui`, `doodads-ui`, `paged-list`, `add-all`, `add-all-view` |
| Record to instance | `units-ui`, `doodads-ui`, `anim-speed` |
| Backdrops | `skyboxes`, `skybox-units`, `ground-sky` |
| Upscaled textures | `hd-textures`, `texture-window` |
| Format `m3` | `geometry`, `shader`, `uv`, `uv-anim`, `bounds`, `draw-order`, `constant-color`, `wide-index`, `cutout`, `displacement`, `fresnel`, `ground-lights`, `billboards`, `particles`, `particle-materials`, `particle-motion`, `particle-ground`, `doodads-survey` |

After the move to a game module these must pass with the same assertions,
through the new routes and the typed test object.

Negative cases the module adds [plan]:

- a doodad row has no team colour control; a unit row has no variation
  control;
- an instance of another game shows neither, and no "hd" box.

## 11. Open points

| ID | Point |
| --- | --- |
| O-SC2-1 | The `models` category lists the files of every dataset together today. As a category of one dataset it lists that dataset's files only. |
| O-SC2-2 | Backdrops come from the default dataset only. Whether each dataset should offer its own is not decided. |
| O-SC2-3 | The `models` tab changes for the user: from "type to see 60 matches" to a paged list of every file. That is a consequence of R-VIEW-40, not a stated wish. |

# SPEC-HD-TEXTURES: Upscaled Terrain Textures

**Date:** 2026-11-15
**Status:** Built. Section 7 gives the state of each requirement and what
backs it. Section 8 lists what only the operator can judge. Section 9 lists
what is not tested.
**Requirements:** [REQ-HD-TEXTURES](../requirements/REQ-HD-TEXTURES.md)

## 1. Principle

The upscaled files are made once, on the GPU, and kept in a cache. The map
build copies them into the built map and points the game at them. The map
source is not touched.

There are two variants of the upscaled files, `Upscale 4x` and
`Generative 4x`. Each has its own cache. A build flag picks the one a map
build applies (section 5).

The game is not asked to treat a file differently. Each upscaled file has the
layout of its original and a new name. A catalog entry in the built map names
it in place of the original.

## 2. Labels

State of a design item:

- **[host]**: a Python `unittest` passed in the named run.
- **[boot]**: the map was launched and the log check passed in the named run.
- **[cache]**: `hd_textures.py verify` passed on the real cache.
- **[built]**: in the code. No passing check for this contract.
- **[operator]**: only a person can judge it. Listed in section 8.

Source of an engine fact:

- **[stock]**: read in the installed game's data.
- **[measured]**: computed from the game's files.
- **[boot]**: seen in the game logs of the named launch.

## 3. Engine Facts

| ID | Fact | Source |
| --- | --- | --- |
| H1 | The map paints with tile set `Zerus`, textures `Zerus1` to `Zerus8`. | `src/SCOBA.SC2Map/t3Terrain.xml` |
| H2 | A terrain texture is a `CTerrainTex` entry. `Texture` names the colour file, `Normalmap` the normal map. The entries are in `mods\swarm.sc2mod\base.sc2data\gamedata\terraintexdata.xml`. | [stock] |
| H3 | The 16 files are `mods\liberty.sc2mod\base.sc2assets\assets\textures\zerus_N.dds` and `zerus_Nnormal.dds`: DXT5, 1024x1024, 11 mips. | [stock] |
| H4 | Colour files hold a specular mask in alpha. Its values run from 0 to about 97. | [measured] |
| H5 | Normal maps hold X in alpha and Y in green. Red is 255 and blue is 0. The file ends in the 4 bytes `_NXD` after the last mip. | [measured] |
| H6 | The game's own mips fit averaging in linear light with gamma 2.2. Averaging the bytes misses its small levels by twice the error. | [measured] |
| H7 | The game keeps a table of texture sizes, `base.sc2data\texturereduction\texturereductionvalues.txt`. Its key is the file name alone. The line for a terrain texture is `zerus_1.dds:8:9:10:10:6:`. The numbers read as size exponents per quality setting. That reading is a guess. | [stock] |
| H8 | A map catalog `Base.SC2Data/GameData/TerrainTexData.xml` that sets `Texture` and `Normalmap` makes the game open the files it names. | [boot] launch 1: the log names all 16 map paths |
| H9 | A map file with the name of a table entry and another size is logged: `WARNING: Texture DB does not match file info or file is corrupt`. 16 lines, one per file. It is not known whether the game then loads the file reduced. | [boot] launch 1 |
| H10 | With names the table does not hold, the game logs no texture warning. | [boot] launches 2, 3, and 4 |
| H11 | A map with 16 files of 4096x4096 DXT5, about 22 MB each, loads. The built map folder measures 367M with `du -sh`. | [boot] launch 2 |

The launches are named in section 10.

## 4. Pipeline

`scripts/hd_textures.py` runs it. The code is the package `scripts/hdtex/`.

| Stage | Module | Does |
| --- | --- | --- |
| Resolve | `sources.py` | Reads the texture ids from `t3Terrain.xml`, the dependencies from `DocumentInfo`, and the `CTerrainTex` entries from the game's catalogs in load order. The map's own catalog is read last. Gives one `TextureRef` per file. |
| Extract | `casc.py` | Reads the originals from the game storage with `tools/stormex`. |
| Split | `roles.py` | Splits each file into planes the upscaler can handle. Colour file: `color` and `alpha`. Normal map: `normal`, with Z rebuilt. |
| Upscale | `upscaler.py` | Runs `arc-upscale` once per model on the planes, with its option that makes opposite edges match. The models come from the variant (4.2). |
| Join | `roles.py`, `lowfreq.py` | Joins the planes, matches the coarse content to the original, and builds the mip chain. Colour mips average in linear light (H6). Normals are unit length again on every level. |
| Encode | `bc3.py`, `dds.py` | Writes DXT5 with the original's trailer (H5). |
| Measure | `metrics.py` | Writes the numbers of section 6 into the manifest. |

The game ships no load order for its own archives. It is fixed in
`sources.DEPENDENCY_ARCHIVES`. A map with another dependency fails with a
message that names the table.

### 4.1 Cache

The cache of a variant is `build/hdtex/<variant>/<source>/`, such as
`build/hdtex/upscale/terrain/`. `SC2_HDTEX_CACHE` moves `build/hdtex`.
`build/` is not in git. A build of one variant writes below its own folder
only.

| Folder | Content |
| --- | --- |
| `original/` | Files as extracted. |
| `planes/<model>/` | PNG planes, the upscaler's input. |
| `upscaled/<model>/` | PNG planes after upscaling. |
| `dds/` | Finished files and one JSON entry each. |
| `preview/` | Comparison sheets. |
| `manifest.json` | The variant, and every file with its hash, size, source, catalog overrides, and measured numbers. |

The web page of section 8 is in `build/hdtex/compare/<source>/`.

Each output has a `.stamp` file: a hash of its inputs and settings. A stage is
skipped while the stamp matches.

The stamp of an upscaled plane holds the version of the tool: a hash of its
`upscale.py` and `uv.lock`. A change of the tool redoes every plane. This is
needed: after the tool's update of 2026-11-15 the model `fast` gave other
pixels for the same input, up to 6 of 255 levels apart. With one version of
the tool, three runs of `fast` gave the same file.

### 4.2 Variants And Models

`arc-upscale` has three models: `pbrify`, `fast`, and `seedvr2`. Its README
says of `seedvr2`: one-step diffusion, the most detail, slow, invents detail.
A variant names the model of each plane. The variants are in
`scripts/hdtex/variants.py`.

| Variant | Key | `color` | `alpha` | `normal` |
| --- | --- | --- | --- | --- |
| Upscale 4x | `upscale` | `pbrify`; `fast` for `zerus_4` and `zerus_8` | `fast` | `fast` |
| Generative 4x | `generative` | `seedvr2` | `fast` | `fast` |

Reasons, judged by eye on comparison crops:

- `pbrify` is the sharper one on colour.
- On dark, low-contrast colour `pbrify` invents structure: hatching on
  `zerus_4`, a repainted look on `zerus_8`. Those two use `fast`.
- `pbrify` draws a crosshatch pattern into smooth masks and normal maps, so
  those planes use `fast`.
- `seedvr2` invents detail. The mask and the normal map are data, so
  Generative 4x upscales them as Upscale 4x does. The two variants differ in
  the colour of the colour files alone. The normal map files are the same.
- From the 1024 original, `seedvr2` looked worse than Upscale 4x to the
  operator: it had too little to work with. So the input of Generative 4x
  colour is the Upscale 4x colour result, shrunk from 4096 to 2048 in linear
  light (`variants.Input`, `roles.shrink_color`). `seedvr2` makes 8192 of
  it, which is shrunk to 4096 the same way before the join.

Generative 4x needs the Upscale 4x cache. Without it the build fails and
names the command to run first. A new Upscale 4x colour result redoes the
Generative 4x texture made from it, and only that one.

`hd_textures.py --variant KEY` names the variant for `list`, `build`,
`verify`, and `preview`. The default is `upscale`.

`--model PLANE=MODEL` changes a plane for every texture.
`--model TEXTURE.PLANE=MODEL` changes it for one, such as
`zerus_4.color=pbrify`. A key that names no plane of the source is an error.

### 4.3 File names

An upscaled file is `Assets\Textures\scoba_hd\scoba_hd_<original name>`. The
prefix is needed: the game sizes a texture by its file name (H7, H9). A file
that keeps the original's name gets the original's table entry.

This also binds a later source. A file that shadows an original by path keeps
its name. Such a source needs catalog overrides and the prefix too.

## 5. Map Build

`expand_map.py` calls `hdtex.inject.apply_hd_textures`. The build flag is the
environment variable `SC2_HD_TEXTURES`:

| Value | The step |
| --- | --- |
| not set | Applies Upscale 4x. Without its cache it prints a notice and the map keeps the built-in textures. |
| `upscale` | Applies Upscale 4x. Fails without its cache. |
| `generative` | Applies Generative 4x. Fails without its cache. |
| `off` | Does nothing. The map keeps the built-in textures. |
| anything else | Fails. |

For the variant it applies, the step:

1. reads every `manifest.json` in the variant's cache, and fails when one
   names another variant;
2. fails when the map paints with a texture the cache does not cover;
3. checks each cached file against its hash and copies it to its map path;
4. writes the overrides into `Base.SC2Data/GameData/TerrainTexData.xml`,
   keeping what the file already holds;
5. prints the variant's name.

Both variants use the same map paths. A built map holds one variant.
`hdtex.inject.variant_in_map` names the cached variant whose files a built
map holds, by their hashes.

`validate-map.py` calls `hdtex.check.check_hd_textures`. It reads the built
map only and fails when:

- a catalog names a file that is not in the map;
- a file in the folder is named by no catalog;
- a file lacks the prefix (4.3);
- a file is not DXT5, has a side that is not a power of two, has a short mip
  chain, or has more than 16 bytes after the last mip;
- some terrain textures are upscaled and others are not.

The log checks fail on a texture warning in a new `Graphics.txt` log (H9):
`sc2-check-logs.py` for `launch-check`, `testkit/logs.py` for every profile
run.

## 6. Limits

`hd_textures.py verify` fails a file that misses one. The values are in
`scripts/hd_textures.py`.

The limits are the same for both variants.

| Limit | Value | Measures | Upscale 4x | Generative 4x |
| --- | --- | --- | --- | --- |
| Encode PSNR | at least 35 dB | Loss of the DXT5 encoding on the largest level. | 36.7 dB and up | 36.0 dB and up |
| Correlation | at least 0.7 | The result shrunk to the original's size, against the original, per channel. An inverted or swapped channel fails. | 0.83 and up | 0.80 and up |
| Coarse RMSE | at most 1.5 levels | A small mip of the result against the same mip made from the original. | 0.82 at most | 1.40 at most |
| Seam growth | at most 1.5 times the original's | The step across the wrap-around edge, relative to the step between inner neighbours. | Every file passes | Every file passes |

Generative 4x is closer to two limits than Upscale 4x: `Zerus_7` colour has
coarse RMSE 1.40 and correlation 0.87, `Zerus_1` colour has correlation 0.80.
In Upscale 4x those files measure 0.82 and 0.97, and 0.95.

`Zerus_2` has a seam in the original: ratio 2.88 for the colour file. The
Upscale 4x file measures 3.39, the Generative 4x file 3.55.

The eight normal map files are the same in both variants, byte for byte. The
eight colour files differ.

Without the coarse match of `lowfreq.py` the coarse RMSE of Upscale 4x
measured 1.9 to 2.35. It was not measured for Generative 4x.

## 7. State Of Each Requirement

Host tests are `test_hdtex_codec.py`, `test_hdtex_sources.py`,
`test_hdtex_build.py`, `test_hdtex_compare.py`, and `test_logs.py` under
`scripts/testkit/tests/`. They
use a storage and an upscaler made for the test. They do not run the game or
the GPU.

| ID | State | Backing |
| --- | --- | --- |
| R-HD-1 | [host] [boot] | `BuiltMapTest`; the builds of launches 3 and 4 printed `hd textures: injected 16 textures` with the variant's name. |
| R-HD-2 | [host] | `MapSourceTest`. |
| R-HD-3 | [host] | `TerrainRefsTest`, `MapFilesTest`, `CatalogTest`, `LocateTest`. `hd_textures.py list` gave 16 files for the map. |
| R-HD-4 | [built] | Ran for the real cache. Host tests replace the storage. |
| R-HD-5 | [built] | Ran for both real caches: 1024 to 4096 per side. Host tests replace the upscaler. |
| R-HD-6 | [host] | `PipelineTest`: a second build redoes nothing, a model change redoes one plane, another version of the tool redoes every plane. `UpscalerToolTest`: the version follows the tool's code and locked dependencies. |
| R-HD-10 | [host] [cache] | `DdsTest`, `NormalRoleTest`, `DiffuseRoleTest`, `PipelineTest`, `CheckTest`. |
| R-HD-11 | [host] [cache] | `LowFrequencyTest`, `DiffuseRoleTest`; limits of section 6. The look itself is O-HD-1. |
| R-HD-12 | [cache] | Seam limit of section 6. The look itself is O-HD-2. |
| R-HD-13 | [host] | `CommandLineTest`: each limit fails a file. |
| R-HD-15 | [host] | `ComparePageTest` and `ModelComparePageTest`: the page of all sources lists every plane of every source, each with a category, its users, and a thumbnail; its image paths exist. The page loaded in headless Chrome on 2026-11-19 with 253 rows and no console error. The filters and the look have no test; no mouse input was tried on the new page. |
| R-HD-50 to R-HD-55 | section 12 | Host tests in `test_hdtex_models.py`. Not finished. |
| R-HD-14 | [host] | `ComparePageTest` in `test_hdtex_compare.py`: the page lists every plane; the layers are ordered Upscale 4x, Generative 4x; each layer shows the file of its own variant; every image it names exists at the stated size. `hd_textures.py compare` wrote 24 entries with 72 images for the real caches. The lines of the page have no test in the repository (section 9). `hd_textures.py preview` wrote 16 sheets per variant; the sheets have no test. |
| R-HD-20 | [host] | `CheckTest`, `InjectTest`, `BuiltMapTest`. |
| R-HD-21 | [boot] | Launch 3 for Generative 4x, launch 4 for Upscale 4x. Launch 1 failed this with 16 texture warnings and led to 4.3. |
| R-HD-22 | [host] | `InjectTest`. Real build: section 10, build C. |
| R-HD-23 | [host] | `InjectTest`. Real build: section 10, build B. |
| R-HD-24 | [host] | `InjectTest`: changed file, missing file, missing texture, other manifest format. `VariantTest`: a cache folder that holds another variant. |
| R-HD-30 | [host] [cache] | `ModelChoiceTest`: the titles, and the models of each variant. `test_every_variant_gives_every_plane_a_model`. Both real caches pass `verify`. |
| R-HD-31 | [host] | `VariantTest`: a variant builds into its own folder and leaves the other's files and manifest alone. |
| R-HD-32 | [host] [boot] | `VariantTest`: the flag picks the variant, and the map then holds that variant's files and not the other's; without the flag the map holds Upscale 4x. `BuiltMapTest`: the built map holds the variant the flag names; passed in the builds of launches 3 and 4. |
| R-HD-33 | [host] | `VariantTest`: a named variant without a cache, and a value that names no variant, fail and leave the map alone. Real builds: section 10, builds A and D. |
| R-HD-35 | [host] | `VariantTest`: the input is the Upscale 4x colour shrunk to half, the other planes still come from the original, the file is still 4x with a full chain; no Upscale 4x cache is an error; a changed Upscale 4x colour redoes one texture. `shrink_color` averages in linear light. |
| R-HD-34 | [cache] [boot] | `verify` passed for both caches (section 6). Launches 3 and 4. The look of each variant is O-HD-1 to O-HD-3. |
| R-HD-40 | [built] | A source is one function in `sources.SOURCES`. A channel layout is one entry in `roles.ROLES`. No second source exists, so this is not tested. |

## 8. Operator Checks

Open, from the requirements: O-HD-1, O-HD-2, O-HD-3, O-HD-4.

The web page is `build/hdtex/compare/index.html`. It opens from disk. It
shows each plane of each texture of every cached source: 381 entries for
the caches of 2026-11-20, 27 terrain and 354 model. A page per source is
written next to it, `compare/<source>/index.html`.

The left side lists the entries with a small picture each, grouped by
category: `Terrain`, `Doodads`, one per named unit (`models.MODEL_UNITS`),
and `Shared` for a model texture more than one of those
use. A unit whose textures are all shared has no category of its own; the
Viking's main textures are under `Shared`. Above the list: a search field, and chips for category and plane with
the number of entries each would show. The keys: arrows step through the
listed entries, `/` search, `F` fit, `1` 1:1, `T` tile, `S` smooth original.
Below the view, one card per side gives the size and the measured numbers.

An entry has one layer per variant that holds its texture. Model textures
have Upscale 4x only. A texture one variant lacks shows the variants it has.

From left to right: the decoded original, the decoded Upscale 4x file, the
decoded Generative 4x file. A line parts each two neighbours:

- Both lines can be dragged.
- The second line stops at the first. It cannot pass it to the left.
- The first line pushes the second when it is dragged past it.
- Two lines at one place: a drag to the left takes the first, a drag to the
  right takes the second.

The wheel zooms, a drag pans, `1:1` shows one texture pixel per screen pixel,
and `Tile` repeats the texture to show its seams. The specular mask is dark,
so every side is spread over black to white with the range of the original;
the page states the range. With one cached variant the page has one line.
The page code is `scripts/hdtex/compare.py` and `scripts/hdtex/compare.html`.

The comparison sheets are in `build/hdtex/<variant>/terrain/preview/`. Each row is one
plane. From left to right: original, result, original across the wrap-around
edge, result across the wrap-around edge.

## 9. Not Tested

- That the game shows the 4096 level on screen, for either variant. Launches
  2 to 4 show the map loads and the log is clean. Launch 1 shows the game
  opens the files a catalog names (H8). The later launches use the same
  mechanism with other names; their logs do not name the files.
- That the game shows the variant the flag names. The check is on the built
  map's files (`BuiltMapTest`), not on the screen. The build stamp is the same
  for every variant, so the stamp in the game log does not tell them apart.
- Memory use and frame rate with the upscaled files.
- Texture quality settings other than the one the test machine uses.
- The meaning of the numbers in the size table (H7).
- The lines of the web page, in the repository. They were checked with a
  script outside the repository that drives a headless browser with mouse
  input (section 10). That script needs Playwright, which is not a
  dependency of this project. No check used a real mouse or Firefox.
- Whether Generative 4x keeps the look of the ground. Its numbers pass the
  limits, and the model invents detail by design. That is O-HD-1 and O-HD-2.

## 10. Runs

| Name | What | Result |
| --- | --- | --- |
| Launch 1 | `scripts/playtest.sh launch-check`, files named like the originals. Log `2026-11-15 03.44.06 Graphics.txt`. | Stamp matched, no script error, 16 texture warnings. The log check of that time did not read them. With the check of section 5 it fails. |
| Launch 2 | `scripts/playtest.sh launch-check`, files with the prefix. Log `2026-11-15 03.54.13 Graphics.txt`. | Stamp `0037eec3083a-497a67faac81c5f4` matched, no script error, no texture warning. |
| Host tests | `scripts/playtest.sh host-tests`, after launch 2 | 176 tests, all passed, none skipped. Its build has the same `BuildManifest.txt` hash as the build of launch 2: `3588241dd53b...`. |

Launches 1 and 2 predate the variants. Their files were Upscale 4x files made
by the older version of the tool. The runs below use the caches of section 6,
both made by one version of the tool. Every build below has the build stamp
`0037eec3083a-497a67faac81c5f4`.

| Name | What | Result |
| --- | --- | --- |
| Build A | `SC2_HD_TEXTURES=sharper scripts/playtest.sh build` | Failed: `SC2_HD_TEXTURES=sharper names no variant; use upscale, generative, or off`. |
| Build B | `SC2_HD_TEXTURES=off scripts/playtest.sh host-tests` | The build printed `off by SC2_HD_TEXTURES=off`. The map has no upscaled files. `BuildManifest.txt` hash `bf6b9082adf5...`. 215 tests passed, 2 skipped: the two `BuiltMapTest` checks, which need upscaled files. |
| Build C | `scripts/playtest.sh build` with `SC2_HDTEX_CACHE` set to an empty folder | The build printed `no cache` and passed. `BuildManifest.txt` hash `bf6b9082adf5...`, the same as build B. |
| Build D | The same with `SC2_HD_TEXTURES=generative` | Failed: `SC2_HD_TEXTURES=generative, but there is no cache at ...`. |
| Launch 3 | `SC2_HD_TEXTURES=generative scripts/playtest.sh host-tests`, then `launch-check` with the same flag. Log `2026-11-15 13.11.31 Graphics.txt`. | Both builds printed `injected 16 textures, variant Generative 4x` and have the `BuildManifest.txt` hash `1408e361ee07...`. 215 tests passed, none skipped. Stamp matched, no script error, no texture warning. |
| Launch 4 | `scripts/playtest.sh host-tests`, then `launch-check`, no flag. Log `2026-11-15 13.13.33 Graphics.txt`. | Both builds printed `injected 16 textures, variant Upscale 4x` and have the `BuildManifest.txt` hash `4d1d2b684899...`. 215 tests passed, none skipped. Stamp matched, no script error, no texture warning. |
| Web page | A script outside the repository drove `build/hdtex/compare/terrain/index.html` with mouse input in headless Chrome 151 and in headless Brave. | 10 of 10 checks passed in each: the order of the three sides and their names; each line moves alone; the second line stops at the first; the first pushes the second; two lines at one place come apart; a pan leaves the lines; drags after a double click and after select-all; the right button moves nothing. |

The 215 tests include tests of other tooling in the work tree.

## 12. Model Textures (proof of concept)

**State: built, not finished.** Host tests pass. The real cache is built and
fails `verify` for 35 of 194 textures. The map builds with it and passes
validation: 210 textures, 152 model files. It was launched once with the
first scope (doodads, Command Center, psi destroyer): stamp matched, no
texture warning in `Graphics.txt`. It was not launched with the later units.

Source `models` (`hdtex/models.py`). It reads the built map, because the map
build places most doodads.

Named units, `models.MODEL_UNITS`: `CommandCenter`, `PsiDecimator`,
`HybridUltraliskShackled`, `VikingAssault`, `VikingFighter`, `Overlord`, `MengskBC`, `SensorTower`,
`Hellion`, `Goliath`.
`MengskBC` shows the model file `BattlecruiserLoki.m3`.
The vista overlord (`SCOBAVistaOverlord`) shows the model `Overlord`.

Named model entries, `models.MODEL_ENTRIES`: `BattlecruiserLokiDeathSlow`,
the death model of `MengskBC`. No other death model is followed.
`validate_slow_deaths.py` takes the patched copy of a generated slow death
model for that model, and checks the copy.

Flip books (R-HD-56). A flip book layer does not hold its cells. The
particle system that draws its material does (`m3tex.flip_grids`). Each
cell gets a rim of 16 of its own edge pixels per side before the upscale
(`flipbook.explode`), and the rim is cut after it (`flipbook.implode`). A
flip book is left when two particle systems or two models name different
cells, when a layer without a flip book names the same file, when the cells
do not divide the picture, or when a cell is below 32 pixels.

A model file the map itself ships is read from the map, not from the game
(`models.map_model`, `models.fetch`). Today that is `VikingAssault.m3`, which
`scripts/footfall/fx.py` writes. The cache keeps the hash of that file.
`inject.stale_models` fails the build when the map's file has changed since.

| Step | Module | Does |
| --- | --- | --- |
| Catalogs | `catalog.py` | Field values with parents, class defaults, and `##token##` values. |
| Models | `models.py` | Placed doodad or named unit, to actor, to `CModel`, to model files with variations. Only the model an actor shows while it stands. |
| Layers | `m3tex.py` | The texture paths in the materials of a model, with the slot of each. |
| Verdict | `models.judge` | A role per texture from its slots, or a reason to leave it. |
| Codec | `bc1.py`, `dds.py` | DXT1 next to DXT5. The result keeps the format. |
| Copies | `pipeline.model_stage` | A copy of each model file that names the upscaled textures. It is read back and compared. |
| Inject | `inject.py` | Copies go to `Assets\Models\scoba_hd\`, textures to `Assets\Textures\scoba_hd\scoba_hd_m_<name>`. `ModelData.xml` gets a `Model` override per `CModel`. |
| Check | `check.py` | Every patched model is named by a `CModel`, every texture by a catalog or a patched model. |

Roles added: `data` (amounts in every channel, byte-averaged mips) and
`normal_red` (a normal map with blue 0 and a red channel of its own; what
red means there is not known, it is kept as an amount).

Census of 2026-11-20, `hd_textures.py census`: 36 `CModel` entries, 152 model
files, 204 textures: 147 DXT5, 56 DXT1, 1 DXT3. 194 are upscaled, 16 of
them flip books. 10 are left: the 4 main textures of the Hellion, which are
2048x1024 already, 4 normal layers of displacement materials, 1 DXT3, 1 of
4x4 pixels. `radius2` was upscaled for the tar pit before; the death model
of the battlecruiser names it in a displacement material, so it is left.

Open:

- `verify` fails 35 textures with the limits of section 6. 17 miss the seam
  limit; a model texture is mostly an atlas that does not tile, so that limit
  and the upscaler's tiling option may not fit it. 16 miss the coarse RMSE
  limit, most of them glows and particles. 2 miss the encode limit and 2 the
  correlation limit. Two textures miss two limits. The limits were not changed.
- Not tested by a program: that the game shows a patched model copy, and that
  it takes a `Model` override with variations below a new base path. The one
  launch gave a clean log; the look is O-HD-5.
- With this cache in place, a map build without `SC2_HD_TEXTURES` injects the
  model textures too.
- `scripts/data/hit_volumes.json` names the patched copy as the `m3` of a
  unit whose model is patched. The measured shapes are the same.
- R-HD-40 did not hold as written: the encode and inject stages changed.

## 11. Commands

| Command | Does |
| --- | --- |
| `uv run python scripts/hd_textures.py list` | Show the files the map resolves to. |
| `uv run python scripts/hd_textures.py build --gpu 1` | Upscale 4x: extract, upscale, encode, and verify. |
| `uv run python scripts/hd_textures.py --variant generative build --gpu 1` | The same for Generative 4x. |
| `uv run python scripts/hd_textures.py [--variant KEY] verify` | Check a variant's cache against its manifest and the limits. |
| `uv run python scripts/hd_textures.py [--variant KEY] preview` | Write a variant's comparison sheets. |
| `uv run python scripts/hd_textures.py compare` | Write the web page with every cached source and variant. It prints the path. Images of an unchanged texture are kept. |
| `uv run python scripts/hd_textures.py census` | List the textures of the map's models with format, size, slots, and verdict. |
| `uv run python scripts/hd_textures.py --source models build --gpu 1` | Model textures: extract, upscale, encode at 2048 at most, patch the models, and verify. |
| `scripts/playtest.sh build` | Build the map with Upscale 4x. |
| `SC2_HD_TEXTURES=generative scripts/playtest.sh build` | Build the map with Generative 4x. |
| `SC2_HD_TEXTURES=off scripts/playtest.sh build` | Build the map with the built-in textures. |

Upscaling one 1024x1024 plane on one Arc A770 took about 72 s with `seedvr2`,
27 s with `pbrify`, and 7 s with `fast`.

`build --max-size 2048` keeps the files at 2048 per side. `arc-upscale` is
found next to this project, or at `ARC_UPSCALE`.

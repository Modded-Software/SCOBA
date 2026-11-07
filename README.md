# SC2Map Format & SC2 Modding Research

Notes compiled 2026-11-03. Sources: reverse-engineered format docs, SC2Mapster/Staredit guides, Galaxy API docs, and inspection of the local `SCOBA.SC2Map` archive.

## 1. Mental Model

- `.SC2Map` is an **MPQ archive**. It is not a ZIP. It contains many named files.
- `.SC2Mod`, `.SC2Campaign`, `.SC2Assets`, `.SC2Data` are also MPQ archives.
- `.SC2Components` is the **unpacked directory form** of the same document.
- A map is a document made of **components** declared in `ComponentList.SC2Components`.
- Components are XML, binary, text, or asset files.
- The game mounts the map plus its dependencies into a virtual filesystem.
- File lookup is priority based. Later archives override earlier ones.

## 2. MPQ Container

- Magic: `0x1A51504D`, bytes `4D 50 51 1A` (`MPQ\x1A`).
- Optional user-data header: `MPQ\x1B`, usually 16 bytes before the real header.
- Header is found at 512-byte-aligned offsets.
- Header sizes: v0 = 32, v1 = 44, v2 = 68 (SC2 treats as v1), v3+ = 208.
- Sector size: `512 << sector_size_shift`.
- SC2 default is 16 KB sectors (`sector_size_shift = 5`).
- All offsets are relative to the MPQ header, not the file start.

### Header fields

| Offset | Size | Field |
|---|---|---|
| `0x00` | 4 | magic |
| `0x04` | 4 | header size |
| `0x08` | 4 | archive size (v0) |
| `0x0C` | 2 | format version |
| `0x0E` | 2 | sector size shift |
| `0x10` | 4 | hash table offset |
| `0x14` | 4 | block table offset |
| `0x18` | 4 | hash table count |
| `0x1C` | 4 | block table count |
| `0x20` | 8 | hi-block table offset (v1+) |
| `0x28` | 2 | hash table offset high (v1+) |
| `0x2A` | 2 | block table offset high (v1+) |
| `0x2C` | 8 | 64-bit archive size (v2+) |
| `0x34` | 8 | BET table offset (v2+) |
| `0x3C` | 8 | HET table offset (v2+) |
| `0x44` | 40 | compressed table sizes (v3+) |
| `0x6C` | 4 | raw chunk size (v3+) |
| `0x70` | 96 | MD5s (v3+) |

### Tables

- **Hash table**: 16 bytes per entry. Encrypted with key from `"(hash table)"`.
- **Block table**: 16 bytes per entry. Encrypted with key from `"(block table)"`.
- Hash entry: name hash A, name hash B, locale, platform, flags, block index.
- Hash lookup: start at `hash % count`, then linear probe.
- Block entry: offset, compressed size, real size, flags.
- Flags include compressed, encrypted, single-unit, checksums, patch/delete, exists.
- v1+ adds a hi-block table for >4 GB offsets.
- v3+ adds HET/BET compact tables.
- SC2 diverges from StormLib in four known ways.
- SC2 repurposes v3+ MD5 fields for HET/BET compressed sizes.
- SC2 rewrites `format_version == 2` to `1`.
- SC2 last-error state is thread-local.
- SC2 validates and overwrites some header offsets.

### File data

- Files are split into sectors.
- A sector offset table stores `sectors + 1` dwords.
- Each sector can be raw or compressed.
- Compression byte is a mask: Huffman, zlib, PKWARE, bzip2, sparse, ADPCM, LZMA.
- SC2 supports `0x20` sparse sectors.
- Special files: `(listfile)`, `(attributes)`, `(signature)`.
- `(listfile)` is optional. Do not rely on it always being complete.

### Observed in `SCOBA.SC2Map`

- Valid MPQ v3 archive.
- Header size 208 bytes.
- Sector shift 5 = 16 KB sectors.
- Hash table: 128 entries.
- Block table: 94 entries.
- Archive size: 571,408 bytes.
- 94 block-table entries.
- 92 names in `(listfile)`.
- Two entries are unlisted or special.
- `(listfile)` present and usable.

## 3. Archive Types and Dependencies

| Extension | Role |
|---|---|
| `.SC2Map` | Playable map document |
| `.SC2Mod` | Reusable dependency mod |
| `.SC2Campaign` | Campaign document |
| `.SC2Assets` | Asset sub-archive: textures, models, sounds |
| `.SC2Data` | Data sub-archive: catalogs, scripts, strings |
| `.SC2Archive` | Generic archive, e.g. shaders |
| `.SC2Layout` | UI layout |
| `.SC2Style` | UI style/font |
| `.SC2Replay` | Replay |
| `.SC2Save` | Saved game |

### Sub-archive slots

- Each top-level archive can have up to 27 sub-archives.
- Layout is 3 tiers × 9 sub-types.
- Sub-types: root ×3, `Base.SC2Assets`, `Base.SC2Data`, locale assets, locale data, `Teen.SC2Assets`, `Team.SC2Assets`.
- Numbered variants exist: `Base.SC2Assets1` … `Base.SC2Assets999`.
- Locale slots fall back to root slots when missing.

### Load order

- `Mods/Core.SC2Mod` loads first.
- Expansion mods load next: Liberty, Swarm, Void.
- Multiplayer chains: `LibertyMulti` → `SwarmMulti` → `VoidMulti` → `BalanceMulti`.
- Map dependencies load after base mods.
- Map-local data wins over dependency data.
- Priority formula: `100 * (db_slot + 1) + 10 * subtype + tier`.
- A later-loaded archive always outranks an earlier archive.
- Tie-breaker: higher serial number wins.
- CVars: `-run`, `-testmod`, `-extramods`, `-meleeMod`.

### Builtin mods

- Core.
- Liberty, LibertyMulti, LibertyCampaign, LibertyStoryCampaign.
- Swarm, SwarmMulti, SwarmCampaign, SwarmStoryCampaign.
- Void, VoidMulti, VoidCampaign, VoidStoryCampaign.
- War3, NovaStoryAssets, StarCoop, Glue.
- BalanceMulti, WarCoop, WarClassic, WarClassicSystem, WarCoopData.

## 4. Document Layout

### Required root files

| File | Format | Purpose |
|---|---|---|
| `ComponentList.SC2Components` | XML | Manifest of components |
| `DocumentHeader` | binary | Product FourCC, build, dependencies |
| `DocumentInfo` | XML | Author-facing metadata, dependencies |
| `MapInfo` | binary | Dimensions, players, teams, lobby setup |
| `MapScript.galaxy` | text | Generated map script |

### Component manifest

```xml
<?xml version="1.0" encoding="utf-8"?>
<Components>
    <DataComponent Type="gada">GameData</DataComponent>
    <DataComponent Type="info">DocumentInfo</DataComponent>
    <DataComponent Type="mapi">MapInfo</DataComponent>
    <DataComponent Type="terr">t3Terrain.xml</DataComponent>
    <DataComponent Type="trig">Triggers</DataComponent>
    <DataComponent Type="text" Locale="enUS">GameText</DataComponent>
    <DataComponent Type="plob">Objects</DataComponent>
    <DataComponent Type="regi">Regions</DataComponent>
    <DataComponent Type="attr">Attributes</DataComponent>
    <DataComponent Type="uiui">UI/Layout/DescIndex.SC2Layout</DataComponent>
    <DataComponent Type="font">UI/FontStyles.SC2Style</DataComponent>
</Components>
```

### Component type codes

| Code | Index | Default file |
|---|---|---|
| `info` | 0 | `DocumentInfo` |
| `text` | 1 | `GameText` |
| `gada` | 2 | `GameData` |
| `attr` | 3 | `Attributes` |
| `aiai` | 4 | `CustomAI` |
| `uiui` | 5 | product-specific |
| `cuts` | 6 | `Cutscenes/Index` |
| `font` | 7 | product-specific |
| `mapi` | 8 | `MapInfo` |
| `terr` | 9 | `t3Terrain.xml` |
| `plob` | 10 | `Objects` |
| `regi` | 11 | `Regions` |
| `trig` | 12 | `Triggers` |
| `cine` | 13 | `Cinematics` |
| `stdi` | 14 | `StandardInfo.xml` |

- `Locale` only matters for `text` components.
- `Optimized` is an optional flag.
- Parser accepts both `DataComponent`/`Type` and lowercase `component`/`type`.

## 5. Metadata Files

### `DocumentHeader`

- Binary, versioned 0–8.
- Current version: 8.
- All integers little-endian.
- Fields: product FourCC, format version, flags, build ID, dependency list, locale list.
- Dependency entry: name, id, path, path cache metadata.
- Locale entry: key, locale id, locale path.
- No writer exists in the game client. The editor writes it.
- Read only for validation and dependency resolution.

Observed `SCOBA.SC2Map`:
- FourCC bytes `H2CS`.
- Format version 8.
- Build tuple starts `1.5.0`.
- Build number ~98310.
- 8 dependencies.
- Dependencies are Liberty and Swarm mods/campaigns.

### `DocumentInfo`

- XML with `<DocInfo>` root.
- Metadata: mod type, icon, tutorial, screenshots, patch notes, preloads.
- Holds dependencies in `bnet:... ,file:...` form.
- Dependency format: `bnet:{Name}/{Version}/{CatalogId},file:{LocalPath}`.
- Loaded before `MapInfo` in the same pipeline.
- Does not hold map dimensions. `MapInfo` does.

Observed `SCOBA.SC2Map`:
- Depends on Liberty mod, Liberty Multi, Liberty campaign, Liberty Story.
- Also Swarm mod, Swarm Multi, Swarm campaign, Swarm Story.
- No map name inside `DocumentInfo`; name is elsewhere.

### `MapInfo`

- Binary. Magic `0x4D617049` (`MapI` as integer, bytes `IpaM`).
- Current version: 39.
- Version-gated fields.
- Core: width, height, locale mode, preview images, minimap, bounds, fog, loading screen, game options, speed.
- Player entries: 432 bytes each, max 16.
- Team entries: 96 bytes each.
- Variant block: variants, slot arrays, bitsets.
- v33+ adds lighting and camera block.
- Integrity hash at end.
- Width/height are in cells. Valid range 1–256.
- World units = cells × 4096.
- Editor concepts: publish mode, map bounds, lobby slots, variants.

Observed `SCOBA.SC2Map`:
- Version 39.
- Map dimensions 128×128 cells.
- Terrain grid is 129×129 vertices.
- 16 player entries.
- Publish mode 2 = Arcade.
- Map description "Zerus"; fog style "Dark"; difficulty Normal.
- Playable bounds fill the whole map.
- Custom loading screen image.
- Integrity hash valid.
- Player/team data uses the v39 layout.

### `.version` files

- One per component, e.g. `MapInfo.version`, `t3Terrain.version`.
- Binary. Magic `cdes` (`0x73656463`).
- v0 = 36 bytes, v1 = 40 bytes, v2 = 44 bytes.
- Fields: type FourCC, format version, build number, major/minor/patch, entry count, timestamp, terminal.
- Used for timestamps and version consolidation.
- Not required for basic parsing, but tools should preserve them.

### `Attributes`

- XML lobby defaults.
- Root `<Attributes>`.
- `DefaultVariants`, `Variant`, `Attribute`, `AttributeHidden`.
- Holds default slot values, max team size, mode names/descriptions.
- Related to `MapInfo` lobby setup.

### `BankList.xml`

- XML list of player banks.
- Entry: `<Bank Name="..." Player="1"/>`.
- Banks are persistent save data.

## 6. Game Data Catalogs

- Path: `Base.SC2Data/GameData/*.xml`.
- Root element: `<Catalog>`.
- Entries use `id` and optional `parent`.
- Parent chain enables inheritance. Max depth: 8.
- Later loads override earlier entries with the same `id`.
- Load order: dependencies first, then loose data, then map-local.
- Common catalogs: Unit, Actor, Ability, Behavior, Effect, Weapon, Button, Model, Sound, Terrain, Water, Light, Turret, Mover, Alert, Camera, GameUI.
- `Base.SC2Data/GameData/GameData.xml` is an `<Includes>` list.
- It points to data-space XML files.

```xml
<?xml version="1.0" encoding="utf-8"?>
<Includes>
    <Catalog path="GameData/UnitData.xml"/>
    <Catalog path="GameData/Heroes/H-Tychus.xml"/>
</Includes>
```

- Data spaces group related edits into one XML file.
- Useful for copying a hero or unit between maps.
- Editor can move entries between data spaces.
- `GameData.xml` must not be edited while the project is open in the editor.
- Save catalogs as UTF-8. Keep CRLF where the editor expects it.

Observed `SCOBA.SC2Map`:
- 18 catalog XMLs.
- `UnitData.xml` patches stock units, e.g. `CUnit id="Armory"` with `CardLayouts`.
- `ActorData.xml` is 15 KB.
- `BehaviorData.xml` is 22 KB.
- `UnitData.xml` is 32 KB.

## 7. Triggers

- File: `Triggers`. XML.
- Root: `<TriggerData>`.
- `<Root>` lists top-level items.
- `<Element Type="..." Id="...">` defines nodes.
- Types include `Category`, `Trigger`, `FunctionCall`, `Param`, `Preset`, `FunctionDef`, `ParamDef`.
- Edges are `<Item Type="Trigger" Id="..."/>`.
- Trigger node holds `Event`, `Condition`, `Action`, plus flags like `<Disabled/>` and `<InitOff/>`.
- Parameters reference function definitions and parameter definitions by library and id.
- Editor IDs are 8-hex-digit opaque values.
- Hand editing is possible but fragile. IDs and references must stay consistent.
- Text is in `TriggerStrings.txt`.
- The trigger editor compiles this graph into `MapScript.galaxy`.
- Do not add logic directly to `MapScript.galaxy`. The editor overwrites it.

Observed `SCOBA.SC2Map`:
- `Triggers` is 1.7 MB XML.
- 38,490 lines.
- Uses `Ntve` library functions.

## 8. Galaxy Scripting

- Galaxy is a statically typed, C-like language.
- Entry point: `MapScript.galaxy`.
- `MapScript.galaxy` includes `TriggerLibs/NativeLib` and expansion libs.
- Generated file. Do not hand-edit.
- Put custom code in `scripts/*.galaxy`.
- Include from a Custom Script element: `include "scripts/main"`.
- Paths are relative to map root, without `.galaxy`.
- Include order matters.
- Header file holds forward declarations.
- All includes share one global compilation unit.
- Functions can call each other across included files.
- `static` means file-private.
- Trigger handlers use `bool name(bool testConds, bool runActions)`.
- Register triggers by name string: `TriggerCreate("MyTrigger")`.
- `main()` typically registers a map-init trigger.

```c
bool onInit(bool testConds, bool runActions) {
    UIDisplayMessage(PlayerGroupActive(), c_messageAreaSubtitle,
                     StringToText("HELLO WORLD"));
    return true;
}

void main() {
    TriggerAddEventMapInit(TriggerCreate("onInit"));
}
```

### Galaxy quirks

- Declare all locals at the top of a function.
- No `++` or `--`. Use `+= 1`.
- No block comments. Only `//`.
- Lines max 2048 characters.
- No exceptions. Use return codes and validation.
- Loops block the trigger thread until done.
- Async work needs triggers.
- Use the Catalog native functions to read/write game data at runtime.
- Field paths look like `InfoArray[0].Unit`.
- Turn on "View Raw Data" in the Data Editor to find field names.

### Useful native areas

- Catalog get/set: `CatalogFieldValueGet`, `CatalogFieldValueSet`, `CatalogReferenceSet`.
- Triggers: `TriggerCreate`, `TriggerAddEvent*`, `TriggerExecute`.
- UI: dialogs, panels, text, images.
- Units: create, kill, issue order, query.
- Players: alliances, resources, score.
- Banks: persistent per-player save data.
- Text: `StringToText`, localized strings.

## 9. Terrain

Terrain is split across one XML descriptor and seven binary files.

### `t3Terrain.xml`

- Root: `<terrain version="...">`.
- Current sample uses version 114. Default reset value is 115.
- `<heightMap>` holds `tileSet`, `uvtiling`, `dim`, `offset`, `scale`.
- `<vertData>` holds `quantizeBias`, `quantizeScale`, `standardHeight`.
- `<masks>` names the texture mask layer.
- `<textureSetList>`: exactly 8 texture sets.
- `<textureList>`: up to 64 textures.
- `<cliffSetList>`: cliff set names.
- `<rampList>`: ramp definitions.
- `<cliffDoodadList>`: cliff doodads.
- `<blockTextureSetList>`: block texture indices. Size derived from `dim`.
- `<cliffCellList>` / `<cc>`: per-half-cell cliff IDs and flags.
- Version gates: `< 114` texture legacy path, `<= 112` clears a cliff flag.

Observed `SCOBA.SC2Map`:
- `terrain version="114"`.
- `dim="129 129"`.
- `tileSet="Zerus"`.
- 8 texture sets, only slot 0 used.
- 64 texture slots, first 8 used.
- 2 cliff sets: `ZerusCliff1`, `ZerusCliff0`.
- `quantizeBias=1.005798`.
- `quantizeScale=0.0004566926`.
- `standardHeight=7.981371`.

### Binary terrain files

| File | Magic | Version | Content |
|---|---|---|---|
| `t3HeightMap` | `HMAP` | 101 | 6 bytes per cell: heightBase, heightAdjustments, mask |
| `t3VertCol` | `VTCL` | 103/104 | Per-vertex color, 56-byte entries |
| `t3CellFlags` | `LFCT` | ≤102 | Pathing/cell flags |
| `t3HardTile` | `HRDT` | 102 | Cliff/hard-surface geometry |
| `t3FluffDoodad` | `DLFT` | 101–103 | Decorative doodads |
| `t3TextureMasks` | `MASK` | ≤102 | 8-layer texture blend weights |
| `t3Water` | `WATR` | 104–110 | Water bodies and waves |

### Height map

- Header: 32 bytes.
- `magic`, `version=101`, `sizeX`, `sizeY`, 16 bytes padding.
- Cells: row-major, Y outer, X inner.
- Cell: `uint16 heightBase`, `uint16 heightAdjustments`, `uint16 mask`.
- File size = `32 + 6 * sizeX * sizeY`.
- Heights are quantized.
- Dequantize each value separately: `value * quantizeScale - quantizeBias`.
- `standardHeight` is a reference height, not part of per-cell decode.
- Mask bit `0x9000` indicates cliff in the runtime vertex.

Observed `SCOBA.SC2Map`:
- `HMAP`, version 101.
- 129×129 cells.
- File size 99,878 = `32 + 6 × 129 × 129`. Exact match.

### Synchronized terrain

These keep multiplayer simulation deterministic.

| File | Magic | Notes |
|---|---|---|
| `t3SyncHeightMap` | `SMAP` | 129×129 grid, ~4 bytes/cell |
| `t3SyncCliffLevel` | `SCLF` likely | 4-bit cliff level grid |
| `t3SyncTextureInfo` | `RTXT` | texture index per cell |

- `t3SyncHeightMap` in sample: `SMAP` v102, 129×129, 66,628 bytes.
- `t3SyncCliffLevel`: 32,800 bytes.
- `t3SyncTextureInfo`: 131,148 bytes.
- These must agree with render terrain and `t3Terrain.xml`.

### Texture masks

- Header: 64 bytes.
- v≥102 uses tiled nibble packing.
- v<102 uses raw pixels.
- 8 blend layers.
- CPU path downsamples to `(8×gridW - 8, 8×gridH - 8)`.
- GPU path decodes straight into textures.
- Sample `t3TextureMasks` is exactly 4 MB: 1024×1024×4.

### Terrain loading order

1. `t3HeightMap`
2. `t3VertCol`
3. `t3CellFlags`
4. `t3HardTile`
5. `t3FluffDoodad`
6. `t3TextureMasks`
7. `t3Water`

- Any failure aborts the whole terrain load.
- Partial terrain is not allowed.

## 10. Placement, Regions, Minimap

### `Objects`

- XML. Root `<PlacedObjects Version="27">`.
- `ObjectUnit`: `Id`, `Position`, `Rotation`, `Scale`, `UnitType`, `Player`.
- Optional `<Flag Index="..." Value="..."/>`.
- Also holds doodads and points in other element types.
- Coordinates are world-space floats.

Observed `SCOBA.SC2Map`:
- 1,405 lines.
- Many `AutoTurret` units for player 7.
- `Flag Index="ForcePlacement"`.

### `Regions`

- XML. Root `<Regions>`.
- `<region id="...">` with `<name value="..."/>`.
- `<shape type="circle">` with center and radius.
- Other shape types exist, e.g. rectangles and polygons.

Observed `SCOBA.SC2Map`:
- Named spawn regions: Tosh, Kerrigan, Nova, Raynor.

### `Minimap.tga`

- TGA image.
- Sample: 128×128, 24-bit RGB, top-origin.
- Separate from `MapInfo` minimap settings.

## 11. Text and Localization

- `GameText` component points to localized text.
- Text tables live under `<locale>.SC2Data/LocalizedData/`.
- Common tables: `GameStrings.txt`, `ObjectStrings.txt`, `TriggerStrings.txt`, `GameHotkeys.txt`.
- Load order: locale data overrides base data.
- `enUS` is the usual fallback.
- Preserve BOM and line endings when editing.
- Text keys are referenced by catalogs, triggers, and UI.

Observed `SCOBA.SC2Map`:
- Locales: enUS, enGB, deDE, esES, esMX, frFR, itIT, koKR, plPL, ptBR, ruRU, zhCN, zhTW.
- `enUS` has the largest trigger string table.

## 12. UI: Layouts and Styles

- `SC2Layout` is XML for UI frames, templates, and includes.
- `SC2Style` defines fonts and styles.
- `DescIndex.SC2Layout` is the root UI layout index.
- `FontStyles.SC2Style` is the global font style file.
- Localized font style overrides live in `LocalizedData/`.
- Layout changes are safe to edit while the editor is open. Scripts too.
- Catalog XML is not safe to edit while the editor is open.

## 13. Preload and Assets

### `Preload.xml`

- XML. Root `<Preload>`.
- `<Asset path="..." Type="Image"/>` for raw files.
- `<Unit id="..."/>`, `<Actor id="..."/>`, `<Sound id="..."/>`, `<Terrain id="..."/>`, `<User id="..."/>` for catalog entries.
- Processed before `PreloadAssetDB.txt`.

### `PreloadAssetDB.txt`

- INI-style text.
- `[Section]`, `id=`, `key=value,value`.
- Lists transitive dependencies for assets.
- Generated by the build system.
- Merged with `Preload.xml` during streaming.

### Other assets

- `Assets/Textures/*.dds` and `.tga`.
- `Assets/Models/*.m3`.
- `Assets/Sounds/*.ogg` / `.wav`.
- `Ico/` map-specific icons.
- `Blank.dds` placeholder.

## 14. Tools and Workflow

### Editing workflow

1. Unpack the document to a component folder.
2. Edit XML, Galaxy, layouts, and data spaces on disk.
3. Test with `scripts/launch-scoba.sh`.
4. Repack to `.SC2Map` only for publishing or distribution.

The editor's `Save As .SC2Components` is just an unpack. The project uses a
programmatic unpack instead of the editor UI.

Current source tree:

- `src/SCOBA.SC2Map/` is the unpacked component folder.
- `SCOBA.SC2Map` is the original packed baseline.
- `dist/` is reserved for repacked artifacts and is ignored by Git.

### Read-only inspection

- `MPQEditor` / Ladik's MPQ Editor.
- `StormLib`.
- `mpyq` (Python).
- `smpq`.
- `mpqtool`.
- `sc2mpq` sidecar from `sc2-map-editor-mcp`.
- The local project uses `mpyq` through `pyproject.toml` and `.venv`.

### Local commands

```bash
uv sync
uv run scripts/sc2map_ls.py SCOBA.SC2Map
uv run scripts/sc2map_ls.py SCOBA.SC2Map --cat Build.txt
uv run scripts/sc2map_ls.py SCOBA.SC2Map --extract src/SCOBA.SC2Map
```

### Build the expanded map

```bash
scripts/build.sh
```

- Builds `out/SCOBA256.SC2Map` atomically.
- Normalizes line endings.
- Writes a deterministic build stamp.
- Validates XML, dimensions, catalogs, script wiring, and stamp.
- Writes `BuildManifest.txt`.

### Launch the map

```bash
scripts/launch-scoba.sh
```

- Uses `out/SCOBA256.SC2Map` by default.
- Falls back to `src/SCOBA.SC2Map` if the build is absent.
- Stops old SC2 processes.
- Clears the SC2 map cache.
- Stages a clean copy into the SC2 `Maps` folder.
- Verifies the staged copy matches the source.
- Runs it through `SC2Switcher_x64.exe` under GE-Proton.
- Falls back to `StarCraft II.exe -run` if the switcher is absent.
- Set `SC2_MAP_SOURCE` to launch another packed map or component folder.
- Set `DRY_RUN=1` to print the command without launching.
- Set `SC2_KEEP_RUNNING=1` to skip stopping old SC2 processes.

### Launch and check

```bash
scripts/launch-and-check.sh
```

- Launches the built map and waits for a runtime build stamp.
- Fails on script errors, map-load errors, and stamp mismatch.
- Set `SC2_AUTO_START=0` to skip automatic start input.

### Install the dock icon

```bash
scripts/install-dock-icon.sh
```

- Installs `scoba.desktop` and `assets/scoba.png`.
- Adds `scoba.desktop` to GNOME favorites.
- Icon uses the map minimap.

### Galaxy tooling

- VS Code extension `vscode-sc2-galaxy` by Talv.
- Galaxy API reference at `mapster.talv.space`.
- SC2 Editor's Trigger Editor.
- Native function declarations bridge GUI actions to Galaxy code.

### Documentation sources

- `sc2-arcade-watcher/sc2-file-format-docs` (Talv): best binary format source.
- SC2Mapster wiki and mkdocs.
- `s2editor-guides.readthedocs.io`.
- Staredit Network wiki.
- `chansey97/sc2-gamedata-documentation` for catalog fields.
- ReverseEngineering.wiki MPQ page.
- `zezula.net` MPQ format reference.

## 15. Common Pitfalls

- Do not treat `.SC2Map` as ZIP. Use an MPQ library.
- MPQ v3 and SC2-specific quirks break naive readers.
- `(listfile)` may be missing or incomplete. Have fallback names.
- Archive paths use backslashes. Normalize on Linux.
- Some files are flat names containing backslashes.
- The editor regenerates `MapScript.galaxy`. Do not put logic there.
- `GameData.xml` cannot be edited while the project is open.
- Catalog XML needs correct encoding and line endings.
- Dependency order is last-wins. A wrong order changes behavior.
- Map-local data always overrides dependency data.
- Text components need matching `Locale` attributes.
- Hand-editing trigger XML can break IDs and references.
- Terrain binaries and `t3Terrain.xml` must stay consistent.
- Sync terrain must match render terrain for multiplayer.
- Map dimensions: `MapInfo` uses cells, terrain uses vertices (`cells + 1`).
- `.version` files should be preserved when repacking.
- Repacking can change byte layout. Keep backups.
- Publishing requires a packed archive and a Battle.net account.
- Map/mod content is subject to Blizzard's ownership and publishing rules.
- Do not use format knowledge for cheating or bypassing protections.

## 16. Suggested Parsing Order

1. Open MPQ. Read `(listfile)`.
2. Read `ComponentList.SC2Components`.
3. Resolve each component to its file.
4. Read `DocumentHeader` (binary) and `DocumentInfo` (XML).
5. Read `MapInfo` (binary).
6. Read `t3Terrain.xml`, then terrain binaries.
7. Read catalogs under `Base.SC2Data/GameData/`.
8. Read `Triggers` and `MapScript.galaxy`.
9. Read `Objects`, `Regions`, `Attributes`.
10. Read text tables and UI files.

## 17. Local Sample Summary

`SCOBA.SC2Map`:

- MPQ v3, 16 KB sectors, 94 blocks / 92 listed files.
- Map name in `MapScript.galaxy` header: `SCOBA`.
- 128×128 map cells, 129×129 terrain vertices.
- Zerus tileset.
- Terrain version 114.
- Dependencies on Liberty and Swarm campaign/multiplayer data.
- Heavy trigger and Galaxy script usage.
- 13 locales shipped.
- Many custom unit data edits.
- Custom UI icons and styles.

## 18. Open Areas

- Full compression/encryption implementation details for every SC2 MPQ variant.
- Complete trigger graph semantics and editor ID allocation.
- Full 87-catalog field schema. See `sc2-gamedata-documentation`.
- Exact `MapInfo` v39 player/team/variant layouts. See `mapinfo.md`.
- Exact trigger-to-Galaxy code generation rules.
- Battle.net publishing and signature internals.

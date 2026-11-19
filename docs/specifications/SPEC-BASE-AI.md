# SPEC-BASE-AI: Bases, Resources and AI Assistance

**Date:** 2026-11-18
**Requirements:** [REQ-BASE-AI](../requirements/REQ-BASE-AI.md)
**Status:** Partly built (section 9 runs). 2026-11-18: the map is made a
proper melee map (4.7a); expansion and attacks are left to the stock AI.
Section 3 lists engine assumptions that are not confirmed.

## 1. Requirement state

States: `[planned]` = no code; `[built]` = code exists, no in-game test
passed; `[tested]` = a check in the `baseai` profile backs it; `[build]` =
the map validator or a host test backs it; `[operator]` = only a person
can judge it.

| ID | State | Planned backing |
| --- | --- | --- |
| R-BASE-1 | [planned] | build check; `sites`: 8 fields and 2 geysers near each spawn |
| R-BASE-2 | [planned] | build check; `sites`: 7 expansion sites |
| R-BASE-3 | [planned] | host test: sites follow the Lurker positions of a changed source |
| R-BASE-4 | [planned] | build check; `sites`: counts; `macro`: minerals collected |
| R-BASE-5 | [planned] | build check; host tests |
| R-BASE-6 | [planned] | build check (lane route with sites in); `lanes`: a unit walks each lane |
| R-BASE-7 | [planned] | build check; host tests |
| R-BASE-8 | [planned] | host test: two builds give the same sites |
| R-BASE-9 | [planned] | `start`: one town hall per lane player, type, distance to the main site |
| R-BASE-10 | [planned] | `start`: 12 workers; one Overlord for Zerg |
| R-BASE-11 | [planned] | `start`: minerals 50, vespene 0 |
| R-BASE-12 | [planned] | `others`: players 7 and 8, no town hall, no worker, resources unchanged |
| R-BASE-13 | [planned] | `start`: difficulty 10 per lane player; `macro`: activity for players 1 to 6 |
| R-BASE-14 | [planned] | `macro`: workers, minerals collected, a new structure, a trained unit; `expand`: a town hall at an expansion site |
| R-BASE-15 | [planned] | `intro`: activity while the intro state is LOOP |
| R-BASE-16 | [planned] | `macro`: owner of every new unit near a base is its lane player |
| R-BASE-17 | [planned] | `control`: order accepted, order read back, unit moved |
| R-BASE-18 | [planned] [operator] | `exclude`: hero order, position, control mode, selection unchanged; play: AC-BASE-5 |
| R-BASE-19 | [planned] | `others`: players 7 and 8 gain no unit |
| R-BASE-20 | [planned] | `exclude`: script units have no AI wave and keep their orders |
| R-BASE-21 | [planned] | `exclude`: supply used does not rise when script units are made |
| R-BASE-22 | [planned] | `exclude`: wave units target their gate; regression `intro` |
| R-BASE-23 | [planned] | regression: `aircreep`, `herodrop`, `intro`, `combat`, `tps` |
| R-BASE-24 | [build] | `melee_map.check` in `validate-map.py`; host `test_melee_map.py` |
| R-BASE-25 | [tested] | `macro`: `StartLoc100` per owner equals its hall point within 4 (run `20261118-221854`) |
| R-BASE-26 | [tested] | `resources.check` in `validate-map.py`: 8 fields and 2 geysers per line in `Objects`, table equal to a fresh plan; host `test_resources.py`: no `UnitCreate` of a resource; `macro` run `20261118-232439`: 12 sites, 144 fields, 36 geysers counted in game, Zerg 10, 13, 14 hold a hall at a placed site |
| R-BASE-27 | [built] | host `test_melee_map.py`: `AIMeleeStart(` called, no `AIDeclareTown(` |
| R-BASE-28 | [built] | host `test_melee_map.py`: no `AIExpand(`, no `AISetAttackState(` in `scripts/app` |
| R-BASE-29 | [built] | `melee_map.check`; host `test_melee_map.py`; `macro` `DepotsQueued` = 2 for Terran |
| R-BASE-31 | [built] | `resources.check`: no tree or unit in a keep-out; host `test_resources.py` |
| R-BASE-32 | [built] | host `test_resources.py`: two plans equal, radii and angle steps vary, hall gap kept |
| R-BASE-33 | [built] | `macro`: supply used + supply lost grows within every 2 minutes (`baseai_live.galaxy` death counter); an attacker lost units |
| R-BASE-34 | [built] | `macro`: attackers ≥ 4 by t480, an owner attacks twice (state 3 left and entered again); `at least 3 owners expanded by t480` |
| R-BASE-30 | [build] | `macro` hall footprint checks (run `20261118-104652`) |

## 2. Facts

Read from the game files and the map source on 2026-11-18. Coordinates are
in the map source (128 cells). The built map doubles them.

| ID | Fact | Source |
| --- | --- | --- |
| F1 | `NativeLib` includes `TriggerLibs/AI`, which includes `TriggerLibs/BaseAI`. The map script includes `NativeLib`. So `AIStart`, `AIMeleeStart`, `AISetUnitScriptControlled`, `AIRemoveUnitFromAnyWaves`, `AIUnitGetWave` and `AIIsScriptControlled` are in reach of the map script. | core.sc2mod `nativelib.galaxy` line 5226, `ai.galaxy` line 944; `scripts/bootstrap_galaxy.py` |
| F2 | `AIMeleeStart(player)` calls `AIStart(player, false, DifficultyAPM(diff))`, sets the difficulty flags, declares town one at `PlayerStartLocation(player)`, starts the harvest, makes seven waves and starts scouting. | core.sc2mod `baseai.galaxy` |
| F3 | The highest stock difficulty is `c_skirChInsane` = 10, "Cheater Insane". `PlayerSetDifficulty` sets it. | core.sc2mod `ai.galaxy`, `natives.galaxy` |
| F4 | At difficulty 10 the harvest bonus starts at 1.2 and rises to 2.0 over 20 minutes. | core.sc2mod `baseai.galaxy`, `meleeai.galaxy` (`AIMeleeCheatResources`) |
| F5 | The race scripts are not in `NativeLib`. `Computer.galaxy` includes `MeleeAI`, which includes `Terran/Terran`, `Zerg/Zerg`. `AIMeleeTerr` is in void.sc2mod `terran/terran.galaxy`. The Zerg file was listed, not read. | core.sc2mod `computer.galaxy`, `meleeai.galaxy`; void.sc2mod |
| F6 | The map source has no start location, no mineral field and no geyser. `Objects` holds 156 units and 285 doodads and no `ObjectPoint`. | `src/SCOBA.SC2Map/Objects` |
| F7 | liberty.sc2mod `RaceData` gives 6 workers and 50 minerals. The other `RaceData` files this map loads were not read. The design does not use them (section 4.3). | liberty.sc2mod `racedata.xml` |
| F8 | No AI runs on the map today. No map script calls an `AI` native. | search of `src/SCOBA.SC2Map/scripts` |
| F9 | Ten `LurkerMPBurrowed` of player 8 stand in two groups of five. Group centres: (61.76, 35.34) and (36.13, 65.49). The Terran jungle regions 12 and 13, mirrored through the centre of X Center, give (33.26, 58.01) and (63.11, 29.44). The group centres are 8.0 and 6.1 from them. | `src/SCOBA.SC2Map/Objects`, `Regions` |
| F10 | Lane spawn regions: player 1 region 1, player 2 region 3, player 3 region 4, player 4 region 2, player 5 region 5, player 6 region 6. | `app/init.galaxy` |
| F11 | The X regions lie on the lanes. A site centred on an X region would block its lane. | `scripts/flora/config.py` `LANE_ROUTES` |
| F12 | Script code makes units for lane players in: `spawns.galaxy` (waves), `air_creep.galaxy`, `hero_switch.galaxy` (heroes), `hero_drop.galaxy` (pod), `medic.galaxy`, `companion.galaxy` (Predator, HunterKiller), `aim.galaxy` (`InvisibleTargetDummy`), `intro.galaxy` (seed units). The map source places `Tosh` and three `RaynorCommando` for player 1 and `Kerrigan` for player 4. Units made by stock library code (`libVCMI`) were not searched. | search of `src/SCOBA.SC2Map/scripts/app` for unit creation calls, `Objects` |
| F13 | Readable from the map script: `c_playerPropSuppliesUsed`, `c_playerPropMineralsCollected`, `PlayerDifficulty`, `TechTreeUnitCount`, `AIUnitGetWave`, `AIIsScriptControlled`. | core.sc2mod `natives.galaxy`, `ai.galaxy` |
| F14 | The spawn timer and the waves run during the intro. The hero is hidden and paused. | SPEC-INTRO, `intro` profile group `boot` |
| F15 | Parsed player records (`player_slots.find_records`): players 1 and 4 user; 2, 3, 5, 6, 7, 8 computer; 9 to 14 neutral; 15 hostile. Lobby: slots 2 to 6 `Comp` locked. Revised 2026-11-18 (REQ-ROSTER): base owners become 9, 11, 12, 10, 13, 14; seats 1 to 3 user, 4 to 6 computer. Owners come from `core/roster.galaxy` (`gf_BaseAiLaneOwner` calls `gf_RosterOwner`: 9, 11, 12, 10, 13, 14). | `MapInfo`, `Attributes`, SPEC-ROSTER F1, F2 |
| F16 | Terran supply depends on the depot footprint. Same build, 8 game minutes: with the stock 2x2 depot (`SC2_BA_DEPOT=stock`) supply used of players 9, 2, 3 reaches 56, 50, 53, no stall. With the map's 4x4 depot: 33, 23, 29; player 2 is capped at 23/23 from t240 with 5052 minerals, `PlaceDepotLow` (lowerable spot) null. With the 8x8 Command Center as well, player 2 builds no depot: 15/15 all game. | `baseai macro` runs `20261118-102700` (stock), `20261118-101055` (4x4), `20261118-104652` (4x4, CC 8x8) |
| F17 | A running `UnitSetHeight` blend cannot be stopped: `UnitSetHeight(u, h, 0)` and `UnitSetPropertyFixed(u, c_unitPropHeight, h)` during it are ignored. A one-tick blend (`UnitSetHeight(u, h, 0.0625)`) or the height property per tick moves exactly and stops when the calls stop. | `baseai flight` run `20261118-104231`, methods mA to mD |
| F19 | Stock expansion has three paths. Fast expand (`TerranHDFastExpand`, `ZergHDFastExpand`) calls `AIExpand` only when `AIHasNearbyOpenExpansion(player)` is true. `AIDefaultExpansion(player, hall, minerals, gas, flags)` expands when minerals left in the towns fall under the threshold (Cheater Insane Terran: 3000, 7000, 17000, 24000, 28000, 40000 by phase) or when there are too many workers. | core.sc2mod `meleehighai.galaxy` 396-425; void.sc2mod `terranchin.galaxy` 2815-2936; SC2Mapster "Default Expansion" |
| F20 | `AIGetUserInt(player, c_numGroundStartLocs) == 0` forces an air opening (`meleebuildai.galaxy` 206) and turns early defence off (`meleehighai.galaxy` 225). The value is `AIGetGroundStartLocs(PlayerStartLocation(player))`. | core.sc2mod |
| F21 | Attacks: the opening calls `AISetAttackStatus(player, unit, minAlly, minSelf, merge)` (e.g. 7 Marines); later attacks need 30 wave units or 120 supply used (`WaveAdvancedIdleAttackLogic`). Target: `AIWaveTargetMelee(player)`. | core.sc2mod `meleehighai.galaxy` 129, `meleewaveai.galaxy` 567, 689; void.sc2mod `terranhdvh.galaxy` |
| F22 | `MapInfo` player record (version 39): id, control, 3 bytes, u32 color, race string, u32, **u32 start location object id**, u32, decal. Void campaign `pkorhal01` (version 39): player 1 → 45 ("Start Location P01"), player 2 → 88, players 3 and 4 → 832, 5 → 102, 6 → 61; its lobby start list after the records is empty. Ladder maps (cache, version 31/32) leave the record field 0 and list their start ids after the records. Ours: every record 0, list empty. | `pkorhal01.sc2map/mapinfo`, `objects` (CASC); cached `.s2ma`; `src/SCOBA.SC2Map/MapInfo` |
| F23 | The stock melee setup needs start locations: `MeleeInitUnits` makes start units only at defined start locations. | SC2Mapster wiki "Tutorials/Artificial Intelligence" |
| F24 | Macro run `20261118-123414`: `AIExpand` returned a town for every owner, no hall was built; `AIHasNearbyOpenExpansion` false all game; halls 1 per owner at t480. Terran p9 at t480: 7 Marines, 34/39 supply, no attack. | `baseai macro` |
| F25 | Macro run `20261118-221854` (start locations, stock `AIMeleeStart`, script-made piles): every owner's `PlayerStartLocation` is its start point (campaign-style record pointer accepted); `GroundStartLocs` 5, `TotalStartLocs` 6; enemies 7 (Terran) and 5 (Zerg), 2 teams; opening type 3. Owners 9, 10, 13, 14 reach attack state 3 by t480 (Zerg from t240, p9 at t300). `AIHasNearbyOpenExpansion` false at every minute for every owner; every town slot but 0 empty; no hall at a site. Main minerals left 48000 at t1. While attacking, p13 fighters 16 → 10 (t300 → t360), supply 52 → 35; p14 fighters 25 → 12 (t360 → t420), supply 56 → 29. | `baseai macro` |
| F26 | Macro run `20261118-230116` (placed piles, 18 lines; the game exited before t480, bank to t420, no crash log): `AIHasNearbyOpenExpansion` true from t1 for 9, 10, 11, 13, 14, false for 12; site table 12 sites, 144 fields, 36 geysers, amounts 6000 / 10000. Zerg 13 and 14 hold a Hatchery at `ZergJungle1B` and `ZergJungle2A` (2.1 from the site point) from t120. Terran 9 and 11: `NearbyOpen` true, ~2900 minerals at t420, no new Command Center, town slot 1 unused. Loss counters: p10 23, p14 20 supply lost by t420; attack entries 1 for 10, 13, 14, 0 for Terran. Terran ChIn depletion thresholds by phase start at 3000 and 7000 minerals left (`terranchin.galaxy` 2815, 2843); the 4x mains start at 48000 (O-BASE-6). | `baseai macro` |
| F27 | Macro run `20261118-232439` (failures 1): Zerg 10, 13, 14 hold a second Hatchery by t240; attackers 9, 11, 12, 10; every owner enters attack state at most once by t480. `UnitTypePlacementFromPoint("CommandCenter")` returns the site point itself at all six Terran-side sites, BrakkFront and both InfestedTank sites; `null` at the four Zerg jungle sites (Zerg-held or on creep). So the 8x8 footprint fits the placed sites (O-BASE-7 closed for placement). p9 town slot 1: claimed at t360, building at t420, unused at t480: a Command Center was started and then lost. Terran ChIn openings 103, 104, 106 never call `TerranHDFastExpand` (`terranchin.galaxy` 282-570); 107, 108, 109, 113 do. Zerg `UnitsLost` rises with `SupplyLost` 0 (p14 76 units, 0 supply at t480), so the unit counter counts zero-supply deaths. The earlier session macro run started 23:15 lost its runner; its bank is kept only as `/tmp` diagnostics, not as a run. | `baseai macro` |
| F28 | Macro run `20261118-233712` (failures 1, death types recorded): all six owners reach attack state by t480 (five by t300); none enters it twice. Dead types: Zerg `Larva` from t60 (the Larva → Egg morph fires a death), then `Zergling`, `ZerglingBurrowed`; Terran `Marine`, `MULE`. Drone → building morphs fire no death. p9 town slot 1 again claimed t360, building t420, unused t480, and no hall of p9 died, so the Command Center was never placed. The death counter now skips types with zero mineral + vespene cost (`UnitTypeGetCost`). | `baseai macro` |
| F18 | WASD and LMB+RMB move the bound unit with `move` orders, so at its own engine speed: the Wraith 7.50 = its data speed, Tosh 3.10. | `baseai flight` run `20261118-104517` |

## 3. Assumptions under test

Not confirmed. Each has a probe in the `probe` group. The probe records raw
values, so a failure shows what the engine did.

| ID | Assumption | Probe | If it fails |
| --- | --- | --- | --- |
| A1 | The engine loads the race scripts on this map and runs them for a player after `AIStart(player, false, apm)`. | Start the AI for computer player 2 with a town hall, 12 workers and minerals. After 60 game seconds: worker count, minerals collected, structure count. | Stop and report. The feature has no base. |
| A2 | `AIStart` works on a user player (1) and the person keeps control. | Same as A1 for player 1. Then: hero order, selection, control mode, `UnitDirectControl` count before and after. | Stop and report. R-BASE-13 needs a new design for played lanes. |
| A3 | `PlayerSetDifficulty(player, 10)` takes effect before `AIStart`, on user and computer players. | `PlayerDifficulty` read back for players 1 to 6. | Record the value. Set the difficulty flags by hand, as `AIMeleeStart` does. |
| A4 | Superseded 2026-11-18 by R-BASE-24: the build adds start location points to `Objects` and `MapInfo`. | Raw: `PlayerStartLocation(player)` x and y, `AIGetTownState(player, c_townOne)`. | - |
| A11 | The engine counts only resources present at map load as expansions, so script-made piles make `AIHasNearbyOpenExpansion` false (F24). | `macro`: `NearbyOpen`, `TownState` of every town slot, halls at sites. | Record raw values and report. |
| A12 | With start locations, `c_numGroundStartLocs` > 0 and the AI picks ground openings. | `macro`: `GroundStartLocs`, `TotalStartLocs`, `OpeningType`. | Record and report. |
| A13 | The AI sees the other team as enemies. | `macro`: `AIGetNumEnemies`, `AINumEnemyBuildings`, `AIGetNumTeams`. | Record and report. |
| A5 | `AISetUnitScriptControlled(unit, true)` with `AIRemoveUnitFromAnyWaves(unit)` keeps a unit out of AI waves and AI orders. | A Marine of player 2 made by script, excluded, ordered to hold. After 60 game seconds: order, position, `AIUnitGetWave`. A second Marine, not excluded, as the control: raw order and wave. | Stop and report. The waves cannot stay as they are. |
| A6 | `UnitSetState(unit, c_unitStateUsingSupply, false)` frees the supply of a unit. | `c_playerPropSuppliesUsed` before and after for one Marine. | Raise the supply limit of the lane players by the wave size instead. |
| A7 | The AI builds and trains with the unit data this map loads and changes. | A1: structure count and trained unit count after 120 game seconds, types recorded. | Report the missing types. Fix the data or the dependency. |
| A8 | The AI finds build space among the scaled trees. | A1: the count of new structures, their distance to the town hall. | Clear more ground around the main sites in the build. |
| A9 | The AI expands to a site the build placed. | `expand` group: a town hall of the player within the site radius of an expansion site, inside the time limit. | Report. R-BASE-14 expansion stays open. |
| A10 | The AI runs while the intro holds the UI in cinematic mode. | `intro` group: minerals collected rises while the intro state is LOOP. | Start the AI at map init and report what the intro blocks. |

## 4. Design

### 4.1 Sites (build)

Package `scripts/mapgen/resources/`, called from `scripts/expand_map.py` before
`apply_flora`. It works on the built map (256 cells).

- **Anchors.**
  - Main sites: the six lane spawn regions (F10).
  - Expansion sites: regions 7, 8, 9 (X), 12, 13 (Terran jungle), and the
    two Lurker groups.
- **Lurker groups** (R-BASE-3): the `LurkerMPBurrowed` units of player 8
  are split into two groups by distance (two-means, seeded by the two
  Lurkers farthest apart). The anchor is the group's centre. The build
  fails when it finds fewer than two Lurkers. No region is added to
  `Regions`.
- **Site shape.** A town hall spot and, around it, 8 mineral fields on an
  arc and 2 geysers at the arc's ends, as on a ladder map. The shape has
  one free parameter: its rotation.
- **Search.** For each anchor the build tries town hall spots on rings
  around the anchor and 16 rotations per spot. It keeps the first spot, by
  ring then by angle, that passes every check. The order is fixed, so the
  result is the same on every build (R-BASE-8).
- **Checks** (R-BASE-5, 6). A spot passes when every cell of the town hall
  footprint, of each field and geyser, and of the ground between them:
  - is dry, flat (`FLAT_SLOPE`) and pathable;
  - is off the lane dirt and outside the lane corridor;
  - is outside every tree blocker, lane hazard and placed unit footprint,
    with a margin;
  - is outside every site already placed.
  - Main sites also keep the town hall outside the spawn region disc, so
    reinforcement pods do not land on it.
- **Lane check** (R-BASE-6): with all sites in, each lane route is
  searched again (`flora.lanes`). The build fails when a lane is cut or
  longer than `LANE_DETOUR_MAX` times its length before.
- **Flora** (R-BASE-7): `flora.scene` adds a keep-out disc per site.
  Hazard placement sees the sites as blocked.
- **Output.**
  - `Objects`: one `ObjectUnit` per mineral field (`MineralField`) and
    geyser (`VespeneGeyser`), player 0, with stable ids.
  - `scripts/app/data/base_sites.galaxy`: the town hall point and
    rotation of each site, the main site of each lane player, the site
    radius. Generated, as `lane_gates.galaxy` is. `src/` holds an empty
    table.
  - `out/SCOBA256.SC2Map/base_sites_report.txt`: each site, its anchor,
    the ring and rotation chosen, and the margins.
- **Validation**: `scripts/validate-map.py` calls `check_base_sites`: 13
  sites, 8 fields and 2 geysers each, the checks above, and the generated
  table equal to a fresh computation.
- **Constants** live in `scripts/mapgen/resources/config.py`. First values, to be
  tuned against the build checks: field arc radius 7, geyser radius 7,
  ring step 2, largest ring 24 for main sites and 16 for expansion sites.

### 4.2 Script units (exclusion)

Module `systems/base/base_ai.galaxy`.

- `gf_BaseAiExclude(unit)`: `AISetUnitScriptControlled(unit, true)`,
  `AIRemoveUnitFromAnyWaves(unit)`, and
  `UnitSetState(unit, c_unitStateUsingSupply, false)` (A5, A6). It also
  counts the calls (`gv_baseAiExcluded`), read by the tests.
- `gf_BaseAiExcludeGroup(unitgroup)`: the same for a group.
- Called at every place script code makes a unit for a lane player (F12):
  the wave groups, the air creeps, the heroes, the hero pod, the Medic,
  the companion, the aim target dummy, the intro seed units.
- At map init, before the AI starts, every unit that players 1 to 6
  already own is excluded. This covers the units of the map source.
- The AI unit set needs no list: it is every unit of a lane player that
  was not excluded.

### 4.3 Starting bases

`gf_BaseAiCreate(player)`, at map init, before the AI starts:

- one town hall at the main site point, with the site rotation;
- 12 workers, made by script next to the town hall (F7: the stock start
  gives 6, so `MeleeInitUnits` is not used);
- one Overlord for Zerg;
- minerals set to 50, vespene to 0.

These units are not excluded.

### 4.4 AI start

`gf_BaseAiStart(player)`, right after 4.3, for players 1 to 6:

- `PlayerSetDifficulty(player, c_skirChInsane)` (A3);
- the body of `AIMeleeStart` (F2) with the main site point in place of
  `PlayerStartLocation(player)` (A4). The map has no start location (F6).
- Players 7 and 8 are not touched (R-BASE-12, 19).

Trigger `gt_BaseAi`: map init. It is not in the list of triggers the intro
turns off, so the AI runs during the intro (R-BASE-15, A10).

Order at map init: `gf_HeroUnitsReplace` (heroes exist) → exclude all →
create bases → start the AI.

### 4.5 Player orders

No new code. Order mode (`systems/orders.galaxy`) already orders one unit
the player owns. The `control` group tests it on an AI unit and records
when the AI next changes the unit's order (O-BASE-3).

### 4.6 Switch for test maps

`const bool c_BASE_AI_ENABLED = true;` in `core/base_ai.galaxy`. With
`false`, no base is made and no AI starts. The exclusion calls stay.

- The map validator requires `true` in the shipped map.
- `scripts/testkit/map_builder.py` sets `false` for every profile but
  `baseai`, as `patch_intro` does for the intro.
- The mineral fields and geysers stay in every test map. They are map
  objects.

### 4.7 Building footprints

`Base.SC2Data/GameData/FootprintData.xml`, `UnitData.xml`.

- Supply depot 4x4 (stock 2x2 scaled x2), raised and lowered (operator
  decision: keep). F16: it starves Terran supply. Open.
- Command Center, Orbital Command, Planetary Fortress: 8x8 (operator
  2026-11-18; stock 5x5). `Footprint8x8CCContour` and
  `Footprint8x8CCDropOff` keep the stock layers: not near resources,
  drop-off placement. The morphs keep the size.

### 4.7a Melee map (R-BASE-24 to 30)

Build step in `scripts/expand_map.py`, module `scripts/mapgen/melee_map.py`, on
the built map (256 cells).

- **Start locations** (built). One `ObjectPoint` of type `StartLoc` per
  base owner, id `2100000000 + owner`, at the centre of its lane spawn
  region (`Regions`), rounded to whole cells. The owner's `MapInfo` record
  points at it, campaign style (F22). Seats 1 to 6, players 7 and 8: 0.
  `scripts/mapgen/melee_map.py`, called in `expand_map.py` after Regions scale.
- **Resources** (built; run `20261118-221854` showed `NearbyOpen` false
  all game with start locations, F25). Package `scripts/mapgen/resources/`
  (`config`, `sites`, `fit`, `build`).
  - **Order** (R-BASE-31), in `expand_map.py`: scale Objects and Regions
    → `melee_map` (start points) → `resources.apply` (plan the lines on
    bare terrain, fit trees, fit units, write piles) →
    `apply_scaled_footprints` (tree blockers at the new tree spots) →
    flora (keep-out per line) → the rest. Anchors are read from the
    source units before any unit moves.
  - **Lines**: the six mains at the start points, then 12 sites:
    Terran jungles (regions 12, 13) and the two Lurker groups as double
    sites (10 either side of the anchor, across the direction away from
    the centre); each camp (Brakk, infested tank) twice: hall 12 from the
    camp toward the centre, and 12 behind it, away from the centre.
  - **Ground** for a line: `t3CellFlags` pathable (tree spots are
    pathable there: 331 of 334), dry, outside the spawn region discs.
    Trees and placed units do not block: they are fitted after.
  - **Shape** (R-BASE-32): per line a generator seeded with
    `SEED:name`. Arc span 100 to 130 degrees, centred off the direction
    away from the map centre, jittered by up to 20. Each field: radius
    6.5 to 9, angle jitter up to 6, every other field set back up to 1.5
    (a loose double row). Geysers: past the arc ends, angle jitter up to
    15, radius 7 to 9. Fields snap to whole x and half y (2x1), geysers
    to half cells (3x3); a pile that fails tries the offsets of
    `SNAP_TRIES`.
  - **Search**: the anchor, then rings 2 to 16 by 2, 16 angles from 0;
    the first spot where the 8x8 hall and every pile cell is on good
    ground and off every earlier line. Mains: the start point only.
  - **Keep-out** of a line: its hall and pile cells grown by 2.
  - **Fit trees** (`fit`): a source tree whose position is inside a
    keep-out grown by `TREE_CLEAR` + `TREE_SCALE_CLEAR` x its scale
    (blockers grow with scale, up to 8) moves to the nearest spot on rings
    (step 1, 16 angles, up to 24) that is on good ground, outside every
    grown keep-out and `TREE_GAP` from every other tree. Its z keeps its
    height above the ground.
  - **Fit units**: each placed unit inside a keep-out grown by
    `UNIT_CLEAR` moves alone to the nearest such cell, `UNIT_GAP` from
    other units and trees.
  - **Output**: one `ObjectUnit` per field (`MineralField`) and geyser
    (`VespeneGeyser`), player 0, ids from `2100001000`; moved trees and
    units in place; `scripts/app/data/base_sites.galaxy` (site names and
    hall points, generated; `src/` holds an empty table);
    `base_sites_report.txt` (lines, moved trees and units).
  - **Flora** keep-out: `flora.scene` adds a disc of `KEEP_HALL` (7) at
    each hall listed in `base_sites_report.txt`; the piles are placed units, so
    they keep out already. The flora lane-detour check proves no lane is
    cut (R-BASE-6).
  - **Hall gap**: every pile cell stays 3 cells off the 8x8 hall square
    (the stock piles mark `NearResources` 3 around them; the 8x8 contour
    rejects it), pushed out along its ray when needed.
  - **Camp sites in water**: both camps stand in water about 3 deep with
    nothing dry within 24 (measured), so the four camp sites may stand in
    water (`WET_SITES`). Every other line stays dry. Operator check: look.
  - **Validation**: `resources.check` on the built map: 18 lines (6
    mains, 12 sites, from the report); 8 fields and 2 geysers per line;
    the hall gap; no overlap; no tree and no placed unit inside a grown
    keep-out; the table equals the placed sites. The same-source rule is a
    host test (the built map's trees and units have moved).
    Host test: two plans of the same source are equal (R-BASE-8); a moved
    Lurker moves its site (R-BASE-3).
  - Amounts: fields 4x by data (unchanged); geysers 4x by
    `gf_SiteFill` at map init, on the placed geysers. No script makes a
    resource.
- **Depots** (built). `src/SCOBA.SC2Map/Objects`: 1689533396, 1971666357 →
  9; 352867994, 1559950947 → 11; 1455266132, 1424795256 → 12. Placed
  structures are not excluded (`gf_BaseAiExcludePlayer`), so the AI owns
  them.
- **AI start** (built). `gf_BaseAiCreateLane` makes the hall and workers
  at `PlayerStartLocation(owner)` and calls `gf_BaseAiStart`:
  `PlayerSetDifficulty` then stock `AIMeleeStart(owner)`.
  `gf_BaseAiStartAt` and the expansion driver (`gt_BaseSitesExpand`) are
  removed.
- **Not changed.** 8x8 Command Center (R-BASE-30). The 200 supply rule and
  the depot/Overlord ban stay until `macro` measures them.
- **Validation.** `scripts/validate-map.py`: six start points, each owner's
  record index, 8+2 resources per site, depot owners.

### 4.8 Watch bodies and flight

- Alt+3 SCV and Alt+4 Viking (`systems/hero_switch.galaxy`), invulnerable;
  only Tosh and Kerrigan get a revive pod. The Viking is found by handle
  (`gv_heroViking`), not by type.
- `SCOBAVikingHero` (flight mode, parent `VikingFighter`): height 7.5,
  speed 12 (operator 2026-11-18: was 16), acceleration 15.75, actor scale 3 (operator 2026-11-18).
- Morph pair (`AbilData.xml`): `SCOBAHeroAssaultMode` lands it as
  `SCOBAVikingHeroAssault` (parent `VikingAssault`, scale 3);
  `SCOBAHeroFighterMode` lifts it back to `SCOBAVikingHero`. The stock
  `FighterMode` made a stock `VikingFighter` (speed 2.75). Both hero forms
  carry no stock morph. The stock transition models get hero events at
  scale 3.
- Landed, it stomps like the Goliath: thump, dust, splash, ripple, camera
  shake, doodad crushing (stomp row, SPEC-FLORA-CRUSH), and lands with an
  impact (stomp_land).
- Landed, it turns at 90 deg/s, moving and in place (`TurningRate`,
  `StationaryTurningRate`). Script turns use `gf_UnitTurn`
  (`systems/turn_rate.galaxy`): the blend lasts at least angle / rate, so
  they follow the data rate too; stock rates (~1000) keep the old blends.
- Landed speed 2.8125: stock `VikingAssault` 2.25 + 25 % (operator
  2026-11-18).
- Turning in place, landed, it plays its Walk clip at time scale 0.5
  (`systems/turn_anim`, `gf_TurnAnimConfig(type, anim, timeScale)`): the
  model has no turn clip; at its own speed the clip was too fast. Off when
  it moves or stops turning (3 still ticks).
- No camera-driven model pitch (operator 2026-11-18: removed).
- Camera refollow (`systems/camera/refollow`): after an alert, idle worker,
  town or selection camera jump, and whenever the camera lost the hero
  (not following it, or > 40 away), the camera follows the hero again.
  Alert recall targets are cleared every 0.25 s (Space is also the stock
  AlertRecall key; this cause is not proven by a test). Not during the
  intro or a hero drop.
- Tests: baseai flight group, `baseai_feel.galaxy` / `baseai_feel.py`
  (camera, turn clip, speed, footfall dust and splash).
- Regular units (not Tosh or Kerrigan): Point & Click only, no TPS; a right
  hold orbits the camera only; Chase is always Move; A and D do nothing
  (`gf_SideBegin` / `gf_SideEnd` in `systems/movement.galaxy`; operator
  2026-11-18: the keys clash with the ability-panel hotkeys). A release
  without a press that set the flag does not stop the unit's order.
- Flight (`systems/flight.galaxy`): Space held climbs, Ctrl held descends,
  4 per game second, between 2 and 60. By F17, every game tick while a key
  is held one `UnitSetHeight` to the next step over one tick; on release no
  call. The camera lift uses the same step target over the same tick. A
  key repeat while held does not restart the move.
- Landing (`gt_FlightLand`, `SCOBAHeroAssaultMode` execute): the morph
  descends only by the flyer's data height (7.5); a Space / Ctrl offset
  stayed on the landed unit (run `20261118-144819`: +4, +8, +12). At each
  landing the script stops flight, probes the height above the ground, and
  blends it to the data height over 0.5 s, before the morph mover (delay
  0.533). The morph's own up-then-down height curve is stock (a stock
  Viking shows it too).
- The engine ground is flat: the build drops `t3SyncHeightMap`, so a
  Marine's z, `WorldHeight` and `CliffLevel` are equal everywhere (run
  `20261118-145950`). The hills are visual only; Galaxy cannot read them.

## 5. Files

| File | Role |
| --- | --- |
| `scripts/mapgen/resources/` (`config`, `sites`, `build`) | Lines (4.7a): anchors, Lurker groups, shape, search, placed piles, site table, `check` for the validator |
| `scripts/expand_map.py` | Calls `resources.apply` after footprints, before flora; calls `melee_map.apply` after Regions scale |
| `scripts/testkit/tests/test_resources.py` | Host tests R-BASE-3, 8, 26 |
| `scripts/mapgen/melee_map.py` | Start locations (Objects, MapInfo records), depot owners, `check` for the validator (4.7a) |
| `scripts/testkit/profiles/baseai_melee.py`, `scripts/testkit/tests/test_melee_map.py` | `macro` melee checks (A11 to A13); host tests R-BASE-24, 27 to 29 |
| `scripts/flora/scene.py`, `scripts/flora/build.py` | Site keep-outs |
| `scripts/validate-map.py` | `check_base_sites`, `c_BASE_AI_ENABLED` |
| `src/SCOBA.SC2Map/scripts/app/data/base_sites.galaxy` | Site table (empty in `src/`) |
| `src/SCOBA.SC2Map/scripts/app/core/base_ai.galaxy` | Constants, state |
| `src/SCOBA.SC2Map/scripts/app/systems/base/base_ai.galaxy` | Exclusion, bases, AI start |
| `src/SCOBA.SC2Map/scripts/app/main.galaxy`, `header.galaxy`, `app/init.galaxy` | Includes, declarations, init order |
| `spawns.galaxy`, `air_creep.galaxy`, `hero_switch.galaxy`, `hero_drop.galaxy`, `medic.galaxy`, `companion.galaxy`, `aim.galaxy`, `intro.galaxy` | Exclusion calls |
| `scripts/testkit/galaxy/baseai.galaxy`, `baseai_macro.galaxy`, `baseai_flight.galaxy`, `scripts/testkit/profiles/baseai.py`, `baseai_viking.py` | In-game tests |
| `scripts/testkit/profiles/registry.py`, `scripts/testkit/map_builder.py`, `scripts/playtest.sh` | Profile, switch, entry point |
| `scripts/testkit/tests/test_base_sites.py`, `test_base_ai.py` | Host tests |
| `README.md` | Feature and command list |

## 6. Tests

`scripts/playtest.sh baseai [group]`. Bank `SCOBABASEAI`. Every scenario
is one bank section. Windows are in game time.

| Group | Asserts | Negative case |
| --- | --- | --- |
| `probe` | A1 to A8, with raw values. Runs first, before feature code, on a harness-made base. | The control Marine of A5 is recorded, so the exclusion is measured against a unit that was not excluded. |
| `sites` | Per site: 8 mineral fields and 2 geysers inside the site radius, alive, owner 0. 13 sites. | No mineral field or geyser outside every site radius. |
| `start` | Per lane player at 1 game second: 1 town hall of the right type within 2 of its main site point; 12 workers; 1 Overlord for Zerg, 0 for Terran; minerals 50; vespene 0; difficulty 10. | No town hall of the other race for the player. |
| `macro` | All six lane owners, waves on, 8 game minutes, the operator in the Alt+4 Wraith. Per owner: minerals collected; workers, supply made, makers, fighters at t480; supply used plus supply lost (R-BASE-33: a harness death counter adds `c_unitPropSuppliesUsed` of every dying owner unit) grows within every 2 minutes; an owner whose fighters fell makes new fighters within 2 minutes (`FightersMade` counter). Terran halls: catalog footprints 8x8, pathing blocked at 3.5 in 4 directions, at start and after the morphs. Wraith flight as in `flight`. | Not supply-capped for 2 minutes. Hall pathing open somewhere at 4.6 (not larger than 8x8). |
| `flight` | Alt+4 Viking (regular unit, PNC), no lanes, no waves. W held and LMB+RMB held: ground speed within 10 % of the unit's speed property, which equals its data speed. Space 1 s climbs 4, Ctrl 1 s descends 4 (within 1), camera = base + flight. Land and lift by the hero morph pair: landed type `SCOBAVikingHeroAssault` on the ground; lifted type `SCOBAVikingHero` at speed 12. Raw: the height methods of F17, each form's ability list. | Speed not Tosh's. Height holds after each release. No jump on the flyer. No TPS, no Stand. No stock morph in either hero form; lift is not a stock `VikingFighter`. A / D: no flag, no move, no turn; the release keeps a move order. Control: Tosh on A moves along camera yaw + 90 (within 20). |
| `macro` raw (A11 to A13) | Per owner at t0 and every minute: `StartLoc100`, `GroundStartLocs`, `TotalStartLocs`, `NumEnemies`, `NumTeams`, `EnemyBuildings`, `OpeningType`, `AttackState`, wave sizes (main, attack), `NearbyOpen`, town state per slot. Asserts: start location equals the hall point; ground start locs > 0; enemies > 0; at least 3 owners hold a hall at a site by t480; at least 4 owners in attack state by t480 and one owner enters it twice (R-BASE-34). | No `AIExpand` call by script (counter stays 0). |
| `expand` | For one Terran and one Zerg lane player: a town hall inside an expansion site radius within the time limit. The time is recorded. | No town hall of a lane player outside every site radius. |
| `control` | A trained AI unit gets a move order from the harness as the player: the order is accepted, read back as the unit's order, and the unit is nearer the point after 3 game seconds. The time until its order changes is recorded. | A unit of another player given the same order as player 1: not accepted. |
| `exclude` | Hero of player 1: no AI wave, `AIIsScriptControlled`, order and position unchanged over 20 game seconds, control mode and selection unchanged. One reinforcement: every wave unit has an attack order to its gate, no AI wave, and supply used did not rise. Air creeps: patrol order kept, no AI wave. | Wave units do not get a gather, build or AI wave order. `gv_baseAiExcluded` rose by the wave size. |
| `lanes` | One Marine per lane walks spawn to enemy spawn through both gates. | Its path does not enter a site radius. |
| `intro` | Intro on: minerals collected rises for players 1 and 4 while the intro state is LOOP. | The hero stays hidden and paused. |
| `others` | Players 7 and 8 after 120 game seconds: no town hall, no worker, unit count not above the start, resources unchanged. | Same row: it is the negative case of R-BASE-12 and 19. |

Timing: no check reads an exact time. `macro` and `expand` use windows of
tens of seconds.

Host tests:

- `test_base_sites.py`: Lurker grouping (two groups, the centres of F9);
  a moved Lurker moves the site; two runs give equal output; each check of
  4.1 rejects a spot built to break it; 13 sites in the built map.
- `test_base_ai.py`: the switch in `core/base_ai.galaxy`; `patch` for
  profiles; every unit creation call in F12 is followed by an exclusion
  call; the profile registry.

Regression, full suites on the same build: `combat`, `tps`, `intro`,
`aircreep`, `herodrop`, `host-tests`.

## 7. Risks

- **A1 or A2 fails.** Then the stock AI cannot be the base of the feature.
  Work stops for an operator decision.
- **Other profiles.** A mineral line near the hero spawn can stand where a
  test places a target. The regression runs show it. The fix is to move
  the main site, not to drop resources from test maps.
- **AI structures in the spawn region.** The AI chooses where it builds.
  It can build where pods land. The engine moves a unit off a blocked
  cell. Not tested yet.
- **Workers under fire.** Waves and heroes pass close to the main sites.
- **Load.** Six AIs at the highest difficulty, plus waves and air creeps.
- **Test time.** `macro` and `expand` need minutes of game time. They are
  the slowest groups of the kit.

## 8. Operator checks

AC-BASE-1 to AC-BASE-7 of the requirements. Also:

- the look of mineral fields and geysers on the lifted, scaled terrain;
- the resource sounds and worker animations;
- whether the AI's army movement suits the lanes (O-BASE-2).

## 9. Runs

| Run | Result |
| --- | --- |
| `baseai/20261118-102700` (`macro`, stock 2x2 depot) | failures 6. Terran supply grows to 50-56, no stall (F16). |
| `baseai/20261118-104231` (`flight`) | failures 3 (speed reference invalid: the click-move guard stops a plain move order). Height methods F17. |
| `baseai/20261118-104517` (`flight`) | failures 0. Speed 7.50 = data (before the 22.5 change), flight climb, hold, descend. |
| `baseai/20261118-104652` (`macro`) | failures 10. CC 8x8 checks pass; Terran supply stalls (F16), Zerg 6 fighters 0 at t240, Zerg 10 capped t300-t360. |
| `baseai/20261118-173611` (`probe`, owners 9, 2) | failures 0. Player 2 `t180 Army` 3 = Medic + 2 Marines: the Medic came from `medic.galaxy` for seat 2, not from the AI. |
| `baseai/20261118-221854` (`macro`, melee map: start locations, stock start) | failures 3. Pass: start location = hall point for all six, ground start locs 5, enemies > 0, attackers 9, 10, 13, 14. Fail: `at least 3 owners expanded by t480: expanded=[]` (`NearbyOpen` 0 all game, F25); `p13 supply used grows within 2 min` (stall t420) and `p14` (stall t480): fighters lost in attacks (F25). The supply check assumes no losses; open, operator decision. |
| `baseai/20261118-204818` (`probe`, owners 11, 13) | failures 1: `p11t180 Army` 2, want > 2. Raw: 15/15 supply from t60, structures CC + 2 Refineries, `BuildOrder=none`, 1356 minerals; the same site as player 2 before (hall 22100,15900; F16). The hero Medic is now for played seats only (REQ-ROSTER), so nothing masks the stall. The probe runs stock supply by design (`t0 SupplyMade` = `START_SUPPLY`); the 200 rule (`gf_BaseAiSupplyInit`) only runs in `gf_BaseAiCreateLane`. Open: operator choice (probe with the 200 rule, or a `macro` run). |
| `baseai/20261118-232439` (`macro`, placed piles, loss counters, site placement probe) | failures 1: `an owner attacked 2 times by t480: repeats=[]`. Pass: 12 sites, 144 fields, 36 geysers; start location = hall for all six; `at least 3 owners expanded by t480: expanded=[10, 13, 14]`; `at least 4 owners attacked: attackers=[9, 11, 12, 10]`; `an attacker lost units`; supply growth for all six. F27. |
| `baseai/20261118-233712` (`macro`, death types, LostHalls) | failures 1: `an owner attacked 2 times by t480: repeats=[]`. Pass: `expanded=[10, 13, 14]`; `attackers=[9, 11, 12, 10, 13, 14]`; losses counted; supply growth for all six. F28. |
| `baseai/20261118-234729` (`macro`, cost-filtered losses, hall build targets) | failures 3: `expanded=[13, 14]` (p10 attacked from t300, first Hatchery order at t464, at 67.5,54.5); `attackers=[10, 13, 14]`; `repeats=[]`. Terran openings 133, 134, 106: attack wave 9-22 units at t420-t480, `AttackEntries` 0, no town claim. The previous run (openings 103, 104) attacked at t300. Operator 2026-11-18: Terran are slow to claim towns; that is not a fault. Open: the t480 window against random stock openings. |

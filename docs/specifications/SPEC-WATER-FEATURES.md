# SPEC-WATER-FEATURES: Procedural Water Features

**Date:** 2026-11-20
**Status:** Built. The carved ground, the pathing and the pipe unit are
tested in the game. Nothing drawn has been seen: the look is an operator
check. Section 9 gives the state of each requirement and the run that
backs it. Section 8 lists what is assumed.
**Requirements:** [REQ-WATER-FEATURES](../requirements/REQ-WATER-FEATURES.md)

## 1. Build step

Package `scripts/mapgen/waterfeatures/`. Entry:
`build.apply_water_features(map_dir)`, called by `scripts/expand_map.py`
after `expand_props` and before spores, resources, footprints and flora.
Those steps then read the carved ground. The engine ground
(`terrain/sync_height.py`) is baked later from the same height map.

- `SC2_NO_WATER_FEATURES=1` skips the step.
- Marker and report: `.water_features` in the built map. A second run on a
  marked map does nothing.
- Tuning: `config.py`. Units are 256-map cells.

The step plans first and writes last. `plan.make` has no file access.
`plan.problems` measures the plan. Any problem raises, before a file is
written (R-WF-12).

## 2. Measured models (R-WF-07)

`measure.py` reads the models of the built map with the vendored `m3addon`
and writes `scripts/data/water_models.json` (committed), in model space:

    PYTHONPATH=scripts uv run python -m mapgen.waterfeatures.measure --print

Re-run only when these models or their ModelData scale change.

- Falls (`Waterfall`): mesh bounds, the water surface the model was made
  for (`base_z`, from its splash emitters), and where its stream lands
  (`splashes`). `RockWaterfall` is no longer measured (operator
  2026-11-20: no rock waterfalls).
- Rocks (`ZerusRockLarge`, variations 0-7): mesh bounds. Read from the
  game storage with stormex: the map has no copy of a doodad it does not
  place yet. About 2 wide, top 0.86 to 2.04 over the origin, underside
  0.70 to 0.88 under it.
- Pipes (`PsiDecimator`): every tube of the mesh. A tube is a welded mesh
  part that is long (>= 4.0), thin (spread <= 0.5) and close to level
  (|axis z| <= 0.2). Per tube: the mouth (outer end), the lip and top of
  the opening, the outward direction, radius and length. The decimator has
  4 tubes, a big and a small one per hole.

Values: `Waterfall` mesh z -0.30..4.48, `base_z` 0.0868, width about 1.5.
Big tube lip 0.0144,
small tube lip 0.3871 (model units; drawn at 7x: ModelData 3.5 x unit
scale 2.0).

## 3. Sites and water level (R-WF-01)

`sites.py`.

- A pipe mouth in the world: unit position + Rz(Rotation) x scale x tube
  mouth. Scale = ModelData scale x placed Scale x the scale a later step
  still applies (`build.pending_unit_scale`: 2.0 until
  `.psi_destroyer_scaled` exists). Lip height = ground at the unit + tube
  lip x scale.
- A site: a water rectangle of a type in `SITE_WATER` (`Albion`) with a
  mouth within `MOUTH_REACH` 4.0.
- Level, per water type: `DROP` 3.0 below the lowest lip of its sites.

Built map (stamp `e466b85c7bcd-8a87055a5b6ebcc3`): 2 sites, rectangles
(208,192,224,200) and (184,208,200,224), two mouths each. Per site 6
falls (3 under each tube) and no rock waterfall. 3 rocks stand in the
first pool, 2 in the second; 90 plants stand round the two. Level 5.452 in
ground space. 599 vertices moved, by -6.11 to +4.00. 114 cells painted no
pathing. 32628 texture mask cells gained dirt on the walls. 12 placed
water doodads dropped: 5 `Waterfall` and all 7
`RockWaterfall` of `src/`, each inside or within 1.4 cells of a site
rectangle. The 4 `Waterfall` and the `ZerusWaterfall` at the far corner
(160 cells off) stay. No tree stood on moved ground.

## 4. Composition (R-WF-02, R-WF-06)

`compose.py`. A chain, nothing scattered:

    pipe mouth -> fall -> pool <- rocks standing in it

- Falls (operator 2026-11-20, in rounds). Height: top on the lip was "way
  too low", 0.6 up the opening was "from the top, not the bottom". The top
  now aims `FALL_TOP` 0.15 (+-`FALL_TOP_JITTER` 0.08 per fall) of the way
  up the opening, plus `FALL_RAISE` 0.2 ("raise regular waterfalls by
  0.2"): the whole fall stands 0.2 higher, so `base_z` is 0.2 over the
  level. The z scale is the height without the raise / model height,
  within `FALL_SCALE` 0.6..2.6. Width: "the bigger pipe gets the bigger
  fall" and no fall "clips outside" its pipe. The x and y scale is apart
  from z: each fall is `FALL_WIDTH` 0.5 (+-`FALL_WIDTH_JITTER` 20 %, was
  8 %: "more variation in their scale") of its opening wide.
  `FALL_COUNT` 3 per mouth, spread so no fall passes the side of the pipe.
  A fall that would land within `RECT_INSET` 1.0 of the rectangle edge
  moves toward the middle of its pipe. Each fall differs in size, turn
  (+-0.12 rad) and depth (+-0.25). Facing (operator 2026-11-20, from the
  game: the right group ran "too much facing the east", the left "too
  much to the south, need a southwest facing"): the falls faced along
  their own pipes, south-southwest at the first site and west-southwest
  at the second. `compose.fall_facing` now turns each by
  `FALL_FACE_COMMON` 1.0 of the way to `common_facing`, the mean
  direction of all pipe mouths: southwest, a turn of about 17.5 degrees
  per group. Where the falls land does not change. Which way the
  operator's "east" and "south" point on the map was not confirmed. Built
  map: 12 falls; big pipe 1.28..1.80 wide x 0.77..0.87 high in scale,
  small pipe 0.82..1.08 x 1.34..1.42. A doodad with unequal scale may
  draw its spray stretched: operator check.
- No rock waterfalls (operator 2026-11-20: "remove rock waterfall
  features entirely"). Their placement, bank and checks are removed.
  Section 6 gives the wall paint that replaces them.
- Rocks in the pool (R-WF-14, operator 2026-11-20: "some rocks inside,
  find appropriate doodads from zerus"): `ROCK_TYPE` `ZerusRockLarge`, the
  Zerus rock doodad of liberty.sc2mod, 8 variations. `compose.pool_rocks`,
  after the ground is final, with its own chance (`SEED:rocks`), so the
  falls do not change with them.
  - Spot: a pool vertex with every neighbour in the pool, moved by up to
    `ROCK_JITTER` 0.3, in water at least `ROCK_MIN_DEPTH` 0.4 deep,
    `ROCK_FALL_CLEAR` 2.0 from where a fall lands, `ROCK_SPACING` 2.5 from
    another rock. Up to `ROCK_COUNT` 4 per pool, no variation twice.
  - Size (`compose.rock_fit`): the origin stands on the pool floor, so the
    model's underside is in the floor. The scale follows the depth so the
    top stands `ROCK_ABOVE` 0.3..0.9 over the water, within `ROCK_SCALE`
    0.45..1.1. Where the largest scale is too small the origin goes up, at
    most `ROCK_LIFT` 0.6 of the underside; else the spot is skipped. The
    first try had tops under the water at one pool.
  - One scale for x, y and z. Random turn. Built map: 3 rocks in the
    first pool, 2 in the second, tops 0.35 to 0.84 over the water.
- Plants round the pool (R-WF-15) are flora's: section 6a.
- Site shift (operator 2026-11-20, from the game: the right feature stood
  2 to 3 cells right of its pipes, the left one 2 to 3 left):
  `sites.toward_big` moves where the water leaves by `SITE_SHIFT` 2.5
  along the row of mouths, from the smallest pipe toward the biggest. The
  measured mouths are not moved; the ground is still freed under them. Why
  the measured mouths are off is not known. A fall that would land within
  `RECT_INSET` 1.0 of the rectangle edge moves toward its pipe's middle.
- Chance (seed `SEED` 20261120) only picks among valid options: the
  turns, the sizes, the depths (R-WF-11). There is one `Waterfall` model,
  so falls vary in size, turn and depth only.
- A fall has one scale value for x and y and one for z. Every doodad has
  the flags `HeightAbsolute` and `ForcePlacement`.

## 5. Ground (R-WF-03, R-WF-04, R-WF-09)

`carve.py`, pure functions on the vertex grid. The engine draws a
rectangle's water wherever its ground is below the water height, so the
ground decides the pool. Order (`plan.make`):

1. Falls are placed. They fix where water lands.
2. `basin`: a bowl under every landing point (radius 3.5, depth 1.2 below
   the level). Only lowers. Only strictly inside the rectangle.
3. `pool`: the wet vertices connected to the landing points, strictly
   inside the rectangle, within `POOL_RADIUS` 7.5.
4. `rim`: every other vertex of the rectangle, and low ground within
   `SHORE_MARGIN` 4.0 outside it, is raised to level + `RIM` 0.4.
5. `feather`: every change fades into the old ground over 4 cells. A cut
   keeps 0.5 per cell, a raise 0.6. Pool vertices are not touched.
6. The rim is restored. `free_mouths`: the ground stays `PIPE_CLEAR` 0.3
   below every lip, around the mouth.
7. Rocks are placed in the pools, on that ground. They move no ground.

No vertex moves more than `MAX_CHANGE` 7.0 (the built map moves one by
6.11).

## 6. Files written

`build.py`, `ground.py`, `paint.py`. All in the built map.

- `t3HeightMap`: changed vertices only, first u16 of the record. Read
  back after the write; more than 0.01 off the plan fails the build.
- `Objects`:
  - placed `Waterfall`, `RockWaterfall`, `ZerusWaterfall` within
    `CLEAR_MARGIN` 12.0 of a site rectangle are dropped (R-WF-08);
  - `ZerusTree*` doodads with `HeightAbsolute` on moved ground move by the
    ground change (R-WF-09);
  - the feature's doodads are added, with new ids: the falls, then the
    rocks.
- `Base.SC2Data/GameData/WaterData.xml`: the height of the site water
  type. An absent or empty `CWater` gets a state. Other types are not
  touched. `Albion` had no entry: it stood at the engine default 9.0. It
  is now about 8.05.
- `CellAttribute_Pnp`: no pathing on pool cells at least `NO_PATH_DEPTH`
  0.3 deep, and on every cell a rock reaches (R-WF-10).
- `Preload.xml`: every placed water doodad type, and `ZerusRockLarge`
  with the variations placed. The `RockWaterfall` line of the map is not
  touched.
- `t3TextureMasks` (R-WF-05, `paint.py`): dirt on the sloped walls.
  - Texture: `WALL_TEXTURE` `Zerus1`, the lane dirt (`flora.dirt.DIRT_NAME`,
    editor name "Zerus Dirt Medium"), slot 5 of the palette in
    `t3Terrain.xml`. Operator 2026-11-20: first a rock texture (`Zerus6`
    was tried), then "switch to dirt, replace with the dirt texture we
    use". The build fails when the texture is not in the palette.
  - Weight per vertex: the slope of the carved ground (rise per cell),
    0 at `WALL_SLOPE` 0.5, solid at 1.2. Only within `WALL_MARGIN` 8.0 of
    a site rectangle. Flat ground gets none.
  - The mask is 2048 x 2048 with 4-bit weights; vertex weights are
    interpolated to it. The dirt layer only gains: new weight =
    max(old, wall). Where it gained, every other layer is scaled by
    (1 - wall weight), as `flora/hazard_paint.py` does for the lava.
  - The layer is read back after the write; a difference fails the build.
  - The lane gates read this layer (`flora/gates.py`). They route along
    the lanes only; the build with the wall dirt passes their check.
  - The HD texture build upscales the texture 1024 -> 4096
    (SPEC-HD-TEXTURES). Operator 2026-11-20: leave the 4096 file as it is.

## 6a. Plants round the pools (R-WF-15)

`scripts/flora/pools.py`, part of the flora step, so the plants are flora
plants: non-blocking footprint, crush data, flora checks.

- Pool: `Terrain.pool`, the cells of a `POOL_WATER` (`Albion`, equal to
  `SITE_WATER`) rectangle whose ground is under the drawn water (WaterData
  height - `GROUND_LIFT`). The rim is not pool.
- Ring: cells within `POOL_GARDEN_BAND` 3.5 of the pool, not in it, slope
  under `POOL_GARDEN_SLOPE` 0.8, outside every placed unit's keep radius,
  outside tree blockers and hazards. The spawn and base region keep-out
  of flora is not applied: the decimator pools lie inside the Terran base
  region, where the general rules place nothing.
- Plants: `POOL_GARDEN`, family and spacing, in this order:
  `ZerusSwampPlantsLarge` 3.5, `ZerusPlantClusterSmall` 2.5, `ZerusPlant`
  2.0, `ZerusSwampPlants` 1.5, `ZerusTallGrassCluster` 1.5. Two families
  keep `MIX_SPACING` 0.35 of their mean spacing apart. Scale and
  variation as the family has them.
- The ring is planted before every family of the general rules; those
  then keep their own spacing from it. Seed `SEED:pool:<family>`.
- Report: `flora_report.txt`, line `pool garden N`. Built map: 90 plants.

Line endings are kept.

Side effect on flora: `flora/terrain.py` now reads a height for `Albion`
(before, the type had no entry and its rectangles counted as dry). Its
placement rules take a cell as wet when the WaterData height is above
the computed ground, without `GROUND_LIFT`. So the rim, 0.4 above the
drawn water, counts as wet there. Built map: 4 `ZerusWaterPlant`, 3
`ZerusTallGrassCluster` and 1 `ZerusSwampPlants` stand on the rim of the
second hole; none in the first; none in a pool. The flora rule is not
changed here: it also shapes the river (operator 2026-11-15). Whether
plants on the rim look right is an operator check.

## 7. Checks (R-WF-12)

`plan.problems` and `paint.problems`. Each line fails the build:

| Check | Limit |
|---|---|
| a site has no fall, or a pipe mouth has none | |
| fall top off its aim | outside lip + (0.15 +- 0.08) x opening + 0.2, +- 0.25 |
| a mouth has under 2 falls, or they are narrower than its opening together | |
| two falls of one mouth have one size | |
| a fall reaches past the side of its pipe | radius + `SIDE_TOLERANCE` 0.3 |
| a bigger pipe whose falls are not wider | |
| fall water surface against the level | `FALL_RAISE` 0.2 over it |
| water lands on dry ground | depth < `WET_MIN` 0.2 |
| water lands outside the pool | |
| ground reaches a pipe mouth | above lip - 0.3 |
| two falls overlap | `FALL_OVERLAP_LIMIT` 0.8 of the smaller footprint |
| no `t3TextureMasks`, or the wall texture is not in the palette | |
| a pool has no rock | |
| a rock outside the pool, or in shallow water | depth < `ROCK_MIN_DEPTH` 0.4 |
| a rock buried or floating | origin under the floor, or over it by more than `ROCK_LIFT` 0.6 x underside |
| a rock top under the water | < level + 0.3 |
| a rock scale out of range | `ROCK_SCALE` 0.45..1.1 |
| a rock where a fall lands | < `ROCK_FALL_CLEAR` 2.0 |
| two rocks too close, or of one variation in a pool | < `ROCK_SPACING` 2.5 |
| a vertex outside the pool is below the rim | rectangle + 4.0 |
| a site has no pool | |
| ground moved too far | `MAX_CHANGE` 7.0 |

`apply_water_features` also fails when no site is found.

## 8. Assumptions, not verified in the game

- **Height spaces.** The plan works in ground space: the computed ground
  of `flora/terrain.py` (`sync_height.vertex_z`). Doodad z and the water
  height are written `GROUND_LIFT` 2.6 higher. `flora.lift` later adds
  `DOODAD_LIFT` 1.85 to every non-flora absolute doodad, so the step
  writes +0.75 while `.doodads_lifted` is absent (`build.doodad_rise`).
- **Facing.** A placed object is drawn as Rz(Rotation) x scale x model.
  The model front is -y. A unit without Rotation is drawn as authored.
- **Pipe base.** The decimator model stands on the computed ground at the
  unit position.
- **Water surface.** A fall's `base_z`, read from its splash emitters, is
  where the model meets the water.

A wrong assumption shows as falls above or below the pipes, turned away
from them, or a water sheet at the wrong height.

## 9. State

Host tests: `scripts/testkit/tests/water/test_water_features.py` and its
parts `_problems`, `_apply`, `_profile` (fixtures in `water_fixtures.py`),
74 tests, and `test_flora_pools.py` in the same folder, 8 tests. `scripts/playtest.sh host-tests` on
2026-11-20: 809 tests OK, map built.

The `waterfeat` profile also samples the rim fall groups
(SPEC-RIM-FALLS). In-game run `20261120-153715` is on the current code:
failures 0, realClicks 0, 106 PASS (52 of the water features before the
rim checks were added, run `20261120-144514`). It proves the carved ground, the pool pathing, the
walk and the pipe unit. It has no check for the fall facing, the wall
dirt, the rocks or the plants: those are placed doodads and paint, which
the profile does not read. They are built and host-tested only.

HD textures of the rock: `ZerusRockLarge` was not in the models cache, and
the inject step fails on a doodad it has not seen. A map was built with
`SC2_HD_TEXTURES=off` into a temporary folder and
`hd_textures.py --source models --map <folder> build --gpu 1` was run on
it. It upscaled `zerusrocks_diffuse` and `zerusrocks_normal` to 2048 (both
`ok` in `verify`) and patched the 8 rock models. Nothing else was
rebuilt. `verify` lists 43 failures on other model textures of that
cache; this run did not make them (SPEC-HD-TEXTURES section 12: not
finished).

In-game profile `waterfeat` (`scripts/playtest.sh waterfeat`): per site,
engine ground against the built ground (pool, shore, far), pool cells not
passable, a Marine ordered into the pool never stands in water
0.3 deep, the pipe unit's place and facing, and a 15 s camera orbit with 5
screenshots. Runs:

- `20261120-122504`: failures 0 (falls on the lip; before the operator's
  three points).
- `20261120-125100`: 2 FAIL, `s0_dry`/`s1_dry` "moved shore over the water
  level" (lowest 5.441 and 5.426 against 5.452). The profile took pool
  edge vertices 0.01..0.03 under water as shore. The profile now calls
  dry what the plan calls dry.
- `20261120-125354`, `20261120-125943`: failures 0, realClicks 0, with
  the higher, thicker, denser falls and rocks. Both are older than the
  current code (they still had rocks and a `rocks` check).
- `20261120-143924`: failures 0, realClicks 0, 52 PASS: dirt walls,
  rocks, plants; falls still along their pipes.
- `20261120-144514`: failures 0, realClicks 0, 52 PASS: the same with the
  falls facing southwest. The current code.
- `20261120-120834`: invalid, one real click.

A screenshot decides nothing (AGENTS.md). Seen in screenshots, run
`20261120-122504`, `s1_orbit-0001.png`, `s0_orbit-0001.png`: the water
sheet shows straight edges on the downhill side. Cause not found.

One profile build crashed once with `TypeError: 'int' object is not
iterable` in `expand_map.expand_heightmap`. Not reproduced in 14 further
calls. Cause unknown.

| ID | State | Evidence |
|---|---|---|
| R-WF-01 | [built] | host `SitesTest`; negative: other unit, other water type, site water with no mouth near |
| R-WF-02 | [built] | host `PlanTest.test_falls_hang_from_the_lip_onto_the_water`, `test_dense_and_varied`, `test_falls_face_the_mean_direction_of_the_pipes`, `test_fall_facing_turns_by_the_share`, `test_bigger_pipe_has_the_bigger_fall`, `test_feature_is_shifted_toward_the_bigger_pipe`; negative `ProblemsTest.test_floating_fall`, `test_fall_from_the_top_of_the_pipe`, `test_fall_past_the_side_of_its_pipe`, `test_small_pipe_with_the_bigger_fall`, `test_thin_stream_and_copies`, `test_mouth_without_fall`. How it is drawn: operator |
| R-WF-03 | [built] | host `PlanTest`; negative `test_fall_on_dry_ground`, `test_fall_outside_the_pool` |
| R-WF-04 | [built] | host `CarveTest`, `PlanTest.test_water_ends_on_a_shore`; negative `test_water_at_the_rectangle_edge`. The drawn water sheet: operator |
| R-WF-05 | [built] | host `PaintTest`, `ApplyTest.test_apply_writes_the_plan` (no `RockWaterfall` added; dirt layer = max(old, wall); grass scaled under new dirt); negative: flat ground and a wall away from a pool unpainted, dirt that was there not weakened, `test_palette_without_the_wall_texture_fails`. Built map: 32628 mask cells gained dirt; the `Zerus6` slot is empty again; lane gates pass. Not tested in the game: no Galaxy read of terrain paint is in use here (not searched for). How it is drawn: operator |
| R-WF-06 | [built] | host `PlanTest.test_no_overlap`; negative `ProblemsTest.test_stacked_falls` |
| R-WF-07 | [built] | host `MeasureTest`; negative: mast, short end and hull are no tubes |
| R-WF-08 | [built] | host `ObjectsTest.test_placed_water_doodads_at_the_sites_are_dropped`, `ApplyTest`; negative: the far water doodad and the tree stay |
| R-WF-09 | [built] | host `PlanTest.test_change_is_local_and_bounded`, `ObjectsTest.test_trees_follow_the_ground`; negative `test_too_much_ground_moved` |
| R-WF-10 | [built] | host `ApplyTest`: deep pool cells and the cell under every rock painted, far cell not; `ObjectsTest.test_rocks_are_added_after_the_falls`. The in-game profile has no check under the rocks yet. In game, run `20261120-144514`: `cells`, `walk` |
| R-WF-11 | [built] | host `PlanTest.test_deterministic`, `ApplyTest.test_second_run_changes_nothing` |
| R-WF-12 | [built] | host `ProblemsTest` (one fault per check), `ApplyTest.test_no_pipe_unit_fails_and_writes_nothing` |
| R-WF-13 | operator check | |
| R-WF-14 | [built] | host `MeasureTest.test_committed_data_has_what_the_build_needs`, `PlanTest.test_rocks_stand_in_the_pools`, `test_rocks_do_not_change_the_falls`, `ObjectsTest.test_rocks_are_added_after_the_falls`, `ApplyTest`; negative `ProblemsTest.test_rock_faults` (none, outside, buried, floating, drowned, scale, under a fall, too close, same variation). Built map: 5 `ZerusRockLarge`, `ModelData.xml` names the HD copy. How they are drawn: operator |
| R-WF-15 | [built] | host `test_flora_pools.py` `PoolGardenTest`: ring round the pool, every garden family, spacing, same input same garden, planted first; negative: none in the water, on a wall, at a hazard, in a tree, in a unit's keep radius, no pool no garden. `ApplyTest`: flora sees the carved pools, not the rim. Built map: `flora_report.txt` `pool garden 90`; the flora check of the build passes. How they are drawn: operator |

## 10. Operator checks

- Fall tops inside the pipe openings (operator 2026-11-20: they started
  too low); fall bases 0.2 over the water.
- Falls thick enough, dense and varied enough in scale (operator
  2026-11-20).
- Falls with unequal x/y and z scale: spray not stretched.
- Dirt on the pool walls: enough of it, and how it meets the grass.
- Rocks in the pools: the right doodad (`ZerusRockLarge`), size, count
  (3 and 2), how they sit in the water.
- Plants round the pools: families, density (90), none where they should
  not be. They stand inside the Terran base region, which flora keeps
  clear otherwise.
- Falls face southwest at both features (operator 2026-11-20).
- The water level in the holes (Albion 9.0 before, about 8.05 now).
- The pool edge: a shore, no straight rectangle edge, no water sheet
  floating over low ground.
- No rock waterfall left at the two holes.
- The carved walls of the holes against the sculpted ones.
- Trees around the holes still stand on the ground.

# SPEC-SCALED-FOOTPRINTS: Pathing Blockers of Scaled Props

**Date:** 2026-11-15
**Status:** Built (v2, trunk outline). Section 6 gives the state of each
requirement and the run that backs it.
**Requirements:** [REQ-SCALED-FOOTPRINTS](../requirements/REQ-SCALED-FOOTPRINTS.md)

## 1. Cause

A footprint is a fixed shape. Stock `ZerusTree` uses `FootprintDoodad1x1`.
The scaled mesh of an 8x tree is up to 15 cells wide. Spores keep their stock
footprint at 3x scale.

## 2. Engine behaviour (probe profile `fprot`)

- Doodad Place cells without a `Shape` block nothing; the `Shape` polygon
  blocks (run `20261115-132159`).
- `Shape` rotation snaps to the nearest quarter turn, ties down:
  45→0, 60→90, 135→90, 225→180, 315→270.
- A concave `Shape` keeps its notch.
- Placed Scale does not scale the `Shape` (run `20261115-132312`).
- The `Shape` follows the placed position rounded to 0.5; the pathing grid is
  0.5 (run `20261115-132422`).
- Units also block their Place cells. A spore with only a `Shape` left disk
  edge points open (treepath run `20261115-133213`).

## 3. Mesh slices

`scripts/mapgen/footprints/measure.py` (`uv run python -m footprints.measure` from
`scripts/`) reads the models with `tools/stormex` and
the vendored `m3addon`. It cuts the mesh triangles at 80 heights (step 0.0025
model units) and writes `scripts/data/footprint_slices.json` (committed).
Re-run only when the game models change.

## 4. Blocker shape

`scripts/mapgen/footprints/`, per placed object:

- Take the slices in the feet band, world z `FEET_LOW`=0.05 to `FEET_HIGH`=0.35,
  divided by the scale. Raise `FEET_LOW` to shrink root-plate blockers.
- Trees: union of variation `v` and `v % 12`. ModelData has `VariationCount 12`,
  but 47 trees use 12-14 (operator check).
- Scale the outline, then rotate by the residual between the placed rotation
  and the engine quarter turn (`ceil(deg/90 - 0.5) % 4`), so the snapped
  `Shape` lands on the mesh.
- Erode the outline by `ERODE` = 0.375 (one unit radius). Units keep their
  centre one radius off a blocker, so the visible blocked area is the Shape
  grown by that radius. Without it blockers looked about 1.75x too large by
  area (operator, 2026-11-15). Total tree area went to 0.67 of before.
- Rasterize on the 0.5 grid (cell blocked at coverage ≥ 0.5), keep the largest
  component, fill holes, close pinches, trace a clockwise rectilinear polygon.
- A trunk with no sub-cell left after erosion blocks the one cell at its
  mesh centre.
- Spores: a disk at the origin with the area of the solid core, plus matching
  Place/Check cell rows (`disk_cells`).

Code: package `scripts/mapgen/footprints/` (`config`, `slices`, `raster`, `catalog`,
`blocker`, `placement`, `build`).

Fit checks (R-FP-07), against the eroded mesh: covered ≥ `MIN_MESH_COVERED`
0.5 when the mesh is over `MIN_CHECKED_MESH` 1.0; blocked area ≤
`MAX_BLOCKED_RATIO` 1.5 × mesh + 1 cell. Spore fit is reported, not enforced
(noisy meshes). Report: `out/SCOBA256.SC2Map/footprint_report.txt`.
`scripts/validate-map.py` calls `check_scaled_footprints`.

## 5. Generated data

- `FootprintData.xml`: `FootprintScoba<sha1[:10]>`, `Shape` polygon; trees
  get 1x1 layers, spores disk rows.
- `ActorData.xml`: `ZerusTreeFp<hash>`, `parent="ZerusTree"`. `Preload.xml`
  entries for each.
- `Objects`: each tree's `Type` becomes its actor. Positions are not moved
  here. Later, `flora.lift.sink_trees` lowers every absolute `ZerusTree*`
  (editor and border trees) by its final scale: scale > 4 by 1, scale > 6
  by 2 (`TREE_SINK`, operator 2026-11-16; not cumulative). Footprints are cut
  before the sink, so a sunk tree's feet band is measured 1-2 higher up its
  model than where it now meets the ground. The ground calibration
  (`flora.terrain._offset`) adds the sink back. Host test:
  `test_tree_sink.py`.
- `UnitData.xml`: `SporeCannon`, `SporeCrawler` `Footprint`.
- Square units (`config.SQUARE_UNITS`, `HybridUltraliskShackled` 12): a fixed
  12x12 `CFootprint` (Shape square, Check and Place rows) linked in `UnitData.xml`.
- `ActorData.xml`: the square unit's `CActorUnit` entry gets
  `config.FLATTEN_EVENTS` appended. The water splash step already writes an
  entry for the ultralisk; without one, a new entry with no parent merges into
  the stock actor. The events: unit birth
  creates core.sc2mod's `BuildingTerrainFlatten` (Normal), `...Instant`
  (Suppressed) or `...Editor` (EditorPlaced). These deformers use the unit
  footprint, so the flattened area is the 12x12 square. It was 8x8 until
  2026-11-20; the unit's hit shapes reach 5 to 6.8 from its centre.
- Flatten-only units (`config.FLATTEN_UNITS`, `VespeneGeyser`; operator
  2026-11-20): the same three events on the unit's actor. The unit keeps its
  own footprint (`FootprintScobaGeyser6x6`, R-BASE-35). Not known: whether
  the deformer covers the solid 6x6 only or also the 12x12 ring of the
  footprint.
- `check_squares` fails the build check when the footprint link, its shape, or
  a flatten event is missing.
- **2026-11-20: the hall is measured on the classic model**
  (`CommandCenter_Remastered.m3`, SPEC-HD-TEXTURES 12; operator: "the legs
  are a tiny bit off need to recalculate footprint"). It has no `Foot_*`
  bones. The triangles of the bones named `*Leg*` are sliced
  (`measure.MODEL_BONES`): three round legs `Leg1..3` and two side plates
  `LegPlate`, `LegPlate2`. `Stand` does not move them. Scale 2.88 and the
  turn of 45 degrees are as before. Result `FootprintScobaHall653a23aebf`:
  35 cells, 7 loops. Three loops of 3 by 3 are the legs, at about
  (-0.5, -5), (-5.5, 0), (4, 4.5). Four smaller loops are what the plates
  put at feet height after `ERODE`. `measure` checks the unit shows
  `measure.HALL_FILES` by file name, so a packaged copy passes. The text below
  on feet, bones and footprint ids describes the stock model, measured
  before. Not seen in the game. The F and A marks of the Alt+0 paint are
  still the stock foot points; the red marks are the engine's cells.
  2026-11-20: the Orbital Command and the Planetary Fortress show the
  same model entry `CommandCenter` (`hitvolumes.resolve` on the map and
  the stock stack). Before, their actors had scale 1 and the units kept
  `FootprintSCOBAHall1x1`: an Orbital Command blocked nothing, and the
  legs opened when the morph started (operator 2026-11-20: "2 of the
  CCs do not have pathing blocking"). Now all three actors have `Scale`
  3.6,3.6,4.2 in the map's ActorData and are in `config.HALL_UNITS`, so
  each links the footprint measured at its own drawn scale; the three
  ids are equal. `check_halls` fails the build check when the hall
  scales differ. `hall` group: a CC morphed to each form keeps the
  footprint during and after the morph.
  `config.HALL_FOOTPRINTS_ON` switches the hall footprints: off, the build
  writes none, `check_halls` checks none, and the Command Center keeps
  `FootprintSCOBAHall1x1` and blocks no pathing.
- Halls (R-FP-10, `config.HALL_UNITS`): `CommandCenter`, model
  `CommandCenter` (`CommandCenterEx1.m3`, measured as group
  `CommandCenter`). The scale is the drawn scale (`hall_scale`): the x of
  the unit's `CActorUnit` `Scale` in the built `ActorData.xml` (3.6) times
  the model's ModelData `ScaleMax` (0.8, liberty `CommandCenterBase`),
  2.88. `measure` resolves the unit along the Void Story data stack
  (`hitvolumes.resolve`), checks the m3 is the sliced one, and stores
  `model_scale` in `footprint_slices.json`. Only the triangles whose three
  vertices are skinned mostly to one `Foot_*` bone are sliced
  (`measure.MODEL_BONES`), one slice set per foot; each foot is filled
  apart and clipped to its own box (`mesh_samples(clip=True)`). Before,
  body triangles and an even-odd fill across the four feet blocked bars
  at y ±3, x -2..2 (operator 2026-11-19: "weird flying strip patterns
  that have nothing to do with the round geometry of the 4 feet"). Feet slices as for trees, eroded by `ERODE`, on
  the 0.5 grid; every 0.5 sub-cell kept (all four legs, not the largest
  component). The Shape is the outline of these sub-cells on the 0.5
  grid, exactly as for trees (`hall_sub_rows`, `hall_polygons`): one
  closed loop per foot, holes filled. Before, the Shape followed whole
  cells (operator 2026-11-19: "large areas that are empty but blocked
  and feet still don't match quite"; 40 cells blocked for a foot area of
  30.5). The Check and Place rows stay whole cells (placement has no
  finer grid): a cell is set when at least `HALL_SUBCELLS` (2) of its
  4 sub-cells block; then every corner pinch gets one cell
  (`close_pinches`). Rows on an odd square centred on the hall origin,
  `Area` `-h,-h,h+1,h+1` (stock 3x3 style, origin on a cell centre).
  The engine blocks unit pathing by the Shape, not by Place cells (`hall`
  run `20261119-134456`: rows only, the Barracks was refused but no cell
  blocked pathing). `FootprintScobaHall<sha1[:10]>` with the same Check
  and Place rows becomes the unit `Footprint`; `PlacementFootprint` stays
  `FootprintSCOBAHall1x1`, so a hall may still stand on a mineral field.
  The flying forms have no footprint, so lift and land need no script.
  Not measured, keep `FootprintSCOBAHall1x1`: the Orbital Command (model
  `OrbitalCommand` is not in the extracted mods) and the Planetary
  Fortress (model `CommandCenter` at actor scale 1 slices to a solid 5x5
  with the middle closed, which would stop the drop-off).
  `check_halls` fails the build check when a hall link is missing.
  Foot bones `Foot_01..04` at (±1.6, ±1.6) model units, the same in the
  bind pose and in `Stand`; drawn at about ±4.6. Foot pad vertices at
  2.88: x -6..-2 and 2..6, y ±3..±7, in model axes. The model is drawn
  turned by the unit `Facing` minus 270 (the facing at which a model is
  drawn as authored): every grounded CC reports `UnitGetFacing` -135 =
  225 (`hall` run `20261119-211246` raw; liberty UnitData says 315), a
  turn of 45 degrees off the model axes, so the feet stand on the axes at about 6.5, not
  on the diagonals (operator 2026-11-19, Alt+0 paint: the unturned
  marks sat 45 degrees off the drawn feet). A structure footprint is
  not turned by the engine, so the turn is baked in
  (`config.HALL_FACING`, `MODEL_FORWARD`, `hall_angle`). The `hall`
  test asserts every grounded CC faces 225. Unproven: 270 as the
  authored facing (225 against 315 differs by a quarter turn, which
  maps the four round feet onto each other).
  `FootprintScobaHall211404f440`: Shape of four loops (12 points) at
  x ±5.0..±8.0, y -1.5..1.5 and y ±5.0..±8.0, x -1.5..1.5, area 32;
  rows 17x17, 32 cells; no bar, no ramp; the middle and the diagonals
  open. Superseded: `FootprintScobaHall10cda09540` (unturned, feet on
  the diagonals),
  `FootprintScobaHall786dfd20ab` (same feet, Shape on whole cells),
  `FootprintScobaHallb775be01c4` (whole mesh,
  bars and ramp). Before (scale 3.6, actor only,
  `FootprintScobaHallfd3a42e7cc`): legs at about ±6, 25% too far out
  (operator 2026-11-19: "do not match where the actual building legs are").

Debug paint (R-FP-11, `scripts/app/systems/debug/hall_paint.galaxy`):
Alt+0 (player 1) toggles it. Every 1 game s, for each ground town hall
(up to 16): every 0.5 sub-cell centre within 9 cells (36x36 sub-cells,
the grid the Shape is traced on) that is not
`PointPathingPassable` gets a red "x" text tag for player 1 at that
point; every 0.25 game s a mark shows only when at least 1.0 in front of
player 1's eye and within 30 of the camera target (a text tag behind the
camera or far away is drawn at the screen edge or the horizon:
the operator's screenshot showed strips). Creep was tried: it spills onto the neighbour cells (83 open
cells around 84 blocked ones at radius 0.5 and at 0.25, `hall` runs
`20261119-193300`, `-193622`), so it cannot mark one cell. Text tags
for player 1: "F" green at the four foot
points, "A" yellow at the foot points at the actor scale alone (3.6),
"O" blue at the origin. F against A: which scale the engine draws
(operator 2026-11-19: F still sat on empty ground). Foot point = hall + (bone x, bone y) x
drawn scale; bones `Foot_01..04` at (1.592 or -1.608, ±1.6) model units;
drawn scale = the CC actor `Scale` x the model `ScaleMax`, both read from
the catalogs at run time (`CatalogFieldValueGet`), so a wrong scale shows
as F marks off the feet. The previous marks are removed before each
repaint; off removes all marks. The game catalogs give actor Scale
3.6,3.6,4.2, model `CommandCenter`, `ScaleMax` 0.8: F scale 2.88
(`hall` run `20261119-193300` raw).

Built map: 334 trees, 249 footprints. Largest trees block about area 75
(root plate at feet height). `uv run python -m footprints.preview` (from `scripts/`) prints ASCII views.

## 6. State

Run `out/test-runs/treepath/20261115-133439` (built-in textures),
`failures: 0`. Targets: largest tree (area 77.75), most off-centre tree, a
1-cell tree, a tree far from a quarter turn, one cannon, one crawler.

| ID | State | Evidence |
|---|---|---|
| R-FP-01 | [tested] | up to 16 points inside each tree `Shape` not passable |
| R-FP-02 | [tested] | same for cannon and crawler |
| R-FP-03 | [tested] | lean and turned trees: inner blocked, outer open |
| R-FP-04 | [tested] | up to 16 points 1.0 outside each `Shape` passable |
| R-FP-05 | [tested] | hero reaches far side (≤ 0.4); path depth inside `Shape` ≤ 0.49 |
| R-FP-06 | [built] | host tests `test_scaled_footprints.py` |
| R-FP-07 | [built] | host tests `test_scaled_footprints.py` |
| R-FP-11 | [tested] | `baseai hall` run `20261119-203139`: on, all 214 engine-blocked 0.5 sub-cells around p9 marked (Miss 0), no open one marked (Extra 0), 640 marks over 3 halls plus 9 per hall (667 tags), F scale 2.88; off, no mark left. The look: operator |
| R-FP-08 | [built] | host test `test_caged_ultralisk_gets_12x12_square`; in game: `treepath` section `cage_ultralisk`, not run yet |
| R-FP-09 | [built] | host test checks the actor events; the flattened look is an operator check |
| R-FP-10 | [tested] | host tests `test_hall_footprints.py`; `baseai hall` run `20261119-203139` (failures 0, `FootprintScobaHall10cda09540`): the engine pathing sampled on the 0.5 grid (36x36 sub-cells) of a built, a created and a landed CC equals the traced feet outline sub-cell for sub-cell; each starting CC covers it. Whether the feet drawn on screen sit on it: operator. Earlier, Shape on whole cells: run `20261119-180620` at 2.88, run `20261119-135358` at 3.6: the engine grid of a built, a created and a landed CC equals the measured cells, the starting CC of p9 blocks every measured cell, origin open, one SCV mines 20 in 25 s, nothing blocked while flying or after death |

That run predates `ERODE`. With `ERODE`, run `20261115-141959` has one
failure: `tree_thin outerBlocked: got=6 want=0` (tree 8 blocks one 0.25
sub-cell; 6 of 16 points 1.0 outside are blocked). The operator was running
the game in parallel, so that run is not valid either way. Erosion is
implemented, not verified.

## 7. Operator checks

- Blocker edge against roots and trunks (in-game look).
- Variation 12-14 trees: which model the engine shows.
- Spores (operator will test).
- Groves still leave intended paths open.
- Sunk large trees (scale > 4) sit right on the ground, not buried.
- Caged ultralisk: the terrain under its 12x12 footprint looks flat, and the
  cage model sits on it.
- Command Center: the blocked cells sit under the visible legs and the ramp
  faces the way the model does (model -y taken as world -y at facing 270).
- Debug paint (Alt+0): red x cells against the visible legs; F marks on
  the visible feet.

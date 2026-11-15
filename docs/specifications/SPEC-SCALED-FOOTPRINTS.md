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

`scripts/footprints/measure.py` (`uv run python -m footprints.measure` from
`scripts/`) reads the models with `tools/stormex` and
the vendored `m3addon`. It cuts the mesh triangles at 80 heights (step 0.0025
model units) and writes `scripts/data/footprint_slices.json` (committed).
Re-run only when the game models change.

## 4. Blocker shape

`scripts/footprints/`, per placed object:

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

Code: package `scripts/footprints/` (`config`, `slices`, `raster`, `catalog`,
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
- `Objects`: each tree's `Type` becomes its actor. Positions are not moved.
- `UnitData.xml`: `SporeCannon`, `SporeCrawler` `Footprint`.

Built map: 334 trees, 249 footprints. Largest trees block about area 75
(root plate at feet height). `uv run python -m footprints.preview` (from `scripts/`) prints ASCII views.

## 6. State

Run `out/test-runs/treepath/20261115-133439` (`SC2_HD_TEXTURES=off`),
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

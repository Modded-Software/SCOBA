# SPEC-RIM-FALLS: Procedural Waterfalls at the Inner Rim

**Date:** 2026-11-20
**Requirements:** [REQ-RIM-FALLS](../requirements/REQ-RIM-FALLS.md)
**Code:** `scripts/mapgen/rimfalls/`

## 1. Build step

`apply_rim_falls(map_dir)` in `build.py`, called from
`scripts/expand_map.py` after the water features and the resources (the
geysers are placed by then, R-RF-13) and before footprints and flora: they
read the cut ground.
`SC2_NO_RIM_FALLS=1` skips it (R-RF-11). The marker `.rim_falls` holds the
report; a second run does nothing.

The step reuses the water features' helpers: `ground` (height map),
`build.move_trees`, `build.add_doodads`, `build.doodad_rise`,
`build.update_preload`, and the measured `Waterfall` and `ZerusRockLarge`.

## 2. Measured models

`scripts/data/rim_models.json`, written by
`PYTHONPATH=scripts uv run python -m mapgen.rimfalls.measure`: the 7
`RockWaterfall` variations from the game storage. Per variation: bounds,
the water surface the model was made for (`base_z` -2.94, from its splash
emitters) and where its streams land. The model front is -y; its back is
at y +0.5. `models.load` adds them to the water features' models. The
water features' own file stays without a rock waterfall.

## 3. Sites (R-RF-01, R-RF-02, R-RF-09)

`sites.py`. All lengths are world units; values are in `config.py`.

- The ground is averaged over 7 x 7 vertices (`NORMAL_RADIUS` 3). Its
  gradient gives the slope and the downhill unit vector per vertex: the
  wall normal on the ground plane.
- A candidate is a vertex with:
  - edge distance `EDGE_MIN` 5 to `EDGE_MAX` 20 (R-RF-14; 8 to 34 before);
  - slope at least `WALL_SLOPE` 0.45;
  - downhill pointing to the map centre (cosine at least `INWARD` 0.3);
  - the ground `WALL_REACH` 6 uphill (or at the map edge) at least
    `WALL_RISE` 2.5 higher;
  - the slope `FOOT_REACH` 6 downhill at most `FOOT_SLOPE` 0.7;
  - no water rectangle within `WATER_MARGIN` 14;
  - nothing placed within `CLEAR` 4.5. A tree reaches 0.5 x its scale
    (its canopy). A `VespeneGeyser` reaches `GEYSER_REACH` 12, so no site
    is within 16.5 of one (R-RF-13). Every other doodad, unit and point
    is a point.
- The rim is cut in `SECTORS` 28 round the map centre. Only the middle
  `SECTOR_USE` 0.85 of a sector takes a site. Each sector gives its
  emptiest candidate.
- Two picks closer than `MIN_SPACING` 14: the emptier one stays.
- So a change in one sector reaches the sectors next to it at most
  (through the spacing rule, one further).

## 4. Basin (R-RF-06)

`carve.py`. The basin centre is `BASIN_AHEAD` 2 downhill of the site. Its
edge level is the uncut ground at its downhill side. Inside
`BASIN_RADIUS` 3 the ground is lowered to a bowl `BASIN_DEPTH` 0.9 deep.
Over `BASIN_BLEND` 2.5 more the cut fades out. On the uphill side this
cuts a notch into the wall. The ground is never raised.

No water sheet is placed. The map has one height per water type
(`WaterData.xml`), and the basins lie at many heights. The fall models
bring their own splashes.

## 5. Composition (R-RF-03, R-RF-04, R-RF-05)

`compose.py`. Each group draws from its own sequence, keyed on the seed
(`SEED` 20261121) and the site position.

- Rock waterfalls: 1 or 2, different variations. Ground-plane scale 0.9
  to 1.7; height scale 0.9 to 1.25 times that. A second one is 0.75 times
  as big, 2 to 3.5 to a side.
- Embedding (R-RF-12, `embed_back`): a rock waterfall stands uphill of
  the basin centre, at the first point where the cut ground covers
  `EMBED` 0.35 to 0.5 (chance) of its height over the water; at least 0.7
  x the basin radius back, `EMBED_REACH` 14 at most. Its water surface
  stays at the basin level, so its lower part and its splash are under
  the ground there.
- Normal waterfalls: 1 to 3, in front of the first rock waterfall by 0.2
  to 1.4, up to 1.8 to a side. Ground-plane scale 0.8 to 1.9. The top
  reaches 0.45 to 0.95 of the rock waterfall's height over the water.
- Facing: `rotation_facing(site.dir)` plus or minus `TURN_JITTER` 0.14
  rad.
- Height: every model's water surface (`base_z`) is at half the basin
  depth below the basin edge.
- Basin rocks: 2 or 3 `ZerusRockLargeScobaRim`, scale 0.3 to 0.7, within
  0.8 of the basin radius, 1.2 apart, 0.9 clear of where the rock
  waterfalls' streams land, origin 0.1 under the cut ground.

## 6. Files written

- `t3HeightMap`: the cut vertices. Read back and compared to the plan.
- `Objects`: the falls and rocks, flags `HeightAbsolute` and
  `ForcePlacement`. Trees on moved ground move with it.
- `ActorData.xml`: `ZerusRockLargeScobaRim`, parent `ZerusRockLarge`, same
  model, footprint `FootprintScobaRimNone` (R-RF-07). The stock rock has a
  2 x 2 footprint.
- `FootprintData.xml`: `FootprintScobaRimNone`, no blocked cell.
- `Preload.xml`: `RockWaterfall`, `Waterfall`, `ZerusRockLargeScobaRim`.
- `CellAttribute_Pnp` is not touched (R-RF-07). The stock `RockWaterfall`
  and `Waterfall` actors have no footprint.
- `.rim_falls`: the report, one block per group.

Upscaled textures: the package step finds the models the map shows by
itself (SPEC-HD-TEXTURES, section 5.1). The package of 2026-11-24 holds
the waterfall textures. A doodad type with no picked texture keeps its
originals and does not fail the build.

## 7. Checks (R-RF-10)

`build.problems`. Each line fails the build before anything is written:

| Check | Limit |
|---|---|
| number of groups | 12 to 24 |
| two sites too close | < `MIN_SPACING` 14 |
| ground raised | any |
| ground cut too deep | > `MAX_CUT` 8 |
| a group without a rock waterfall or without a normal one | |
| a group without a basin rock | |
| a fall turned off the wall normal | > `TURN_JITTER` 0.14 |
| a fall off the map | |
| a rock waterfall not embedded | ground covers < `EMBED_MIN` 0.25 of its height over the water |

## 8. Assumptions

Shared with the water features (SPEC-WATER-FEATURES section 8): height
spaces, and that a placed object is drawn as Rz(Rotation) x scale x model
with the model front at -y. Not verified in the game for the rock
waterfall: that its `base_z` is where it meets the water.

## 9. State

Built map of 2026-11-20 (stamp `e466b85c7bcd-8a87055a5b6ebcc3`), after the
operator's second round (embedded, no geysers, closer to the rim): 16
groups, 58 falls, 36 rocks, 1262 vertices moved, deepest cut 6.67, no tree
moved. Rock waterfalls embedded 0.40 to 0.62. Edge distance 5 to 20.
Nearest geyser 18.0 or more.

**The in-game run below is from before that round** (13 groups, other
sites). No in-game run exists on the current sites: the operator's game was
running. Rows that cite the run are "implemented, not verified" for the
current build until it is re-run.

| Requirement | State | Backed by |
|---|---|---|
| R-RF-01 groups at the rim | Verified for the count and the cut ground; placement rules host-tested | run `20261120-153715` (`rim fall groups built`, `r*_basin` checks); `SitesTest` |
| R-RF-02 empty positions | Implemented, host-tested | `SitesTest` |
| R-RF-03 layered rock and normal falls | Implemented, host-tested; the look is an operator check | `ComposeTest` |
| R-RF-04 chance | Implemented, host-tested | `ComposeTest.test_sizes_and_turns_vary` |
| R-RF-05 facing the wall normal | Implemented, host-tested; not verified in the game (Galaxy cannot read a doodad's rotation) | `ComposeTest`, `ApplyTest.test_written_falls_face_the_wall` |
| R-RF-06 basin with rocks | Basin cut: verified. Rocks: implemented, host-tested | run `20261120-153715` (`r*_basin engine ground = built ground`, `basin is cut`); `CarveTest`, `ComposeTest` |
| R-RF-07 walkable | Verified on the 39 sampled points that lie on ground the map leaves walkable | run `20261120-153715` (`r*_walk`, `rim points on ground the map left walkable`) |
| R-RF-08 rock waterfalls here only | Implemented, host-tested | `test_water_features.py` (no rock waterfall in the water features) |
| R-RF-09 same input, same groups; local change | Implemented, host-tested | `ApplyTest.test_two_builds_are_identical`, `SitesTest.test_a_change_only_reaches_the_sectors_near_it`, `ComposeTest.test_a_group_does_not_depend_on_the_other_sites` |
| R-RF-10 build fails | Implemented, host-tested | `ApplyTest.test_a_map_without_a_rim_fails_and_writes_nothing` |
| R-RF-11 flag | Implemented, not verified by a test; used once by hand for a staged build | |
| R-RF-12 embedded | Implemented, host-tested; the look is an operator check | `ComposeTest.test_rock_waterfalls_are_embedded_in_the_wall`, `test_a_floating_rock_waterfall_is_a_problem` |
| R-RF-13 no geysers | Implemented, host-tested | `SitesTest.test_sites_keep_away_from_geysers` |
| R-RF-14 close to the rim | Implemented, host-tested | `SitesTest.test_sites_are_close_to_the_rim` |

Host tests: `scripts/testkit/tests/water/test_rim_falls.py`, 34 tests, and the
rim cases of `test_water_features.py` `ProfileTest`.
`scripts/playtest.sh host-tests` on 2026-11-20: 813 tests OK, map built.

In-game: the `waterfeat` profile samples each group (`r<i>_basin`,
`r<i>_rocks`). Run `20261120-153715`: failures 0, realClicks 0, 106 PASS.

Known limits:

- In that run, groups 1 (basin 222,245) and 7 (basin 35,34) stood on
  ground the map itself paints as not walkable. Their points were listed,
  not judged. Not re-checked for the current sites.
- Embedding hides the foot of a rock waterfall and its splash in the
  wall. The normal waterfalls stand in front of it on the slope, so their
  feet are under the ground too.
- An earlier run (`20261120-153031`, 6 failures) judged every point and
  failed on those painted cells and on one cell under a tree footprint.
  The check now judges only ground the map leaves walkable.
- 16 groups against a lower limit of 12. A port that fills the rim can
  fail the build.
- Flora runs later and plants on and round the basins (vines were found
  inside one).
- The basins hold no water sheet (section 4).

## 10. Operator checks

- Where the groups stand, and whether 16 is enough.
- Whether the rock waterfalls now read as part of the wall.
- Size of the rock waterfalls against the wall.
- Layering and facing as drawn.
- The basins: dry floor with rocks, and the splash of the falls on it.
- Plants in and round the basins.

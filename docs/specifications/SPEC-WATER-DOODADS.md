# SPEC-WATER-DOODADS: Water Doodad Density

Requirements: [REQ-WATER-DOODADS](../requirements/REQ-WATER-DOODADS.md).

## 1. Build step

`scripts/mapgen/water_doodads.py`, `apply_water_doodads(map_dir)`. Called by
`scripts/expand_map.py` after `expand_props`, so positions are in 256-map
units, and before `lift_doodads` and `disable_doodad_occlusion`, so copies
get the same lift and occlusion handling. `SC2_NO_WATER_DOODADS=1` skips it.
Marker file: `.water_doodads` in the built map, with counts before and after.

## 2. Rules

| Constant | Value | Meaning |
|---|---|---|
| `WATER_TYPES` | Waterfall 1, RockWaterfall 7, ZerusWaterfall 1 | in-scope types and model VariationCount (liberty.sc2mod ModelData) |
| `DENSITY_FACTOR` | 2 | count multiplier |
| `NEIGHBOR_RADIUS` | 6.0 | gap fill search radius, 256-map units |
| `SIDE_OFFSET` | 1.5 x scale | lone copy offset across the facing |
| `POSITION_JITTER` | +-0.25 | x and y |
| `SCALE_JITTER` | +-15 % | uniform scale |
| `ROTATION_JITTER` | +-0.2 rad | keeps the flow direction |
| `SEED` | 20261119 | fixed seed, Id order |

- Gap fill: each source takes the nearest water doodad within the radius
  whose pair is not filled yet. The copy goes to the midpoint, height averaged.
- Fallback: the copy goes `SIDE_OFFSET x scale` to the left or right of the
  source facing, at the source height.
- Copies keep all source flags (HeightOffset, HeightAbsolute,
  ForcePlacement). They get new Ids after the highest Id in the map.
- Types with more than one variation get a different one.
- `Preload.xml` of the built map gets an entry for every placed water type.
  Missing entries are added after the last `Actor` entry. Types with more
  than one variation list every variation then placed.
- The step fails the build when a type does not end at exactly 2x.

## 3. State

| ID | State | Proof |
|---|---|---|
| R-WD-01 | Verified (host) | `test_water_doodads.test_doubles_every_water_type`; build marker counts |
| R-WD-02 | Verified (host) | `test_copy_fills_gap_to_neighbour`, `test_lone_copy_beside_source_across_facing`, `test_pair_filled_once` |
| R-WD-03 | Verified (host) | `test_variation` |
| R-WD-04 | Verified (host) | `test_other_doodads_untouched` |
| R-WD-05 | Verified (host) | `test_deterministic` |
| Preload | Verified (host) | `test_apply_marker_and_preload`, `test_preload_adds_missing_entries` |
| Look in game | Operator check | density and placement on the cliffs |

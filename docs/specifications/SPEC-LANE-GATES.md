# SPEC-LANE-GATES: lane gates

Implements REQ-LANE-GATES.

## Dirt mask (`scripts/flora/dirt.py`)

- Texture `Zerus1` ("Zerus Dirt Medium"), its slot read from `t3Terrain.xml`.
- `t3TextureMasks`: 64-byte header, 8 layers of 64 x 64 four-bit tiles.
- A map cell is dirt when its mean weight is at least 8 of 15.

## Gates (`scripts/flora/gates.py`)

- Per lane and side: cheapest route spawn -> X region, off-dirt cost x25.
- Gate centre: the middle dirt cell of that route, moved (up to 6 cells) to
  the point farthest from the dirt edge.
- Gate radius: 0.8 x the distance to the dirt edge there.
- Build writes `scripts/app/data/lane_gates.galaxy` (`gv_gateAt[side][lane]`,
  `gv_gateRadius[side][lane]`; side 0 Zerg, 1 Terran; lane 1 center,
  2 bottom, 3 top). `src/` holds an empty table (radius 0 = no gate).
- Build fails if any point in a gate is off the dirt or the table differs.

## Orders (`scripts/app/systems/lanegates.galaxy`)

- Spawn (`spawns.galaxy`): each unit attack-moves to a random point in its
  side's gate, then (queued) a random point in its X region.
- X region (`camera.galaxy` X triggers): attack-move to a random point in the
  enemy side's gate, then a random point in the enemy spawn region.
- Random gate point: uniform over the circle area.

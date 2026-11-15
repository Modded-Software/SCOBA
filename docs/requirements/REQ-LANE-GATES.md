# REQ-LANE-GATES: waves follow the lanes

Operator requirements, 2026-11-16.

1. Timer-spawned waves follow their curved dirt lane ("Zerus Dirt Medium")
   and do not cut through the jungle.
2. One extra point per half-lane, between each spawn and its X region, on the lane.
3. Each unit goes to a random point in each target area (gate, X region,
   enemy spawn), areas almost as broad as the lane, so units do not all walk
   the same line.

## Verification

- 2 and on-lane gates: build check (`flora.gates.problems`) and host tests
  (`test_lane_gates.py`).
- 1, 3 in game: not yet tested (planned profile `lanegates`).

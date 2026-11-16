# SPEC-FLORA-CRUSH: crushable flora

Implements REQ-FLORA-CRUSH.

## Data

- A script cannot list placed doodads, so the build writes a table:
  `scripts/app/data/flora_crush.galaxy` (generator `scripts/flora/crush.py`).
- Rows: x, y, z, kind, effect size. Sorted into 8 x 8 cell buckets on a 32 x 32 grid.
- Effect size = doodad scale x family spacing / 3.0.
- `src/` holds an empty table; `apply_flora` writes the real table and
  `check_flora` fails the build when it differs from the plan.

## Runtime (`scripts/app/systems/crush.galaxy`)

- Every 0.25 s, each live Goliath and Queen checks the 3 x 3 buckets around it.
- A plant within 2.5 of the unit is removed with `libNtve_gf_RemoveDoodadsinRegion`
  (circle 0.3, that kind only).
- Effects: the rock clip at once; the two dust clips are queued (64 slots) and
  played by a 0.0625 s timer after 0.1-0.3 s.
- Per clip: scale = size x random 1.5-2.0; origin offset random up to 0.6 in x and y;
  `AnimPlay Birth`; global animation time scale 0.25; destroyed after 16 s
  (ring of 384 actors).
- The effect is created at script height (no height override).

## Lava hazards near water

- `config.HAZARD_WATER_CLEAR`: 8 cells beyond the hazard's half size.
- `lanes.blocker` rejects spots near water; `HAZARD_SHIFTS` adds shifts of 9, 12, 15.
- Known: the first lava pair (18 from the crossing) finds no spot on any lane and
  is dropped (15 hazards instead of 18).

## Tests

- `crushtest` profile: Marine walks 3 plants (none removed), Goliath and Queen
  3 each (all removed).
- `fxgallery`: operator gallery of candidate clips, not pass/fail.

## Sounds

- Rock clip: random `PhysicsImpactRockHeavy` / `PhysicsImpactRockMassive`.
- First dust clip: random `PhysicsImpactDirtMedium` / `Heavy` / `Massive`.
- `SoundPlayAtPointForPlayer`, all players, at the plant.

## Ground shake (`scripts/app/systems/quake.galaxy`)

- Every 1/16 s per hero player: each live Goliath/Queen adds
  amp = 0.04 x radius x speed share x (1 - d / (12 x radius)); d from the hero.
- Stepped wave: a jolt per footfall (2 Hz at full speed), then x(-0.35) per
  tick, random 0.7-1.0 per step; roll random sign.
- Sum capped: height +-0.06, roll +-0.5 deg. Written with `CameraSetValue`,
  no blend (height = 0.9 base + sum, roll = sum).
- `CameraGetTarget` is not the TPS camera position; the hero is used.

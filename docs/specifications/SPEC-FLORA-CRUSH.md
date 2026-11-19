# SPEC-FLORA-CRUSH: crushable flora

Implements REQ-FLORA-CRUSH.

## Data

- A script cannot list placed doodads, so the build writes a table:
  `scripts/app/data/flora_crush.galaxy` (generator `scripts/flora/crush.py`).
- Rows: x, y, z, kind, effect size. Sorted into 8 x 8 cell buckets on a 32 x 32 grid.
- Effect size = doodad scale x family spacing / 3.0.
- `src/` holds an empty table; `apply_flora` writes the real table and
  `check_flora` fails the build when it differs from the plan.

## Stomp config (`scripts/app/systems/stomp.galaxy`)

One row per unit type, set by call:
`gf_StompConfig(type, crush, crushReach, shake, stepHz, fx)` adds or
replaces a row (16 rows).

| Param | Effect |
| --- | --- |
| `crush`, `crushReach` | Doodad destruction within the reach (crush.galaxy). |
| `shake` | Camera shake gain; 0 = none. 1 = the Goliath's. Reach and size still follow the unit radius. |
| `stepHz` | Shake footfalls per second at full speed. |
| `fx` | Footfall sounds and effects: the script sets actor status `ScobaFootFx` 1 or 0 (quake.galaxy, re-sent every 0.5 s; a morph makes a new actor). |

- `gf_StompDefaults()` (map init): Goliath, Queen, `SCOBAVikingHeroAssault`
  (landed hero Viking, operator 2026-11-18): crush 2.5, shake 1, 1 Hz, fx on.
- A unit whose type leaves its row (a morph) loses its slot at once.
- `FOOTFALL_UNITS.thumps`: extra stock sounds layered on each footstep. The
  hero Viking: `Thor_Land`, own footstep +4 dB over the Goliath's, dust,
  splash and ripple x2 (its feet are ~1.8x the Goliath's).
- Landing impact (`scripts/app/systems/stomp_land.galaxy`):
  `gf_StompLandConfig(abil, size, hits, spread, shakeRadius, shakeGain,
  shakeLife, sound)`. On the ability's execute the script probes the height
  above the ground each tick; at touchdown (<= 0.05) it plays
  `gf_CrushImpactAt` at the unit and `hits` more within `spread`, a
  `gf_QuakeImpulse` and the sound. Default: `SCOBAHeroAssaultMode`, size
  1.5, 3 hits within 3, shake 3 / 3.0 / 2.5 s, `Thor_Land`. Smaller than a
  drop pod (scale 3, 6 hits within 8; operator: scale 4 too large).
- Gates: each actor event tests one `IsStatus`. The engine drops an event
  with two at map load (Alerts.txt: "Has event without a triggering
  message"); from 2026-11-18 15:36 that removed every dust and splash
  event of the Goliath, Queen and hero Viking. Dust and splash test
  `ScobaFootGround` (0 off, 1 dry, 2 wet); sound, thumps and ripples test
  `ScobaFootFx 1`. Both are set by `systems/quake.galaxy`.
- Guards: `validate_assets.check_actor_events` fails the build on an event
  with two `IsStatus` terms; `testkit/logs.py` fails a run on the alert.
- In-game proof: `ActorGetText(ActorFromScope(unit scope, name))` is
  empty without the actor and shows it while it lives (baseai flight
  group: dust on dry ground, splash in water, Viking and Goliath).
  `ActorFromScope` alone returns non-null for any name.
- Footfall data per model: `scripts/footfall/fx.py` `FOOTFALL_UNITS`
  (`unit` name key, `model` CModel id, `actors` CActorUnit ids, feet, scales,
  sound). Every effect `On` needs `IsStatus ScobaFootFx 1`;
  `check_footfall_fx` fails the build otherwise. The hero Viking row uses
  the Goliath's sound and scales; its feet are `Bone_Box30` / `Bone_Box42`
  (`Ref_Hardpoint 01/02`; the stock Left/Right points are on the arms).

## Runtime (`scripts/app/systems/crush.galaxy`)

- Every 0.25 s, each live unit of a stomp row with `crush` checks the 3 x 3
  buckets around it.
- A plant within the row's reach is removed with `libNtve_gf_RemoveDoodadsinRegion`
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
- `baseai flight` (stomp, `scripts/testkit/galaxy/baseai_land.galaxy`): the
  hero Viking walks through a plant. Flying: no slot, no fx send, no shake,
  plant stays. Landed, defaults: slot, fx sends, shake, plant removed.
  Landed, all off by `gf_StompConfig`: no fx send, no shake, plant stays.
  Lifted: slot freed. The look and sound are operator checks.

## Sounds

- Rock clip: random `PhysicsImpactRockHeavy` / `PhysicsImpactRockMassive`.
- First dust clip: random `PhysicsImpactDirtMedium` / `Heavy` / `Massive`.
- `SoundPlayAtPointForPlayer`, all players, at the plant.

## Ground shake (`scripts/app/systems/quake.galaxy`)

- Every 1/16 s per hero player: each live unit of a stomp row adds
  amp = shake x 0.04 x radius x speed share x (1 - d / (12 x radius)); d from
  the hero. The step rate is the row's `stepHz`.
- Stepped wave: a jolt per footfall (2 Hz at full speed), then x(-0.35) per
  tick, random 0.7-1.0 per step; roll random sign.
- Sum capped: height +-0.06, roll +-0.5 deg. Written with `CameraSetValue`,
  no blend (height = 0.9 base + sum, roll = sum).
- `CameraGetTarget` is not the TPS camera position; the hero is used.

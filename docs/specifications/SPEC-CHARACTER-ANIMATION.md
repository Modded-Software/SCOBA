# SPEC-CHARACTER-ANIMATION: Character Animation

**Date:** 2026-11-10
**Status:** Active implementation specification
**Requirements:** [REQ-CHARACTER-ANIMATION](../requirements/REQ-CHARACTER-ANIMATION.md)

## 1. Approach

> Use the existing animation system where possible. Extend it. Do not rewrite
> and destroy everything. Understand how it works before changing it.

Outside aim, the native unit baseline is authoritative for idle, walk, and turn.

Inside aim, one generated splitbody group is authoritative.
The group contains a frozen upper aim pose and the active lower-body direction.
The two STCs run concurrently inside that group.
The map does not play separate render brackets during aim.

This shape is required because StarCraft II does not render two independent
brackets at the same time on one model. Higher priority hides the lower bracket.
Lower priority hides the upper bracket. Concurrent STCs inside one group avoid
that choice.

## 2. Existing System

Galaxy:

- `core/animation.galaxy`: state IDs, hero profiles, constants, config tables.
- `systems/animation_fsm.galaxy`: splitbody aim selection, facing, and state.
- `systems/animation_aim.galaxy`: direction selection and aim config tables.
- `systems/aim.galaxy`: aim entry and exit.
- `systems/movement.galaxy`: native and aim movement.
- `core/globals.galaxy`: per-player animation state and aim group table.

Python:

- `scripts/character_anim_assets.py`: splitbody group generation and model output.
- `scripts/character_anim_m3.py`: M3 clone, freeze, reverse, and splitbody helpers.
- `scripts/animation_tokens.py`: allowed animation names.
- `scripts/validate-map.py`: build validation.

## 3. Baseline

Each hero actor keeps its native Stand and Walk baseline outside aim.

The generated models retain full-body Stand, Walk, Stand Left, and Stand Right clips.
Baseline state drives idle, locomotion, and turning outside aim.
Outside aim the map sends only lower-body track clips.
The upper bracket stays clear.

## 4. Splitbody Aim Groups

Aim uses one animation group per lower-body state and direction.
Each group contains two concurrent STCs.

| STC | Tracks | Priority | Motion |
| --- | --- | --- | --- |
| Upper | Upper bones | High | Frozen Attack start pose |
| Lower | Lower bones | Baseline | Directional locomotion |

The upper STC never advances while aim is held.
The lower STC keeps the legs, hips, and feet moving.

The eight lower directions are:

| Direction | Lower source |
| --- | --- |
| Forward | `Walk Leg` |
| Forward left | Lower Walk rotated 45 degrees |
| Left | Lower Walk rotated 65 degrees |
| Back left | Reversed lower Walk rotated -45 degrees |
| Back | Reversed `Walk Leg` |
| Back right | Reversed lower Walk rotated 45 degrees |
| Right | Lower Walk rotated -65 degrees |
| Forward right | Lower Walk rotated -45 degrees |

Movement heading is relative to camera yaw and uses native path-checked orders.
Backward heading uses reversed backpedal animation.
No direction may exceed 65 degrees of torso-to-lower twist.
A 180-degree lower turn with planted feet is invalid.

Generation steps:

1. Create an upper STC from the upper `Attack Ready` tracks.
2. Freeze every upper track to its first Attack start key.
3. Drop upper event, sound, and bounds tracks.
4. Create a lower STC from `Stand Leg` or `Walk Leg`.
5. Rotate the lower root bone by the direction yaw.
6. Use reversed lower tracks for backpedal directions.
7. Set `runsConcurrent` on both STCs.
8. Set the upper priority to 10 and the lower priority to 0.
9. Add the upper and lower STCs to one animation group.
10. Clone the lower sequence timing.
11. Set the group name from the lower state and direction.

The upper STC and lower STC names stay tied to the group name.

## 5. Runtime Aim State

`gv_animAimClip[profile][lower_state][direction]` stores the aim group name.

In `gf_AnimTick`:

1. Compute the lower-body state.
2. Compute movement heading relative to camera yaw.
3. Snap to one of eight directions.
4. Apply direction hysteresis.
5. On aim, play the selected splitbody group.
6. Keep hero facing on camera yaw.
7. Keep the lower direction on movement heading.
8. Outside aim, clear the aim group and restore baseline lower playback.
9. Keep the upper bracket clear outside aim.

`gf_AnimFullSet` records `gv_animFullState` and skips a repeated state write.
`gf_AnimFullClear` clears the aim group and resets the splitbody state.

Aim holds one fixed upper pose.
Camera pitch does not change the upper pose.
Aim exit clears the aim group and leaves the baseline visible.
Control mode change and hero reassignment also clear animation state.

Turning uses no upper overlay.

### 5A. Upper-Body Pitch

Aim pitch follows camera pitch in a later pitch sub-stage.
The first step is yaw and movement correctness.
Pitch must use upper-body joints: spine, shoulders, arms, and elbows.
A lower-back-only pivot is not acceptable as the final pitch system.
The upper yaw STC remains frozen for the yaw stage.
Pitch poses will be generated as upper-body pitch variants once the yaw and
movement system is proven.

## 6. Attack While Aiming

Aim attack animation is DEFERRED to a later stage.
This stage must not add an attack overlay or attack STC.
The lower body must not depend on an aim attack feature.

## 7. States and Config

Animation state is data, not transition code.

To add an aim lower state:

1. Add a state ID before the layer count.
2. Add the baseline lower clip row.
3. Add the eight directional aim group rows.
4. Keep existing transition code.
5. Run the normal build validation.

The lower states are none, idle, walk, and walk back.
The config tables are the only per-state and per-direction aim data.
Tosh and Kerrigan use generated splitbody aim groups.
Firebat uses its shipped model and baseline animation.

Actor clip references use comma-separated props.
Use existing animation names and the token validator.
Do not invent custom sequence names.

## 8. Facing and Motion

Native baseline owns idle, walk, and turn animation outside aim.
The engine turn path uses full-body `Stand Left` and `Stand Right`.
Non-aim facing changes use `UnitSetFacing`, a configured duration, and a yaw
deadband.
Non-aim A/D/S movement writes facing toward the movement direction.
RPG right and middle holds use the same turn path.
Native move orders remain in use outside aim.

Aim does not use the non-aim facing path.
Aim facing is camera yaw at all times, including while moving.
Aim movement uses one camera-relative travel heading per tick.
Per-key movement loops only set and clear input flags during aim.
One aim movement loop owns travel and issues at most one movement command per tick.
Aim MUST write camera facing every 0.05 seconds with
`c_ANIM_AIM_TURN_DURATION`.
Aim facing MUST be independent of movement orders.
Aim MUST NOT use `c_ANIM_TURN_DEADBAND`.
Aim MUST add `SCOBAAimNoTurn` (`SuppressTurning`) on entry and remove it on
exit.
Aim MUST NOT disable `Turnable` or zero turning rates.
Tosh and Kerrigan MUST use high turning rates so aim facing does not lag.
Aim movement MUST use native path-checked move orders.
Aim movement MUST NOT write facing. `gf_AnimFacingTick` is the only aim facing
writer.
W moves camera-forward, S moves camera-backward, A/D move camera-left/right.
Diagonals preserve both components.
S uses reversed backpedal lower animation and never turns the unit around.
A/D use lateral lower animation and never turn the unit.
The splitbody lower STC keeps the legs and feet moving in the travel direction.
Aim entry without a movement key issues Stop and restores the idle aim group.
Normal action movement uses the RPG move-and-turn path.

Baseline movement selects walk and restores idle.
Combat state is untouched.

## 9. Model Assets

Use the existing generator for Tosh and Kerrigan.
It reads source models, writes models into the built map, and updates model data.
It generates splitbody aim groups with one upper STC and one lower STC.
It generates eight lower directions, including reversed backpedal clips.
It keeps full-body Stand, Walk, Stand Left, and Stand Right clips.

Keep generated asset output out of hand edits.
Keep generation deterministic, idempotent, and reversible.
Firebat keeps its shipped model.

## 10. Validation and Tests

Build validation checks animation names, configured clips, and generated
tracks.

Tests use the existing test framework.
They record aim state, aim group name, direction index, lower frame IDs, and facing.
Model frame data is derived from M3 metrics and local timing.
It is not live actor time.
Live actor time is reported only when a real actor query worker exists.

Aim tests must prove:

1. Aim uses one splitbody group.
2. The upper pose does not loop.
3. Lower frame IDs advance in all eight directions.
4. Backward movement uses a reversed backpedal clip.
5. Torso-to-lower twist stays at or below 65 degrees in either strafe direction.
6. Aim hold records no upper overlay start event.
7. Real W/A/S/D and diagonal keys keep unit facing within tolerance of camera yaw.
8. S moves opposite camera forward and A/D move laterally without turning.
9. Aim release restores the baseline.

## 11. Change Rule

Extend the current system. Do not replace it with a parallel animation path.
Do not duplicate baseline, state, config, bracket, movement, or asset logic.
When the existing system lacks a capability, extend the closest existing
module and keep its data-driven shape.
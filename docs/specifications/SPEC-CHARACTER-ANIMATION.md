# SPEC-CHARACTER-ANIMATION: Character Animation

**Date:** 2026-11-10
**Status:** Active implementation specification
**Requirements:** [REQ-CHARACTER-ANIMATION](../requirements/REQ-CHARACTER-ANIMATION.md)

## 1. Approach

> Use the existing animation system where possible. Extend it. Do not rewrite
> and destroy everything. Understand how it works before changing it.

Outside aim, the native unit baseline is authoritative for idle, walk, and turn.

Inside aim, two animation brackets run concurrently on the same model:

- `SCOBAUp` plays one shared upper aim clip with dense keyframe-driven lower-back pitch.
- `SCOBALo` plays the active lower-body direction group.

These are animation brackets on one model, not separate render brackets.
The map does not create a second model or a separate render actor during aim.

The upper clip contains the frozen aim pose plus a lower-back pitch sweep.
Non-spine upper tracks stay held at one key across the clip duration.
The lower group contains one lower STC for the active state and direction.

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

`gv_animAimClip[profile][lower_state][direction]` stores the lower group name.

In `gf_AnimTick`:

1. Compute the lower-body state.
2. Compute movement heading relative to camera yaw.
3. Snap to one of eight directions.
4. Apply direction hysteresis.
5. On aim, play the shared upper pitch clip on `SCOBAUp`.
6. On aim, play the selected lower-only group on `SCOBALo`.
7. Apply camera pitch time to the SCOBAUp animation reference.
8. Keep hero facing on camera yaw.
9. Keep the lower direction on movement heading.
10. Outside aim, clear both aim brackets and restore baseline playback.

`gf_AnimFullSet` records `gv_animFullState` and skips a repeated state write.
`gf_AnimFullClear` clears the lower aim group and resets the splitbody state.
`gf_AnimAimUpperClear` clears the upper aim clip and resets pitch time.

Aim holds one upper clip while camera pitch changes its playback time.
Aim exit clears both aim brackets and leaves the baseline visible.
Control mode change and hero reassignment also clear animation state.

Turning uses no upper turn overlay.

### 5A. Upper-Body Pitch

Aim pitch follows camera pitch across the full camera range: 80 degrees down and 60 degrees up.
The torso clip sweeps from -95 to 50 degrees with fixed rest -13.
The whole upper body pivots at one lower-back spine bone, including the head.
A single lower-back pivot keeps the head, neck, and shoulders connected.
The pivot does not rotate the lower body or model root.
Shoulder, arm, and elbow correction is deferred until visual validation.

Asset generation creates one shared upper pitch clip per hero:

- the Attack upper pose sampled at 350 ms is the base pose, where the gun is near horizontal.
- the lower-back rotation track sweeps from 95 degrees down to 50 degrees up.
- keyframes are densely spaced so nearest-keyframe selection looks continuous.
- all other upper position, rotation, and scale tracks stay held at one key
  across the clip duration.
- the clip duration is fixed by `c_ANIM_AIM_PITCH_TIME`.
- the clip is shared across all eight lower directions.

Runtime pitch:

1. Read CameraGetPitch(player) in degrees.
2. Normalize wrapped pitch: if above 180 degrees, subtract 360.
3. Subtract camera pitch from rest pitch and clamp to the range `-95..50`.
   Camera up produces a positive value and a higher `SCOBAUp` time. Camera down
   produces a negative value and a lower `SCOBAUp` time.
4. Map clamped pitch to the nearest dense keyframe time.
5. Unpause `SCOBAUp` on the main actor.
6. Send `AnimSetTime SCOBAUp` with the exact target time.
7. Pause `SCOBAUp` after the frame is applied.
8. Do not pause the upper bracket before the first frame is applied.
9. The rest pitch stays fixed at `c_ANIM_AIM_PITCH_REST`; aim entry never
   captures the current camera pitch as rest.
10. Drive the tick from `TriggerAddEventCameraMove` and a periodic timer.
11. Send `AnimBlendTimeRemove` on aim exit so engine blend defaults return.
12. Set model actor `AnimBlendTime` to 0 for Tosh and Kerrigan.
13. Unpause `SCOBAUp` and clear it on aim exit.
14. Keep the lower `SCOBALo` bracket playing its Stand or Walk animation while
    the upper body is held. Aim idle uses `Attack,Stand`; aim in-place turn
    uses `Attack,Stand,Left` or `Attack,Stand,Right`; aim walk uses
    `Attack,Walk,<direction>`.

Pitch entry must reset the upper pose and write the current camera pitch
before the first frame. Do not blend or add to the prior idle upper pose.

Pitch uses local bone rotation. The local pitch axis and sign are per-hero
configuration values validated in game.

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
It generates one shared upper pitch clip per hero.
It generates lower-only groups for idle and eight movement directions,
including reversed backpedal clips.
Spine pitch bones, weights, axis, sign, and sample count are per-hero
configuration values.
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

1. Aim uses `SCOBAUp` for the shared upper pitch clip.
2. Aim uses `SCOBALo` for lower state and direction.
3. The upper pose does not loop.
4. Lower frame IDs advance in all eight directions.
5. Backward movement uses a reversed backpedal clip.
6. Torso-to-lower twist stays at or below 65 degrees in either strafe direction.
7. Aim hold records one upper pitch start event and no repeated upper start events.
8. Real W/A/S/D and diagonal keys keep unit facing within tolerance of camera yaw.
9. S moves opposite camera forward and A/D move laterally without turning.
10. Aim release restores the baseline.
11. Camera pitch up and down changes upper clip time and the spine pose.
12. Pitch reaches 80 degrees down and 60 degrees up.
13. Pitch changes no lower frame and no model root rotation.

## 11. Change Rule

Extend the current system. Do not replace it with a parallel animation path.
Do not duplicate baseline, state, config, bracket, movement, or asset logic.
When the existing system lacks a capability, extend the closest existing
module and keep its data-driven shape.

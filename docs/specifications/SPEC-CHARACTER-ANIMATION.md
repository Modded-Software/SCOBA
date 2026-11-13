# SPEC-CHARACTER-ANIMATION: Character Animation

**Date:** 2026-11-10
**Status:** Active implementation specification
**Migration:** Dedicated gameplay actors and native lower-body playback are implemented.
**Requirements:** [REQ-CHARACTER-ANIMATION](../requirements/REQ-CHARACTER-ANIMATION.md)

## 1. Approach

> Use the existing animation system where possible. Extend it. Do not rewrite
> and destroy everything. Understand how it works before changing it.

Outside aim, the native unit baseline is authoritative for idle, walk, and turn.
RPG attack adds one root-excluded upper attack instance and one target-pitch
instance. It never writes the lower body.

Inside aim, two animation instances run concurrently on the same model:

- `SCOBAUp` plays one shared upper aim clip with dense keyframe-driven lower-back pitch.
- `SCOBALo` plays the active lower-body direction group.

These are `AnimPlay` animation instance names on one model, not bracket names.
They are not separate render brackets, models, or actors.

The upper clip contains the frozen aim pose plus a lower-back pitch sweep.
Non-spine upper tracks stay held at one key across the clip duration.
The lower group contains one lower STC for the active state and direction.

## 2. Existing System

Galaxy:

- `core/animation.galaxy`: state IDs, hero profiles, constants, config tables.
- `systems/animation_fsm.galaxy`: splitbody aim selection, non-aim attack overlay, facing, and state.
- `systems/animation_aim.galaxy`: direction selection and aim config tables.
- `systems/aim.galaxy`: aim entry and exit.
- `systems/combat_cooldown.galaxy`: starts the non-aim attack overlay on `UnitStartedAttack2`.
- `systems/movement.galaxy`: native and aim movement.
- `core/globals.galaxy`: per-player animation, attack, and aim group table.
- `Base.SC2Data/GameData/ActorData.xml`: clean ToshSCOBAUnit and KerriganSCOBAUnit actors.
- `Base.SC2Data/GameData/UnitData.xml`: clean ToshSCOBA and KerriganSCOBA unit types.

Python:

- `scripts/character_anim_assets.py`: splitbody group generation and model output.
- `scripts/character_anim_m3.py`: M3 clone, freeze, reverse, and splitbody helpers.
- `scripts/animation_tokens.py`: allowed animation names.
- `scripts/validate-map.py`: build validation.

## 3. Baseline

Each hero actor keeps its native Stand and Walk baseline outside aim.

The generated models retain full-body Stand, Walk, Stand Left, Stand Right, Stand Work, Attack, and Spell clips.
Baseline state drives idle, locomotion, and turning outside aim.
Outside aim the map does not send any lower-body animation.
Gameplay uses clean unit types `ToshSCOBA` and `KerriganSCOBA`.
Clean actors `ToshSCOBAUnit` and `KerriganSCOBAUnit` use `unitName` equal to the clean unit type.
Clean actors parent `GenericUnitBase` and define no native attack events.
Native `Tosh` and `QueenOfBlades` unit types and actors stay untouched.
The upper attack overlay is the only non-aim animation the map writes.

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

1. While aim is active, compute the lower-body state.
2. Compute movement heading relative to camera yaw.
3. Snap to one of eight directions.
4. Apply direction hysteresis.
5. Play the shared upper pitch clip on `SCOBAUp`.
6. Play the selected lower-only group on `SCOBALo`.
7. Apply camera pitch time to the SCOBAUp animation reference.
8. Keep hero facing on camera yaw.
9. Keep the lower direction on movement heading.
10. Outside aim, clear both aim animation instances and restore native playback.
11. Outside aim, do not compute or write a lower-body animation state.

`gf_AnimFullSet` records `gv_animFullState` and skips a repeated state write.
`gf_AnimFullClear` clears the lower aim group and resets the splitbody state.
`gf_AnimAimUpperClear` clears the upper aim clip and resets pitch time.

Aim holds one upper clip while camera pitch changes its playback time.
Aim exit clears both aim animation instances and leaves the baseline visible.
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

- the upper-only `Attack Arm Alternate` clip sampled at 350 ms is the base pose, where the gun is near horizontal.
- the pitch source MUST be upper-only; a full-body source copies lower tracks into every `SCOBAUp` pitch clip and freezes the legs.
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
8. Do not pause the upper animation instance before the first frame is applied.
9. The rest pitch stays fixed at `c_ANIM_AIM_PITCH_REST`; aim entry never
   captures the current camera pitch as rest.
10. Drive the tick from `TriggerAddEventCameraMove` and a periodic timer.
11. Send `AnimBlendTimeRemove` on aim exit so engine blend defaults return.
12. Set model actor `AnimBlendTime` to 0 for Tosh and Kerrigan.
13. Unpause `SCOBAUp` and clear it on aim exit.
14. Keep the lower `SCOBALo` animation instance playing its Stand or Walk animation while
    the upper body is held. Aim idle uses `Attack,Stand`; aim in-place turn
    uses `Attack,Stand,Left` or `Attack,Stand,Right`; aim walk uses
    `Attack,Walk,<direction>`.

Pitch entry must reset the upper pose and write the current camera pitch
before the first frame. Do not blend or add to the prior idle upper pose.

Pitch uses local bone rotation. The local pitch axis and sign are per-hero
configuration values validated in game.

## 5B. Non-Aim Attack Overlay

Non-aim attack uses two upper-body instances:

- `SCOBAAimAtk` plays the root-excluded attack clip.
- `SCOBAUp` holds the target pitch clip.

It never writes `SCOBALo`, native lower animation, movement orders, facing,
camera, or control state.
The overlay must not rely on native actor attack events.
Clean actors define no native attack events.

Force kickback:

- The attack clips contain a 0.5 s weapon-shoulder kickback.
- It starts at the firing frame, flexes the weapon shoulder back rapidly, then returns.
- Tosh uses `BoneShoulderR`; Kerrigan uses `Box04`.
- It is baked into `Attack Arm Alternate 01` and `Spell Arm Alternate 01`.
- It must not write the spine, pitch root, lower body, or model root.

Attack state:

| State | Clip | Duration |
| --- | --- | --- |
| `c_ANIM_UPPER_ATTACK` | `Attack Arm Alternate 01` | Native Attack clip |
| `c_ANIM_UPPER_ATTACK_SPELL` | `Spell Arm Alternate 01` | Native Spell clip |

`UnitStartedAttack2` starts the overlay:

1. Ignore the event while aim is active.
2. Read `EventUnitGetWeapon()`.
3. Read `EventUnitTarget()`; use `gv_unitTarget[player]` when the event target is invalid.
4. Tosh uses `Attack Arm Alternate 01`.
5. Kerrigan `RazorTalons` uses `Attack Arm Alternate 01`.
6. Kerrigan `QueenOfBladesPsiBlast` uses `Spell Arm Alternate 01`.
7. Start the attack on `SCOBAAimAtk` with `FullMatch | NonLooping`.
8. Play at `c_ANIM_ATTACK_TIME_SCALE` 2.0 with `c_animTimeVariantAsTimeScale`.
9. Send `AnimSetTime SCOBAAimAtk c_ANIM_ATTACK_START_TIME 0` so playback starts at the firing/recoil frame.
10. Start `SCOBAUp` target pitch from the hero-to-target vector.
11. Clear both instances on attack end or weapon stop.
12. A fixed timer may exist only as a safety cap.

Target pitch:

1. `dz = UnitGetHeight(target) - UnitGetHeight(hero)`.
2. `dist = DistanceBetweenPoints(UnitGetPosition(hero), UnitGetPosition(target))`.
3. `angle = ATan2(dz, dist)`.
4. `pitch = c_ANIM_AIM_PITCH_REST + angle`.
5. Clamp to `c_ANIM_AIM_PITCH_MIN..c_ANIM_AIM_PITCH_MAX`.
6. Map pitch to the nearest `Ready Alternate NN` step.
7. Play `SCOBAUp` with the shared pitch clip.
8. Refresh the step on every animation tick while the attack is active.
9. Clear `SCOBAUp` when the attack ends.

The target height is required so air and elevated targets pitch the torso up
and low targets pitch it down.
Do not use only the target ground point.

Attack-mode pitch is camera-driven.
RPG pitch is target-driven.
Both use the same `SCOBAUp` pitch clips and the same clamp range.

`gv_animAttackState` stores the active attack state.
`gv_animAttackUntil` stores the safety-cap end time.
`gv_animTargetPitchStep` stores the active target pitch key.

`gf_AnimTick` outside aim:

1. Do not select or play any lower-body animation.
2. While attacking, refresh the target pitch on `SCOBAUp`.
3. Select the root-excluded attack state on `SCOBAAimAtk`.
4. Otherwise clear both upper instances.
5. Clear the upper state when the attack ends.

The upper attack state is one-shot. It must not use `PlayForever`.
The attack state is reset by `gf_AnimReset`.

### Rejected actor design

The previous designs fought the native attack events:

| Attempt | Result |
| --- | --- |
| `<On index="N" removed="1"/>` on Tosh/QueenOfBlades | Unverified. Native attack events still ran. |
| Upper-only replacement of the model `Attack` group | Native attack froze the lower body at its last frame. |
| Runtime `AnimBracketStop Attack` with or without timers | Not deterministic. Native state outlived the map state. |
| Dedicated actors using the native `unitName` | SC2 creates both actors and renders the model twice. |
| Empty native tracks or renamed native tokens | Either froze the lower body or dropped all animations. |
| Custom non-aim lower on `SCOBALo` | Redundant with native locomotion and lost to the native bracket. |

Do not restore any of these patterns.

### Clean actor setup

Tosh:

- unit type `ToshSCOBA`, parent `Tosh`;
- actor ID `ToshSCOBAUnit`;
- `unitName="ToshSCOBA"`;
- `Model="ToshSCOBA"`;
- `Scale=0.75`;
- no native attack, work, or ready animation events.

Kerrigan:

- unit type `KerriganSCOBA`, parent `Kerrigan`;
- actor ID `KerriganSCOBAUnit`;
- `unitName="KerriganSCOBA"`;
- `Model="KerriganSCOBA"`;
- `Scale=0.75`;
- no native attack, work, or ready animation events.

Map init replaces the placed native Tosh and Kerrigan with these unit types at the same position and facing.
Native `Tosh` and `QueenOfBlades` unit types and actors stay untouched.
Do not add stop timers, periodic native stop messages, empty native tracks, or renamed native tokens.

### Native lower body

Non-aim lower animation is native Stand, Walk, and turn.
The map must not select non-aim lower clips.
Do not add displacement checks, hold timers, move-intent state, or custom lower playback outside aim.

Native movement keeps the Walk clip during attack-chase orders.
Attacking while stationary keeps the Stand clip advancing.

## 6. Attack While Aiming

Aim attack is a separate upper overlay on the `SCOBAAimAtk` animation instance.
`SCOBAUp` remains the sole owner of the aim spine pitch.

The aim attack clips omit the pitch root tracks:

- Tosh: `BoneSpine01`.
- Kerrigan: `Bone07`.

The overlay animates the remaining upper bones relative to the aim spine.
It must not pause, clear, restart, or replace `SCOBAUp`.
It must not touch `SCOBALo`.

The overlay clips are:

| State | Clip | Priority |
| --- | --- | --- |
| `c_ANIM_UPPER_ATTACK_AIM` | `Attack Arm Alternate 01` | 12 |
| `c_ANIM_UPPER_ATTACK_SPELL_AIM` | `Spell Arm Alternate 01` | 12 |

`gf_AnimAimAttackStart`:

1. Select the aim attack state from the started weapon.
2. Play `gv_animUpperClip[profile][state]` on `SCOBAAimAtk`.
3. Use `FullMatch | NonLooping`.
4. Blend with `c_ANIM_AIM_ATTACK_BLEND`.
5. Play at `c_ANIM_ATTACK_TIME_SCALE` 2.0 with
   `c_animTimeVariantAsTimeScale`.
6. Send `AnimSetTime SCOBAAimAtk c_ANIM_ATTACK_START_TIME 0`.
7. Set `gv_animAimAttackUntil`.
8. Leave the upper state, pitch time, and pitch step unchanged.

`gf_AnimTick` keeps calling `gf_AnimUpperSet` and `gf_AnimAimPitchTick` during
the aim attack.
Aim pitch remains live during the attack.

`gf_AnimAimPitchTick` does not return early for an aim attack.

`gf_AnimAttackStart` sends the aim branch to `gf_AnimAimAttackStart`.
`gf_AnimReset`, `gf_AimEnd`, and hero switch clear `SCOBAAimAtk`.

The aim attack must preserve the aim yaw and pitch.
It must not snap the torso to the native forward pose.

## 7. States and Config

Animation state is data, not transition code.

To add an aim lower state:

1. Add a state ID before the layer count.
2. Add the baseline lower clip row.
3. Add the eight directional aim group rows.
4. Keep existing transition code.
5. Run the normal build validation.

The lower states are none, idle, walk, and walk back.
The upper states include none, aim down, aim mid, aim up, attack, and attack spell.
The config tables are the only per-state and per-direction aim data.
Tosh and Kerrigan use generated splitbody aim groups.
Firebat uses its shipped model and baseline animation.

Actor clip references use comma-separated props.
Use existing animation names and the token validator.
Generated root-excluded attack clips use unique names `Attack Arm Alternate 01` and `Spell Arm Alternate 01`.
Pitch groups use `Ready Alternate NN`.
Clean actors have no native attack events.

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
One aim movement loop owns travel.
Aim movement writes camera facing immediately before it issues a move order.
`gf_AnimFacingTick` writes aim facing when no movement key is held.
Aim MUST NOT use `c_ANIM_TURN_DEADBAND`.
Aim MUST add `SCOBAAimNoTurn` (`SuppressTurning`) on entry and remove it on
exit.
Aim MUST NOT disable `Turnable` or zero turning rates.
Tosh and Kerrigan MUST use high turning rates so aim facing does not lag.
Aim movement MUST use native path-checked move orders.
W moves camera-forward, S moves camera-backward, A/D move camera-left/right.
Diagonals preserve both components.
S uses reversed backpedal lower animation and never turns the unit around.
A/D use lateral lower animation and never turn the unit.
The splitbody lower STC keeps the legs and feet moving in the travel direction.
Aim entry without a movement key issues Stop and restores the idle aim group.
Normal action movement uses the RPG move-and-turn path.

Baseline movement selects walk and restores idle.
Walk selection uses movement keys, move orders, and actual displacement.
Actual displacement keeps attack-chase orders on the Walk lower clip.
Combat state is untouched.
Non-aim attack changes only the upper animation layer.

## 9. Model Assets

Use the existing generator for Tosh and Kerrigan.
It reads source models, writes models into the built map, and updates model data.
It keeps native Stand, Walk, Stand Left, Stand Right, and Stand Work groups intact.
It adds upper-only `Attack Arm Alternate` and `Spell Arm Alternate` clips.
Upper attack clips keep only the weapon shoulder chains and the head chain.
Tosh keeps `BoneShoulderL`, `BoneShoulderR`, and `BoneHead` descendants.
Kerrigan keeps `Box04`, `Box05`, and `Bone29` descendants.
Upper attack clips drop the spine, waist, and back tracks.
Upper attack clips set `runsConcurrent=1` and priority 10 so they layer over native lower locomotion.
It adds root-excluded `Attack Arm Alternate 01` and `Spell Arm Alternate 01` clips at priority 12.
The aim attack clips remove every track for the hero pitch root bone.
Actor messages use the unique clip names.
Token form uses commas only where needed. Do not use spaces in actor messages.
It generates one shared upper pitch clip per hero.
It generates lower-only groups for idle and eight movement directions,
including reversed backpedal clips.
Spine pitch bones, weights, axis, sign, and sample count are per-hero
configuration values.

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

Non-aim attack tests must prove:

1. Tosh and Kerrigan attacks keep native lower frame IDs advancing.
2. Attack-chase movement keeps the native Walk lower clip.
3. Repeated attacks restart the upper attack clip.
4. Kerrigan `RazorTalons` uses `Attack Arm Alternate` and `QueenOfBladesPsiBlast` uses `Spell Arm Alternate`.
5. Actor logs show no duplicate actor for Tosh or Kerrigan.
6. RPG and Action attacks use the same overlay.
7. Aim never shows the non-aim attack overlay.
8. Attack stops when the clip completes or the weapon stops.
9. The map sends no non-aim lower animation on `SCOBALo`.
10. The map never sends `SCOBAUp` or `SCOBALo` to an `AnimBracket*` message.

Asset and actor tests must prove:

1. Generated models keep Stand, Walk, Stand Left, Stand Right, and Stand Work groups and add `Attack Arm Alternate`/`Spell Arm Alternate`.
2. Generated models add distinct upper-only Attack and Spell clips.
3. Every configured clip name exists in the generated M3.
4. `ToshSCOBAUnit` and `KerriganSCOBAUnit` use the clean unit names.
5. Clean actors define no native attack events.
6. `ToshSCOBA` and `KerriganSCOBA` unit types parent the native heroes.
7. Runtime logs contain no invalid actor message for `SCOBAUp` or `SCOBALo`.

## 11. Change Rule

Extend the current system. Do not replace it with a parallel animation path.
Do not duplicate baseline, state, config, bracket, movement, or asset logic.
When the existing system lacks a capability, extend the closest existing
module and keep its data-driven shape.

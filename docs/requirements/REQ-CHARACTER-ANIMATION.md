# REQ-CHARACTER-ANIMATION: Character Animation

**Date:** 2026-11-10
**Status:** Active binding requirement

## 1. Scope

This contract binds hero animation:

- native baseline idle, walk, and turn;
- splitbody aim animation with eight lower-body directions;
- frozen upper aim pose with camera yaw and pitch;
- deferred aim attack animation;
- camera yaw facing and action-mode turning;
- generated hero models.

Controls live in [REQ-MOUSE-CONTROLS](REQ-MOUSE-CONTROLS.md).
Combat state lives in [REQ-COMBAT-CONTROLS](REQ-COMBAT-CONTROLS.md).
Implementation lives in
[SPEC-CHARACTER-ANIMATION](../specifications/SPEC-CHARACTER-ANIMATION.md).

## 2. Requirements

| ID | Requirement |
| --- | --- |
| R-ANIM-1 | Heroes MUST keep full-body baseline Stand and Walk animations outside aim. |
| R-ANIM-2 | Non-aim movement and turning MUST use the native baseline animation state. |
| R-ANIM-3 | Aim MUST show the weapon-ready upper pose. |
| R-ANIM-4 | Aim MUST keep the lower body Stand or Walk animating at the same time as the upper pose. |
| R-ANIM-5 | Aim MUST play one animation group per lower-body state and direction. |
| R-ANIM-6 | Aim MUST NOT play separate render brackets at the same time. |
| R-ANIM-7 | Aim groups MUST contain two concurrent STCs: frozen upper aim tracks and lower locomotion tracks. |
| R-ANIM-8 | Upper aim tracks MUST be clamped to one key at time zero. |
| R-ANIM-9 | Upper aim tracks MUST NOT loop an attack swing while aim is held. |
| R-ANIM-10 | Upper event tracks MUST be omitted from aim hold clips. |
| R-ANIM-11 | Aim MUST select the aim group from the active lower-body state and movement direction. |
| R-ANIM-12 | Aim hold MUST produce no upper overlay start events. |
| R-ANIM-13 | Aim exit MUST clear the aim group and restore baseline animation. |
| R-ANIM-14 | Aim MUST take hero facing from camera yaw. |
| R-ANIM-15 | Aim facing MUST work while stationary and moving. |
| R-ANIM-16 | Aim movement MUST use a camera-relative travel heading and path-checked native move orders independent of unit facing. |
| R-ANIM-17 | Non-aim movement MUST keep native move orders. |
| R-ANIM-18 | Aim entry, control mode change, and hero reassignment MUST clear animation state. |
| R-ANIM-19 | Tosh and Kerrigan MUST use generated models with baseline clips and splitbody aim groups. |
| R-ANIM-20 | Firebat MUST use its shipped model and baseline animation. |
| R-ANIM-21 | Generated assets MUST be deterministic, idempotent, and reversible. |
| R-ANIM-22 | Animation changes MUST leave combat state unchanged. |
| R-ANIM-23 | Tests MUST keep model-derived frame data separate from live actor time. |
| R-ANIM-24 | Build checks MUST reject unknown or missing animation names. |
| R-ANIM-25 | Non-aim facing changes MUST use engine turn duration, not per-tick angle stepping. |
| R-ANIM-26 | Turning MUST use the full-body baseline Stand Left and Stand Right clips. |
| R-ANIM-27 | The map MUST NOT create an upper-body turn overlay. |
| R-ANIM-28 | The frozen upper pose MUST come from the Attack start keyframe. |
| R-ANIM-29 | Aim attack animation is DEFERRED to a later stage. |
| R-ANIM-30 | Aim clip changes MUST be idempotent for an unchanged lower-body state. |
| R-ANIM-31 | Non-aim A/D/S movement MUST turn the hero toward the movement direction and use the Walk lower clip. |
| R-ANIM-32 | Aim MUST use eight lower-body movement directions. |
| R-ANIM-33 | Aim lower-body direction MUST come from the camera-relative movement vector. |
| R-ANIM-34 | Aim unit facing and upper body MUST stay locked to camera yaw while moving. |
| R-ANIM-35 | Aim torso-to-lower twist MUST NOT exceed 65 degrees in either direction while strafing. |
| R-ANIM-36 | Backward aim movement MUST use reversed backpedal animations. |
| R-ANIM-37 | Aim MUST NOT turn the unit 180 degrees toward travel or show a planted-feet torso twist. |
| R-ANIM-38 | Aim MUST NOT use a turn deadband. Camera facing MUST be applied every animation tick, independent of movement orders. |
| R-ANIM-39 | Aim upper-body pitch MUST follow camera pitch. |
| R-ANIM-40 | Aim upper-body pitch MUST use spine, shoulder, arm, and elbow pose changes, not only a lower-back pivot. |
| R-ANIM-41 | Aim S MUST backpedal, A/D MUST strafe, and diagonals MUST preserve both camera-relative components. |
| R-ANIM-42 | Aim per-key movement loops MUST NOT issue separate move orders; one aim movement loop owns travel. |
| R-ANIM-43 | Aim MUST use `SCOBAAimNoTurn` with `SuppressTurning` and remove it on exit. It MUST NOT disable `Turnable` or zero turning rates. |
| R-ANIM-44 | `gf_AnimFacingTick` MUST be the only aim facing writer. Aim movement MUST NOT write facing. |
| R-ANIM-45 | Tosh and Kerrigan MUST use high turning rates so aim facing does not lag camera yaw. |

## 3. Acceptance criteria

| ID | Check |
| --- | --- |
| AC-ANIM-1 | Idle and walk play one continuous baseline loop outside aim. |
| AC-ANIM-2 | Aim shows the upper pose while lower frame IDs advance. |
| AC-ANIM-3 | Aim holds one fixed upper pose without an attack loop. |
| AC-ANIM-4 | Aim facing follows camera yaw at rest and in motion. |
| AC-ANIM-5 | Aim release clears the aim group and leaves combat state unchanged. |
| AC-ANIM-6 | Tosh and Kerrigan models keep full Stand and Walk clips and splitbody aim groups. |
| AC-ANIM-7 | Firebat uses its shipped model and baseline animation. |
| AC-ANIM-8 | Two asset builds produce identical output. |
| AC-ANIM-9 | Aim hold and all eight aim movement directions keep the lower body animating. |
| AC-ANIM-10 | Turning uses native full-body turn clips and creates no upper turn events. |
| AC-ANIM-11 | Aim hold records no upper overlay start event. |
| AC-ANIM-12 | Splitbody aim groups contain one upper key per upper track. |
| AC-ANIM-13 | Aim attack animation is not implemented in this stage. |
| AC-ANIM-14 | Non-aim A/D/S turns the hero toward movement and keeps Walk frame IDs advancing. |
| AC-ANIM-15 | Backward aim movement uses a reversed backpedal clip. |
| AC-ANIM-16 | Aim twist stays at or below 65 degrees in either strafe direction. |
| AC-ANIM-17 | Aim lower clip changes across all eight directions. |
| AC-ANIM-18 | Aim W/A/S/D and diagonal combinations keep unit facing within tolerance of camera yaw. |
| AC-ANIM-19 | Aim S moves opposite camera forward and uses the reversed backpedal lower clip. |
| AC-ANIM-20 | Aim upper-body pitch follows camera pitch. |
| AC-ANIM-21 | Aim upper-body pitch changes upper-body joints, not only the lower back. |
| AC-ANIM-22 | Aim facing follows camera rotation without perceptible lag. |
| AC-ANIM-23 | Aim movement does not write facing and does not change `Turnable` or turning rates. |

## 4. Out of scope

- Facial, material, and weapon animation.
- Procedural per-bone runtime control.
- Network animation prediction.

## 5. References

- StarCraft II baseline animations and split-body track sets.
- Existing animation code and asset pipeline described in
  [SPEC-CHARACTER-ANIMATION](../specifications/SPEC-CHARACTER-ANIMATION.md).
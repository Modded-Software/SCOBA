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
| R-ANIM-8 | Upper aim tracks MUST be held at one key across the clip duration. |
| R-ANIM-9 | Upper aim tracks MUST NOT loop an attack swing while aim is held. |
| R-ANIM-10 | Upper event tracks MUST be omitted from aim hold clips. |
| R-ANIM-11 | Aim MUST select the aim group from the active lower-body state and movement direction. |
| R-ANIM-12 | Aim hold MUST produce one upper pitch start event and no repeated upper start events after entry. |
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
| R-ANIM-28 | The frozen upper pose MUST come from the Attack aim frame at 350 ms, where the gun is near horizontal. |
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
| R-ANIM-39 | Aim upper-body pitch MUST follow camera pitch across the full camera range: 80 degrees down and 60 degrees up. The torso clip sweeps -95..50 degrees with fixed rest -13. |
| R-ANIM-40 | Aim upper-body pitch MUST pivot the whole upper body around one lower-back spine bone, including the head, shoulders, and arms. It MUST NOT rotate the lower body or model root. |
| R-ANIM-41 | Aim S MUST backpedal, A/D MUST strafe, and diagonals MUST preserve both camera-relative components. |
| R-ANIM-42 | Aim per-key movement loops MUST NOT issue separate move orders; one aim movement loop owns travel. |
| R-ANIM-43 | Aim MUST use `SCOBAAimNoTurn` with `SuppressTurning` and remove it on exit. It MUST NOT disable `Turnable` or zero turning rates. |
| R-ANIM-44 | `gf_AnimFacingTick` MUST be the only aim facing writer. Aim movement MUST NOT write facing. |
| R-ANIM-45 | Tosh and Kerrigan MUST use high turning rates so aim facing does not lag camera yaw. |
| R-ANIM-46 | Aim MUST use `SCOBAUp` for the upper aim pitch clip and `SCOBALo` for lower locomotion. |
| R-ANIM-47 | Aim pitch MUST select the nearest dense `SCOBAUp` keyframe from `CameraGetPitch` and send `AnimSetTime SCOBAUp <time> 0` to the unit main actor. Camera up MUST map to a higher `SCOBAUp` time. Camera down MUST map to a lower `SCOBAUp` time. |
| R-ANIM-48 | Aim pitch MUST use one shared upper clip per hero, not one pitched upper clip per direction. |
| R-ANIM-49 | Non-spine upper tracks MUST be held at one key across the clip duration while pitch time changes. |
| R-ANIM-50 | Aim pitch MUST NOT use actor root or whole-model rotation. |
| R-ANIM-51 | Galaxy angles are degrees. `CameraGetPitch` MAY return a wrapped value above 180 degrees; aim pitch MUST normalize it to the signed range before use. |
| R-ANIM-52 | Aim pitch MUST use the animation reference name `SCOBAUp`, not the clip props name `Ready`, for `AnimSetTime`. |
| R-ANIM-53a | Aim pitch MUST pin the `SCOBAUp` group by sending `AnimSetTime` on every aim tick. It MUST NOT use `AnimSetPaused` and MUST NOT freeze `SCOBALo`. |
| R-ANIM-53 | Aim pitch MUST use densely spaced keyframes and map camera pitch to the nearest target time. |
| R-ANIM-53b | Aim pitch MUST send the exact target time on every aim tick. It MUST NOT advance time between sends. |
| R-ANIM-54 | Aim pitch MUST send the exact target time. It MUST NOT add elapsed time. |
| R-ANIM-55 | Aim pitch MUST reassert the target time every aim tick, even when the target is unchanged, so the upper pose does not drift. |
| R-ANIM-56 | Aim pitch MUST update on camera move events, not only on a periodic timer. |
| R-ANIM-57 | Tosh and Kerrigan `CActorModel` entries MUST set `AnimBlendTime` to 0 so `AnimSetTime` changes pose immediately. |
| R-ANIM-58 | Aim entry MUST apply the frozen upper pose at the current camera pitch without blending from the prior idle pose. |
| R-ANIM-59 | Aim pitch rest MUST stay fixed at `c_ANIM_AIM_PITCH_REST`. Aim entry MUST NOT capture the current camera pitch as rest. |
| R-ANIM-60 | Aim exit MUST send `AnimBlendTimeRemove`, unpause `SCOBAUp`, and clear pitch state. |
| R-ANIM-61 | Aim lower body MUST keep its idle, in-place turn, or walk animation playing while the upper body is held. Aim idle MUST use `Attack,Stand`; aim in-place turn MUST use `Attack,Stand,Left` or `Attack,Stand,Right`; aim walk MUST use `Attack,Walk,<direction>`. |


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
| AC-ANIM-11 | Aim hold records one upper pitch start event and no repeated upper start events. |
| AC-ANIM-12 | Splitbody aim groups contain one upper key per upper track. |
| AC-ANIM-13 | Aim attack animation is not implemented in this stage. |
| AC-ANIM-14 | Non-aim A/D/S turns the hero toward movement and keeps Walk frame IDs advancing. |
| AC-ANIM-15 | Backward aim movement uses a reversed backpedal clip. |
| AC-ANIM-16 | Aim twist stays at or below 65 degrees in either strafe direction. |
| AC-ANIM-17 | Aim lower clip changes across all eight directions. |
| AC-ANIM-18 | Aim W/A/S/D and diagonal combinations keep unit facing within tolerance of camera yaw. |
| AC-ANIM-19 | Aim S moves opposite camera forward and uses the reversed backpedal lower clip. |
| AC-ANIM-20 | Aim upper-body pitch follows camera pitch. |
| AC-ANIM-21 | Aim upper-body pitch pivots at the lower back so the head, neck, and shoulders stay connected. |
| AC-ANIM-22 | Aim facing follows camera rotation without perceptible lag. |
| AC-ANIM-23 | Aim movement does not write facing and does not change `Turnable` or turning rates. |
| AC-ANIM-24 | Aim camera pitch up and down changes only the upper body spine pose. |
| AC-ANIM-25 | Aim pitch reaches the 80 degree down and 60 degree up camera limits. |
| AC-ANIM-26 | Aim pitch does not move the lower body or the model root. |
| AC-ANIM-27 | Aim pitch stays continuous while the lower animation changes direction. |
| AC-ANIM-28 | Camera pitch 59, 29, and 4 degrees map to three distinct `SCOBAUp` times after wrap normalization, with 59 lowest and 4 highest. |
| AC-ANIM-29 | Aim pitch `AnimSetTime` targets the `SCOBAUp` reference and visibly changes the spine pose. |
| AC-ANIM-30 | Pitch keyframes are tightly spaced and camera pitch updates the upper pose on every change. |
| AC-ANIM-31 | Camera pitch changes update the upper pose on the same camera move, without a fixed slow delay. |
| AC-ANIM-32 | Reasserting pitch does not drift or stutter during a held camera pitch. |
| AC-ANIM-33 | Aim entry starts at the current camera pitch pose without a visible idle-to-aim blend offset. |
| AC-ANIM-34 | Aim hold shows no two-frame alternating jitter at a fixed camera pitch. |
| AC-ANIM-35 | Aim exit restores engine blend defaults and normal animation playback. |

## 4. Out of scope

- Facial, material, and weapon animation.
- Procedural per-bone runtime control.
- Network animation prediction.

## 5. References

- StarCraft II baseline animations and split-body track sets.
- Existing animation code and asset pipeline described in
  [SPEC-CHARACTER-ANIMATION](../specifications/SPEC-CHARACTER-ANIMATION.md).

# REQ-SLOW-WALK: Hero Slow Walk on Shift

**Date:** 2026-11-21
**Status:** Stated by the operator on 2026-11-21. Plan approved the same day
("GO"); built, not yet run in game. The operator decided the slow walk jump
(R-SLOW-18). The specification lists the state of each requirement and the
run that backs it.

## 1. Scope

In scope:

- holding Shift while moving slows Tosh to 30 % speed;
- free walk (the W loop without a strafe hold), strafe hold (TPS, or a right
  hold in Point & Click), aim mode, and Point & Click move orders;
- split-body slow leg clips baked from Tosh's stock `Walk Slow`: forward,
  eight directions, and backpedal;
- new lower states in the animation FSM;
- a slow upper-body clip from the same `Walk Slow` when not aiming (R-SLOW-19).

Out of scope:

- Kerrigan and other heroes (Shift has no effect on them).

Implementation lives in [SPEC-SLOW-WALK](../specifications/SPEC-SLOW-WALK.md).

## 2. Definitions

- **Hero**: the unit the player controls (`gv_tPSUNIT`).
- **Slow key**: Shift (`gv_sLOWWALK` = `c_keyShift`).
- **Slow walk**: the slow key is held and the hero is Tosh.
- **Normal speed**: the hero speed without the slow walk, with all other buffs.
- **Lower bracket**: the leg animation layer (`SCOBALo`).

## 3. Requirements

### 3.1 Input and speed

| ID | Requirement |
| --- | --- |
| R-SLOW-1 | Holding Shift MUST turn the slow walk on for Tosh. Releasing Shift MUST turn it off. It MUST work in TPS and in Point & Click. |
| R-SLOW-2 | During the slow walk, Tosh's travel speed MUST be 30 % of normal speed (engine travel 0.25 to 0.35 of the same move without Shift). Operator 2026-11-22; was 40 % (2026-11-21), before that 50 %. |
| R-SLOW-3 | After release, the travel speed MUST be back to normal speed (0.95 to 1.05) when the R-SLOW-21 ramp ends, 1 s after the release (operator 2026-11-21; was within 0.25 s). |
| R-SLOW-4 | The slow walk MUST NOT change orders, facing, the move direction, backpedal, strafe, aim, or attacks. Only the speed and the leg clips change. |
| R-SLOW-5 | Shift MUST NOT slow any hero other than Tosh. |
| R-SLOW-6 | A hero switch or Tosh's death MUST remove the slow from the old unit. Switching to Tosh while Shift is held MUST start the slow walk on Tosh. |
| R-SLOW-7 | The slow key is Shift (operator 2026-11-21; it was Alt). The move keys MUST still move the hero while Shift is held. No other map key may use Shift. |
| R-SLOW-9 | The FOV zoom MUST be on Z (operator 2026-11-21; it was Shift). |
| R-SLOW-8 | The slow walk MUST be off during the intro (`gv_introActive`). |

### 3.2 Animation

| ID | Requirement |
| --- | --- |
| R-SLOW-10 | The slow leg clips MUST be baked from Tosh's own `Walk Slow`. No donor model. They MUST move only lower-bracket bones, like `Walk Leg`. |
| R-SLOW-11 | There MUST be a forward slow leg clip and eight directional slow leg clips (`Attack Walk Slow <dir>`), built the same way as the `Attack Walk <dir>` clips: the same yaw per direction, the back three played in reverse. |
| R-SLOW-12 | Every slow leg clip MUST have the length of `Walk Slow`. |
| R-SLOW-13 | The FSM MUST have two new lower states: slow walk and slow backpedal. During the slow walk, a walk state MUST become its slow state. Idle and turn states MUST NOT change. |
| R-SLOW-14 | During the slow walk, the lower bracket MUST play a slow leg clip whenever the hero moves: forward in free walk and Point & Click, the move direction in strafe hold and aim mode, the back clip on backpedal. Free walk forward MUST play the slow clip, not the stock walk. |
| R-SLOW-15 | The slow clip rate MUST match the feet to the ground: rate = 1.33 x travel speed / slow clip stride speed (operator 2026-11-21: 33 % faster to match the movement speed; was 1.25 x, 1.0 x). The stride speed MUST be measured from the baked clip at build time, not guessed. |
| R-SLOW-16 | When Shift is released while moving, the legs MUST return to the normal clip choice (stock walk, strafe walk, aim walk) within 0.25 s. |
| R-SLOW-17 | Aim pitch, attacks, and head look MUST keep working during the slow walk. |
| R-SLOW-18 | A jump from the slow walk MUST go directly into the regular walk and then jump, with a minimal blend (operator 2026-11-21). The legs MUST take the regular walk at the same foot phase and take off with the walk jump clips (R-JUMP-16, 18) and the jump blend (`c_JUMP_BLEND`, at most 0.05 s). The jump MUST run as a regular walk jump: no slow during the jump, the push-off burst applies (R-JUMP-22). After the landing recovery, with Shift still held, the slow walk MUST return. |
| R-SLOW-19 | When not aiming, the upper body MUST play Tosh's own `Walk Slow` on the upper bones while a slow leg clip plays (operator 2026-11-21), at the leg rate and the leg phase. With the reversed (back) leg clips it MUST play reversed. Aiming keeps the aim pose. An attack and the Point & Click pose hold replace it while they last. Without the slow walk the upper body MUST be as before. |
| R-SLOW-20 | The blend into and out of the slow walk clips, legs and arms, MUST be 3 times the normal 0.15 s clip blend: 0.45 s (operator 2026-11-21). Other transitions MUST keep their blend. |
| R-SLOW-21 | The speed MUST change smoothly between walk and slow walk: on a Shift press it MUST fall from normal to 30 % over 1 s, and on the release rise back over 1 s, linear in time (operator 2026-11-21). A jump, the intro, a hero switch and death still end the slow walk at once (R-SLOW-6, 8, 18). The leg and arm clips still switch at the key (R-SLOW-16). |

## 4. Open items

| ID | Item |
| --- | --- |
| O-SLOW-1 | Closed by R-SLOW-19 (operator 2026-11-21). |
| O-SLOW-2 | Closed by R-SLOW-18 (operator 2026-11-21). |
| O-SLOW-4 | Unconfirmed: the engine sends the Shift key alone to `TriggerAddEventKeyPressed`. The tests call the trigger's function; a real Shift press is an operator check (AC-SLOW-5). |
| O-SLOW-3 | Unconfirmed: SC2 queues orders on Shift. A Point & Click order given with Shift held may queue behind the current one. |

## 5. Acceptance (operator checks)

| ID | Check |
| --- | --- |
| AC-SLOW-1 | Hold Shift and walk: Tosh walks calmly, the feet do not slide. |
| AC-SLOW-2 | Hold Shift and strafe, backpedal, aim walk: the legs fit each direction. |
| AC-SLOW-3 | Press and release Shift while walking: no pop in the legs. |
| AC-SLOW-4 | Point & Click with Shift: the slow walk looks the same as TPS forward. |
| AC-SLOW-5 | A real Shift press and release slows and restores Tosh (O-SLOW-4). |
| AC-SLOW-6 | Jump from a slow walk: the legs go into the regular walk and take off with no visible pop; after landing the slow walk resumes smoothly. |
| AC-SLOW-7 | Hold Shift and walk without aiming, in every direction: the arms and torso move calmly with the legs; no pop at the start, the release, or a direction change. |

# REQ-JUMP: Hero Jump (MVP)

**Date:** 2026-11-16
**Status:** Stated by the operator on 2026-11-16. Built as an MVP. Revised
the same day after play: lower jump, ballistic flight, jump legs mixed with
idle or walk, camera follows the height (R-JUMP-3, 16, 17). The
specification lists the state of each requirement and the run that backs it.

## 1. Scope

In scope:

- a jump on the jump key for the active hero;
- the hero elevation during the jump;
- the lower-body (leg) clips of the jump on the split-body system, mixed
  with the idle or walk clip;
- the upper body staying independent during the jump;
- the camera height following the jump height.

Out of scope for the MVP:

- clearing cliffs, units, or doodads (pathing stays ground);
- the aim ray origin while airborne;
- jump clips for Kerrigan;
- upper-body jump clips; takeoff sound and dust.

Implementation lives in [SPEC-JUMP](../specifications/SPEC-JUMP.md).

## 2. Definitions

- **Hero**: the unit the player controls (`gv_tPSUNIT`).
- **Height**: the hero height above the ground, as the engine reports it
  (`UnitGetHeight`).
- **Airborne**: from the press until the height is back to 0.
- **Landing recovery**: a short time after touchdown. The legs play the
  landing clip.
- **Lower bracket**: the leg animation layer (`SCOBALo`). **Upper bracket**:
  torso, arms, attack, and head layers.

## 3. Requirements

### 3.1 Elevation

| ID | Requirement |
| --- | --- |
| R-JUMP-1 | The jump key (Space) MUST start a jump of the active hero in both control modes. It replaces the old `DehakaJump` behavior on Space. |
| R-JUMP-2 | The jump MUST be responsive: the height MUST pass 0.1 within 0.25 s of the press. The first 0.125 s is the takeoff crouch: the height MUST stay 0 (within 0.02). |
| R-JUMP-3 | The height MUST follow ballistic flight: launch speed and gravity, peak 0.6 (within 0.08) about 0.45 s after the press. The fall MUST use stronger gravity than the rise, so the touchdown speed is above the launch speed. Touchdown about 0.69 s after the press (within 0.08 s); the takeoff crouch is 0.15 s (revised 2026-11-17, was 0.133 s). After the flight, the height MUST be 0. Revised 2026-11-16: the first arc (a 1.5 parabola, 0.8 s) was too high and did not look believable. |
| R-JUMP-4 | A press while airborne MUST NOT start a jump or change the arc. A press during landing recovery MUST start a new jump. |
| R-JUMP-5 | Without a press, the height MUST stay 0. |
| R-JUMP-6 | The jump MUST NOT change the hero's orders, facing, or walk. Walking during the jump MUST still move the hero. |
| R-JUMP-7 | A hero switch or the hero's death during a jump MUST put that unit back at height 0 and end the jump. |
| R-JUMP-17 | The camera height offset MUST carry the jump height in real time: every game loop of the jump it MUST be the base offset plus the quake shake plus the hero's jump height, with the same target height as the hero, blended linearly over the same loop time. The camera MUST NOT lead or trail the hero (operator 2026-11-16: an eased blend lagged; a one-loop lead made the model trail the camera, removed). At the end of the jump (touchdown, hero switch, death) the jump part MUST be 0. Without a jump the jump part MUST stay 0. |
| R-JUMP-8 | Touchdown MUST play a thump at the hero's feet: the stock light physics impact dust (`PhysicsImpactDustLight`, map model `ScobaJumpDust`) and the Queen `QueenFootstep` sound (light stone footsteps; revised 2026-11-17: `GoliathFootstep` was too big). Revised 2026-11-16: `JumpLandDust` was too large at the Goliath scale (1.25-1.5) and still too large at the Queen scale (0.75-0.9). It MUST play once per touchdown, in the game loop where the height reaches 0. Like the Goliath, it MUST play no dust in water. A jump that ends in the air (R-JUMP-7) MUST NOT play it. Added by the operator 2026-11-16 as "JumpImpactLarge"; no stock asset has that name, so the effect the Goliath thump really uses is named here. |

### 3.2 Animation

| ID | Requirement |
| --- | --- |
| R-JUMP-10 | Tosh's legs MUST play three phases in order: takeoff, air, landing. The poses MUST be built from Tosh's own stand and walk clips: the pelvis crouches, the knees bend, the feet tuck and point. No donor model is used. Revised 2026-11-16: the Spectre `Unload End` donor (a dropship landing) held the feet together and fought every fix. |
| R-JUMP-16 | A jump clip MUST be built on the lower clip the hero would play: idle, or walk in the walk direction (eight directions). A stand jump MUST keep the stand stance: feet where they stand, along the ground. A walk jump MUST keep the stride of the walk: feet split along the walk direction, not side to side (operator reports 2026-11-16: legs held together; then legs spread left to right). The base is chosen at takeoff, at the start of the air phase, and at touchdown. Walk MUST be the base only while the hero really moves under a movement key or move order; a stand jump, a jump right after stopping, or a key held against a wall MUST use idle (operator report 2026-11-16: a stand jump looked like running in place). |
| R-JUMP-18 | A walk jump MUST match the feet of the walk. The walk has two flight frames per cycle, one per leading foot; a walk jump exists once per stride. At takeoff the script MUST pick the stride whose takeoff clip begins nearest the walk phase it tracks. The takeoff clip MUST begin on the walk pose of that phase, play the walk up to the flight frame, and hold it in the air. The landing clip MUST play the walk on from the flight frame and end on a walk pose; an aim or strafe walk MUST resume at that phase. One jump MUST use one stride from takeoff to landing: the legs never swap in the air. |
| R-JUMP-19 | The knee, ankle and hip angles of the stand jump MUST match a motion capture reference: CMU Graphics Lab Motion Capture Database, subject 16 trials 01, 02 (jump), 03, 04 (high jump), 05 (forward jump), subject 75 trials 01-03 (run jump), 12 (hops). Changes from the standing pose, degrees, range over the trials: deepest takeoff crouch knee +51.5..+84.6, ankle -21.0..-15.4 (dorsiflexed, foot flat); flight knee +7.6..+45.4, ankle +24.9..+36.5 (toes down), hip +5.5..+17.4 (thigh forward); deepest landing crouch knee +37.5..+64.3, ankle -22.8..-8.7. The targets MUST be the strongest real trials: high jump crouch (+72) and landing (+52), tucked flight knee (+35). The build MUST fail outside these ranges widened by 5 degrees. On the ground the feet MUST stay flat. Added 2026-11-16 (operator: more knee bending, some ankle bending, from a real reference). Revised 2026-11-17 (operator: the jump was stiff; knees and feet must come up; real reference first, stylized only if it still looks stiff). |
| R-JUMP-22 | A walk jump MUST push off with a very short speed burst: move speed x1.4 for 0.2 s (`SCOBAJumpBurst`), over in the air. The takeoff clip and crouch MUST play at the walk clip rate times the burst; the landing clip at the walk clip rate; the air clip at 1. The landing recovery MUST be short (250 ms clip). A stand jump MUST have no burst and all rates 1. |
| R-JUMP-11 | The jump clips MUST move only the pelvis (`Root`) and the leg bones; every other track is the base clip's. The clips MUST NOT hold any upper-body bone. The torso rides on the pelvis. |
| R-JUMP-12 | The leg bones MUST keep their length in every jump clip (the build fails above 0.001). |
| R-JUMP-13 | The jump MUST NOT write the upper bracket. Aiming, aim pitch, and attacks MUST keep working during the jump. |
| R-JUMP-14 | After landing recovery, the legs MUST return to the normal clip choice (stand, walk, aim walk). |
| R-JUMP-15 | Kerrigan MUST jump (R-JUMP-1 to 7) with her normal leg clips. |

## 4. Open items

| ID | Item |
| --- | --- |
| O-JUMP-1 | The aim ray origin while airborne. (Camera follow: done, R-JUMP-17.) |
| O-JUMP-4 | Closed by R-JUMP-18: the script tracks the walk phase itself. Left open: the takeoff clip begins up to a quarter cycle from the tracked phase (two strides); the 0.08 s blend covers it. |
| O-JUMP-5 | The torso does not lean forward in the crouch (the reference hips flex about 46 degrees). A lean would turn the upper body, which the jump must not write (R-JUMP-13). |
| O-JUMP-6 | The takeoff crouch lasts 0.15 s (operator 2026-11-17: 150 ms at most; was 0.133 s); the reference takes about 0.5 s down and 0.2 s up. The angles match; the speed is the game's. |
| O-JUMP-2 | A leg source for Kerrigan. Her own `Jump End` is a candidate. |
| O-JUMP-3 | Upper-body jump clips while not aiming or attacking. |

## 5. Acceptance (operator checks)

| ID | Check |
| --- | --- |
| AC-JUMP-1 | Tosh crouches and extends on takeoff, holds the legs in the air with the toes pointed, lands toes first, and absorbs the landing. The knee and ankle bend look natural. |
| AC-JUMP-2 | The feet do not pop or twist between the jump clips and the stand or walk clips. |
| AC-JUMP-3 | Aiming during the jump: the torso follows the crosshair. The legs show the jump. |
| AC-JUMP-4 | The touchdown dust and the light thump sound fit Tosh and line up with the feet hitting the ground. |
| AC-JUMP-5 | The jump height and the flight look believable: a short crouch, a quick rise, a slower top, a faster drop. |
| AC-JUMP-6 | Jumping while walking: the legs push off from the walk, hold a stride in the air along the move direction, and land back into the walk on the leading foot. Jumping from idle: the legs crouch and tuck from the stand, feet at the stand width. No pop at the phase changes or at the release. |
| AC-JUMP-7 | The camera rises and falls with the hero, smoothly, with no lag or step. |

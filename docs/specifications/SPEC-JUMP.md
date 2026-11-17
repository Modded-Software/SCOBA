# SPEC-JUMP: Hero Jump (MVP)

**Date:** 2026-11-16
**Requirements:** [REQ-JUMP](../requirements/REQ-JUMP.md)

## 1. Requirement state

States: `[tested]` = a check in the `jump` profile backs it; `[build]` = the
map validator or a host test backs it; `[operator]` = only a person can
judge it.

| ID | State | Backed by |
| --- | --- | --- |
| R-JUMP-1 | [tested] | `jump_stand`: `pressOk`, `starts` (the key trigger calls the same `gf_JumpPress`) |
| R-JUMP-2 | [tested] | `crouchH100` 0..2 (ms <= 125), `firstUpMs` 125..250 |
| R-JUMP-3 | [tested] [build] [operator] | `peakH100` 52..62, `peakMs` 370..500, `lastUpMs` 560..720, `endH100` 0..1, `landSpeed100` > `v0100`; host `BallisticTest`; feel: AC-JUMP-5 |
| R-JUMP-4 | [tested] | `jump_double` (rejected, arc unchanged), `jump_rejump` (two arcs) |
| R-JUMP-5 | [tested] | `jump_none`: `peakH100` < 2, no start |
| R-JUMP-6 | [tested] | `jump_stand`: no order, facing and position unchanged; `jump_aimwalk`, `jump_freewalk`: travel while airborne |
| R-JUMP-7 | [tested] | `jump_switch`: old unit `endH100` 0..1, phase 0, `camEnd100` 0 |
| R-JUMP-8 | [tested] [build] [operator] | `thumps` per scenario (1; 0 none; 1 double; 2 rejump; 0 switch), `thumpMs` 670..735, same loop as `firstDownMs`, `thumpH100` 0..10, `thumpActor`; `jumpanim.validate.check_thump`; host test: `ScobaJumpDust` is `PhysicsImpactDustLight`, not `JumpLandDust`; look and sound: AC-JUMP-4 |
| R-JUMP-10 | [tested] [build] [operator] | `clipLog`: Start, Air, End in order; `jumpanim/validate.py`; host test: no donor in the bake; look: AC-JUMP-1, 2 |
| R-JUMP-11 | [build] | `jumpanim/validate.py`: no bone under `BoneSpine01` in any jump clip |
| R-JUMP-12 | [build] | `jumpanim.validate.check_bones`: leg bone length change <= 0.001 over all 51 clips |
| R-JUMP-13 | [tested] | `jump_aimwalk`: `midAim`, `midUpper` = aim mid |
| R-JUMP-14 | [tested] | `jump_aimwalk`: `afterFull` > 0 after recovery |
| R-JUMP-15 | [tested] | `jump_kerrigan`: full arc, `midOwned` false, empty `clipLog` |
| R-JUMP-16 | [tested] [build] [operator] | `clipLog` has only clips built on a base (`no bare jump clip`); base Stand in `jump_stand`, `jump_stopjump`, `jump_keystill` (`no stride clip`); base `Walk,Forward` in `jump_aimwalk`, `jump_freewalk`; `jumpanim/validate.py`: stand jump feet <= 0.02 off the stand stance along the ground; walk jump air feet <= 0.02 off the walk stride, stride split >= 0.45, forward width <= 0.75 of the stand width; no bare clip in the model; look: AC-JUMP-6 |
| R-JUMP-18 | [tested] [build] [operator] | `takeoff stride is the nearest` (mirror of `gf_JumpGaitStride`), `Start, Air, End use the takeoff stride`, `gait phase tracks the walk`, `walk resumes where the landing stops` (aim walk), `walk resume absent` (free walk), `no clip time set in the air`; `jumpanim/validate.py`: flight frames within 0.03 of the pelvis height maxima, seams <= 0.01, gait constants equal the bake's; look: AC-JUMP-2, 6. Not exercised in game: stride 02 (both walk scenarios take off in stride 01). |
| R-JUMP-19 | [build] [operator] | `jumpanim.validate.check_reference`: six angles inside the reference ranges +-5 degrees; feet flat on the ground; host `LegSolveTest`, `ProfileTest`; look: AC-JUMP-1 |
| R-JUMP-22 | [tested] | `jump_aimwalk`, `jump_freewalk`: one burst, gone at the end; engine travel in the first loops >= 1.2x the walk before, back within 1.1x in the air (`hero moves faster at the push-off`, `burst is over in the air`); `scaleLog` Start = walk clip rate x `c_JUMP_BURST_SPEED`, Air 100, End = walk clip rate; `c_JUMP_BURST_SPEED` = data `MoveSpeedMultiplier`; landing recovery 250 ms / scale. Negative: `jump_stand`, `jump_stopjump`: no burst, all scales 100. The speed property is asserted unchanged only: the engine does not show the buff in it (F16). |
| R-JUMP-17 | [tested] [operator] | `camMax100` 52..62; camera part written at each sample = engine height one loop (62 ms) later, within 0.02 (`camera matches the hero, no lead`); `camEnd100` 0; `jump_none`: `camMax100` 0; tps regression unchanged; smoothness: AC-JUMP-7 |

Run results go in section 7.

## 2. Facts

| ID | Fact | Source |
| --- | --- | --- |
| F1 | Tosh has no jump clip. Kerrigan has `Jump End` only. | model dump, `/mnt/ws-fast/inspect/jump_hits.txt` |
| F2 | Spectre shares Tosh's leg bones with the same rest pose. Marine does not. No longer used (F11). | bone dump, `/mnt/ws-fast/inspect/unload.txt` |
| F3 | Spectre `Unload End`: `Main` z 1.8 -> 0 over 0-333 ms; calves bend 56 -> 130 degrees by 433-466 ms and recover by 1100 ms. No longer used (F11). | `/mnt/ws-fast/inspect/timing.txt` |
| F11 | The Spectre `Unload End` landing holds the feet 0.12 apart; Tosh stands 0.26 apart (unscaled). Blended onto the stand it held the legs together; forced to the stand width on every base it spread the walk jump sideways. Dropped as a pose source. | `/mnt/ws-fast/inspect/symmetry.sh`; operator reports 2026-11-16 |
| F12 | Tosh's leg chain: `Root` (pelvis) -> `BoneWaist` (scale 0.84) -> `BoneHipL/R` -> `BoneLegL/R` (thigh, scale 1.18) -> `BoneCalfL/R` -> `BoneFootL/R` (ankle). `Main` is scaled 1.58. No toe bone. Model forward is -Y: the knees bend toward -Y. Thigh 0.272, shin 0.287, hip to foot standing 0.525. | `/mnt/ws-fast/inspect/rig.sh`, `jump_pose.sh` |
| F13 | `Attack Walk <dir>` (0-667 ms) is a jog: two flight frames per cycle at phase 0.05 and 0.55 (pelvis height maxima); the back walks are the walk reversed (0.45, 0.95). | `jump: flight frames` build line; `jump_pose.sh` |
| F14 | Motion capture reference: CMU Graphics Lab Motion Capture Database (mocap.cs.cmu.edu), subject 16, trials 01, 02 (jump), 05 (forward jump), 120 fps. Changes from standing, degrees (01 / 02 / 05). Crouch lowest: knee +64 / +71 / +53, ankle -17 / -18 / -17, hip +46 / +47 / +50, pelvis -0.18 / -0.21 / -0.14 m. Flight peak: knee +9 / +12 / +19, ankle +35 / +27 / +35. Landing lowest: knee +40 / +38 / +44, ankle -15 / -17 / -9, pelvis -0.10 / -0.10 / -0.13 m. Trial 01 timing: crouch down 0.5 s, up to liftoff 0.17 s; at liftoff the knees have about 30% of the crouch left; the ankle goes from -17 to +37 within about 0.1 s around liftoff, and from +30 to 0 within about 0.07 s around touchdown; landing lowest 0.13 s after touchdown. | `/mnt/ws-fast/inspect/mocap/amc_legs.sh` on `16_01.amc`, `16_02.amc`, `16_05.amc` |
| F15 | `libNtve_gf_AnimSetTime` sends `{False}`, which the engine rejects (`Invalid actor msg`). `libNtve_gf_SetAnimationTime` sends 0/1. | ScriptError 2026-11-16 18.41.38 |
| F16 | `UnitGetPropertyFixed(c_unitPropMovementSpeed, c_unitPropCurrent)` does not show the `SCOBAJumpBurst` buff: 310 at the press and during the burst, while engine travel is 1.4x. The burst is tested by travel; the Start clip rate uses `c_JUMP_BURST_SPEED`. | `jump/20261117-014046` |
| F4 | `UnitGetHeight` gives a unit's height; a unit position has none. | SPEC-TPS T35 |
| F5 | No stock asset or catalog id is named `JumpImpactLarge`. The only `JumpImpact` id is the Fenix sound `FenixChampionJumpImpact`. The footfall dusts are `JumpLandDust` at unit scales: `GoliathFootDust` 1.25-1.5, `QueenFootDust` 0.75-0.9. The Goliath sound is `GoliathFootstep`. | CASC listing `/mnt/ws-fast/inspect/jumpfx.txt`; `scripts/footfall/fx.py` |
| F10 | Stock dust puffs, measured (particles, life, speed, size; spread ~ speed x life): `JumpLandDust` 82, 1.5 s, 8.2, 1.83, ~12; `PhysicsImpactDustLight` 28, 0.5 s, 0.81, 0.80, ~0.4; `PhysicsImpactDustMed` 36, 0.85 s, 1.25, 0.80, ~1.1. All have one `Birth` clip (Light, Med: 2 s). | `/mnt/ws-fast/inspect/dust_extract.sh`, `/tmp/opencode/dust_measure.log` |
| F6 | A game timer started at the press fires one loop after the periodic tick reaches the same time. | `jump/20261116-165438` |
| F7 | `gf_AnimMoving` reads false at the jump press, even while walking: the anim tick has just stored the position. A per-loop travel read in the jump tick sees the walk (0.19 per loop). | `jump/20261116-173659`, `jump/20261116-174057` |
| F9 | Galaxy has no getter for the player camera height offset (only target, pitch, yaw, distance). | `natives.galaxy` lines 750-755 |
| F8 | In free mode, `gv_fORWARD` alone does not move the hero; `gf_ForwardBegin` issues the move orders. | `jump/20261116-173659` |

## 3. Design

### 3.1 Flight (`systems/jump.galaxy`)

- `gf_JumpPress(player)`: rejects while airborne (RISE, AIR) or with no live
  hero. Otherwise it sets phase RISE, stores the start time and unit, picks
  the base clip, and steps at once (R-JUMP-2).
- Curve `gf_JumpArc(t)`, `t` = time since the press, `s = t - crouch`:
  - `s <= 0`: 0 (takeoff crouch on the ground);
  - rise: `v0 * s - g_up * s^2 / 2`;
  - fall: `peak - g_down * (s - t_up)^2 / 2`, floored at 0.
  - `g_up = 2 * peak / t_up^2`, `v0 = g_up * t_up`,
    `g_down = gain * g_up`, `t_down = sqrt(2 * peak / g_down)`,
    `airtime = crouch + t_up + t_down`. Set in `gf_JumpConfigInit`.
  - Closed form, not integrated: no drift between loops.
  - Values: v0 4.0, g_up 13.3, g_down 21.3, t_down 0.237 s, airtime
    0.670 s, touchdown speed 5.06.
- `gf_JumpStep(player)`, every game loop (`c_JUMP_TICK` 0.0625 s):
  `UnitSetHeight(hero, h(t + tick), tick)`; the engine blends to the next
  loop's height. The next time is capped at `airtime`.
- Touchdown (`gf_JumpLand`): the first step with `t >= airtime` (F6). It sets
  height 0, the camera jump part 0, phase LAND, picks the base again, plays
  the landing clip and the thump. It does nothing once the jump is no longer
  airborne.
- Thump (`gf_JumpThump`, R-JUMP-8): `GoliathFootstep` at the hero position;
  `ScobaJumpDust` (stock `PhysicsImpactDustLight`, F10; source
  `ModelData.xml`) at the same point, Birth one-shot, destroyed after
  `c_JUMP_THUMP_LIFE`. In water (`gf_QuakeInWater`) the dust is skipped. One
  actor per player; a new thump destroys the old one.
- RISE -> AIR at `c_JUMP_RISE_TIME` (base picked again). LAND -> NONE after
  `c_JUMP_LAND_TIME`. Hero changed or died: height 0, camera part 0, end
  (R-JUMP-7).
- Pathing, mover, orders, and facing are not touched (R-JUMP-6). The ground
  height under the hero is the engine's: `UnitSetHeight` is above ground.

| Constant | Value |
| --- | --- |
| `c_JUMP_PEAK` | 0.6 |
| `c_JUMP_CROUCH` | 0.133 s |
| `c_JUMP_TIME_UP` | 0.30 s |
| `c_JUMP_FALL_GAIN` | 1.6 |
| `c_JUMP_RISE_TIME` | 0.267 s |
| `c_JUMP_LAND_TIME` | 0.4 s |
| `c_JUMP_BLEND` | 0.08 s |
| `c_JUMP_WALK_STEP` | 0.03 per loop |
| `c_JUMP_THUMP_MODEL` | `ScobaJumpDust` |
| `c_JUMP_THUMP_SOUND` | `GoliathFootstep` |
| `c_JUMP_THUMP_LIFE` | 2.0 s |

### 3.2 Camera (R-JUMP-17)

- `gf_CameraHeightApply(player, time)` in `systems/camera.galaxy` writes
  `c_SCOBA_CAMERA_HEIGHT_OFFSET + gv_quakeHeight + gv_jumpCamHeight` and
  stores it in `gv_cameraHeightApplied`.
- The write is a linear blend: `CameraSetValue(..., time, 0, 0)`
  (initial velocity 0, deceleration 0). The first version used `(-1, 10)`
  (carried velocity, eased end), and the operator saw it lag.
- The jump step sets `gv_jumpCamHeight` to the hero's own `h(t + tick)` and
  blends over the hero's loop time. Same target, same time, no lead. A
  one-loop lead was tried (`jump/20261116-175352`); the model then trailed
  the camera (operator), so it was removed. Galaxy cannot read the current
  camera height offset (F9). The test checks the written values; whether
  the camera looks in step is AC-JUMP-7.
- The quake tick writes through the same function with time 0, except while
  airborne: there the jump step writes every loop, and a snap would run one
  loop ahead of the unit.
- Touchdown and `gf_JumpEnd` write the jump part 0 at once.

### 3.3 Lower bracket and base clip (R-JUMP-16)

- `gv_jumpClip[profile][phase]` holds the phase prefix: `Jump,Start`,
  `Jump`, `Jump,End`. Only Tosh has them.
- Base: `gf_JumpPickBase` at the press, at RISE -> AIR, and at touchdown.
  - Walking (`gf_JumpWalking`): the hero moved more than
    `c_JUMP_WALK_STEP` over the last loop (`gf_JumpTrackMove`, in the jump
    tick, F7), and a movement key or a move order drives it.
  - Walking: base `Walk,<dir>`. `<dir>` is `gv_animAimDir` while aiming or
    in right-hold strafe, else Forward (free movement faces the move).
  - Otherwise: base `Stand` (idle). A key against a wall, a leftover move
    order, or a push is idle.
- Clip: `<prefix>,<base>[,<stride 01|02>],Leg`, e.g. `Jump,Start,Stand,Leg`,
  `Jump,Walk,Back,Left,02,Leg`. Walk clips carry the stride.
- Gait (R-JUMP-18):
  - `gf_JumpGaitTrack` (every jump tick) advances `gv_jumpGait`, the walk
    phase 0..1, at the walk clip rate (speed / `WalkAnimMoveSpeed`). A free
    walk starts at 0 when the hero starts to move; an aim or strafe walk
    clip starts at 0 when `gf_AnimFullSet` plays it.
  - `gf_JumpGaitFlight(dir, stride)`: the flight frame phase,
    `c_JUMP_GAIT_FLIGHT` (0.05; back walks `_FLIGHT_BACK` 0.95) + stride / 2.
  - `gf_JumpGaitStride`: the stride whose Start clip begins nearest the
    tracked phase. The Start clip begins `c_JUMP_GAIT_PUSH` (0.25) before
    its flight frame.
  - The stride is picked at the press and kept to the end of the jump
    (`gv_jumpStride`; -1 outside a walk jump).
  - Release into an aim or strafe walk: `gv_jumpGait` is set to the phase
    the End clip stops at (flight + `c_JUMP_GAIT_LAND` 0.35) and
    `gf_JumpGaitOnLowerPlay` sets the walk clip time to it (tag `R` in
    `gv_jumpSetTimeLog`, F15). A free walk goes back to the stock walk.
- `gf_JumpOwnsLower`: a phase is active and the hero has a prefix. While it
  is true, `gf_AnimFullSet` returns at once.
- `gf_JumpAnimApply` plays the clip on `SCOBALo` once per change, blend
  0.08 s. Start and End hold their last frame; Air loops. Each played clip
  is appended to `gv_jumpClipLog` (tests).
- `gf_AnimReset` calls `gf_JumpAnimInvalidate`, so the next step plays the
  clip again. At NONE, `gf_JumpAnimRelease` clears `SCOBALo` and resets
  `gv_animFullState` and `gv_animFullDir` (R-JUMP-14).
- The jump never writes `SCOBAUp`, the attack brackets, or `SCOBAHead`
  (R-JUMP-13).

### 3.4 Clips (`scripts/jumpanim/bake.py`, `kin.py`, `ik.py`)

No donor (F11). Each clip is the hero's own base clip, sampled every 33 ms,
with three operations on the pose (`shape_pose`):

- **Crouch**: the pelvis (`Root`) moves down and back along the way the
  knees bend. A foot on the ground stays in place; a foot in the air (more
  than 0.03-0.15 of the leg above its standing height) moves with the
  pelvis. Down sets the knee bend; back keeps the shin upright.
- **Tuck**: the feet rise.
- **Point**: the foot turns at the ankle, toes down, to the flight angle.

Crouch and tuck are two-bone inverse kinematics per leg (`knee_position`,
`solve_leg`): the bone lengths are kept, the knee stays on the side it bends
to, the reach is clamped to 0.25..1 of the leg. On the ground the foot keeps
its world rotation, so the ankle dorsiflexes as the shin leans.

Depths come from the reference angles (F14, R-JUMP-19). `make_rig` solves
them on the standing pose by bisection:

| Target (change from standing) | Value | Solved on Tosh |
| --- | --- | --- |
| Takeoff crouch: knee, ankle | +62, -17 | pelvis down 0.185, back 0.062 |
| Landing crouch: knee, ankle | +40, -14 | pelvis down 0.098, back 0.029 |
| Air: knee | +13 | feet up 0.024 |
| Air: ankle | +32 | foot turned at the ankle |

Weights over the clips (ms):

| Clip | Length | Crouch | Tuck | Point |
| --- | --- | --- | --- | --- |
| `Jump Start` | 267, holds | fast down to 1 at 60, extends faster and faster, 0 at 148 | 0 to liftoff, 1 at 267 | 0 to liftoff, 1 at 199 |
| `Jump` | 533, loops (never wraps in a jump) | 0 | 1 | 1 |
| `Jump End` | 250, holds | impact to 1 at 60, standing again at 220 | 1 -> 0 over 0-66 | 1 -> 0 over 0-66 |

Crouch curve (`punch`): quadratic, fastest at touchdown and at liftoff, no
ease (operator 2026-11-16: explosive). The feet are flat while the hero is
on the ground. At touchdown they are still raised by the tuck and pointed:
the toes come down first.

Stand jump only: the legs gather (`gather_weight`, 0 at liftoff, 1 at the
apogee, 0 at touchdown). Feet to 0.80 and knees to 0.93 hip widths; never
outward. Reference: CMU subject 16 at the flight peak, feet 0.32..1.12,
knees 0.68..1.11 hip widths.

Bases (`JUMP_BASES`): `Stand` from `Attack Stand`, and `Walk <dir>` from the
eight `Attack Walk <dir>` clips. Stand: 3 clips; the stand runs on under
them. Walk: 3 phases x 8 directions x 2 strides = 48 clips (F13):

- Start plays the walk over `PUSH_CYCLE` (0.2) up to the stride's flight
  frame during the crouch (133 ms): walk rate 1.
- Air plays the walk on very slowly, `AIR_CYCLE` (0.03) from liftoff to
  touchdown (operator 2026-11-16: no freeze frame).
- End plays the walk on to `LAND_CYCLE` (0.405) in 250 ms: walk rate 1.

The script plays walk Start and End at the walk clip rate
(`gf_JumpGaitRate`, strafe x1.25), so the feet keep the ground speed. The
takeoff crouch is `c_JUMP_CROUCH / rate` long, and the landing recovery is
`c_JUMP_LAND_TIME / rate`. Base clip events (footsteps) are dropped; the
thump is the landing sound. Marker version 43.

### 3.5 Input

Space (`gv_jUMP`) calls `gf_JumpPress(EventPlayer())` in both control
modes. The old `DehakaJump` trigger and preload entry are removed.

## 4. Files

| File | Content |
| --- | --- |
| `src/.../core/jump.galaxy` | Constants and state. |
| `src/.../systems/jump.galaxy` | Press, curve, step, base pick, clips, camera part, thump, triggers. |
| `src/.../systems/camera.galaxy` | `gf_CameraHeightApply`. |
| `src/.../systems/quake.galaxy` | Writes the height through `gf_CameraHeightApply`. |
| `src/.../systems/animation_bracket.galaxy` | Guard in `gf_AnimFullSet`. |
| `src/.../systems/animation_fsm.galaxy` | `gf_JumpAnimInvalidate` in `gf_AnimReset`. |
| `src/.../systems/animation_bracket.galaxy` | `gf_JumpGaitOnLowerPlay` hook after the walk clip plays. |
| `scripts/jumpanim/bake.py` | The bake: clip plan, timing, weights, clips. |
| `scripts/jumpanim/kin.py` | Vectors, clip sampling, forward kinematics. |
| `scripts/jumpanim/ik.py` | Leg IK, rig, crouch, tuck, point, gather, reference angles. |
| `scripts/jumpanim/validate.py` | Map checks: clips, names, bones, stance, gather, stride, air drift, walk rate, seams, reference angles, thump ids, camera smoothing. |
| `src/.../Base.SC2Data/GameData/CameraData.xml` | Follow target and height offset smoothing 0. |
| `src/.../Base.SC2Data/GameData/BehaviorData.xml` | `SCOBAJumpBurst`: takeoff speed x1.4 for 0.2 s. `c_JUMP_BURST_SPEED` in `core/jump.galaxy` carries the same value for the Start clip rate. |
| `scripts/testkit/galaxy/jump.galaxy`, `profiles/jump.py`, `profiles/jump_rates.py` | In-game test. `jump_rates.py`: burst, clip rates, landing (R-JUMP-22). |
| `scripts/testkit/tests/test_character_anim_jump.py`, `test_character_anim_jump_ik.py` | Host tests. |

## 5. Tests

`scripts/playtest.sh jump [arc|body|hero]`. Each scenario resets aim, jump,
toggles, orders, and position (`gf_JtReset`), then samples once per game
loop. Raw samples: `raw` (height), `cam` (camera jump part / camera target
height), `clipLog`, press inputs.

| Scenario | Group | Measures | Negative case |
| --- | --- | --- | --- |
| `jump_stand` | arc | flight, phases `1230`, Stand clips, camera | no order, no turn, no drift |
| `jump_none` | arc | (none) | no height, no start, no clip, camera part 0 |
| `jump_double` | arc | flight, camera | second press rejected, flight unchanged |
| `jump_rejump` | arc | two flights | (none) |
| `jump_aimwalk` | body | flight, travel, upper on aim, `Walk,Forward` clips, stride, walk resume phase | no clip time set in the air |
| `jump_stopjump` | body | walk, release, jump two loops later | no walk clip, no stride |
| `jump_freewalk` | body | free walk (`gf_ForwardBegin`), `Walk,Forward` clips, stride | no walk resume (stock walk) |
| `jump_keystill` | body | key held, no travel | Stand, not walk, no stride |
| `jump_switch` | hero | old unit back at 0 | no thump, camera part 0 |
| `jump_kerrigan` | hero | flight, camera | no jump clip |

## 6. Known limits

- The aim ray origin uses the ground height while airborne (O-JUMP-1).
- Kerrigan has no jump clips (O-JUMP-2).
- The takeoff clip begins up to a quarter walk cycle from the tracked phase
  (O-JUMP-4). Stride 02 is built and checked at build time; no in-game
  scenario takes off in it.
- The torso does not lean in the crouch (O-JUMP-5). The crouch is faster
  than the reference (O-JUMP-6).
- The reference is one subject, three trials. The rig has no toe bone: the
  foot turns as one piece (F12).
- Galaxy cannot read bone poses or the clip time. Whether the engine applies
  the walk clip time on `SCOBALo` is an operator check.
- The jump is visual: the hero keeps ground pathing and stays a ground
  target.
- The speed property does not show the takeoff burst (F16).

## 7. Runs

| Run | Build stamp | Result |
|---|---|---|
| `jump/20261116-164314` | `d6bcf1b3bbaa-43a761f86e4b27f3` | failures: 0. First arc (1.5, 0.8 s); before R-JUMP-8. |
| `jump/20261116-165438` | `d6bcf1b3bbaa-f714955d55c7331c` | failures: 4. Timer touchdown one loop late (F6). Design changed. |
| `jump/20261116-165834` | `d6bcf1b3bbaa-78fd053fbf5d9c95` | failures: 0. R-JUMP-8 with the first arc. |
| `tps/20261116-170110` | `nogit-59fd62f85d037475` | failures: 26. Clean HEAD `d6bcf1b` baseline (`git archive`). |
| `jump/20261116-172626` | `d6bcf1b3bbaa-5d055e5e722b21ed` | failures: 0. Ballistic flight, mixed clips, camera. |
| `tps/20261116-172802` | `d6bcf1b3bbaa-5d055e5e722b21ed` | failures: 26, same checks as the baseline. |
| `jump/20261116-173353` | `d6bcf1b3bbaa-9c6c6e3b3d64185d` | Invalid: real mouse clicks. |
| `jump/20261116-173659` | `d6bcf1b3bbaa-4f1c25411a54589d` | failures: 7. Walk detection at the press (F7, F8). Design changed. |
| `jump/20261116-174219` | `d6bcf1b3bbaa-a0f1f46cdec87d69` | failures: 0. Idle base fixed (operator report: stand jump used walk). |
| `jump/20261116-175352` | `d6bcf1b3bbaa-208c0d8debae6943` | failures: 0. Linear camera blend with a one-loop lead; `QueenFootDust`. Lead rejected by the operator (model trailed the camera). |
| `tps/20261116-175539` | `d6bcf1b3bbaa-208c0d8debae6943` | failures: 26, same checks as the baseline. |
| `jump/20261116-180658` | `d6bcf1b3bbaa-80baa812e197c33e` | failures: 0. Lead removed: camera part = hero target each loop. |
| `tps/20261116-180844` | `d6bcf1b3bbaa-80baa812e197c33e` | failures: 26, same checks as the baseline. |
| `jump/20261116-182000` | `d6bcf1b3bbaa-e4e634219ccfdf6e` | failures: 0. Thump dust `ScobaJumpDust` (`PhysicsImpactDustLight`). |
| `jump/20261116-185027` | `d6bcf1b3bbaa-2b16e09359e5977a` | failures: 0. Donor bake forced to the stand width (marker 40). Rejected by the operator: walk jump legs spread sideways (F11). |
| `jump/20261116-190927` | `d6bcf1b3bbaa-071d5a3c06a98238` | failures: 0. Poses from Tosh's own clips, two strides (marker 41). Operator: more knee and ankle bend, from a reference. |
| `jump/20261116-192245` | `d6bcf1b3bbaa-071d5a3c06a98238` | failures: 0. Knee and ankle angles from motion capture (marker 42, R-JUMP-19). |
| `tps/20261116-192438` | `d6bcf1b3bbaa-071d5a3c06a98238` | failures: 26, same checks as the baseline. |
| `jump/20261117-014046` | `53218f36484e-da48f9bd6e36fa6a` | failures: 4. Speed property shows no burst (F16); Start scale without the burst (code bug). |
| `jump/20261117-014722` | `53218f36484e-66852ba562d8b843` | failures: 0. Start scale x `c_JUMP_BURST_SPEED`; burst by travel. |

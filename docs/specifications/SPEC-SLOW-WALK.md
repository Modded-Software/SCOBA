# SPEC-SLOW-WALK: Hero Slow Walk on Shift

**Date:** 2026-11-21
**Requirements:** [REQ-SLOW-WALK](../requirements/REQ-SLOW-WALK.md)

## 1. Requirement state

States: `[tested]` = a check in the `slowwalk` profile passed in a run of
section 6 (`slow_free` excepted: it fails, F11); `[build]` = the map validator or a host
test backs it; `[operator]` = only a person can judge it.

| ID | State | Backed by |
| --- | --- | --- |
| R-SLOW-1 | [tested] [operator] | `slow_*`: `slowBuff` 1, `slowSlowOn` after `gf_SlowWalkSet` (the key triggers call it); `presses` 1; host `SlowWalkTest.test_slow_key_triggers`; real key: AC-SLOW-5 |
| R-SLOW-2 | [built] | Changed 2026-11-22 to 30 % (was 40 %, not run in game; 50 % passed before); not run in game. `slow walk is 30 % speed`: engine travel `slowSpeed1000` / `refSpeed1000` 0.25..0.35 in `slow_pnc`, `slow_strafe`, `slow_back`, `slow_aim` (`slow_free` fails, F11); host `test_buff_is_thirty_percent_speed` |
| R-SLOW-3 | [built] | Changed 2026-11-21 (ramp); not run in game. `normal speed after the release`: `afterSpeed1000` / `refSpeed1000` 0.95..1.05, window after the 1 s ramp and 0.4 s settle |
| R-SLOW-4 | [tested] | `facing kept` (10 degrees) in every walk; `slow_pnc`: move order kept; `slow_strafe`, `slow_back`: `slowHoldStrafe`; `slow_aim`: `slowAim` |
| R-SLOW-5 | [tested] | Changed 2026-11-23: Tosh and Kerrigan (`gf_SlowWalkAllowed`). `slow_kerrigan`, `slow_kerrigan_aim`: see R-SLOW-22. Passed in `slowwalk/20261123-163132` (`hero` group, stamp `3a640a05615d-46100e5b8bedaa6d`, failures: 0). Host `test_slow_clips_are_tosh_only` (the clips stay Tosh's) |
| R-SLOW-6 | [built] | `slow_switch`: `toshBuffAway` 0, `toshBuffBack` 1, `toshBuffEnd` 0. Changed 2026-11-23: with Shift held Kerrigan takes the slow at the ramp level held: `kerriganBuff` 1 (`SCOBASlowWalkKerrigan`), `kerriganToshBuff` 0, `levelAway` 16, `slowOnAway` true. Passed in `slowwalk/20261123-163132` (`hero` group, stamp `3a640a05615d-46100e5b8bedaa6d`, failures: 0) |
| R-SLOW-7 | [tested] [build] | travel > 0 with the key held (every walk); host `test_slow_key_triggers`: `gv_sLOWWALK` is Shift. Shift key itself: not run in game since the change (AC-SLOW-5) |
| R-SLOW-9 | [build] [operator] | host `test_slow_key_triggers`: `gv_zOOM` is `c_keyZ`; the zoom on Z: operator check |
| R-SLOW-8 | [tested] | `slow_intro`: `introBuff` 0 with the key flag set, `afterBuff` 1 |
| R-SLOW-10 | [build] | `walkanim.slow.check_slow` in the map validator: no track under `BoneSpine01` |
| R-SLOW-11 | [build] | `check_slow`: nine clips; host `test_clip_table_matches_the_bake` |
| R-SLOW-12 | [build] | `make_slow_groups` raises, `check_slow` fails on a length other than `Walk Slow` |
| R-SLOW-13 | [tested] [build] | `slowFullState` 6 or 7 while moving; host `test_lower_states` |
| R-SLOW-14 | [tested] | `slowClip` = `Attack,Walk,Slow,Forward` (`slow_pnc`, `slow_aim`; `slow_free` passes the clip, not the travel), `...,Left` (`slow_strafe`), `...,Back` (`slow_back`); negative: `no slow clip without Shift` (`refClip`) |
| R-SLOW-15 | [build] [operator] | Changed 2026-11-27 (`c_ANIM_SLOW_RATE` 1.66, was 1.33 from 2026-11-21, before that 1.25; host `test_slow_rate_factor`). `slow clip rate matches the ground`: `slowWalkScale1000` = `c_ANIM_SLOW_RATE` x travel / `c_ANIM_SLOW_STRIDE` within 10 %; `check_slow`: `c_ANIM_SLOW_STRIDE` within 2 % of the baked stride; feet: AC-SLOW-1 |
| R-SLOW-16 | [tested] [operator] | `normal legs within 0.25 s` (`out1FullState` not 6 or 7; was `releaseFullState`, renamed 2026-11-21); pop: AC-SLOW-3 |
| R-SLOW-17 | [tested] | `slow_aim`: `slowUpperState` aim mid |
| R-SLOW-19 | [build] [operator] | Not run in game. Build: `check_slow` (both arm clips exist, `Walk Slow` length, upper bones only, priority 10, script clip names); host `test_arm_states_and_clips`. Planned in game: `slow_pnc`, `slow_strafe` (`slow_free` too, F11) `slowUpper` 10, clip `Walk,Slow,Arm`; `slow_back` 11, `Walk,Slow,Arm,Back`; negatives `ref`, `after`, `slow_aim`, `slow_kerrigan`: no arm state. Arms in step with the legs: AC-SLOW-7 |
| R-SLOW-20 | [build] [operator] | Not run in game. `c_ANIM_SLOW_BLEND` 0.45 (`core/slow_walk.galaxy`): `gf_AnimFullSet` uses it when the new or the old lower state is slow (the jump resume blend still wins); `gf_AnimFullClear` and `gf_AnimUpperClear` send `AnimClear <bracket> 0.450` out of a slow state; the arm clips are configured with it; `gf_AnimUpperSet` uses at least it out of the slow arms. In game: `slow_*` windows `LowerBlendMs` / `UpperBlendMs` (last play or clear, `gv_slowLowerBlendMs` / `gv_slowUpperBlendMs`): 450 at `slow` and `after`; negative: `ref` not 450. Arms only where not aiming. Host `test_slow_blend_is_three_times`. Unconfirmed: that `AnimClear` takes the blend time as its second argument (used the same way in `turn_anim.galaxy`). Smoothness: operator |
| R-SLOW-21 | [build] [operator] | Not run in game. Design: 16 speed levels, one buff at a time on the hero: `SCOBASlowWalkRamp01`..`15` (`BehaviorData.xml`, `MoveSpeedMultiplier` 1 - 0.7 k / 16) and level 16 `SCOBASlowWalk` (0.3; operator 2026-11-22, was 0.4). `gf_SlowWalkApply` (every anim tick, 0.05 s) moves `gv_slowRamp` 0..1 at 1 / `c_SLOW_WALK_RAMP` (1.0 s) per game second, the level is the nearest k. `gf_SlowWalkAllowed` false (jump, intro, death, not Tosh): level 0 at once. `gv_slowOn` is the wanted state, so the clips switch at the key. In game: `slow_*` `in1..4` / `out1..4` every 0.25 s after the key: speed property / `ref` property 0.825, 0.65, 0.475, 0.3 in and 0.475, 0.65, 0.825, 1.0 out, within 0.08; negative: the first sample not at the end value. `slow_switch` `levelAway` 0, `slow_jump_*` `pressLevel` 0. Waits for the final buff are 1 s longer (switch, intro, jump end). Host `test_speed_ramp_levels_are_linear`. Feel: operator |
| R-SLOW-22 | [tested] [operator] | `gf_SlowWalkClips` (Tosh only) gates the slow states in `gf_AnimSlowState` and the free-walk slow clip in `gf_AnimTick`: Kerrigan keeps her walk states, so `gf_AnimWalkScale` (`c_ANIM_STRAFE_RATE` x speed / `WalkAnimMoveSpeed`) and the engine's stock walk slow with the buff. Changed 2026-11-23: `KerriganSCOBA` `Speed` 2.6; `gf_SlowWalkBuff` gives her `SCOBASlowWalkKerrigan` (0.5) and the ramp `SCOBASlowWalkKerriganRamp01..15` (1 - 0.5 k / 16). `slow_kerrigan` (Point & Click, stock walk) and `slow_kerrigan_aim` (aim walk): `Buff` 0, 1, 0 at `ref`, `slow`, `after`, `BuffTosh` 0 at all three; `SpeedProp1000` 2600 and 1300 (+-20) at `ref` and `slow`; ramp in 0.875, 0.75, 0.625, 0.5 and out 0.625, 0.75, 0.875, 1.0 (+-0.08); travel 0.45..0.55 slow, 0.95..1.05 after; Tosh's walks: `BuffKerrigan` 0; lower state 0 and 2 kept; no slow clip, no slow arms at any window; aim: `WalkScale1000` slow / ref 0.45..0.55, engine lower clip time over 0.5 s game time at `slow` / its script scale 0.6..0.85 (T43 of SPEC-TPS: about 0.72) and under 0.6 x the same for the `ref` scale; the `ref` reading may wrap the 1 s clip and is raw only. Host `test_kerrigan_speed_and_buff`. Passed in `slowwalk/20261123-163132` (`hero` group, stamp `3a640a05615d-46100e5b8bedaa6d`, failures: 0): props 2597 and 1296, travel ratio 0.497 and 0.504, script clip scale ratio 0.499, engine rate per scale 0.739. The stock walk rate in Point & Click is not read: operator AC-SLOW-8 |
| R-SLOW-18 | [tested] [build] [operator] | `slow_jump_aim`, `slow_jump_pnc`: `slowJumps` 1, `pressBuff` 0, `pressFullState` (2 aim, 0 free), `pressBase` walk, one burst, `airBuff` 0, first clip a walk stride clip, no slow clip, `endBuff` 1 and `endFullState` 6 after landing; `check_slow`: foot phase offset within 0.02 of `c_ANIM_SLOW_GAIT_OFFSET`; host `test_jump_blend_is_minimal`; look: AC-SLOW-6 |

## 2. Facts

| ID | Fact | Source |
| --- | --- | --- |
| F1 | `src/SCOBA.SC2Map/Assets/Units/Terran/Tosh/ToshSCOBA.m3` is stale (marker `1`, 2026-11-11). The build bakes the model into `out/` (marker `44`). Measure the built model only. | `.character_anim_assets` markers |
| F2 | Built model: `Walk`, `Walk Leg`, `Attack Walk <dir>` are 667 ms; `Walk Slow` is 1000 ms, looping, no move speed. | `/tmp/opencode/stride2.py` |
| F3 | Planted-foot speed, model units/s: `Walk` and `Walk Leg` 2.598, `Walk Slow` 1.394 (0.537 of the walk). Baked slow clips 1.384..1.396 in all directions. | `/tmp/opencode/stride2.txt`, `/tmp/opencode/slowbake.txt` |
| F4 | Left foot furthest ahead: `Walk Leg` at phase 0.495, `Walk Slow Leg` at 0.500; right foot at 0.0 in both. The same foot phase maps 1:1 (offset 0.005). | `/tmp/opencode/lead.txt` |
| F5 | The move key triggers ignore modifiers; they fire with Shift held. | `systems/movement.galaxy` 156-400 |
| F6 | Shift: before 2026-11-21 the FOV zoom key (`gv_zOOM`); no other trigger uses Shift (all Shift modifier states are Ignore). Z was unused. | `core/constants.galaxy`, `rg TriggerAddEventKeyPressed` |
| F7 | The speed property shows `SCOBASlowWalk`: 1.550 with it, 3.101 without; engine travel 1.545 and 3.099 per s. (SPEC-JUMP F16 found the burst not shown; this buff is.) The slow clip rate reads the property. | `slowwalk/20261121-162021` |
| F11 | With the Chase toggle on stand, a Point & Click move order is stopped (`gt_DisableClickMove`) and `SCOBAStandRoot` holds the hero; the W loop in free mode gave no travel too. The harness runs the no-hold scenarios with Chase on. | `slowwalk/20261121-162021`; same symptom `jump/20261119-145013` `jump_freewalk` moved10=4 |
| F8 | In Point & Click without a hold, the hero turns to its travel (`gf_UnitTurn` in the W, S loops) and the actor plays the stock `Walk` (lower state none). TPS strafes always, except during a middle hold. | `movement.galaxy` 218-241, `strafe.galaxy` `gf_StrafeHoldSync` |
| F9 | `c_JUMP_BLEND` is 0.04 s, already minimal. | `core/jump.galaxy` 26 |
| F10 | File limits: `systems/`, `scripts/`, `scripts/testkit/tests/` are full (56); `validate-map.py` is at 512 lines; `jump.galaxy` at 501. | `find -maxdepth 1 -type f`, `wc -l` |

## 3. Design

### 3.1 Input and speed (`systems/input.galaxy`, `core/slow_walk.galaxy`)

- `gt_SlowKeyDown`, `gt_SlowKeyUp`: `gv_sLOWWALK` (Shift) press and release, all
  modifiers ignored. Both call `gf_SlowWalkSet(p, on)`, the single entry
  also used by the harness.
- The press is in the scene input hold (`gf_SceneTrigger` 43,
  `c_SCENE_TRIGGERS` 44). The release is never held back, so a key let go
  in a scene does not stay down.
- `gf_SlowWalkWanted(p)`: key held, not `gv_introActive`, hero alive, hero
  is Tosh, no jump (`gv_jumpPhase` none).
- `gf_SlowWalkApply(p)`: puts `SCOBASlowWalk` on the hero when wanted and
  takes it off the unit that has it (`gv_slowUnit`) when not, or when the
  hero changed. Called by `gf_SlowWalkSet`, the jump press, and every anim
  tick (0.05 s): hero switch, death, intro end and jump end take effect on
  the next tick.
- `SCOBASlowWalk`: `CBehaviorBuff`, hidden, `MoveSpeedMultiplier="0.3"` (was 0.4, before that 0.5), no
  duration. Point & Click move orders slow with it; no PNC code changed.

### 3.2 FSM (`systems/animation_fsm.galaxy`)

- States `c_ANIM_LOWER_WALK_SLOW` 6, `c_ANIM_LOWER_WALK_SLOW_BACK` 7,
  `c_ANIM_LOWER_COUNT` 8.
- `gf_AnimSlowState(p, state)`: walk to slow walk while `gv_slowOn`, and
  back when it is off. Idle and turn pass through.
- `gf_AnimTick`:
  - aim: the lower state goes through `gf_AnimSlowState`.
  - strafe hold: the same; the forward exception (stock walk) does not
    apply to the slow states.
  - no hold, `gv_slowOn`, moving: `WALK_SLOW`, direction forward (F8).
  - turn in place: unchanged.

### 3.3 Clips and rate (`animation_config`, `animation_aim`, `animation_bracket`)

- `gf_AnimConfigAimSlow`: `Attack,Walk,Slow,<dir>` per direction, for both
  slow states, Tosh only.
- `gf_AnimWalkScale` for the slow states: `c_ANIM_SLOW_RATE` (1.66, operator
  2026-11-27; was 1.33, 1.25) x speed property (with the buff, F7) /
  `c_ANIM_SLOW_STRIDE` (1.61 game units/s at rate 1). The arms play at the
  same rate (`gv_slowGaitScale`).
- `gf_SlowWalkGaitMark`: the slow clip phase, reset when a slow clip
  starts, folded when its rate changes.

### 3.3a Upper body (R-SLOW-19, `systems/input.galaxy`)

- Upper states `c_ANIM_UPPER_WALK_SLOW` 10 (`Walk,Slow,Arm`) and
  `c_ANIM_UPPER_WALK_SLOW_BACK` 11 (`Walk,Slow,Arm,Back`),
  `c_ANIM_UPPER_COUNT` 12; set in `gf_AnimConfigAimSlow` (Tosh only).
- `gf_AnimTick`, not aiming, no attack, no pose hold:
  `gf_SlowWalkUpperState` picks 10 with a slow leg state, 11 when the
  direction is back-left, back or back-right (the reversed leg clips), else
  none (the stock clip, as before).
- `gf_SlowWalkUpperPlay`: on `SCOBAUp`, looping, blend 0.15, rate =
  the leg rate (`gv_slowGaitScale`), start time = the leg phase
  (`gv_slowGait`, folded to now) x `c_ANIM_SLOW_CYCLE`. A pose or an
  attack on the bracket is cleared first.
- `gf_SlowWalkGaitMark`: a leg restart plays the arms again from 0 with the
  blend; a leg rate change sets the arm rate.
- An attack start clears the arms first (same priority 10). Aiming plays
  the aim pose on `SCOBAUp`, which replaces them. No target pitch tick in
  the arm states.

### 3.4 Jump (R-SLOW-18, `gf_SlowWalkJumpPress`)

- Called by `gf_JumpPress` after the phase is set, before the base pick.
- From a slow state: the walk phase becomes the slow phase plus
  `c_ANIM_SLOW_GAIT_OFFSET` (0.0, F4), so the walk jump stride matches the
  feet. `gv_animFullState` becomes the regular walk the jump reads: `WALK`
  or `WALK_BACK` with aim or strafe, none in free walk (stock walk).
- `gf_SlowWalkApply` then takes the buff off: the jump is a regular walk
  jump with the burst. The Start clip plays with `c_JUMP_BLEND` (F9).
- After the landing recovery the next anim tick puts the buff back and
  plays the slow clip, while Shift is held.

### 3.5 Clips (`scripts/walkanim/slow.py`)

- `character_anim_assets.generate_model(..., slow=True)` for `SLOW_HEROES`
  (Tosh): `Walk Slow` to `Walk Slow Leg` on the lower bones (`make_clip`),
  then `make_slow_groups`: one `Attack Walk Slow <dir>` per
  `AIM_DIRECTIONS`, yaw and reverse as the aim walk. `make_slow_arms`:
  `Walk Slow Arm` (`Walk Slow` on the `BoneSpine01` subtree, priority 10)
  and `Walk Slow Arm Back` (the same reversed). `MARKER_VERSION` 45.
- `check_slow` (called from `jumpanim.validate.check_jump`, F10): clip set,
  lengths, lower bones only, script clip table, `c_ANIM_SLOW_STRIDE` within
  2 % of the measured stride (walk calibration: WalkAnimMoveSpeed 3 x slow
  / walk planted-foot speed), `c_ANIM_SLOW_GAIT_OFFSET` within 0.02 of the
  measured foot phase offset.

### 3.6 Harness (`scripts/testkit/galaxy/slowwalk.galaxy`, `profiles/slowwalk.py`)

- Groups: `walk` (`slow_free`, `slow_pnc`), `mode` (`slow_strafe`,
  `slow_back`, `slow_aim`), `hero` (`slow_kerrigan`, `slow_switch`,
  `slow_intro`), `jump` (`slow_jump_aim`, `slow_jump_pnc`).
- A walk scenario has three 1 s travel windows in one walk: `ref` (no Shift),
  `slow`, `after` (0.25 s after the release). Each records engine travel,
  raw steps per 0.25 s, buff count, slow flags, lower state, direction,
  clip, clip rate, speed property, facing, orders.
- `slow_intro` sets `gv_introActive` for 0.3 s only.

## 4. Files

| File | Change |
| --- | --- |
| `core/slow_walk.galaxy` (new), `main.galaxy` | constants, globals, triggers; include and init |
| `systems/input.galaxy`, `header.galaxy` | slow walk functions and key triggers |
| `core/animation.galaxy` | lower states 6, 7, count 8 |
| `systems/animation_fsm.galaxy` | `gf_AnimSlowState`, tick |
| `systems/animation_config.galaxy`, `animation_aim.galaxy`, `animation_bracket.galaxy` | slow clip table, rate, phase |
| `systems/jump.galaxy` | `gf_SlowWalkJumpPress` call |
| `systems/scene.galaxy`, `core/scene.galaxy` | Shift press gated |
| `Base.SC2Data/GameData/BehaviorData.xml` | `SCOBASlowWalk` |
| `scripts/walkanim/` (new), `character_anim_assets.py`, `jumpanim/validate.py` | bake and build check |
| `scripts/testkit/galaxy/slowwalk.galaxy`, `profiles/slowwalk.py`, `profiles/registry.py`, `scripts/playtest.sh` | in-game tests |
| `scripts/testkit/tests/test_character_anim.py` | `SlowWalkTest` |

## 5. Known limits

- The arm phase is set from the script's leg phase; no native reads the
  actor's clip time, so arms and legs in step is an operator check
  (AC-SLOW-7).
- A real Shift press is not tested (O-SLOW-4, AC-SLOW-5).
- The free-mode W loop moved nothing in the harness (F11). The no-hold
  scenarios use Chase on; whether the W loop moves with Chase on is read
  from `slow_free` raw steps.

## 6. Runs

The runs below used Alt (the key change came after them; the harness calls
`gf_SlowWalkSet`, so the key does not change what they test).

| Run | Build stamp | Result |
| --- | --- | --- |
| `slowwalk/20261121-162021` (all) | `5cada69f13ab-e1e95c407e2fb83f` | 17 failures: no travel without a hold (F11); clip rate half (`scale1000` 481 vs 960: the buff was applied twice, F7). Fixed. |
| `slowwalk/20261121-162447` (all) | `5cada69f13ab-2f311d98d606fb7f` | 6 failures, no ScriptError: `slow_free` (W loop, no travel: ref 0, slow 0, after 0; F11) and `slow_jump_free` (same walk, stand base). All other scenarios pass: travel 0.499 of normal (386 vs 774 per 0.25 s), back to 774 after release, rate 963 vs 960. |
| `slowwalk/20261121-162727` (jump) | `5cada69f13ab-2f311d98d606fb7f` | 0 failures, no ScriptError, 31 checks: `slow_jump_aim`, `slow_jump_pnc` (replaces `slow_jump_free`). |
| `slowwalk/20261123-163132` (hero) | `3a640a05615d-46100e5b8bedaa6d` | 0 failures, no ScriptError, real clicks 0. Kerrigan 2.6 and 1.3, her own buff and ramp (R-SLOW-22). |
| `slowwalk/20261123-163642` (all) | `3a640a05615d-46100e5b8bedaa6d` | 21 failures, the same as `20261123-114920`: `slow_free` no travel (F11), slow blend 449 vs 450 ms. Kerrigan and every `BuffKerrigan` negative pass. |

Not yet: a full-suite run with 0 failures. `slow_free` fails on the W loop
(F11), which also fails `jump_freewalk` (`jump/20261119-145013`).

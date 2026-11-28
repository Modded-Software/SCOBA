# SPEC-TPS: WASD / TPS Mode

**Date:** 2026-11-14
**Status:** Built. Section 4 gives the state of each requirement and the run
that backs it. Section 9 lists what only the operator can judge. Section 10
lists what is not tested.
**Requirements:** [REQ-TPS](../requirements/REQ-TPS.md)

## 1. Principle

TPS is a second input layer over the same engine behavior that Point & Click
uses. The engine owns the weapon effects, the damage, the sound, and the
cooldown clock. Outside aiming, script translates the crosshair and the mouse
buttons into the same orders Point & Click issues.

The aim shot differs in one point. It holds no attack order, because an
attack order stops a walking hero (T27, T29). Script asks the engine to run
the weapon's own effect and starts the weapon's cooldown with the time in the
weapon data.

TPS adds no ability and no second cooldown. It copies no weapon value.

## 2. Labels

State of a design item:

- **[tested]**: built, and a programmatic in-game check passed in the named run.
- **[built]**: in the code. No passing check for this contract.
- **[operator]**: only a person can judge it. Listed in section 9.

Source of an engine fact:

- **[stock]**: read in stock game data or the natives file.
- **[pnc]**: fact of that number in
  [SPEC-POINT-AND-CLICK](SPEC-POINT-AND-CLICK.md) section 3.
- **[probe]**: measured in the named run. Raw values, not a test verdict.

Runs are under `out/test-runs/`. The full suites that back section 4 are
named in section 12. The `controls` and `rungun` profiles have no real-click
guard; `tps` and `combat` assert `RealClicks` 0.

## 3. Engine Facts

| ID | Fact | Source |
| --- | --- | --- |
| T1 | A unit holds at most 32 abilities. Both heroes hold 32. | [pnc] F16 |
| T2 | An `attack` order on a unit fires the stock weapon. The effect-used event fires once per shot. | [pnc] F5, F9 |
| T3 | `SCOBAAttackEnd` ends an attack order after one shot. | [pnc] F2 |
| T4 | The weapon effects start the `Weapon Attack` button cooldown on every shot. | [pnc] F14 |
| T5 | `UISetCursorVisible(group, false)` hides the cursor. Galaxy has no getter for it. | [stock] natives |
| T13 | The screen-centre ray passes through the point the camera follows at the camera height offset (0.9), along the camera yaw and pitch: the hero at rest, the shoulder proxy while aiming. Engine hover and script pick on a Zergling at 3, 5, 8, 12 agree within 0.1 to 0.8 degrees in pitch and yaw, at rest and in aim. The camera distance does not move the ray. | [probe] `pncprobe/20261115-224549` (measure), `pncprobe/20261115-231002` (match) |
| T33 | The engine hover is dead while `CameraForceMouseRelative` is on. A hidden free cursor still picks. | [probe] earlier `pncprobe` hover runs |
| T34 | Mouse down raises `CameraGetPitch`: positive pitch looks down. | [probe] `pncprobe/20261115-223159` |
| T36 | `UnitInRangeAndAbleToAttackTarget` needs the hero to face the target: false at distance 1 to 2 while aiming (hero facing 14 to 27 degrees off, shoulder ray) and false at every distance with the hero facing away. Not a range check. | [probe] `pncprobe/20261116-145352`, group `inrange` |
| T35 | A unit position has no height; `UnitGetHeight` gives it (Overseer 7.0). | [probe] `tps/20261115-213703` |
| T14 | All three hero weapons exclude `Hidden` and `Invulnerable` targets. `RazorTalons` requires `Ground`. Stock Psi Blast has `MinimumRange` 2; the map sets 0 (R-TPS-63). | [stock] weapon data |
| T15 | Stock `InvisibleTargetDummy` is unselectable, uncommandable, 1000 life, and carries `ImmuneToDamage`. | [stock] swarm unit data |
| T19 | `attack` command 0 on an own unit is valid for both heroes. Without a block the unit takes full damage. | [probe] `pncprobe/20261114-185541`, `tps_ally_*` |
| T23 | `attack` command 0 on a neutral `InvisibleTargetDummy` is valid for both heroes. One shot, the order ends, the hero does not move, the proxy keeps 1000/1000. `UnitSetHeight` raises it; the height reads back. | [probe] `pncprobe/20261114-201119` |
| T24 | A `DamageResponse` with `Location="Attacker"` on the hero cancels damage to own and allied units and leaves enemy damage alone. Own Marine 45/45, enemy Marine dies, both heroes. Without `Location="Attacker"` the own Marine died. | [probe] `pncprobe/20261114-202552`, `pncprobe/20261114-202433` |
| T25 | `UnitWeaponPeriod` read 16.0 for Tosh while the attack cooldown ran about 1 s. The value is not seconds. No code depends on it. | [probe] `tps/20261114-211403`, `tps_shot_walk` `AimPeriodMs` |
| T26 | `CameraGetTarget` read (12.0, 8.0) in all 27 snapshots while the hero stood near (184, 192). It does not follow the hero camera. | [probe] `controls/20261114-210112` |
| T27 | The strafe walk step issues `move` with replace whenever the hero has no move order. It replaced a fresh attack order before the weapon effect: no shot, cooldown spent. | [probe] `rungun/20261114-210757` |
| T28 | The engine adds 2 to the hero weapon range (`UnitDirectControl`). Data `Range` 12 reads 14.0 for Tosh; 10 reads 12.0 for Psi Blast; `RazorTalons` reads 3.0. | [probe] `tps/20261114-225316`, `pncprobe/20261114-230331` |
| T29 | An attack order on a walking hero, with the move issued after the shot: one shot, and the walk path falls behind the walk without a shot. | [probe] `pncprobe/20261114-232735`, `walk_order` |
| T30 | The auto twin weapon fires while walking, but not at the neutral proxy (0 shots), and it picked a nearer decoy over the chosen target. It cannot be steered. | [probe] `pncprobe/20261114-232735`, `walk_auto_proxy`, `walk_auto_idle`, `walk_auto_decoy` |
| T31 | `UnitCreateEffectUnit(hero, "SCOBAToshShot", target)` on a walking hero: one shot, the walk path equals the walk without a shot, the target lost 35 life. The button clock started (750 ms); the weapon cooldown link read 0. | [probe] `pncprobe/20261114-232735`, `walk_effect` |
| T32 | Psi Blast killed an enemy Marine at distance 3.0. At 3.5, 4.0, 4.5, 5.0, and 9.5 the weapon effect event fired and the Marine kept full life, also 3.85 s later. Same at 4.0 and 5.0 with the data `Range` set back to 4. Cause: T37. The kill at 3.0 was not examined again (the talons read range 3.0 then, T28). | [probe] `pncprobe/20261114-230104`, `pncprobe/20261114-230331` |
| T41 | Watch, `combat psiwatch`: with `SCOBAAttackCooldown10` as `LaunchEffect` of `PsiBlastLaunchMissile`, the missile was drawn from the shooter's feet to its head for the stock `Kerrigan`, `KerriganSCOBA` and a Hydralisk firing Psi Blast; Needle Spines from `KerriganSCOBA` and the Hydralisk drew right. A stock `MissileDefault` did not change it. With the clock beside the missile in an effect set it draws right (operator). | [operator] `combat/20261122-160534`, `combat/20261122-152927`, `combat/20261122-161915` |
| T42 | `CEffectEnumArea` `Arc` 90 from Kerrigan, created at a point ahead, on herself, or by a persistent at her: the same enemies were hit at facings 49 and 139, in a world band about 250 to 295 degrees. The arc did not follow her facing. | [probe] `combat/20261123-100054`, `combat/20261123-100936` |
| T44 | `CameraGetTarget` of a hero-following camera read (12, 8), far from the hero at (188, 186), on most 0.02 s ticks while the view did not move. The ground clamp then measured the wrong ground and the distance jumped (operator 2026-11-23: bounce, then jumps every 0.5 s). Fix: `gf_CameraSafeDistance` uses the hero's position when the read is over `c_CAM_TARGET_LOST` (40) from the hero, and its height offset is the camera's own (`gf_CameraHeightTotal`, was 1.35 x scale). Group `combat camclamp`: pitch sweeps in TPS and PNC settle on the clamp with no reversal, the eye stays above the ground; negatives: walking and the free arm keep the full arm. | [tested] `combat/20261123-150027`; bounce: `combat/20261123-144957`, `145745` |
| T43 | The swing clip on a bracket, 0.437 game s per reading, the clip time it advanced (ms) at time scale 1, 1.333, 2, 2.5, 2.667, 3: 311, 436, 625, 811, 875, 936. Linear in the scale, about 0.72 clip s per game s at scale 1; readings step by 62.5 ms. | [probe] `combat/20261123-112703` |
| T37 | With `ImpactLocation` `TargetUnitOrPoint` on `PsiBlastLaunchMissile` (the map's data since `e2ba12d`), the `KerriganWeapon` missile flew to its target at 2.0 to 8.0 and `PsiBlastDamage` fired at the target's place with no target unit: life 500 stayed 500, by effect, by attack order and by the aim click. The same shot with `TargetUnit`, written to the catalog at run time, dealt 25 to the Zergling; the neutral proxy got a 0 damage event and kept its life. `PsiBlastDamage` alone at the unit dealt 25. | [probe] `combat/20261122-113428`, `psi_fx_*`, `psi_order_*`, `psi_unit_04`, `psi_unit_proxy`, `psi_direct_04` |
| T38 | The map's `Kerrigan` unit carried the stock `PoisonNova` ability (swarm.sc2campaign: autocast on, radius 2, 20 damage, cooldown 10 s, its model on the caster). With an enemy at 2.0 it hit for 20 on its own; with the ability disabled it did not. No nova hit at 3.0 or beyond. | [probe] `combat/20261122-113428`, `psi_nova_02`, `psi_nonova_02`, `psi_fx_03` |

Facts T16 to T22 of the earlier draft (Barrage on a point, `PointSetHeight`
dropped by orders) were measured in `pncprobe/20261114-185541` and
`pncprobe/20261114-192859`. The design does not use point orders, so they are
not repeated here.

## 4. Requirement State

| Req | State | Evidence |
| --- | --- | --- |
| R-TPS-1 | [tested] effect name, effect event, damage, cooldown, button clock. Muzzle, sound, animation [operator]. | `tps` group `shot`: `ShotEffect`, `EarlyCdMs`, `EarlyBtnMs` |
| R-TPS-2 | [built] | One strafe step, one left-click result (`gf_LeftClickTarget`), one effect handler. The UI floater is a new module: a world text tag cannot show at the sky (R-TPS-73). |
| R-TPS-3 | [built] | The five aim-shot abilities are removed. The build validator fails if their ids return. No in-game ability count check. |
| R-TPS-10, 11 | [tested] | `tps` group `move` |
| R-TPS-12 | [tested] | `tps_head`: torso pitch step 0 outside aiming |
| R-TPS-13 | [built] Changed 2026-11-21 to the R-TPS-16 look point; not run in game. Look and direction [operator]. | `tps_head` |
| R-TPS-14 | [built] Head off while aiming; not run on the current build. Torso nod axis from the rest pose (2026-11-22): [build] `heroanim.validate.check_nod`; direction on screen [operator]. | `tps_head`, `tps_head_lead` `taimdown`; 5.2a |
| R-TPS-15 | [built] | TPS uses the right-hold step and clips. No check compares the two walks. |
| R-TPS-17 | [tested] script state; look [operator] | `tps` group `pose`: `tps_pose_auto`, `tps_pose_walk`, `tps_pose_single`, full suite run `tps/20261116-235526`. 5.9 |
| R-TPS-18 | [build] every walk direction clip keeps the legs rigid and moves the feet off the forward path (`walkanim.strafe.check`); not run in game. The look [operator]. | 5.2a |
| R-TPS-19 | [build] every pitch clip is one closed 4 s loop with moving tracks; Tosh's are still. [built] phase sync; `combat` group `kerrigan` (`breath_kerrigan`, `breath_tosh`) not run. The look [operator]. | 5.2a |
| R-TPS-63 | [build] unit weapon slots, `MinimumRange` 0 (`validate_aim_shot.py`). [failed] `combat/20261122-144438` group `kerrigan`: the engine reports 3 weapons, the third `RazorTalons`. Changed 2026-11-23: `gf_HeroWeaponsSet` removes it; the talons auto twin is added. Not run. | 5.5a |
| R-TPS-66 | [build] swing data, F binding, weapon removal (`validate_aim_shot.check_kerrigan_talons`). Group `talons`: not run. | 5.5b |
| R-TPS-64 | [build] `PsiBlastLaunchMissile` overrides no `ImpactLocation`, `LaunchLocation` or `LaunchOffset` (`validate_aim_shot.check_kerrigan_psi_blast`). [tested] `combat/20261122-144438` group `psiprobe`: 25 damage on the target by effect at 2 to 8, by attack order (PNC) at 4 and 8, the aim click at the proxy keeps 1000/1000. Where the missile is drawn: [operator]. | 5.5a |
| R-TPS-65 | [build] no `PoisonNova` ability or button on `Kerrigan` and `KerriganSCOBA`. [tested] `combat/20261122-144438` `psiprobe`: `novaExists` false, no nova hit. | 5.5a |
| R-TPS-16 | [built] Changed 2026-11-21 to hold on the camera target (was a lead); not run in game. Look, yaw direction, Kerrigan [operator]. | `tps_head_lead` |
| R-TPS-20 | [tested] script flag. The cursor itself [operator] (T5). | `tps` group `cursor` |
| R-TPS-21, 22 | [tested] | `tps` group `cursor` |
| R-TPS-23 to 26 | [tested] crosshair kind, Tosh. Colors [operator]. Kerrigan not tested. | `tps` group `shot` |
| R-TPS-27 | [operator] | |
| R-TPS-30 to 33 | [tested] flags | `tps` group `cursor` |
| R-TPS-34 | [built] | The Alt triggers are removed. No key test. |
| R-TPS-35 | [tested] no aim in the free-cursor state; the free-cursor state ends aiming | `tps` group `cursor` |
| R-TPS-36 | [tested] the state holds after the release and ends on the switch to Point & Click. No camera lock: build check. That the real cursor is free is [operator]: the harness has no real mouse. | `tps_cursor` `tmid`, `tend`; `validate_aim_shot.py` |
| R-TPS-37 | [built] camera data, build check. The effect on a real drag is [operator]. | `validate_aim_shot.py` |
| R-TPS-40, 41, 42, 44 | [tested] | `tps` group `aim` |
| R-TPS-43 | [built] | Galaxy has no field-of-view getter. [operator] |
| R-TPS-50 | [tested] standing and walking | `tps_shot_*`, `tps_shot_walk`, `rungun` |
| R-TPS-51 | [tested] | `tps_shot_noaim` |
| R-TPS-52 | Tosh [tested] damage. Kerrigan not tested (section 8). The damage text is the Point & Click floater; not asserted here. | `tps_shot_enemy` |
| R-TPS-53, 54 | [tested] Tosh | `tps_shot_far`, `tps_shot_ground`, `tps_shot_sky` |
| R-TPS-55 | [tested] with a Marine in range | `tps_shot_friendly` |
| R-TPS-56 | [operator] | |
| R-TPS-57 | [tested] one game loop after the shot effect: hero cooldown and button clock above 0 and at most the weapon cooldown, command on cooldown. The ring itself [operator]. | `gf_DbgClockRead` (`common.galaxy`): `EarlyCdMs`, `EarlyBtnMs`, `EarlyCmdCd`, `CdTimeMs` in every shot case |
| R-TPS-58 | [tested] second click in the same loop, while the cooldown runs (`AgainCdMs` above 0) | every standing shot case |
| R-TPS-59 | [built] | The crosshair and click targeting reject the proxy. Attacks on it by other units are not tested. |
| R-TPS-60 | [tested] | every standing shot case |
| R-TPS-61 | [tested] Tosh. The path over 1 s after the click is at least 97 % of the path over 1 s before it. Never an attack order, always a move order. Kerrigan [built]. | `tps_shot_walk` |
| R-TPS-62 | [tested] effect choice by proxy height, Tosh. That no impact shows or sounds is [operator]. Kerrigan has no air effect: not built. | `tps_shot_sky`, `tps_shot_far`, `tps_shot_ground`: `ShotEffect`, `ProxyZ100` |
| R-TPS-70 to 72 | [tested] counters | every shot case, `tps_shot_stop` |
| R-TPS-73 to 76 | [built], look [operator] | |
| R-TPS-77, 78 | [built], look [operator] | No test run. 5.6 |
| R-TPS-85 | [tested] frames hooked up, no dialog (build check). That the cursor picks a unit behind the overlay is [operator]: the harness has no real mouse. | `tps/20261115-010604`: `CrosshairHooked`, `TextHooked` |
| R-TPS-84 | [tested] script ray equals the engine screen-centre ray (`pncprobe` group `point`). [built] hit volumes on the new ray: group `pick` passed on the old ray only (`tps/20261115-222609`); its rerun produced no bank. Operator reported "looks better" live; no case named. | `pncprobe/20261115-231002`, 5.8 |
| R-TPS-80 | [tested] | `tps` group `target` |
| R-TPS-81 | [tested] attack command in the free-cursor state. A cursor left click in the free-cursor state is [built]. | `controls_attack` |
| R-TPS-82 | [tested] | `tps` group `target` |
| R-TPS-83 | [tested] flags after leaving TPS | `tend` of every `tps` scenario |
| R-TPS-90 | [untested] Tosh, Kerrigan, SCV: applied target height, desired arm, engine camera distance, aim pick eye height; the heights equal the generator's. No unit and a type without a height row are not known (`gf_CameraHeightKnown`, section `cam_known`); asking their height stops with a script error. The framing itself is [operator] (AC-TPS-25). Viking flying and after the landing morph: applied height = its form's offset (+ flight), arm 6. | `combat` group `camheight`; no run of the current code |

## 5. Design

### 5.1 Movement and body (R-TPS-10 to 15)

- `gf_StrafeHoldSync` turns strafe movement on for the whole of TPS, except
  in the free-cursor state.
- The hero carries `SCOBAAimNoTurn` while strafe is on. Script sets the facing
  to the camera yaw, standing and moving.
- The WASD loops and the periodic `gt_AimMoveTick` both call
  `gf_AimMoveStep`.
- The free-cursor state turns backpedal and the torso follow off (operator decision,
  closes O-TPS-1).

### 5.2 Head tilt and lead (R-TPS-13, 14, 16)

- `scripts/character_anim_assets.py` generates 99 static head-only clips,
  `Ready Cover 01` to `99`, from the `Stand` pose: a grid of 9 pitch steps
  (-30 to +30 degrees, 7.5 each; operator 2026-11-21, was +-15) by 11 yaw steps (-25 to +25, 5 degrees each). Clip
  number = (yaw step - 1) * 9 + pitch step. 99 is the two-digit token limit.
  Priority 14. The torso clips are unchanged.
- The yaw axis is the head bone's local axis closest to model up, taken from
  the rest pose at build time and printed in the build log. Tosh: `Z +1`.
  Kerrigan: `X +1`.
- The pitch axis is the head bone's local axis closest to model left-right
  (X), signed so + turns the face up (model forward is -Y): Tosh `X -1`,
  Kerrigan `Z +1`. Operator 2026-11-21: the head tilted sideways. Cause: the
  head took the torso pitch axis (`BoneSpine01` local `Y`); on `BoneHead`
  local Y is the forward/back axis (rest axes printed by a probe of the
  stock models: X (1, 0, 0), Y (0, 0.91, 0.40), Z (0, -0.40, 0.91)). Host:
  `HeadAxisTest`. Direction on screen: operator check.
- Look (operator 2026-11-21, replaces the lead): `gf_AnimHeadLookUpdate`
  takes a look point `c_ANIM_HEAD_LOOK_DIST` (8, operator "test with 8
  first") along the screen-centre ray past the camera target (the
  `gf_AimPickRay` ray, computed locally). From the eye, at
  `c_ANIM_HEAD_EYE_FRAC` (0.85, not measured on the model) of the unit
  height, it wants the yaw (minus hero facing, clamped +-25) and the pitch
  (up +, clamped +-30) to that point. Both ease with `c_ANIM_HEAD_LOOK_TAU`
  (0.15 s). The head holds while the camera is still. Tosh at camera pitch
  20: the point is about 2.6 below the eye, about 19 degrees down (the old 15 clamp held it fully down). The
  operator reported the lead as twitching and not looking at the target;
  cause not measured. The pitch replaces the R-TPS-13 0.4 scale.
- `gf_AnimHeadHoldStep`: a pitch or yaw step changes only when the angle is
  `c_ANIM_HEAD_HOLD` (0.75) step widths from the shown step's center, so
  the head does not flip between two steps. The head blend is one game loop
  (0.0625 s), so steps interpolate every frame.
- Not aiming only: yaw and pitch from the look. Aiming clears the head
  bracket.
- Test `tps_head`: camera pitch 0 level, 60 fully down, -45 fully up (was -25 at the 15 range).
  Test `tps_head_lead` (name kept): camera 60 degrees left, then right, of
  the facing; full range that way; negative: no new head clip in 1 s with
  the camera still. Both: each step part shows its eased angle, and the
  eased angle reaches the wanted one. Raw camera yaw and pitch, facing,
  wanted and eased angles recorded.
  Unconfirmed: that TPS leaves the standing hero's facing when the camera
  turns.
- The head tick runs at most once a game loop (62.5 ms); tests wait two loops.
- The head bone is a per-model setting; the build fails if the model lacks
  it. Tosh: `BoneHead`, the parent of the `Ref_Head` attachment. Kerrigan
  has no `Ref_Head`; the setting is `Bone29`. That choice and the tilt
  direction are [operator].
- `gf_AnimHeadTick` maps tilt plus lead to a clip and plays it in its own
  bracket, `SCOBAHead`. Level pitch is 20 degrees. It clears the bracket
  while aiming, in the free-cursor state, and in Point & Click.
- The build validator and a host test fail if the script step counts or
  ranges differ from the generated clips.
- O-TPS-2 is closed: the head turns sideways as the lead.

### 5.2a Hero rigs: torso axis, strafe legs, aim breathing (R-TPS-14, 18, 19)

- `scripts/heroanim/rig.py` holds one `HeroRig` record per hero model
  (`HEROES`): bones, leg roots, aim pose clip, breathing. The bake
  (`character_anim_assets.generate_model`) has no per-hero code. Turn axes
  are not configured: `pitch_axis` and `yaw_axis` read them from the rest
  pose (model forward -Y, up +Z, side X).
- Torso pitch (R-TPS-14): the local axis of the pitch bone closest to model
  left-right, signed so + turns the front up. Tosh `BoneSpine01`: `Y +1`
  (unchanged; his model is byte-identical). Kerrigan `Bone07`: `Z +1`.
  Operator 2026-11-22: her torso pitched on the wrong axis. Cause: her rig
  had Tosh's axis `Y`; on `Bone07` local Y is the forward/back axis (rest
  axes X (0, -0.13, 0.99), Y (0, 0.99, 0.13), Z (-1, 0, 0)), so the pitch was
  a roll. Build check `check_nod`: from the lowest to the highest pitch
  step the head moves back, and its sideways part is under half of the move
  (measured: Tosh 0.43, his aim pose stands side-on; Kerrigan 0.08).
  Kerrigan's kick axis (`Box04`, `Y`, copied from Tosh) is not changed and
  not checked.
- Strafe legs (R-TPS-18): a walk direction clip is the walk with the pelvis
  turned. Kerrigan's feet are keyed on `Dummy01` and `Dummy02`, which hang
  on `Bone_Link_Object`, not on the pelvis `Box01`: the thighs turned and
  the feet kept walking forward (shins moved 0.1 to 0.19 model units).
  `walkanim.strafe.turn_leg_roots` gives each rig `leg_roots` bone the
  pelvis turn, about the pelvis, at every key. Build check
  `walkanim.strafe.check`: in all 8 direction clips every distance between
  two leg bones equals the walk's within 0.01 (measured 0.00022), and a
  turned clip moves the leg roots at least 0.02 off the forward path
  (measured 0.174). Tosh has no leg roots: his feet hang on the pelvis.
- Aim breathing (R-TPS-19): `heroanim.breath.make_breath_pitch_group` bakes
  each of the 99 pitch steps as a loop of `breath_ms` (Kerrigan 4000). The
  pose frame of the aim clip (`Spell`, 350 ms) swings `breath_frames` (4)
  source frames to each side on a sine, 16 keys a breath; the last key is
  the first. Measured: hands move about 5 % of her height, chest 3 %. The
  operator asked for 8 frames; on her `Attack` clip that moved a hand 78 %
  of her height, so the operator chose this. Tosh: 0 frames, a still pose.
- Phase (`gf_AnimAimBreathSync`, `systems/animation_aim.galaxy`): a new
  pitch step is a new clip and would start the breath over. After each
  pitch clip play (aim pitch tick, target pitch) the script sends
  `AnimSetTime` with the game clock modulo the hero's breath period
  (`c_ANIM_BREATH_KERRIGAN`, 4.0; build check against the rig). Unconfirmed
  in the engine: that `AnimSetTime` right after `AnimPlay` moves the new
  clip. The Point & Click target pitch uses the same clips, so that pose
  breathes too.
- Tests: host `test_hero_rig.py`, `test_character_anim.py`
  (`TorsoAxisTest`). In game: `combat` group `kerrigan`, sections
  `breath_kerrigan` (one sync per pitch clip play; none with a still
  camera; the engine clip is 4 s long and stands at the game clock's place
  in the breath, raw values recorded) and `breath_tosh` (negative: pitch
  clips play, no sync). Not run.

### 5.3 Cursor, crosshair, free-cursor state (R-TPS-20 to 36)

| State | Mouse look | Cursor | Crosshair |
| --- | --- | --- | --- |
| TPS | on | hidden | shown |
| TPS, aiming | on | hidden | shown |
| TPS, free-cursor state | off | shown | hidden |

- `gf_TpsMouseDown` and `gf_TpsMouseUp` handle the middle and right buttons.
  The Alt path is removed.
- A middle click toggles the free-cursor state. In TPS `gv_mOUSEMIDDLE` holds
  that state, not the button. The press only sets `gv_tpsMiddleDown`; the
  release of a press seen in TPS flips the state. No mouse button is down when
  the mouse mode changes (R-TPS-33, 36). The mode switch clears both flags.
- Operator report on a toggle at the press: the first click freed the cursor;
  the third stopped mouse look but the cursor stayed hidden. Cause not
  measured: the harness has no real mouse.
- Operator report 2026-11-16, same symptom on the release toggle: after some
  aims a middle click stops mouse look, but the cursor does not act on the
  game UI; it goes to the OS. A second click restores mouse look. Aim start
  and end called `gf_ControlApply`, which re-sent `CameraSetMouseRotates`,
  `CameraForceMouseRelative`, and `UISetCursorVisible` with unchanged values
  every time. Hypothesis, not confirmed: the engine (or Wine) mis-tracks
  repeated sends.
- Send once [tested] `tps_sends`: `gf_ControlSendRelative` and
  `gf_ControlSendCursor` call the engine only when the value changes. Map
  start and the mode switch force one send (`gf_ControlForceSend`). The PNC
  orbit starts use the same gate. Ten aim cycles send nothing; each middle
  click sends one of each. Whether this cures the report is [operator].
- Operator report 2026-11-21, after the intro hid the cursor (R-INTRO-19):
  in TPS a middle click stops mouse look, the cursor stays hidden. Read from
  the code, not measured: `gv_introActive` is cleared at touchdown, so the
  rule asks for the cursor; the one script path that can drop the send is the
  send-once gate, if the engine cursor state differs from the cached value
  (the intro sends it inside `CinematicMode`). Change: each free-cursor
  toggle calls `gf_ControlForceSend` first, so the click always sends
  `CameraSetMouseRotates`, `CameraForceMouseRelative` and
  `UISetCursorVisible` once each. Aims still send nothing. Cursor on screen:
  [operator].
- The free-cursor state ends aiming and blocks it.
- The script never calls `CameraLockInput`. An earlier build locked the camera
  input for a middle hold; the operator reported the cursor still not free.
- With mouse look off, a middle drag is the engine drag scroll (the
  `CameraSetMouseRotates` reference says so). The map camera sets
  `ForwardScale` and `StrafeScale` to 0 for `Normal` and `Follow`, so the drag
  moves nothing (R-TPS-37). That these fields scale the drag scroll is
  [operator].
- The crosshair is one image tinted by kind: normal white, enemy in range
  green, enemy out of range gray, friendly yellow (`gf_ReticleKind`,
  `gf_ReticleColor`).

### 5.4 Aiming (R-TPS-40 to 44)

- `gf_AimBegin` and `gf_AimEnd`.
- `c_SCOBA_AIM_SIDE` is `right`. `gf_AimSideAngle` derives the arm angle.
- No behavior suppresses the hero attack while aiming.

### 5.5 Aim shot (R-TPS-50 to 62)

- `gf_AimShotPress` issues no order. It calls
  `UnitCreateEffectUnit(hero, effect, target)` once (T31). The effect is the
  `Effect` field of the hero's weapon, read from the weapon data
  (`gf_AimShotEffect`).
- The script-run effect does not start the weapon cooldown (T31). Script
  starts it with `UnitAddCooldown` and the weapon's `Cost.Cooldown.TimeUse`.
  The weapon effect starts the button clock itself (T4).
- The hero keeps its move order, so a shot does not slow the walk (R-TPS-61).
  An attack order was rejected (T27, T29). The auto twin weapon was rejected
  (T30).
- `gf_AttackOrder` stays the Point & Click attack. The aim shot does not call
  it.
- `gf_AimShotPress` picks the target and the pending outcome:

| Under the crosshair | Shot target | Pending outcome |
| --- | --- | --- |
| Enemy in range | the enemy | hit |
| Enemy out of range | proxy | `Out of range` |
| Ground or sky | proxy | `Miss` |
| Friendly unit in range | the unit | `Friendly Fire Disabled` |
| Friendly unit the hero cannot attack | proxy | `Friendly Fire Disabled` |

- The proxy is one stock `InvisibleTargetDummy` per player, owned by the
  neutral player (T15, T23). Script places it on the aim ray inside weapon
  range and raises it to the ray height.
- Friendly fire: the hero carries `SCOBAFriendlyFireBlock`, an attacker-side
  damage response that cancels damage to own and allied units (T24).
- A click on cooldown, or with a shot pending, does nothing (R-TPS-58).
- Air shot (R-TPS-62): `gf_TpsProxyPlace` stores the proxy height. Above
  `c_TPS_PROXY_AIR_HEIGHT` (0.1) a Tosh shot runs `SCOBAToshAirShot`:
  `SCOBAToshAirU`, a child of `ToshU` with damage 0, plus the Tosh button
  clock. Its actor `SCOBAToshAirAttack` has the Tosh launch model and sound
  and an empty impact map. A proxy on the ground keeps the weapon effect.
  Kerrigan has no air effect yet.
- A stop command does not cancel a fired shot: there is no order to cancel
  (`tps_shot_stop`).
- `gf_TpsShotExpire` drops a pending shot after `c_TPS_SHOT_TIMEOUT` (2 s).

### 5.5a Kerrigan: Psi Blast and the talons twin (R-TPS-63)

- `KerriganSCOBA` weapon slots: stock slot 0 `QueenOfBladesPsiBlast`
  stays; stock slot 1 becomes `QueenOfBladesPsiBlastAuto`;
  `RazorTalonsAuto` is appended. `SCOBAAttackSingle` disables both auto
  twins, so the engine uses the talons on its own only with Attack `auto`.
- The engine also gives her the stock `RazorTalons` (run
  `combat/20261122-144438`). `gf_HeroWeaponsSet` (`hero_return.galaxy`)
  removes it, from `gf_HeroAbilitiesDefault` and at her creation in
  `hero_switch.galaxy`.
- `QueenOfBladesPsiBlast` has `MinimumRange` 0 (stock 2), so she fires it
  at any distance.
- `gf_AimWeaponIndex` returns the first enabled weapon: Psi Blast.
- Build check: `validate_aim_shot.check_kerrigan_weapons`.
- Tests, `combat` group `kerrigan`: `psi_close_single` and `psi_close_auto`
  at distance 1.2, `psiblast_single` at 3.0. Engine state: 3 weapons,
  Psi Blast, its twin, `RazorTalonsAuto`. In `single`: shots are Psi Blast
  effects; negative: no talons effect. In `auto` at 1.2: a talons effect.
  Not run.

### 5.5b Kerrigan: talons swing on the TPS left click (R-TPS-66)

- TPS left mouse down (`gt_TargetClick`, gated by `gf_InputHeld`) calls
  `gf_TpsLeftPress` (`targeting.galaxy`). Aiming: the aim shot. Not
  aiming: `gf_TpsLeftClick` (UI target) and `gf_TalonsSwing`, at once; the
  release no longer targets. PNC left click is unchanged. F has no swing;
  Order mode and hire are Ctrl + E only (`input.galaxy`).
- `gf_TalonsSwing` acts only for `KerriganSCOBA`, alive, with the
  `SCOBA/Attack` cooldown at 0. It runs the button clock
  `SCOBAAttackCooldown10` and adds the `RazorTalons` cooldown (1 s; its
  `Period` is 1 too, for the auto twin; operator 2026-11-23), as
  the aim shot does. It does not stop a walk. Other heroes do nothing.
- The arc is picked in script (`gf_TalonsInSwing`): an enemy, ground,
  not hidden, dead, in stasis or invulnerable, within 1 edge to edge
  (`c_SCOBA_TALONS_REACH`), its centre within 45 degrees of her facing
  (`c_SCOBA_TALONS_ARC` 90). Each gets `SCOBATalonsSwingHit`: the stock
  `RazorTalonsDamage` (25) at 0 and 0.3 s. A `CEffectEnumArea` with `Arc`
  90 hit a fixed world band, about 250 to 295 degrees, at facings 49 and
  139, cast three ways (T42).
- Clip: `Attack Arm Alternate Close`, baked from the model's `Attack 01`
  (2 s), spine up and her back talons (`Bone34` chains, both sides,
  `rig.melee_roots`); the legs keep their clip (operator 2026-11-23). Her
  pitch pose (the `Spell` frame) is cleared for the swing: it covered the
  arms. It
  plays from 0 at 2.0 / 0.75 and holds 0.75 s (`c_ANIM_MELEE_PLAY_TIME`;
  operator 2026-11-23: 2x the first 1.5 s fit), then she is idle until the
  1 s cooldown ends (`gf_AnimAttackScale`, `gf_AnimAttackHold`). The auto
  twin `RazorTalonsAuto` plays it too.
- Build checks: `validate_aim_shot.check_kerrigan_talons`,
  `heroanim.validate.check_melee`.
- Tests, `combat` group `talons`, each press through `gf_TpsLeftPress`
  with TPS on: one enemy at 1.45 in front, two at
  +-30 degrees, one at 1.6: each loses 50 in 2 damage events. No enemy:
  she swings and the cooldown is about 1 s. A ring of 8 every 45 degrees
  from 22.5, at facings 50 and 140: only the two at +-22.5 are hit.
  Negatives: at 2.6, at +-90 degrees, behind, the other 6 of the ring: no
  damage; 3 presses within the cooldown: 1 swing; Tosh: no swing; the
  press while aiming and in PNC: no swing. Each enemy's angle before the
  swing is checked. Engine: the attack bracket holds the 2 s clip; clip
  time over game time 1.72 to 2.3 over 0.5 s (the old swing read 1.0); script rate
  2.67, hold 0.75 s; no pitch pose. A probe (the removed group `combat swingwatch`, run
  `20261123-112703`) read clip time over game time as about 0.72 x the
  scale at 1, 1.33, 2, 2.5, 2.67 and 3 (T43). Not run on this build.
- R-TPS-64: Psi Blast is a stock projectile (operator 2026-11-22: no
  special handling). The map does not override `PsiBlastLaunchMissile`.
  `QueenOfBladesPsiBlast` fires `SCOBAPsiBlastShot`, a set of the stock
  missile and the button clock `SCOBAAttackCooldown10`, as Tosh's
  `SCOBAToshShot`. Before, the clock was the missile's `LaunchEffect`:
  the missile was drawn from the shooter's feet to its head, with any
  shooter (T41). The stock impact `TargetUnit` gives `PsiBlastDamage`
  the target unit; the map override `TargetUnitOrPoint` caused T32 (T37)
  and is removed. A missed aim shot ends at the neutral proxy: a 0 damage event,
  which the floater, blood and XP scripts skip (`lv_damage <= 0.0`).
- R-TPS-65: the map's `Kerrigan` unit has no `PoisonNova` ability and no
  button for it (T38). Tosh keeps his. Open: with Kerrigan, the Offense
  talent tree and the abilities dialog still name Poison Nova; the
  operator has not decided what they show.
- Build check: `validate_aim_shot.check_kerrigan_psi_blast`.
- Tests, `combat` group `psiprobe`: one Psi Blast at an enemy at 2.0, 3.0,
  3.5, 4.0, 8.0 by effect and at 4.0, 8.0 by attack order; at the proxy in
  the air; by the real aim click. Engine state per game loop: the missile
  units, their distance and height; then the damage event's unit and
  place, every damage on the target with its effect, the life. Catalog:
  the missile's actors and models (`QueenOfBladesRangedAttackMissile`,
  `QueenOfBladesRangedAttack`, `KerriganWeapon`, `KerriganWeaponImpact`,
  all from liberty.sc2campaign) are valid entries. Negative:
  no Poison Nova on her and no nova hit; no talons effect; the proxy keeps
  its life; the damage effect alone launches no missile. Not run on the
  changed data.

### 5.6 Shot floaters (R-TPS-70 to 76, 79)

- Off (R-TPS-79, 2026-11-17): `c_SCOBA_SHOT_TEXT_ON` is false.
  `gf_UiFloaterShow` returns at once, and `gf_PncAttack` creates no
  `Out of range` text. Setting the constant true restores the behavior
  below. The pending outcome is still computed; the reticle is unchanged.
  Tests assert the counters `gv_tpsFloaterCount` and
  `gv_pncRangeFloaterCount` do not rise (`tps_shot_*`, `single_out_stand`).
- `gt_CombatAttackEffect` runs when the engine fires the weapon. If the fired
  target is the pending shot target, it shows the floater and clears the
  pending outcome. Nothing else creates these floaters.
- Overlay frames (R-TPS-85): the crosshair image and the four text labels
  are frames in `Base.SC2Data/UI/Layout/Custom/ScobaTps.SC2Layout`, under
  `GameUI/UIContainer/FullscreenUpperContainer`. Every frame has
  `AcceptsMouse` false. Script hooks them up (`gf_ReticleHookup`,
  `gf_UiFloaterHookup`) and only shows, moves, tints, and fills them. The
  frames are shared; each call names the player.
- Regression in `e2ba12d`: the texts were labels in a trigger dialog. From
  the first shot text on, the invisible dialog (860 x 200 px above the
  screen center) took the mouse and blocked the engine's cursor pick of
  every unit behind it. Found by the operator; confirmed by the operator
  (clickable before the first miss, dead after). The crosshair was a
  trigger dialog too and is moved with it.
- `systems/ui_floaters.galaxy` moves a label up, fades it, and hides it.
- `scripts/validate_tps_overlay.py` fails the build if a frame accepts the
  mouse, or if `aim.galaxy` or `ui_floaters.galaxy` creates a dialog.
- Font: style `SCOBAFloaterText`, height 32, in
  `Base.SC2Data/UI/FontStyles.SC2Style`. The build validator fails if the
  style is missing or below 28.
- `gf_FloaterCreate` stays for world floaters (damage, Point & Click). It
  takes the font size.
- Damage number size (R-TPS-77): `gf_FloaterDamageSize` maps the damage in a
  straight line from `c_FLOATER_SIZE_BASE` (32) at 0 to `c_FLOATER_SIZE_MAX`
  (72) at `c_FLOATER_DAMAGE_FULL` (1000) and above. The Point & Click
  `Out of range` text uses the base size. [built]; the look is [operator].
  Whether the engine draws a text tag at size 72 is not proven.
- Random start (R-TPS-78). UI texts: the text panel's lower edge is 40 px
  above the screen center (layout anchor), so no text covers the crosshair
  (R-TPS-73). Each text starts up to `c_UI_FLOATER_JITTER_X` (80)
  left or right and up to `c_UI_FLOATER_JITTER_Y` (30) higher, then rises
  `c_UI_FLOATER_RISE` (240 px) over its life.
  World floaters: `gf_FloaterCreate` moves the start point up to
  `c_FLOATER_JITTER` (0.5) in x and y, then rises at `c_FLOATER_RISE_SPEED` (1.05 per second, operator
  2026-11-27; was 1.40 earlier that day, before that 0.70) for its 1.6 s
  life: 1.68 high.
  [built]. That a positive label offset
  from the bottom anchor is upward is not measured.
- Assumption for O-TPS-3: the damage floater stays at the enemy.

### 5.7 Targeting (R-TPS-80 to 83)

- Not aiming: the left click and the highlight use the unit under the
  crosshair and call `gf_LeftClickTarget`, the Point & Click result.
- Free-cursor state: the handlers take the Point & Click path with the cursor.
- Aiming: the left click calls `gf_AimShotPress` only. It never calls
  `gf_UnitTargetSet`.
- `gf_PncRestore` ends aiming, clears the pending shot, removes the proxy,
  and hides the UI floaters.

### 5.8 Crosshair pick (R-TPS-84)

- One ray for the reticle, the status bar, the shot and the crosshair ground
  point: `gf_AimPickRay`. Origin `gf_AimCameraFocus` (hero, or the shoulder
  proxy while aiming) at hero height + `gf_CameraTargetOffset` (0.9 for
  Tosh, 5.10);
  direction from the camera yaw and pitch (T13). The old origin, 0.5 aside
  and 1.5 high, never hit a Zergling the engine hovered.
- The ray starts inside the hero; the pick skips the player's own hero.
- The pick has no practical range: `c_SCOBA_PICK_MAX_RANGE` 256 (the whole
  map). The reticle and status bar show for a unit at any distance. Only the
  ground point stops at `c_SCOBA_CROSSHAIR_MAX_RANGE` (20).
- In range (`gf_AimTargetInRange`): hero centre to the target edge (unit
  `Radius`) within `UnitWeaponRange` and not below the weapon
  `MinimumRange`; never for an invulnerable unit. Facing does not matter
  (T36). Beyond range: gray reticle and `Out of range`, no damage.
- Each unit is tested against its hit volume: spheres, capsules and boxes
  from the rest-pose m3 hit-test shapes, with actor `Scale` x model
  `ScaleMax` baked in, then scaled x1.15 about the unit origin
  (`HV_INFLATE`, `scripts/hitvolumes/galaxy.py`). The JSON keeps the
  measured shapes. Model facing is model -y (`c_HV_MODEL_YAW` 90).
- Hive, SCOBAOvermind and PsiDecimator (psi destroyer) are scenery: no hit volume
  (`HV_UNPICKABLE`), and UnitData sets them invulnerable, untargetable,
  with no collision and no footprint. `tps_pick_scenery` asserts the
  invulnerable state and the target filter only. Damage and collision are
  not tested: the `UnitDamage` probe took life from them and the Zergling
  path probe failed on the Marine control too (operator 2026-11-16: dropped).
- TerranDropPod is not pickable either (`HV_UNPICKABLE`): the escort pods
  fall through the lanes, and the m3 box is the whole fall path (reach
  147), not the pod. Before every stock type was measured it had no volume.
- ZergDropPod, ZergDropPodLarge and SCOBAHeroPod are not pickable either
  (`HV_UNPICKABLE`), for the same reason: m3 bounds boxes of reach 71, 47
  and 106. The lane and scenery pods are ZergDropPod
  (`libVCMI_gf_CreateDropPod`). The crosshair started inside a pod box 50
  to 58 away, picked the invulnerable pod, and turned gray over a Spine
  Crawler 3.4 away (SCOBAAIMLOG marks 2 to 5, operator 2026-11-27).
  pncprobe `roach` case `pod` reproduced it (5 failures) and passes after
  the fix (pncprobe 20261127-102041). Guard:
  `test_no_map_type_has_a_bloated_bounds_volume` fails on any type the map
  names with a bounds-only volume of reach above `HV_BOUNDS_REACH_MAX` (20)
  that is not in `HV_UNPICKABLE`. Overmind (reach 14) stays pickable.
- Data: `scripts/hitvolumes/measure.py` writes `scripts/data/hit_volumes.json`
  and `hitvolumes.galaxy` writes `scripts/app/data/hit_volumes_*.galaxy`.
  Measuring is a separate step: it reads the game install, the build does
  not. Unit types (`units.py`): every concrete `CUnit` of the stock stack
  (`resolve.STACK`, melee and campaign mods; no templates, no missiles),
  every map `CUnit`, placed unit and unit-create call, and every harness
  file below `scripts/testkit/galaxy/`. 3097 types: 2551 measured
  (1413 fuzzy, 24 tight, 1114 bounds), 546 without a volume, each with its
  reason in the JSON: no model (glue-screen dummies), a morph state drawn
  in another pose (burrowed units, lowered gates), a model path the stock
  data names but the storage lacks, or an m3 the reader cannot parse (12
  files).
- Actor of a type: same id, else `unitName`, else the actor its
  `UnitBirth` creates (morph states such as ArchiveSealed). `CActorMissile`
  counts as a unit actor (Dehaka, KerriganVoid). A model with
  `VariationCount` uses its `_00` file.
- Stale data (`hitvolumes/fresh.py`, called by validate-map through
  `galaxy.check_map`): each record keeps a key of the map's own inputs:
  actor and model entries on its chains, map actors that claim the type,
  and the bytes of a map m3. The build fails on a changed key or an
  unmeasured map type: `run hitvolumes.measure`. XML comments do not count.
  Stock data is not re-read: a game patch needs a manual measure.
- Measure time, 32 cores: 26 s (catalogs 9, find 1.3, extract 9 in
  parallel batches of 100, shapes 6 in a process pool). Serial (`--jobs 1`):
  111 s, same JSON. Before: 96 types, 24 s.
- Near types: scanned in a circle of range + `c_HV_NEAR_REACH`. Far types
  (reach above 20, 277 now): `gv_hvFarUnits`, one group kept by events
  (`gf_HvFarInit`: the units at start, then every unit that enters the map).
  It replaces one whole-map `UnitGroup` per far type on each pick. A unit
  that morphs into a far type is not added (not tested).
- Script size: the full table is 2548 types and 5205 shapes, one load call
  each. A test map with about 20 more harness lines failed to load: `Code
  jump out of bounds (try reducing the size of very large functions or
  triggers)` (`tps` 13:47 run, no bank). The map is likely at the script
  size limit (not confirmed).
- A type without a volume is not pickable and is recorded once
  (`gv_hvMissing`).

### 5.8a Crosshair range recorder (`systems/recorders/aim_log.galaxy`)

- Operator 2026-11-27: the crosshair sometimes turns gray on a close enemy
  in range ("like the hit volume disappears"), in TPS and in aim. Cause not
  found. Every launch of the shipped map records (operator).
- Player 1 only. Bank `SCOBAAIMLOG`, section `aimlog`, cleared at map start;
  `meta/build` holds the build stamp. At most 3000 entries.
- Entries: `mark` (key M: state now, then `before`, the last 30 polls of
  0.1 s), `gray` (shown reticle turned gray, at most once per second),
  `press` (left mouse press in TPS).
- State: shown and recomputed reticle kind, pick, range check and its
  inputs (weapons, enabled flags, ranges, `SCOBAAttackEnd`,
  `SCOBAAttackSingle`, `UnitDirectControl`), UI target, ray origin and
  direction, camera height, and each unit within 16 of the hero with the
  ray entry distance into its volume (`-1` miss, `-2` no volume).
- It changes no game state. Remove it when the cause is fixed.
- Roach probe: `pncprobe` group `roach` (`roachprobe.galaxy`,
  `profiles/pncprobe/roach.py`), Tosh and Kerrigan, Roach at 0.5 to 6 and
  16 (negative), TPS and aim, one aim shot each. Case `pod`: a ZergDropPod
  30 behind Tosh, a Roach 3 ahead; the pod must not be picked, the Roach
  must be picked and hit.

### 5.9 Shooting pose, Attack auto, not aiming (R-TPS-17)

- The Point & Click pose hold (SPEC-POINT-AND-CLICK 5.11) also runs in TPS.
  `gf_AnimReadyHold` adds one TPS gate: Attack `auto`.
- The auto weapon fires with no attack order (F4 there). In TPS the hold
  therefore rests on the 2 s linger after each shot. Measured: 0 of 64
  standing samples had an attack order (`tps/20261116-235345`).
- The pose is the target pitch pose (`gv_animTargetPitchStep`). The aim
  torso pitch (`gv_animAimPitchStep`) stays 0, so R-TPS-12 holds.
- Aiming clears the linger and owns the upper body. Switching to Attack
  `single` ends the hold at once.
- Tosh's attack clip plays at 2x the weapon-period rate, aiming or not
  (SPEC-POINT-AND-CLICK 5.11, `c_ANIM_ATTACK_RATE_TOSH`). The linger is
  unchanged.

### 5.10 Camera by unit height (R-TPS-90)

- Height of a unit type: the top of its measured hit shapes in
  `scripts/data/hit_volumes.json` (scale baked in, not the x1.15 pick
  inflation). Sphere: centre z + r. Capsule: the higher end + r. Box: centre
  z + the vertical extent of its three half axes.
- `scripts/hitvolumes/camera_heights.py` writes
  `data/camera_heights.galaxy`: `c_CAM_HEIGHT_REFERENCE` (ToshSCOBA, 0.9305)
  and one `gf_CamHeightType` call per type. `CAMERA_HEIGHT` pins a type's
  height: ToshSCOBA 0.9305 (operator 2026-11-21: Tosh actor scale 0.675,
  was 0.75, measured 0.8374; every camera unchanged). Host test
  `test_tosh_camera_kept_after_the_shrink`. `--check` and validate-map fail
  when it is stale. `main` loads it into a data table (`gf_CamHeightLoad`).
- `systems/camera/camera_height.galaxy`: `gf_CameraHeightKnown` (a valid unit whose type has a row), `gf_CameraUnitHeight` (stops with a script error
  for no unit or a type without a row, through `gf_CamHeightFail`), `gf_CameraHeightScale` = height /
  reference, `gf_CameraTargetOffset` = 0.9 x scale, `gf_CameraArm` = 1.5 x
  scale.
- Users: `gf_CameraHeightApply` (base of the applied height, then quake,
  jump, drop, flight), `gf_HeroApplyCamera` and map init (arm and height),
  `gf_AimPickRay` (eye height), the collision clamp (`gv_mARINE` 1.35 x
  scale; the old 2.3 for non-Tosh units is gone).
- The Viking keeps the arm `c_HERO_VIKING_CAM_DIST` 6. Its target offset
  follows the form: `SCOBAVikingHero` 2.9807 (offset 2.88, plus the flight
  height), `SCOBAVikingHeroAssault` 4.1436 (offset 4.01). Both measured at
  the in-game scale 2.55: actor `Scale` 3 x model `ScaleMax` 0.85 (`ScaleMin`
  is the same 0.85, so the engine has no choice).
- A morph keeps the unit and changes its type. `gt_CameraMorphTick` (0.125
  s) writes the height again, over 0.5 s, when the bound unit's type differs
  from the type of the last write. Before, nothing wrote it after the
  landing: the camera stayed at the flyer's base with no flight part and
  looked at the landed Viking's feet (operator 2026-11-19).
- Build check (`camera_heights.check_map`): every bound unit type
  (`BODIES`) has a height, and every measured actor scale equals the map's
  `ActorData` `Scale`. The JSON had no Viking types: it was measured before
  they existed.
- Measured values: KerriganSCOBA 1.7813 (offset 1.72, arm 2.87; was 0.9 and
  2.5), SCV 1.0172 (offset 0.98, arm 1.64; was 0.9 and 2.5).
- 2026-11-20: the SCV is the classic model at actor scale 2; its height
  is 2.0345 (not run in the game). The classic Command Center is 14.1710,
  its Orbital Command and Planetary Fortress forms the same (their actors
  have its scale), the classic Ultralisk 4.8761 (SPEC-HD-TEXTURES 12).
  6x6 gas (R-BASE-35): VespeneGeyser 1.2747 to 2.5493; new entries
  Refinery and AutomatedRefinery 4.9421, Extractor and AutomatedExtractor
  5.6112.
- Map init now turns camera height smoothing off for every hero, as the hero
  switch already did. Before, Kerrigan kept it on at init.

## 6. Module Structure

| Module | Role |
| --- | --- |
| `systems/strafe.galaxy` | Strafe for all of TPS. The walk step does not know about shots. |
| `systems/controls.galaxy` | Mode switch, middle and right button handlers, cursor state. |
| `systems/aim.galaxy` | Aim camera, aim side, crosshair kind and color. |
| `systems/aim_shooting.galaxy` | Crosshair ray (`gf_AimCameraFocus`, `gf_AimPickRay`), pick, proxy, pending shot, `gf_AimShotEffect`, `gf_AimShotPress`. |
| `systems/hit_volumes.galaxy`, `data/hit_volumes_*.galaxy` | Hit-volume ray tests and generated volume data. |
| `scripts/hitvolumes/` | Volume measurement, Galaxy generator, host ray reference. |
| `scripts/hitvolumes/camera_heights.py`, `data/camera_heights.galaxy`, `systems/camera/camera_height.galaxy` | Camera target height and arm by unit height (5.10). |
| `systems/ui_floaters.galaxy` | UI-layer floaters. |
| `systems/combat_fsm.galaxy` | `gf_AttackOrder` (Point & Click), root rules. |
| `systems/combat_cooldown.galaxy` | Weapon effect event: animation, pending shot, single shot. |
| `systems/targeting.galaxy` | `gf_LeftClickTarget`, `gf_TpsLeftClick`. |
| `systems/animation_aim.galaxy` | Torso pitch tick, head tilt tick. |
| `scripts/character_anim_assets.py` | Head clips, the split-body bake. |
| `scripts/heroanim/` | Hero rig records and axes (`rig.py`), aim breathing (`breath.py`), build checks (`validate.py`). |
| `scripts/walkanim/strafe.py` | Leg root turn of the walk direction clips and its check. |
| `scripts/attack_cooldown_link.py` | Cooldown link on the three hero weapons. |
| `scripts/validate_aim_shot.py`, `scripts/validate-map.py` | Build checks. |

## 7. Tests

- Entry point: `scripts/playtest.sh tps [group]`. Groups: `move`, `cursor`,
  `aim`, `head`, `target`, `pick`, `shot`, `hold`, `pose`.
- `SC2_TEST_GROUP=point scripts/playtest.sh pncprobe`, with the host pointer
  injector parking the hidden cursor at the window centre: engine hover
  against script pick (R-TPS-84). The start Medic (`gt_MedicSpawn`) and all
  other units near the lane are parked first.
- Host: `test_hit_volumes.py` checks shapes, scale, the generator, the
  `pick` cases, and the measured engine bands against the new and the old
  ray origin.
- The harness sets mode, hold flags, camera yaw and pitch, and spawns units on
  the aim ray. It calls the handlers the mouse events call. It does not send
  real mouse or key events.
- `scripts/playtest.sh rungun`: one aim click while walking.
- `scripts/playtest.sh controls`: mode switch, free-cursor state, and the attack
  command in the free-cursor state.
- Host tests: `scripts/testkit/tests/`. `test_character_anim.py` ties the
  head tilt constants in script, assets, and the `tps` profile together.

| Group | Asserts | Negative case |
| --- | --- | --- |
| `move` | Facing on the camera yaw while S and A move the hero; facing follows a camera turn. | Leaving TPS removes `SCOBAAimNoTurn`. |
| `cursor` | Input flags for TPS, aiming, free-cursor state. The state holds after the middle release; a second click ends it. Engine sends: each middle click sends mouse look and cursor once. | A right press in the free-cursor state does not aim. The switch to Point & Click ends the state. Ten aim cycles, and calls that change nothing, send nothing. |
| `aim` | Aim flag, anchor on the right, shorter camera arm. | Release restores the distance and removes the anchor. |
| `head` | Head step level, down, up with the camera pitch. Lead: a 60 degree turn left and right turns the head ahead within two game loops. | Step 0 in Point & Click, while aiming (also on a fast look down), in the free-cursor state, after leaving TPS. No lead 1 s after each turn. The turn right does not lead left. |
| `target` | Not aiming: the click sets the UI target. | The click never attacks. Aiming: the UI target is unchanged. |
| `shot` | Per outcome: shots +1, life, proxy, effect name, cooldown and button clock one loop after the shot, hero position, one text of the right kind. Walking: one shot, the walk keeps its speed. Weapon ranges. | Click while the cooldown runs, click when not aiming: no shot, no text. Walking: never an attack order. Air proxy: not the hit effect. No late damage 2 s after a miss. |
| `pick` | Medic head, Marine thigh and middle, Ultralisk front, Zergling at 18.5, Overseer body, Hive top, Marine before Hive, Thor chest with aim held (reticle, status bar, shot). | Above the Medic, beside the Marine and Zergling, behind the Ultralisk, under the Overseer, north of the Hive. |
| `pose` | Attack `auto`, not aiming: upper pose state and target pitch in every sample, standing and strafing; shots repeat; no bracket clear. | Aiming: hold off, aim state. Attack `single`: hold off at once, no shot. `single` with an enemy in range and in the arc: no pose. Torso pitch step 0. |
| `combat camheight` | Tosh, Kerrigan, SCV, flying Viking, Viking after `SCOBAHeroAssaultMode` after a hero switch: height = generator's, applied height = 0.9 x scale, desired arm = 1.5 x scale (within 0.01), engine distance = arm or clamp (within 0.05), pick eye = ground + offset. Invalid unit: 0.9 and 1.5. Host: `test_camera_heights.py`. | Kerrigan is not on 0.9, not on 1.5 or the old 2.5. Landed Viking: no flight part, height above 2. |
| `combat kerrigan` | 3 weapons: Psi Blast, its twin, `RazorTalonsAuto`; one Psi Blast effect per command at 1.2 and 3.0, with damage; a talons effect on its own in `auto` at 1.2. Breath: one sync per pitch clip play; the engine clip is 4 s and in step with the game clock. | No talons effect in `single`. No stock `RazorTalons`. No Poison Nova ability. No sync with a still camera. Tosh: no sync. |
| `combat talons` | TPS left press without aim: enemies at 1.45 in front, at +-30 degrees and at 1.6 lose 50 in 2 damage events; ring of 8 at two facings: the two at +-22.5 are hit; with no enemy she swings and the 1 s cooldown starts; the attack bracket holds the 2 s clip at 2x the old rate (engine clip time over game time). | At 2.6, at +-90 degrees, behind, the other 6 of the ring: no damage. Presses inside the cooldown: no swing. Tosh, aiming, PNC: no swing. No pitch pose. |
| `combat psiprobe` | One Psi Blast per case: the missile exists and reaches its target; the damage event names the target unit and lands there; an enemy loses 25; the engine's `ImpactLocation` is `TargetUnit`. `PsiBlastDamage` alone at the unit deals 25. | No Poison Nova ability, no nova hit. No talons effect. The proxy keeps its life. The damage effect alone launches no missile. |
| `pncprobe point` | Engine and script band centres within 2 degrees, pitch at 3, 5, 8, 12 and yaw at 5, rest and aim. Nothing but hero and target near the lane; Medic parked. | No script pick 4 degrees outside the engine band. |

Floater checks read script counters. They do not prove the text is visible.

## 8. Findings Outside This Phase

- T26: `systems/camera/camera.galaxy` reads `CameraGetTarget` for the camera
  collision sample. If the value is stuck as measured, the sample is taken at
  the wrong point. Not changed here. The pushed commit `b3988d1` has the same
  code.
- A friendly `Medic` 0.6 from the hero read as not attackable. The shot went
  to the proxy with the `Friendly Fire Disabled` text
  (`tps/20261114-211914`, raw `CrossType`). R-TPS-55 asks for a shot at the
  unit. Cause not found.
- `controls_collision_clamp distance: got=1 base=1` was a stale test, not
  a camera fault. The snap stored whole units; the Tosh arm is 1.5 and the
  clamp at pitch -60 takes it to about 1.13, so both read 1. The distance
  checks now read `Distance1000` and report to `summary.txt`:
  `controls/20261117-014522` base 1496, flat 1476, clamp 1128, restore
  1468, 0 failures.
  Not investigated.
- Kerrigan is a proof of concept. Psi Blast dealt no damage at any distance
  (T32, T37); fixed 2026-11-22 (R-TPS-64). The missile draws from
  shooter to target since the clock left its `LaunchEffect` (T41).
  With Kerrigan, the Offense talent tree and the abilities dialog still
  name Poison Nova, which she no longer has (R-TPS-65); not decided. The `tps` group `kerrigan` is deleted (operator
  2026-11-16). Kerrigan has no air effect (R-TPS-62).

## 9. Operator Checks

- The cursor is hidden in TPS and shown in the free-cursor state.
- Crosshair colors and their contrast.
- `Miss` is visible when aiming at the sky; floater size, position, motion,
  color.
- Muzzle effect, weapon sound, and attack animation on every aim shot.
- The proxy shows nothing: no model, bar, impact, or death.
- A shot at the sky travels upward.
- Head tilt outside aiming: amount and direction, both heroes. Kerrigan's
  head bone (`Bone29`).
- Head lead (R-TPS-16): that it looks good, that the head turns the right
  way sideways (yaw axis from the rest pose), the 0.2 s settle, both heroes.
- Torso pitch while aiming. Kerrigan (2026-11-22): she nods up and down,
  not sideways, and up is up.
- Kerrigan strafe, backpedal and diagonals: the legs turn as one, the feet
  do not twist or slide (R-TPS-18).
- Kerrigan aim pose: the breathing look, amount and speed; no jump when
  the camera pitch changes (R-TPS-19).
- Kerrigan attacks with Psi Blast up close in `single`: missile, sound,
  cast animation (R-TPS-63).
- Kerrigan's TPS left-click swing: `Attack 01` plays on the upper body
  and back talons, standing and walking; it plays in 0.75 s of the 1 s cooldown; the
  swing starts on the press (R-TPS-66).
- Attack `auto`, not aiming: Tosh holds the shooting pose between shots,
  standing and strafing, with no idle flicker (5.9).
- Backpedal and strafe animation in TPS.
- A shot while walking: no stutter, attack animation plays.
- A Tosh shot at the sky or beyond range: launch and sound, no impact, no
  impact sound.
- The free-cursor state after a middle click: the cursor moves freely and
  hovers and clicks units; the camera does not turn or scroll.
- The same after ten or more aims (5.3, operator report 2026-11-16). Also
  with no aiming at all.
- Aim camera side and field of view.
- Crosshair pick on large units live (Thor chest, head, arm; Hive top).
- Camera framing per unit height (AC-TPS-25): Tosh, Kerrigan, SCV.

## 10. Not Tested

- Real mouse and key events. The harness calls the handlers.
- A cursor left click in the free-cursor state (R-TPS-81).
- The proxy as a target of other units (R-TPS-59).
- The field of view (R-TPS-43).
- The Alt key (R-TPS-34).
- An in-game ability count (R-TPS-3).
- Any Kerrigan shot case (R-TPS-23 to 26, 52 to 55, 61).
- Scenery damage and collision (section 5).
- A real middle click with a real cursor (R-TPS-31, 36).
- A real middle press and drag (R-TPS-37).
- The `pick` group, full `tps`, `combat`, `controls`, `rungun` on the new
  crosshair ray (R-TPS-84).
- The baked scale rule (actor x model) in game. Marine volumes reach 0.93
  high against model bounds of 3.42; not checked.

## 11. Open Points

O-TPS-2, O-TPS-3 in the requirements.

## 12. Runs

Full suites on the build with the middle-click toggle and the layout overlay:

| Run | Result |
| --- | --- |
| `tps/20261115-015007` | 438 passes, 2 failures: `tps_pick_marine thigh CrossEnemy: got=False want=True` (R-TPS-84, open) and `tps_kerr_enemy tlate EnemyHp: got=500 want<500` (section 8). `RealClicks` 0. |
| `combat/20261115-015410` | 188 passes, 0 failures. `RealClicks` 0. |
| `controls/20261115-015316` | 51 passes, 0 failures. |
| `rungun/20261115-015745` | 0 failures. |

Other runs:

- `tps/20261115-011630`: group `cursor` with the toggle test on the hold code,
  19 failures (`tps_cursor tmid CursorVisible: got=False want=True`).
- `tps/20261115-011742`: group `cursor` on the toggle code, 0 failures.
- `tps/20261115-014818`: group `cursor` with the release test on the press
  toggle, 3 failures (`tps_cursor tdown CursorVisible: got=True want=False`).
- `tps/20261115-014918`: group `cursor` on the release toggle, 0 failures.
- `tps/20261114-233625`: the three bug tests on the old code, 12 failures
  (no `ShotEffect`, walk path 2519 against 3101, attack order while walking).
- `tps/20261114-234058`: group `shot` on the new code, 0 failures. Walk path
  3101 against 3101.
- `pncprobe/20261114-232735`: walk-shot probes (T29 to T31).
- `pncprobe/20261114-235342`: `spawn_scan`. A harness spawn 12 to 20 east of
  the anchor lands at 9.5 to 11.8 or at 18.3 to 20.4, never between. The
  `combat` case `auto_move_near` moves the hero instead of the spawn.

Crosshair pick (R-TPS-84):

- `tps/20261123-135303`: group `pick`, 0 failures, every stock type
  measured. New cases: SCV, Drone, Dehaka body in, beside or above out;
  Overlord made after start in `gv_hvFarUnits` and picked, a Marine not in
  it; the table loads 2548 types, 5205 shapes, 281 far types, the same
  after a second `gf_HvLoad`; BanelingBurrowed has no volume. Raw: a
  real-time timer read 0 ms around the second load (it does not move
  within one script run), so the load time is not measured.
- `tps/20261123-134920`: group `pick`, 2 failures (`tps_pick_scv tbody`,
  `tps_pick_fargroup tbody`): an escort TerranDropPod, newly measured, on
  the ray. Fixed by `HV_UNPICKABLE`.
- `tps/20261115-222609`: group `pick`, 0 failures, hit volumes on the old ray.
- `tps/20261115-215132`: full `tps`, 1 failure (`tps_kerr_enemy tlate
  EnemyHp`, section 8), old ray.
- `pncprobe/20261115-222935`: Thor pitch sweep; engine and script bands
  differ by about 20 degrees on the old ray.
- `pncprobe/20261115-224549`: Zergling sweep, engine ray measured (T13).
- `pncprobe/20261115-230450`: aim yaw off by 0.25 with a hero-proxy midpoint
  origin, 3 failures.
- `pncprobe/20261115-231002`: group `point`, 0 failures, `RealClicks` 0.
- A `tps pick` rerun on the new ray ended with `no tps test bank produced`.
- Host tests: 277 OK.
- `pncprobe/20261116-145352`: group `inrange` on the native check, 11
  failures (close enemies out of range while aiming or facing away; no pick
  at 30).
- `pncprobe/20261116-145555`: group `inrange` on the distance check and the
  uncapped pick, 0 failures. Marine at 1, 2, 4, 8, 11.8 in range in every
  state; at 30 picked and out of range.
- `tps/20261116-150246`: group `target`, 0 failures.
- `tps/20261116-150349`: group `shot`, 21 failures, all from the 0.25 s Tosh
  period of `067ffff`: the second click per case fires (Shots +1, one more
  floater) and `CooldownMs`, `ButtonCdMs` read 0 at `tshot`. Same in `sky`
  and `ground`, where no unit is picked. Host tests: 350 OK.
- `controls/20261116-150635`: 1 failure, `controls_collision_clamp distance:
  got=1 base=1` (camera collision; cause not found).
- `rungun/20261116-150740`: 1 failure, `rungun shot CooldownRingMs: got=0`
  (likely the 0.25 s period of `067ffff`; not measured).
- `combat`: not run. The build failed in the map validator: `tree 2145865770
  footprint does not match its mesh`, from uncommitted flora work
  (`scripts/flora/build.py`, `scripts/flora/border.py`).

Shot clocks on the 0.25 s Tosh period:

- `tps/20261116-215657`: group `shot`, 21 failures. A probe one loop after
  the shot read 125 ms on the hero cooldown and the button clock in each
  aimed case. The old read at +0.25 s found both over.
- `tps/20261116-220628`: group `shot` on `tpsclock.galaxy`, 0 failures.
- `tps/20261116-222551`: full `tps`, 403 passes, 0 failures, `RealClicks`
  0. Kerrigan group deleted, scenery damage and collision checks dropped.
- `tps/20261117-013357`: full `tps` on the combined tree (pose, send-once,
  hero drop), 0 failures. Harness split: `tpssends.galaxy`, `tpspose.galaxy`,
  `profiles/tps_sends.py`, `profiles/pose.py`, `profiles/bank_checks.py`.
- `controls/20261117-014522`: 0 failures, distance checks in thousandths
  (section 8).

Only the harness files of `combat` and `pncprobe` changed after
`tps/20261114-234256`.

Close Roach out of range (operator 2026-11-27, section 5.8a):

- `pncprobe/20261127-085438`: group `roach`, 2 failures, both the negative
  case at 30 (the Roach lost about 25 life/s to something on the map). Every
  in-range case: check 1, pick 1, the aim shot dealt damage. The engine kept
  Tosh 1.813 and Kerrigan 2.188 from the Roach centre: the edge distance
  never went negative. Not reproduced.
- `pncprobe/20261127-092004`: group `roach`, negative case at 16, 0 failures.
  Not reproduced.
- Cause found in the operator's SCOBAAIMLOG marks: the pick was a
  ZergDropPod 50 to 58 away (bloated bounds volume, section 5.8).
- Group `roach` with case `pod`, before the fix (log `roach-pod-1.log`):
  5 failures, pod picked at t 0, reticle 3, shot kind 2.
- `pncprobe/20261127-102041`: group `roach` after the fix, 0 failures.
- `tps/20261127-102526`: group `pick`, 0 failures.
- `pncprobe/20261127-102904`: group `all`, 0 failures.

Tosh cooldown 0.15 s (operator 2026-11-27: 0.1 was too fast; before that
0.25): `Tosh` Period and cooldown TimeUse, `SCOBAAttackCooldown01`.
`validate_aim_shot` checks all three against `TOSH_CLOCK`. 0.15 s is 2.4
game loops. Galaxy fixed point holds it as 614 / 4096, so a read in ms gives
149 or 150. The clock checks allow one loop below 0. No run at 0.15 s yet.

Runs at 0.1 s (an expired clock read -25 or -50; the weapon clock could be
over in the loop that saw the shot effect):

- `combat/20261127-111646` `button`, `combat/20261127-111901` `pose`: 0 failures.
- `combat/20261127-105141` `single`: 4 shots for 3 commands (one command
  fired twice). `combat/20261127-111410`: 3 shots; damage check failed
  (one -7, three -28; damage is 8 to 12 random).
- `tps/20261127-112145` `shot`: 5 failures. `tps_shot_friendly` 7 shots
  for 6, `tps_shot_ground` 4 for 3: an extra shot. `AgainCdMs` 0, -25, -13:
  the second click came after the 0.1 s clock ended. Open.

## Camera depth of field (REQ-CAMERA-DOF)

`gf_CameraDofApply` (systems/camera/camera.galaxy), own 0.05 s timer
`gt_CameraDofTick`, PnC and TPS. Skipped during the intro and the hero drop.
Focus = camera arm d. Max strength = the intro DOF (near 1..6, far 4..18).

- Near: k = clamp((d - 1) / 39); near falloffs = (0.08 d, (1 - 0.6375 k) d):
  scaled to the arm, feathered.
- Far: kf = clamp((d - 3) / 37); far falloffs = (2.5, 12) / kf; kf = 0: far
  falloff 100000 (none).
- Aim: focus 2, near falloffs (0.2, 1.8), absolute (operator pick,
  aimdof/20261117-134320 point 5); no far blur.
- k = 0 and kf = 0: DOF off.

The blur's look is an operator check.

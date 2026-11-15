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
| T35 | A unit position has no height; `UnitGetHeight` gives it (Overseer 7.0). | [probe] `tps/20261115-213703` |
| T14 | All three hero weapons exclude `Hidden` and `Invulnerable` targets. `RazorTalons` requires `Ground`. Psi Blast has `MinimumRange` 2. | [stock] weapon data |
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
| T32 | Psi Blast killed an enemy Marine at distance 3.0. At 3.5, 4.0, 4.5, 5.0, and 9.5 the weapon effect event fired and the Marine kept full life, also 3.85 s later. Same at 4.0 and 5.0 with the data `Range` set back to 4. Cause not found. | [probe] `pncprobe/20261114-230104`, `pncprobe/20261114-230331` |

Facts T16 to T22 of the earlier draft (Barrage on a point, `PointSetHeight`
dropped by orders) were measured in `pncprobe/20261114-185541` and
`pncprobe/20261114-192859`. The design does not use point orders, so they are
not repeated here.

## 4. Requirement State

| Req | State | Evidence |
| --- | --- | --- |
| R-TPS-1 | [tested] effect name, effect event, damage, cooldown, button clock. Muzzle, sound, animation [operator]. | `tps` group `shot`: `ShotEffect`, `CooldownMs`, `ButtonCdMs` |
| R-TPS-2 | [built] | One strafe step, one left-click result (`gf_LeftClickTarget`), one effect handler. The UI floater is a new module: a world text tag cannot show at the sky (R-TPS-73). |
| R-TPS-3 | [built] | The five aim-shot abilities are removed. The build validator fails if their ids return. No in-game ability count check. |
| R-TPS-10, 11 | [tested] | `tps` group `move` |
| R-TPS-12 | [tested] | `tps_head`: torso pitch step 0 outside aiming |
| R-TPS-13 | [tested] step follows the camera pitch. Look and direction [operator]. | `tps_head` |
| R-TPS-14 | [tested] | `tps_head`: head step 0 and torso pitch step above 0 while aiming |
| R-TPS-15 | [built] | TPS uses the right-hold step and clips. No check compares the two walks. |
| R-TPS-20 | [tested] script flag. The cursor itself [operator] (T5). | `tps` group `cursor` |
| R-TPS-21, 22 | [tested] | `tps` group `cursor` |
| R-TPS-23 to 26 | [tested] crosshair kind. Colors [operator]. | `tps` groups `shot`, `kerrigan` |
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
| R-TPS-52 | Tosh [tested] damage. Kerrigan fails: Psi Blast deals no damage at this distance (T32, section 8). The damage text is the Point & Click floater; not asserted here. | `tps_shot_enemy`; failing `tps_kerr_enemy tlate EnemyHp` |
| R-TPS-53, 54 | [tested] | `tps_shot_far`, `tps_shot_ground`, `tps_shot_sky`, Kerrigan cases |
| R-TPS-55 | [tested] with a Marine in range | `tps_shot_friendly`, `tps_kerr_friendly` |
| R-TPS-56 | [operator] | |
| R-TPS-57 | [tested] | `CooldownMs`, `ButtonCdMs` in every shot case |
| R-TPS-58 | [tested] | second click in every shot case |
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

### 5.2 Head tilt (R-TPS-13, 14)

- `scripts/character_anim_assets.py` generates nine static head-only clips,
  `Ready Cover 01` to `09`, from the `Stand` pose, from -15 to +15 degrees.
  They sit under the upper-body clips in priority.
- The head bone is a per-model setting; the build fails if the model lacks
  it. Tosh: `BoneHead`, the parent of the `Ref_Head` attachment. Kerrigan
  has no `Ref_Head`; the setting is `Bone29`. That choice and the tilt
  direction are [operator].
- `gf_AnimHeadTick` maps the camera pitch to a step and plays the clip in its
  own bracket, `SCOBAHead`. Level pitch is 20 degrees. It clears the bracket
  while aiming, in the free-cursor state, and in Point & Click.
- The build validator and a host test fail if the script step count or range
  differs from the generated clips.
- Assumption for O-TPS-2: pitch only.

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

### 5.6 Shot floaters (R-TPS-70 to 76)

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
  left or right and up to `c_UI_FLOATER_JITTER_Y` (30) higher, then rises.
  World floaters: `gf_FloaterCreate` moves the start point up to
  `c_FLOATER_JITTER` (0.5) in x and y. [built]. That a positive label offset
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
  proxy while aiming) at hero height + `c_SCOBA_CAMERA_HEIGHT_OFFSET` (0.9);
  direction from the camera yaw and pitch (T13). The old origin, 0.5 aside
  and 1.5 high, never hit a Zergling the engine hovered.
- The ray starts inside the hero; the pick skips the player's own hero.
- Each unit is tested against its hit volume: spheres, capsules and boxes
  from the rest-pose m3 hit-test shapes, with actor `Scale` x model
  `ScaleMax` baked in. No radius, no margin. Model facing is model -y
  (`c_HV_MODEL_YAW` 90).
- Data: `scripts/hitvolumes/` measures `scripts/data/hit_volumes.json`
  (70 units) and generates `scripts/app/data/hit_volumes_*.galaxy`
  (63 types). `validate_aim_shot.py` fails on stale data.
- Near types: scanned in a circle of range + `c_HV_NEAR_REACH`. Far types
  (reach above 20): scanned per type on the whole map.
- A type without a volume is not pickable and is recorded once
  (`gv_hvMissing`).

## 6. Module Structure

| Module | Role |
| --- | --- |
| `systems/strafe.galaxy` | Strafe for all of TPS. The walk step does not know about shots. |
| `systems/controls.galaxy` | Mode switch, middle and right button handlers, cursor state. |
| `systems/aim.galaxy` | Aim camera, aim side, crosshair kind and color. |
| `systems/aim_shooting.galaxy` | Crosshair ray (`gf_AimCameraFocus`, `gf_AimPickRay`), pick, proxy, pending shot, `gf_AimShotEffect`, `gf_AimShotPress`. |
| `systems/hit_volumes.galaxy`, `data/hit_volumes_*.galaxy` | Hit-volume ray tests and generated volume data. |
| `scripts/hitvolumes/` | Volume measurement, Galaxy generator, host ray reference. |
| `systems/ui_floaters.galaxy` | UI-layer floaters. |
| `systems/combat_fsm.galaxy` | `gf_AttackOrder` (Point & Click), root rules. |
| `systems/combat_cooldown.galaxy` | Weapon effect event: animation, pending shot, single shot. |
| `systems/targeting.galaxy` | `gf_LeftClickTarget`, `gf_TpsLeftClick`. |
| `systems/animation_aim.galaxy` | Torso pitch tick, head tilt tick. |
| `scripts/character_anim_assets.py` | Head clips. |
| `scripts/attack_cooldown_link.py` | Cooldown link on the three hero weapons. |
| `scripts/validate_aim_shot.py`, `scripts/validate-map.py` | Build checks. |

## 7. Tests

- Entry point: `scripts/playtest.sh tps [group]`. Groups: `move`, `cursor`,
  `aim`, `head`, `target`, `shot`, `kerrigan`, `pick`.
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
| `cursor` | Input flags for TPS, aiming, free-cursor state. The state holds after the middle release; a second click ends it. | A right press in the free-cursor state does not aim. The switch to Point & Click ends the state. |
| `aim` | Aim flag, anchor on the right, shorter camera arm. | Release restores the distance and removes the anchor. |
| `head` | Head step level, down, up with the camera pitch. | Step 0 in Point & Click, while aiming, in the free-cursor state. |
| `target` | Not aiming: the click sets the UI target. | The click never attacks. Aiming: the UI target is unchanged. |
| `shot` | Per outcome: shots +1, life, proxy, effect name, cooldown, hero position, one text of the right kind. Walking: one shot, the walk keeps its speed. Weapon ranges. | Click on cooldown, click when not aiming: no shot, no text. Walking: never an attack order. Air proxy: not the hit effect. No late damage 2 s after a miss. |
| `kerrigan` | The shot cases with Kerrigan. | As `shot`. |
| `pick` | Medic head, Marine thigh and middle, Ultralisk front, Zergling at 18.5, Overseer body, Hive top, Marine before Hive, Thor chest with aim held (reticle, status bar, shot). | Above the Medic, beside the Marine and Zergling, behind the Ultralisk, under the Overseer, north of the Hive. |
| `pncprobe point` | Engine and script band centres within 2 degrees, pitch at 3, 5, 8, 12 and yaw at 5, rest and aim. Nothing but hero and target near the lane; Medic parked. | No script pick 4 degrees outside the engine band. |

Floater checks read script counters. They do not prove the text is visible.

## 8. Findings Outside This Phase

- T26: `systems/camera.galaxy` reads `CameraGetTarget` for the camera
  collision sample. If the value is stuck as measured, the sample is taken at
  the wrong point. Not changed here. The pushed commit `b3988d1` has the same
  code.
- A friendly `Medic` 0.6 from the hero read as not attackable. The shot went
  to the proxy with the `Friendly Fire Disabled` text
  (`tps/20261114-211914`, raw `CrossType`). R-TPS-55 asks for a shot at the
  unit. Cause not found.
- Kerrigan is a proof of concept. Psi Blast deals no damage beyond about 3.0
  (T32). `tps_kerr_enemy tlate EnemyHp` fails. Cause not found. Kerrigan has
  no air effect (R-TPS-62).

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
- Torso pitch while aiming.
- Backpedal and strafe animation in TPS.
- A shot while walking: no stutter, attack animation plays.
- A Tosh shot at the sky or beyond range: launch and sound, no impact, no
  impact sound.
- The free-cursor state after a middle click: the cursor moves freely and
  hovers and clicks units; the camera does not turn or scroll.
- Aim camera side and field of view.
- Crosshair pick on large units live (Thor chest, head, arm; Hive top).

## 10. Not Tested

- Real mouse and key events. The harness calls the handlers.
- A cursor left click in the free-cursor state (R-TPS-81).
- The proxy as a target of other units (R-TPS-59).
- The field of view (R-TPS-43).
- The Alt key (R-TPS-34).
- An in-game ability count (R-TPS-3).
- A walking shot with Kerrigan (R-TPS-61).
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

Only the harness files of `combat` and `pncprobe` changed after
`tps/20261114-234256`.

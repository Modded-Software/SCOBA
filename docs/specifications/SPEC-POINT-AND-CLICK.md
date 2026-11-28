# SPEC-POINT-AND-CLICK: WASD / Point & Click Mode

**Date:** 2026-11-14
**Status:** Partly built. Section 4 gives the state of each requirement.
**Requirements:** [REQ-POINT-AND-CLICK](../requirements/REQ-POINT-AND-CLICK.md)

## 1. Principle

The engine owns attack, acquisition, chase, move, follow, firing while moving,
and the attack cooldown. Data configures the engine. Script only translates
input into orders and keeps UI state.

Script does not scan for enemies, pick targets, re-issue orders on a timer,
time a cooldown, or track a combat state machine.

## 2. Labels

State of a design item:

- **[tested]**: built, and a programmatic in-game check passed in the named run.
- **[built]**: in the code. No passing check.
- **[planned]**: not in the code.
- **[operator]**: only a person can judge it. Listed in section 9.

Source of an engine fact:

- **[stock]**: read in stock game data or the natives file.
- **[probe]**: measured in game by the `pncprobe` profile, run named.
- **[open]**: not confirmed. Code must not depend on it until it is.

Runs are under `out/test-runs/`. The full `combat` suite is green in run
`combat/20261114-153801`: 0 failures, 165 checks. A check marked **[tested]**
passed in that run unless another run is named.

## 3. Engine Facts

| ID | Fact | Source |
| --- | --- | --- |
| F1 | `StateFlags Passive` stops a unit from acquiring. It still obeys an attack order. | [stock] `GhostHoldFire`; [tested] `single_idle`, `single_shot` |
| F2 | A behavior that disables `CAbilAttack` for 0.07 s ends the current attack order. | [stock] `GhostHoldFire`; [probe] `pncprobe/20261114-140102` |
| F3 | A `stop` order does not end an attack. The hero attacks the same target again. | [probe] `pncprobe/20261114-135727` |
| F4 | A weapon with both `OnlyFire` options `0` keeps firing at its target with no order. `Passive` does not stop it. Neither does F2 once it has fired more than once. | [probe] `pncprobe/20261114-143124` |
| F5 | A weapon with the stock `OnlyFire` options fires only inside an attack order. F2 stops it at any time. | [probe] `pncprobe/20261114-143420` |
| F6 | A weapon fires only at a target inside its `Arc`. With `Arc 360` it fires at any facing. | [tested] `move_fire_auto`, `combat/20261114-144027` |
| F7 | `DefaultAcquireLevel=Offensive` acquires an enemy and walks into range. | [tested] `auto_move_near` |
| F8 | A unit with `SuppressMoving` still acquires and attacks in range. | [tested] `auto_stand_in` |
| F9 | The effect-used event fires once per shot for all three hero weapons. | [tested] `single_shot`, `talons_single`, `psiblast_single` (before 2026-11-22; Kerrigan carries no talons now, SPEC-TPS 5.5a) |
| F10 | Unit cooldowns and ability cooldowns are separate stores, even under one link name. | [probe] `pncprobe/20261114-145027` |
| F11 | A weapon `Cost` cooldown with `TimeUse` starts a unit cooldown on each shot. Without `TimeUse` it reads 0. | [probe] `pncprobe/20261114-140102` |
| F12 | A unit cooldown shared by weapon and button does not draw the cooldown clock. The button's own ability cooldown is the store the clock was last seen on. | [operator] 2026-11-14 |
| F13 | `UnitCheckAbilCmdState` never reports a cooldown for the button. It is not a usable check. | [probe] `pncprobe/20261114-145027` |
| F14 | `CEffectModifyUnit` with `<Cost Abil="…" CooldownOperation="Set" CooldownTimeUse="…"/>` sets an ability's cooldown. | [stock] `mod_void_effectdata.xml:748`; [probe] `pncprobe/20261114-140102` |
| F15 | The command shown by a `CAbilBehavior` toggle button follows toggle commands only. Adding or removing the behavior directly leaves the button unchanged. `c_cmdStateHidden` on command 0 reads which face shows. | [probe] `pncprobe/20261114-151352` |
| F16 | A unit holds at most 32 abilities. Both heroes hold 32. | [stock] |
| F17 | `move` targeting a unit follows it. | [stock], used in `medic.galaxy` |
| F18 | In the unit-attacked event, `EventUnit` is the victim and `EventUnitTarget` is the attacker. | [tested] `single_attacked` |

## 4. Requirement State

| Req | State | Note |
| --- | --- | --- |
| R-PNC-1, 2, 3 | [built] | Scan loops, tick, FSM, and `move 3` are removed. The single-shot flag is the one script addition (5.5). |
| R-PNC-10, 11, 12, 14 | [built] | Unchanged this phase. No test yet. Selection still uses the hero reselect. |
| R-PNC-13, 31 | [built] | Ground clicks call `gf_PncCancel`. The real left-click path has no test. |
| R-PNC-15 | [tested] | `single_attacked`. |
| R-PNC-20, 21 | [tested] | `single_shot`. |
| R-PNC-22 | [tested] | `auto_click`. |
| R-PNC-23 | [tested] | `single_out_move`, `auto_move_near`. |
| R-PNC-24 | [tested] | `single_out_stand`: no order, no movement, no `Out of range` floater (counter `PncRangeFloat`). |
| R-PNC-25, 27, 28 | [tested] | `ground_move`, `ground_stand`. The ground marker is [operator]. |
| R-PNC-26 | [planned] | A friendly right click still moves to the click point. |
| R-PNC-30, 33 | [tested] | `cancel`. |
| R-PNC-32 | [built] | No test for Ctrl + C. |
| R-PNC-40, 51, 52 | [tested] | `auto_stand_in`, `auto_stand_out`, `auto_move_near`. |
| R-PNC-41 | [tested] | `single_idle`, `single_attacked`. |
| R-PNC-42, 45 | [tested] | `single_shot`, `weapon_button`. |
| R-PNC-43 | [tested] | `auto_to_single`. |
| R-PNC-44 | [tested] | `switch_single_stand`, `switch_auto_move`, hero state and button state. |
| R-PNC-46 | [tested] | Read one game loop after the shot effect (`gf_DbgClockRead`; the 0.25 s Tosh period is over by the old 0.5 s read): `EarlyCdMs`, `EarlyBtnMs` above 0, at most the weapon cooldown for Tosh; Kerrigan above 0 only (her button clock is not her first weapon's). Every shot path: `single_shot`, `weapon_button`, `auto_click`, `auto_stand_in`, `talons_single`, `psiblast_single`, `talons_auto`. Since 2026-11-22 the Kerrigan sections are `psi_close_single`, `psiblast_single`, `psi_close_auto` (SPEC-TPS 5.5a); not run. The clock overlay is [operator]. |
| R-PNC-47 | [tested] | `startup`, hero state and button state. |
| R-PNC-48 | [tested] | `toggle buttons match hero state` over every snapshot; `auto_to_single`; both switch scenarios. |
| R-PNC-50, 53 | [tested] | `wasd_stand`, `auto_stand_out`. |
| R-PNC-54 | [tested] | `move_fire_auto`, `move_fire_single`, run `combat/20261114-144027`. |
| R-PNC-57, 58, 59 | [planned] | Design and tests in 5.8a. |
| R-PNC-55, 56, 60 to 63 | [built] | Unchanged this phase. No test yet. |
| R-PNC-64, 65 | [tested] | `hold_right_back`, `hold_right_left`, `hold_middle`. The tests set the hold flags; the real mouse path has no test. The clips' look is [operator]. |
| R-PNC-66, 67 | [built] | Unchanged this phase. No test yet. |
| R-PNC-68 | [tested] turn and forward walk; [operator] strafe and backpedal clip rate | `hold_middle_fwd`, `hold_right_fwd`, `hold_right_turn`. See 5.8. |
| R-PNC-70, 71, 72 | [planned] | Handlers are shared and branch on the mode. Design in 6. |
| R-PNC-73, 74 | [built] | Labels are in `ButtonData.xml`. Their look is [operator]. |
| R-PNC-75 | [built] | No test yet. |
| R-PNC-80, 81, 82 | [tested] script state; [operator] the look | `pose_single_seq`, `pose_auto`, `pose_cancel`, `pose_idle`, `pose_kerrigan`, run `combat/20261117-000426`. TPS (R-TPS-17): run `tps/20261116-235526`. Design in 5.11. |

The `RazorTalons` damage checks were removed on operator order.

## 5. Design

### 5.1 Attack toggle

- Behavior `SCOBAAttackSingle` marks Attack `single`. It carries `Passive`
  (F1) and disables the three auto weapons (5.2). [tested]
- The toggle ability `SCOBAAutoAttackToggle` toggles that behavior. The `On`
  command face reads `Attack: Auto`, the `Off` face reads `Attack: Single`.
  Each face names the current state. [built]
- Switching to `single` applies `SCOBAAttackEnd` (F2). [tested]
  `auto_to_single`
- Attack `auto` uses engine acquisition: `DefaultAcquireLevel=Offensive` on
  `ToshSCOBA` and `KerriganSCOBA` (F7). [tested]

Toggles change through their toggle commands only (F15). [tested]

- `gf_ToggleSet` issues command 0 or 1. `gf_AttackSingleSet` and
  `gf_ChaseStandSet` wrap it.
- The defaults are set at map start in `init.galaxy`. The units carry no
  toggle behavior.
- Hero switch sets both toggles on the new hero from the old hero's state.
- The test harness uses the same setters.
- The validator fails a toggle behavior on a unit and a direct add or remove
  in script.

### 5.2 Weapons

Each hero attack is two weapons. [tested] by `auto_to_single`,
`move_fire_auto`, `move_fire_single`.

| Weapon | Role | Data |
| --- | --- | --- |
| `Tosh`, `RazorTalons`, `QueenOfBladesPsiBlast` | Order-bound. Serves Attack `single`. | Stock options (F5). |
| `ToshAuto`, `RazorTalonsAuto`, `QueenOfBladesPsiBlastAuto` | Fires on its own, while moving, at any facing. Serves Attack `auto`. | Child of the stock weapon. `AllowedMovement=Moving`, both `OnlyFire` options `0`, `Arc 360` (F4, F6). |

Since 2026-11-22 no hero carries `RazorTalons` or `RazorTalonsAuto`: Kerrigan
attacks with Psi Blast only (REQ-TPS R-TPS-63, SPEC-TPS 5.5a). The two
weapons stay in the data.

- `SCOBAAttackSingle` lists the three auto weapons in `WeaponDisableArray`.
- Attack `single` has no shot while WASD-moving. A WASD `move` order replaces
  the attack order.
- WASD issues plain `move` orders only.
- W and S each run one loop per player (`gv_moveLoopFwd`, `gv_moveLoopBack`
  in `systems/movement.galaxy`). W and S held together cancel. Releasing
  one restarts the loop of the other if it is still held. A key repeat
  does not start a second loop. A W or S release clears its key flag even
  during an input hold. Fix for operator 2026-11-25 (flying Viking: W/S
  sometimes stopped). [not tested]
- With `Arc 360` the hero can fire without turning to the target. [operator]
- Attack `auto` while moving: the engine picks the target. It may not be the
  clicked enemy. [open]

### 5.3 Chase toggle

- Chase `stand`: the hero has `SCOBAStandRoot` (`SuppressMoving`). [tested]
- WASD removes the root while a movement key is held and restores it on
  release. Order mode and aim also remove it. [tested] `wasd_stand`
- The default is set at map start with the toggle command. [tested] `startup`

### 5.4 Attack command

One function, `gf_PncAttack(player, target)`. Callers: right click on an
enemy, and the `Weapon Attack` button. [tested]

| Target | Chase | Action |
| --- | --- | --- |
| In range | any | Set UI target. Issue `attack` on the unit. |
| Out of range | `move` | Set UI target. Issue `attack` on the unit. |
| Out of range | `stand` | Set UI target. No order. No text (R-TPS-79; the `Out of range` text is off). |

In range uses `UnitInRangeAndAbleToAttackTarget`.

Other right clicks:

| Target | Chase | Action | State |
| --- | --- | --- | --- |
| Ground | `move` | Cancel. Issue `move` to the point. Show the move marker. | [tested] |
| Ground | `stand` | Cancel. | [tested] |
| Friendly | `move` | Issue `move` targeting the unit (F17). UI target unchanged. | [planned] |
| Friendly | `stand` | Nothing. | [planned] |

### 5.5 Single shot

The engine has no one-shot attack order. This is the one script addition
(R-PNC-3). [tested] `single_shot`

1. `gf_PncAttack` with Attack `single` sets `gv_pncSingleShot[player]`.
2. The weapon-effect handler `gt_CombatAttackEffect` sees the shot (F9) and
   calls `gf_PncShotFired`.
3. `gf_PncShotFired` clears the flag and calls `gf_PncAttackEnd`, which adds
   `SCOBAAttackEnd` (F2). No `stop` order (F3).
4. `SCOBAAttackSingle` keeps the hero from attacking again (F1, F5).

Defect against R-PNC-21 (operator 2026-11-27), with the Tosh period at
0.1 s: one command fired twice (`combat/20261127-105141`, `single_shot`: 4
shots for 3 commands). [plan]

- Test `single_burst` (group `single`): 48 commands, 0.625 s apart; each
  gives exactly one shot. Negative: no shot in the 2 s after the last. Raw
  per command, for 8 game loops: shots so far, the attack order,
  `SCOBAAttackEnd`, the weapon cooldown.
- Measured, run `combat/20261127-124958` (24 commands, before the fix): 2
  commands gave two shots. In every command the first shot is seen in loop
  2, with the order and `SCOBAAttackEnd` both on; the order is gone in loop
  3. Both second shots came between loop 2 and loop 3. The order outlives
  the first shot by one game loop.
- Cause, not confirmed until the test passes: `Tosh` inherits the stock
  random delay, -0.063 to +0.125 s, made for the stock 1 s period. At 0.1 s
  the weapon is ready again after 0.037 to 0.225 s. Under one game loop
  (0.0625 s) it fires again before the order ends.
- Fix: `RandomDelayMin` 0 and `RandomDelayMax` 0 on `Tosh`; `ToshAuto`
  inherits them. The weapon is ready again after exactly its period
  (R-PNC-46).
- The period is 0.15 s since (operator 2026-11-27: 0.1 was too fast). The
  fix stays. No run at 0.15 s yet.

### 5.6 Cancel

One function, `gf_PncCancel(player)`. [tested] `cancel`

1. Clear the UI target.
2. Clear `gv_pncSingleShot`.
3. Call `gf_PncAttackEnd`.

Callers: left ground click, right ground click, and Ctrl + C outside order
mode. In order mode Ctrl + C exits order mode and does nothing else.

### 5.7 Left click and UI target

- Unit or building: set the UI target. No order. [built]
- Ground: `gf_PncCancel`. [built]
- An enemy that attacks the hero sets the UI target (F18). [tested]
- Selection: the hero reselect stays. Disabling click selection with
  `UISetSelectionTypeEnabled` is [planned] and needs a probe that unit click
  events still fire.

### 5.8 Movement and mouse holds

| Input | Camera | Hero facing | WASD frame | S | State |
| --- | --- | --- | --- | --- | --- |
| No button | still | travel direction | camera view | turns and walks toward the camera | [built] |
| Left hold | orbits | not turned by the orbit | hero facing at press | turns around and walks | [built] |
| Middle hold | orbits | travel direction | camera view | walks toward the camera, facing it | [built] |
| Right hold | orbits | locked to camera yaw | camera view | backpedals | [tested] |
| Left + right | orbits | camera view | camera view | walks forward without a key | [built] |

Right hold [tested]:

- `gv_holdStrafe[player]` is true during a PNC right hold with no middle
  hold. `gf_StrafeHoldSync` sets it on the camera turn tick. TPS and
  order mode clear it.
- While it is set the hero carries `SCOBAAimNoTurn` (`SuppressTurning`), as
  in aim. The facing follows the camera yaw.
- `gf_StrafeMoveActive(player)` gates the aim movement step: true for aim and
  for the right hold. WASD then moves the hero relative to the camera yaw.
- The animation layer plays the directional walk clips during the hold.
  Standing keeps the stock clip. Their look is [operator].
- `gv_rOTATEUNIT` stays for the camera turn. Middle hold is unchanged.

Right hold matches middle hold (R-PNC-68):

- Turn [tested]: while a movement key is held, the WASD loop is the only
  facing writer. `gf_StrafeLoopStep` calls `gf_AimMoveStep` in the loop
  thread, every 0.01 s, with `c_ANIM_MOVE_TURN_DURATION`, the constant the
  middle-hold loops use. The camera turn tick skips `gf_TurnToYaw` then.
  `hold_middle_fwd` and `hold_right_fwd` assert equal facing lag, equal
  distance and equal smallest step while the camera turns 90 degrees.
- Forward walk [tested]: direction forward sets no lower override, so the
  engine plays the stock `Walk`, as in a middle hold (`FullState` 0).
- Strafe and backpedal: the clips are full-length copies of `Walk`; the
  build fails if a length differs. `gf_AnimWalkScale` sets their time scale
  to unit speed / `WalkAnimMoveSpeed`. The scale value is [tested]
  (`walk clip rate`). That this equals the engine's stock walk rate is an
  assumption and [operator]: Galaxy cannot read the stock clip's rate.
- The harness sets the A and S flags without the key loops, so
  `hold_right_turn` exercises the periodic step only.

### 5.8a WASD keys (R-PNC-57 to 59) [planned]

Defect (operator 2026-11-27): a WASD key stays down and the hero stops, in
any setting. Causes found by reading the code; none is measured yet:

- A key down starts a loop thread and returns early in an input hold, in
  order mode and with no hero. Nothing replays the key afterwards.
- Chase `stand`: a W or S release puts the root back. A press within the
  same game loop returns at the loop guard, before the root is removed.
- W and S together end both loops.
- Order mode entry clears the four direction flags with the keys down.
- An A or D release in an input hold is dropped.
- The strafe step issues no order when no point 6 or more ahead is
  reachable in a straight line.

Design:

- Key state: `gv_kEYFORWARD`, `gv_kEYBACKWARD`, `gv_kEYLEFT`, `gv_kEYRIGHT`.
  `gf_MoveKeySet(player, key, down)` is the one entry of the eight key
  triggers and of the harness. It stores every down and every up. Nothing
  gates the store.
- Direction flags `gv_fORWARD`, `gv_bACKWARD`, `gv_lEFT`, `gv_rIGHT`:
  `gf_MoveKeysApply` derives them from the key state and the two-button
  walk. W against S and A against D: the one pressed last (R-PNC-59). A
  regular unit gets no A and D. An input hold gives no direction.
- No loop threads. `gt_AimMoveTick` steps every hero each game loop:
  `gf_AimMoveStep` in strafe movement, else `gf_MoveStep`. `gf_MoveStep`
  runs only with a key or the two-button walk down, so a flag set alone
  moves nothing in the free walk (SPEC-JUMP F8). It removes the stand root
  on every pass.
- Key down: one step at once, with a new strafe target. It replaces any
  move order of the hero (R-PNC-58).
- Release: with no direction left, `gf_AimMoveStop` and the root sync.
- Input hold: the keys are stored and the hero does not move.
  `gf_SceneLeave` applies the stored keys.
- Order mode does not block the keys and clears no flag (R-PNC-58).
- A mode switch ends the two-button walk (`gf_ControlModeApply`, R-PNC-72).
- Strafe step with no reachable far point: the short step of the free walk.
  The hero walks up to the obstacle.

Tests, `combat` group `keys` [planned]. Harness
`scripts/testkit/galaxy/combat/combat_keys.galaxy`, checks
`scripts/testkit/profiles/combat_parts/combat_keys.py`. The keys go through
`gf_MoveKeySet`, each call in its own thread, as a key event. Travel is
measured along the camera yaw. Host test of the checks:
`scripts/testkit/tests/keys/test_combat_keys.py`.

Real input, same group. In `key_real` and `key_combo` the host sends real
keys, mouse motion and mouse buttons to the game window (XTest), so the
key events and the key triggers are in the path. Harness
`scripts/testkit/galaxy/combat/combat_keys_real.galaxy`. The W key of
`key_real` is `combat_keys.press_real_key`. The sequence and the checks of
`key_combo` are `scripts/testkit/profiles/combat_parts/combat_keys_real.py`,
host test `scripts/testkit/tests/keys/test_combat_keys_real.py`. The harness
has its own
triggers on the four key events. They keep the keys the game saw go down
and up. Each game loop of `key_combo` writes one row: the keys by the key
events, the script key state, the direction flags, aim, the move order,
the hero position and the camera yaw.

| Section | Proves | Negative |
| --- | --- | --- |
| `key_real` | a real W key: the game sees the down, the hero walks, the game sees the up | after the release: no travel, no move order |
| `key_combo` | TPS, real keys held in pairs (W+A, S+D, A then W, D then S), with a camera turn, an aim start and end, and left clicks while two keys are down: the hero travels in the direction of the keys that are down | no key edge the host did not send and none missing; no loop where the script key state or the direction flags differ from the keys down; no stretch with a key down and no travel; no mouse click beyond the ones sent |
| `key_tps` | TPS through its toggle order: W walks forward, A walks left | after each release: no travel; TPS is on before and off after |
| `key_hold` | W down walks for 2 s, root off | after the release: no travel, no move order, root back |
| `key_retap` | W up and W down in one game loop: walks, root off | after the release: no travel |
| `key_ws` | W then S: walks back; S up: forward again | after both are up: no travel |
| `key_ad` | A then D: walks right; D up: left again | after both are up: no travel |
| `key_order` | W replaces a click move within one game loop; W walks in order mode; W held into order mode keeps walking | after the release: no travel |
| `key_scene` | W pressed in an input hold walks when the hold ends | no travel in the hold, key pressed in it or before it; keys released in the hold: no travel after it |
| `key_strafe` | right hold, W: walks in the open and up to a block 4 ahead (a row of Bunkers under every far point) | it does not enter the block; after the release: no travel |

The group runs on free ground. The harness searches a spot with 9 free in
eight directions (`key_spot`); the run fails when it finds none.

Raw values in the bank: the free ground at the anchor and at the spot and
the units ahead of the anchor (`key_spot`), the order target against the
click point (`key_order`), the reachability of each far point in the open
and at the block (`key_strafe`), key calls sent and run (every section).

Measured before the fix, run `combat/20261127-141451` (12 failures,
`RealClicks` 0), on free ground (`key_spot` ring 4, direction 1):

- `key_hold`: passes. W walked 3.1 in each second.
- `key_retap`: the root stayed after the retap (`Root` 1); no travel.
- `key_ws`: S after W: 0.5 forward in 1.5 s, the hero stood. After S up W
  walked again (4.7).
- `key_ad`: D after A kept walking left (4.3).
- `key_order`: W in order mode: no travel. W held into order mode: no
  travel. W replaced the click move within one loop (passes).
- `key_scene`: W pressed in the hold: no travel after it. A held into the
  hold walked on in it (2.4), on after its release in it (3.8), and on
  after the section's release (1.9, move order still on).
- `key_strafe`: open passes. At the block every far point was unreachable
  and the hero did not move (0.0).

The first run, `combat/20261127-140800` (18 failures), ran at the profile
anchor. The ground 0.5 ahead of it and 45 degrees to each side is not
passable (`key_spot` `anchorRow` `1 1 18 13 18 18 18 1`). W walked 0.4 and
stood for 2 s with the key down, a move order and no root: the 0.5 step
ends in the obstacle. Open: what the free walk does at an obstacle that
has a way around (operator decision; not part of this fix).

After the fix, run `combat/20261127-142805` (1 failure, `RealClicks` 0),
same spot. Every check of `key_hold`, `key_retap`, `key_ws`, `key_ad`,
`key_order` and `key_scene` passes. `key_strafe` at the block: the hero
walked 3.8 forward and stayed out of the block, and it moved 1.9 to the
right in the same 1.5 s. The check allows 1.0 across. This is the open
point above: at an obstacle the short step moves the hero along it. Not
green; the items stay `[planned]`.

Real input, run `combat/20261127-152340` (5 failures; not green). The
operator still saw the defect in play after the fix: TPS, A and W held,
the hero walked straight ahead. `key_combo` did not show it:

- 417 rows. The game saw 4 downs and 4 ups of each key, as sent. No row
  with the script key state or the direction flags off the keys.
- W+A: 95 rows, travel 12.8 forward and 13.0 left, heading 46 (want 45).
  S+D: 93 rows, heading -138 (want -135). No stall and no row off the
  heading, with 24 rows in aim and a camera turn of 74 degrees.
- Failing: 6 mouse button downs counted, 7 sent (`key_combo` and
  `RealClicks`). Which button is not known; the harness counts them
  together.
- Failing: `key_real`. The game saw no W down. The same key was seen in
  the run before. Cause not known.
- Failing: `key_strafe` at the block, as above.

Open: the defect of the operator's report is not reproduced. Not covered
by `key_combo`: the real start (intro, drop, touchdown), enemies and
hits, a real keyboard and mouse, holds longer than 2 s, the jump key.

### 5.8b Stuck recorder (`systems/recorders/move_log.galaxy`)

- Operator 2026-11-27: a direction key is held and the hero stands. A
  camera turn does not free it. Another key does not free it. Both force a
  new move order in 5.8a, so a move order that is not reissued is not the
  cause. Cause not found. [plan]
- Every launch of the shipped map records, player 1, as the crosshair
  recorder does (SPEC-TPS 5.8a). Bank `SCOBAMOVELOG`, section `movelog`,
  cleared at map start; `meta/build` holds the build stamp. It changes no
  game state. Remove it when the cause is fixed.
- It has its own triggers on the four key events: the keys the game saw,
  apart from the script key state.
- Each game loop it keeps the hero position. Entries:
  - `stuck`: a key is down, by the key events or by the script, for 8
    loops (0.5 s), and the hero's path in them is under 0.15 (a walk: about
    1.5). The path is the sum of the steps of the loops: a turn-around
    walks out and back and is not a stand. Once per case. Then `before`:
    the short state of the last 32 loops.
  - `free`: the hero travels again with the key still down.
  - `released`: every key went up while it stood.
  - `keys`: the script key state differs from the key events for 2 loops.
  - `mark`: key M, the key of the crosshair recorder: the state now and
    `before`.
- State of an entry:
  - keys by the events, script key state, direction flags, two-button walk;
  - input hold and its scene owners;
  - TPS, strafe, aim, order mode, free cursor, mouse holds;
  - the strafe target;
  - runs of the movement tick (`gv_moveTicks`) and steps it issued
    (`gv_moveSteps`): tick runs with no steps is a guard, steps with no
    travel is a unit that cannot move;
  - the first three orders with their targets;
  - every behavior of the hero, the stand root, the states move
    suppressed, turn suppressed and stunned, the jump phase, the speed;
  - pathing at the hero and 0.5, 2 and 6 ahead on the key heading (the
    test of the strafe step);
  - each unit within 2.5.
- Test, group `keys`, section `key_stuck`
  (`galaxy/combat/combat_keys_stuck.galaxy`,
  `profiles/combat_parts/combat_keys_stuck.py`). W is held and the hero is
  stunned: one
  `stuck` entry, its state shows the stun and steps without travel. The
  stun ends: one `free` entry. Negative: W held on free ground writes no
  `stuck` entry; a stand with no key writes none; a turn-around (W, then
  also S) writes none. A key through the script entry alone, with no key
  event: one `keys` entry. [plan]
- Run `combat/20261127-162040` (10 failures; not green). The recorder
  loaded and wrote. Every `key_stuck` check passed. Its bank showed two
  things:
  - An entry for each turn-around of `key_ws` and `key_ad` (`stuck` 2 to
    5): travel was measured end to end. Now the path is summed; the
    turn-around case above is the test.
  - `stuck` 1, in `key_real`: the real W was down, the script stepped
    (`order0=move@point,d0.50`), and the ground 0.5, 2 and 6 ahead was not
    passable. Head-on at blocked ground the hero stands.
- Same run, `key_combo`: the game saw A down and, 0.125 s later, A up. The
  host sends that up 2 s later. No host key reached the game after it; all
  7 mouse button downs did. The keyboard focus left the game window, or
  the game released the key itself: not known which. `play` now reads the
  focus window before each key and button and stops with an error when it
  changed (`input_driver.focus_id`).
- Run `combat/20261127-162819` (1 failure: `key_strafe` at the block, the
  open point of 5.8a; not green, so the items stay `[plan]`). Every
  `key_stuck` check passed, the turn-around case too. `key_real` and every
  `key_combo` check passed: keys and the 7 button downs as sent (left 3,
  middle 2, right 2), W+A heading 46, S+D heading -138, no stall. The
  recorder's bank held 4 `stuck` entries: the blocked ground of
  `key_real`, the two input holds of `key_scene` (`held=1`), the stun of
  `key_stuck`. None for a turn-around.
- Operator's play, build `741b28c8b830-280ca76ba0874f38` (2026-11-27). At
  mark 2 the operator held D and the hero stood. The entry: no key down by
  the key events for 1.2 s before the mark (`raw=0 keys=0 flags=0`); the
  last event was W up. The script followed the key events. What the
  recorder lacked:
  - no `stuck` entry: it needs a key down by the key events;
  - no time of each key edge, and 2 s of rows: it does not show when D
    was lost, or whether its down ever came;
  - only the four keys: no modifier, no other key, no mouse button;
  - nothing outside the game to compare with.
  Cause not found.
- Input edge log (`systems/recorders/move_log_keys.galaxy`). Every edge the game
  gives the script, with game time, as `<ms><d|u><name>`: [plan]
  - `W`, `S`, `A`, `D`: the recorder's triggers on the four keys;
  - `k<code>`: one trigger on any key (`c_keyNone`), the four keys too: a
    second witness of each of them;
  - `B1`, `B2`, `B3`: the left, middle and right mouse button.
  A tap, a down and an up of one key with no edge between, is one entry
  `<ms>rk<code>*<n>from<ms of the first down>`; taps of that key in a row
  add to its `n`. The last 480 entries are kept. A `mark` and a `stuck`
  write them as `edges` entries, 24 each, oldest first.
- A `mark` writes the last 160 loops (10 s) as `before`; a `stuck` the
  last 32. A `mark` carries the travel of the window. At most 6000
  entries. [plan]
- Host key log (`scripts/testkit/host_keys.py`; `make key-log`, ARGS
  `--minutes n`). It reads the X server 250 times a second: the game keys
  (W A S D, Shift, Ctrl, Alt, Space, Z, E, C, M, Enter, Escape, Tab), the
  three mouse buttons, the focus window. It writes each edge with the
  clock time in ms to `$SC2_WORK/keylog/<stamp>.log`. [plan]
  - Keys and buttons are written only while the game window has the
    focus. Outside it only the focus change is written. On the way back
    in: the keys down at that moment.
  - Reading both logs: a key the host log holds down and the game's edge
    log has no down for was lost between the X server and the script. A
    focus change at that time names the window that took it. The M key
    is in both logs: it ties the two clocks.
- Test, group `keys`, section `key_combo`. The host log runs for the
  sequence. The host presses M once with S and D down. [plan]
  - host log: downs and ups of each key and button as sent, none else;
    the focus never left the game;
  - edge log: `W S A D` downs and ups as sent; the `k` edges of those
    keys and of M as sent; button edges as sent;
  - Negative: no `k` edge of a key the host did not send;
  - one `mark` by the real M: its state has S and D down and a travel,
    and it wrote its 160 rows and its edges;
  - Negative: no `k` edge and no button edge in `key_stuck`, where only
    the script sends keys.
- Run `combat/20261127-165541` (5 failures). The host log and the mark
  passed. The edge log held 580 edges for 80 sent and its 240 places had
  lost the sequence: the game got a NumLock tap (`k81`) with every key
  event. Taps are one entry since then.
- Run `combat/20261127-170350` (2 failures; not green, the items stay
  `[plan]`).
  - Passed: the host log (keys and buttons as sent, focus in the game
    throughout); the edge log for the four keys, their `k` edges, M and
    the buttons; the mark (S and D down, travel 1.54, 166 entries); every
    `key_stuck` check; `key_real`; the other `key_combo` checks.
  - Failed, `key_combo edge log: no key the host did not send`:
    `dk81` 250, `uk81` 250. One NumLock tap before each key edge, and
    about 27 in each 1.7 s hold. The X server has Num Lock on and repeats
    a held key 25 times a second after 660 ms (`xset q`): the taps follow
    the X key events, the repeats too. The game does not pass the repeats
    themselves to the script (`repeats=0`). Whether a real keyboard gives
    the same taps, and whether they have a part in a lost key: not known.
  - Failed, `key_strafe` at the block: the open point of 5.8a.
- Operator's play, build `741b28c8b830-cb21f46f7bfb777d` (2026-11-27),
  host log `keylog/20261127-170832.log`. Marks 1 and 2: D held, the hero
  stood (`raw=0 keys=0`). Both logs, tied by the first M down (game ms =
  host ms - 1795799506494; the game's times are steps of one loop, 62.5
  ms, so a game edge reads up to one loop later than its host edge):
  - The X server held D down for 6.2 s, from 2.8 s before mark 1 to 0.9 s
    after mark 2. The game got no D down in that time, by the four-key
    trigger or by the any-key trigger. The key was lost between the X
    server and the script. The movement code had no key to act on.
  - In the 38 s the edge log held, the host log has about 60 downs of the
    four keys. The game got all but three: D (game ms 150696), W
    (151531), D (151669). Their ups did not come either.
  - Each of the three fell in the gap between a left-button up and the
    next left-button down: 39, 12 and 16 ms after the up; 0, 18 and 10 ms
    before the down. The right button was held (aim) and the left button
    clicked every 130 ms or so.
  - At each of the three the game got a NumLock tap (`k81`) and no key
    edge after it. In the test runs a tap comes with each X key event. So
    the key press likely reached Wine. Inferred, not proven.
  - Other downs with the left button clicking arrived: one 13 ms before a
    button down with no button up before it; ones 13, 44, 67 and 71 ms
    after a button down.
  Where the key is dropped, in Wine or in the game, is not known. Three
  cases in one 38 s window: that the clicks cause the loss is not shown.
  The host log has no second witness.
- Test, group `keys`, section `key_race`
  (`profiles/combat_parts/combat_keys_race.py`,
  `galaxy/combat/combat_keys_race.galaxy`). In TPS with the right button held the
  host clicks the left button 180 times and sends key downs 12 ms after a
  button up and 15 ms before the next button down (D and W, 15 each), and
  as a control in the middle of a button hold (A and S, 15 each). The
  edges go out at once (`input_driver.key_edge`, `button_edge`); the mouse
  moves through every round (`sweep` steps, 2 pixels about every 4 ms,
  both ways). [plan]
  - every key down and up the host sent reaches the game: the harness
    recorder, the script key state and the map's own key triggers;
  - the hero walks while a key is down;
  - the arrangement: 180 left clicks, one aim hold, the camera turned;
  - host log `host_keys_race.log`: edges as sent, and each gap key down
    within 60 ms after a left-button up and before the next down;
  - Negative: no key left down at the end, no up without a down.
- The three runs below were started without asking whether the desktop
  was free. It was in use (operator 2026-11-27): real keys, pointer moves
  and focus changes from the desktop can be in each of them. None of them
  proves or disproves anything about the lost keys.
- Run `combat/20261127-193353` (6 failures; not confirmed), `key_race`
  without mouse motion. All 60 key downs and ups arrived, the 30 gap downs
  8 to 13 ms after the button up and 12 to 17 ms before the next down by
  the host log. A NumLock tap came with each key event here too (240
  `k81` edges for 120 key edges).
  - Failed, `key_combo`: the game got one of the two middle clicks
    (`dB2` 1, sent 2). The X server held both. The lost one came 0.58 s
    after the first, which had turned the free-cursor state on; the mark
    after it still has `free=1`. Not confirmed as a lost edge: input from
    the desktop is not ruled out.
  - Failed: the host log lacked the last button up (the log stopped with
    the sequence; the sequence ends with a wait since then), the `k81`
    check, `key_strafe`.
- Run `combat/20261127-194334` (19 failures; invalid). The focus guard
  stopped the sequence before the first click: the focus went from the
  game to window `0x600003` (1x1 at -100,-100, override redirect, no
  name: the window manager's own) 0.27 s after the right-button down.
  Before that the X server had an Alt tap the host did not send.
  `key_combo` got one of the two middle clicks again.
- Run `combat/20261127-195020` (invalid): no test bank. The game window
  had the focus for 3.4 s, lost it to the same window, and the game was
  gone. No crash folder, no `ScriptError.txt`.
- Open: `key_race`, with or without mouse motion, has no valid run. A run
  needs the operator's word that the desktop is free.
- Read in the code, not tested as a cause: on every left-button up in TPS
  the script clears the selection and selects the hero again
  (`gf_SelectHeroForce`, `targeting.galaxy`). The three lost downs of the
  operator's play fell 12 to 39 ms after such an up. `key_race` ran that
  path 180 times in run `193353` and lost no key (run not confirmed).
- Leads from reports of others, none tested here:
  - An input method between X and Wine. This desktop runs `ibus-daemon`
    1.5.29-rc2 with `XMODIFIERS=@im=ibus`, GNOME on Wayland, the game on
    Xwayland. Reports name ibus for key events lost or out of order in
    Wine games (ibus issues 2480 and 2656, a Linux Mint 22.3 forum
    thread). Most are about lost key ups; ours are lost key downs.
  - Num Lock. Wine bug 60059: with Num Lock on and a low-level keyboard
    hook, Wine sends a NumLock key before every key. It matches the `k81`
    taps. Wine bug 59055: StarCraft II wants Num Lock off at launch for
    some shortcuts. Only the titles and a summary were read. Neither
    says a key down is lost.
- `scripts/launch-scoba.sh` sets `XMODIFIERS=@im=none` for the game
  (operator 2026-11-27), so its window takes no input method. The play
  and the test runs both start through it. Not verified: that the game
  process gets the value, and that it ends the lost keys. [plan]

### 5.9 Weapon Attack button and cooldown clock

- The button is `SCOBAAutoAttackStatus`. Its handler calls `gf_PncAttack`.
  [tested] `weapon_button`
- The clock is drawn by the engine from the button ability's own cooldown:
  `<Cooldown Link="Abil/SCOBAAutoAttackStatus" Location="Ability" TimeUse="1"/>`.
- Data starts it on every shot (F14). `SCOBAAttackCooldown10` sets it to
  1 s; the talons used `SCOBAAttackCooldown15` (1.5 s) until 2026-11-23.
  [tested]
  - `Tosh` fires the set `SCOBAToshShot`: `ToshU`, then the cooldown effect.
  - `RazorTalonsPersistent` runs it as `InitialEffect`.
  - `PsiBlastLaunchMissile` runs it as `LaunchEffect`.
- The auto weapons are children of the stock weapons and run the same effects.
- `TimeUse` is `1`: the engine draws the clock only when it is above 0. The
  ability therefore starts a 1 s clock whenever it executes, also on an
  enemy out of weapon range in Chase `stand`, where no shot fires. Accepted
  by the operator; R-PNC-49 was dropped.
- Script never sets, reads, or times the cooldown.
- The weapons keep the unit link `SCOBA/Attack`. The button no longer uses it.
- Whether the clock draws is [operator].

### 5.10 Naming

`ButtonData.xml` [built]:

- `SCOBAControlPNC`: `Controls: WASD / Point & Click`.
- `SCOBAAutoAttackOn` / `Off`: `Attack: Auto` / `Attack: Single`.
- `SCOBARightClickMove` / `Stand`: `Chase: Move` / `Chase: Stand`.
- The `Weapon Attack` tooltip says the button is disabled while the weapon
  recharges. No test shows that. [planned]

Ability ids keep their names. New code uses `Pnc`.

### 5.11 Shooting pose hold

R-PNC-80 to 82. [tested] for the script state, run
`combat/20261117-000426`. The look is [operator].

Cause of the report: `gf_AnimTick` kept the upper body posed only inside the
attack window, 0.5 s / (1 / weapon period). For Tosh (period 0.25 s) that is
0.125 s. After it the tick cleared the `SCOBAUp` bracket.

- A shot plays the attack clip on `SCOBAAimAtk` and the pitch pose
  `Ready,Alternate,NN` on `SCOBAUp` (unchanged).
- `gf_AnimReadyHold(player)` is true for Tosh, not aiming, while he has an
  `attack` order or `gv_animReadyUntil` has not passed. In TPS it also needs
  Attack `auto` (R-TPS-17, SPEC-TPS 5.9).
- `gf_AnimAttackStart` sets `gv_animReadyUntil` to now +
  `c_ANIM_READY_LINGER` (2 s) on each shot.
- `gf_AnimTick`: attack window over and hold on gives upper state
  `c_ANIM_UPPER_READY`. `gf_AnimUpperSet` then keeps `SCOBAUp` as it is. The
  pitch tick keeps the pose on the target. Hold off gives `NONE`, which
  clears the bracket, as before.
- `gf_PncCancel` calls `gf_AnimReadyEnd`. Hero switch and death go through
  `gf_AnimReset`. Aim entry clears the linger.
- Legs are untouched: no lower override.
- This is animation state only. It issues no order and times no attack
  (R-PNC-2).

Not confirmed: what the engine's own attack animation shows under the
bracket between shots. [open] If idle still shows through, actor data needs
a change. That is the operator check in section 9.

Tosh attack clip rate (operator 2026-11-17: 2x). [built], not verified.
`gf_AnimAttackSpeed` multiplies the weapon-period factor by
`c_ANIM_ATTACK_RATE_TOSH` (2.0) for Tosh only. Both shot paths (not aiming
and aiming) read it. Tosh at the 0.15 s period: factor 13.3, time scale
26.7, attack window 0.0375 s (at 0.25 s: 8, 16, 0.0625 s).
The clip span shown per shot is unchanged; it plays in half the time. The
ready linger (2 s) does not depend on it. Kerrigan is unchanged. Test:
`combat pose`, section `attack_rate`. The look is [operator].

## 6. Module Structure [planned]

| Layer | Module | Owns |
| --- | --- | --- |
| Shared | `systems/ui_target.galaxy` | UI target, boss bar. From `targeting.galaxy`. |
| Shared | `systems/toggles.galaxy` | Attack and Chase toggle state, root sync. |
| Shared | `systems/movement.galaxy` | WASD key state and move orders. |
| Shared | `systems/strafe.galaxy` | Strafe hold state, strafe move step, loop step. |
| Shared | `systems/mouse_input.galaxy` | Raw button and hold state. Dispatches to the active mode. |
| Shared | `systems/orders.galaxy` | Order mode. Unchanged. |
| Mode | `modes/pnc.galaxy` | PNC click, hold, attack, and cancel actions. |
| Mode | `modes/tps.galaxy` | TPS click and aim entry. Moved as is. |

`mouse_input` calls exactly one mode module per event. Mode modules call
shared modules. Shared modules never test the mode. A mode switch calls
`gf_MouseInputReset(player)`.

Today the PNC functions live in `systems/combat_fsm.galaxy`
(`gf_PncAttack`, `gf_PncAttackEnd`, `gf_PncShotFired`, `gf_PncCancel`, root
sync) and the handlers in `systems/targeting.galaxy`, `camera.galaxy`,
`combat_attack.galaxy`.

## 7. Aim-Shot Work (TPS)

Decision: parked, not reverted. The TPS phase replaces it; see
[SPEC-TPS](SPEC-TPS.md) section 5.5.

- Its script (`aim_shooting.galaxy`, the trace) stays untouched. PNC code does
  not call it.
- `gt_CombatAttackEffect` stays. PNC uses it for the single shot (5.5).
- The five aim abilities stay over the 32 cap (F16) and stay dead. They do not
  affect PNC.
- `scripts/validate_aim_shot.py` checks the cooldown link. It follows 5.9.

## 8. Tests

- Entry point: `scripts/playtest.sh combat [group]`. Groups: `idle`, `single`,
  `auto`, `cancel`, `wasd`, `keys`, `hold`, `button`, `switch`, `pose`,
  `kerrigan`. No group runs all.
- `pose` reads script animation state (upper state, pitch step, bracket
  clear count) beside shots, damage and orders. Galaxy cannot read what an
  actor bracket plays.
- One group takes about one minute. The full suite takes about three.
- Engine probes live in the `pncprobe` profile. They record raw values and
  assert nothing about the product.
- A run with real mouse clicks is invalid. The suite fails it.
- Missing tests: left click, Ctrl + C, friendly follow, order mode, real
  mouse input for the holds.

## 9. Operator Checks

- The cooldown clock on the `Weapon Attack` button (5.9).
- The toggle button labels and icons (5.1, 5.10).
- Firing without turning to the target in Attack `auto` (5.2).
- Backpedal and strafe animation in a right hold (5.8).
- The ground move marker (5.4). No `Out of range` text shows (R-TPS-79).
- Attack animation, effects, and sound.
- Tosh holds the shooting pose between sequential shots and for 2 s after
  the last, with no idle flicker (5.11).

## 10. Remaining Work

1. Operator checks (section 9).
2. Friendly follow (5.4), missing tests (8), module split (6).

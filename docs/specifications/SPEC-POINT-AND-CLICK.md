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
| F9 | The effect-used event fires once per shot for all three hero weapons. | [tested] `single_shot`, `talons_single`, `psiblast_single` |
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
| R-PNC-24 | [tested] | `single_out_stand`: no order, no movement. The floater is [operator]. |
| R-PNC-25, 27, 28 | [tested] | `ground_move`, `ground_stand`. The ground marker is [operator]. |
| R-PNC-26 | [planned] | A friendly right click still moves to the click point. |
| R-PNC-30, 33 | [tested] | `cancel`. |
| R-PNC-32 | [built] | No test for Ctrl + C. |
| R-PNC-40, 51, 52 | [tested] | `auto_stand_in`, `auto_stand_out`, `auto_move_near`. |
| R-PNC-41 | [tested] | `single_idle`, `single_attacked`. |
| R-PNC-42, 45 | [tested] | `single_shot`, `weapon_button`. |
| R-PNC-43 | [tested] | `auto_to_single`. |
| R-PNC-44 | [tested] | `switch_single_stand`, `switch_auto_move`, hero state and button state. |
| R-PNC-46, 49 | [tested] | The button cooldown runs after every shot path and stays 0 after a press with no shot: `single_shot`, `weapon_button`, `button_out`, `auto_click`, `auto_stand_in`, `talons_single`, `psiblast_single`, `talons_auto`. The clock overlay is [operator]. |
| R-PNC-47 | [tested] | `startup`, hero state and button state. |
| R-PNC-48 | [tested] | `toggle buttons match hero state` over every snapshot; `auto_to_single`; both switch scenarios. |
| R-PNC-50, 53 | [tested] | `wasd_stand`, `auto_stand_out`. |
| R-PNC-54 | [tested] | `move_fire_auto`, `move_fire_single`, run `combat/20261114-144027`. |
| R-PNC-55, 56, 60 to 63 | [built] | Unchanged this phase. No test yet. |
| R-PNC-64, 65 | [tested] | `hold_right_back`, `hold_right_left`, `hold_middle`. The tests set the hold flags; the real mouse path has no test. The clips' look is [operator]. |
| R-PNC-66, 67 | [built] | Unchanged this phase. No test yet. |
| R-PNC-68 | [tested] turn and forward walk; [operator] strafe and backpedal clip rate | `hold_middle_fwd`, `hold_right_fwd`, `hold_right_turn`. See 5.8. |
| R-PNC-70, 71, 72 | [planned] | Handlers are shared and branch on the mode. Design in 6. |
| R-PNC-73, 74 | [built] | Labels are in `ButtonData.xml`. Their look is [operator]. |
| R-PNC-75 | [built] | No test yet. |

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

- `SCOBAAttackSingle` lists the three auto weapons in `WeaponDisableArray`.
- Attack `single` has no shot while WASD-moving. A WASD `move` order replaces
  the attack order.
- WASD issues plain `move` orders only.
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
| Out of range | `stand` | Set UI target. No order. Show `Out of range` at the enemy. |

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
  hold. `gf_StrafeHoldSync` sets it on the camera turn tick. Action mode and
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

### 5.9 Weapon Attack button and cooldown clock

- The button is `SCOBAAutoAttackStatus`. Its handler calls `gf_PncAttack`.
  [tested] `weapon_button`
- The clock is drawn by the engine from the button ability's own cooldown:
  `<Cooldown Link="Abil/SCOBAAutoAttackStatus" Location="Ability" TimeUse="0"/>`.
- Data starts it on every shot (F14). `SCOBAAttackCooldown10` and
  `SCOBAAttackCooldown15` set it to 1 s and 1.5 s. [tested]
  - `Tosh` fires the set `SCOBAToshShot`: `ToshU`, then the cooldown effect.
  - `RazorTalonsPersistent` runs it as `InitialEffect`.
  - `PsiBlastLaunchMissile` runs it as `LaunchEffect`.
- The auto weapons are children of the stock weapons and run the same effects.
- `TimeUse` is `0`, so a press that fires no shot starts no clock. [tested]
  `button_out`
- Script never sets, reads, or times the cooldown.
- The weapons keep the unit link `SCOBA/Attack`. The button no longer uses it.
- Whether the clock draws is [operator].

### 5.10 Naming

`ButtonData.xml` [built]:

- `SCOBAActionModeRPG`: `Controls: WASD / Point & Click`.
- `SCOBAAutoAttackOn` / `Off`: `Attack: Auto` / `Attack: Single`.
- `SCOBARightClickMove` / `Stand`: `Chase: Move` / `Chase: Stand`.
- The `Weapon Attack` tooltip says the button is disabled while the weapon
  recharges. No test shows that. [planned]

Ability ids keep their names. New code uses `Pnc`.

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
| Mode | `modes/action.galaxy` | Action mode click and aim entry. Moved as is. |

`mouse_input` calls exactly one mode module per event. Mode modules call
shared modules. Shared modules never test the mode. A mode switch calls
`gf_MouseInputReset(player)`.

Today the PNC functions live in `systems/combat_fsm.galaxy`
(`gf_PncAttack`, `gf_PncAttackEnd`, `gf_PncShotFired`, `gf_PncCancel`, root
sync) and the handlers in `systems/targeting.galaxy`, `camera.galaxy`,
`combat_attack.galaxy`.

## 7. Aim-Shot Work (Action Mode)

Decision: parked, not reverted. The next phase builds on it.

- Its script (`aim_shooting.galaxy`, the trace) stays untouched. PNC code does
  not call it.
- `gt_CombatAttackEffect` stays. PNC uses it for the single shot (5.5).
- The five aim abilities stay over the 32 cap (F16) and stay dead. They do not
  affect PNC.
- `scripts/validate_aim_shot.py` checks the cooldown link. It follows 5.9.

## 8. Tests

- Entry point: `scripts/playtest.sh combat [group]`. Groups: `idle`, `single`,
  `auto`, `cancel`, `wasd`, `hold`, `button`, `switch`, `kerrigan`. No group
  runs all.
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
- The `Out of range` floater and the ground move marker (5.4).
- Attack animation, effects, and sound.

## 10. Remaining Work

1. Operator checks (section 9).
2. Friendly follow (5.4), missing tests (8), module split (6).

# SPEC-COMBAT-CONTROLS: Combat FSM

**Date:** 2026-11-09
**Status:** Draft
**Contract:** [REQ-COMBAT-CONTROLS](../requirements/REQ-COMBAT-CONTROLS.md)

## 1. Purpose

This specification defines the combat finite state machine for SCOBA heroes.
It replaces the ad-hoc combat branch in `systems/combat_tick.galaxy`.

The design follows verified StarCraft II behavior:

- `AbilityCommand("move", 2)` is Hold Position.
- A hidden root behavior with `ModifyFlags SuppressMoving` prevents chase.
- An attack order on a unit chases the unit until it is in weapon range.
- `TriggerAddEventUnitStartedAttack2` fires when a unit starts an outgoing
  attack.
- `TriggerAddEventUnitAttacked2` fires when a unit is attacked. The attacking
  unit is `EventUnitTarget()`.

## 2. Evidence

### 2.1 Move command indexes

`mods/core.sc2mod/base.sc2data/gamedata/AbilData.xml` defines `CAbilMove`:

| Index | Command |
| --- | --- |
| 0 | Move |
| 1 | Patrol |
| 2 | Hold Position |
| 3 | Acquire Move |
| 4 | Turn |

The current `move 2` order in `combat_attack.galaxy` is therefore Hold
Position, not a generic stop.

### 2.2 Stand attack

Per Blizzard basic unit controls, Hold Position keeps the unit stationary and
attacks enemies inside range. The unit does not chase.

The map test showed that `Order(AbilityCommand("move", 2))` did not produce an
attack order for these heroes while `DefaultAcquireLevel` was `None`.

The implementation separates stance state from movement lock:

- `SCOBARightClickStandBehavior` records the Stand stance only;
- `SCOBAStandRoot` sets `ModifyFlags SuppressMoving`;
- the FSM adds the root while Stand is active, independent of auto state;
- the FSM removes the root only on Walk, reset, and player movement;
- removing the root restores movement, so WASD still works in Stand;
- the FSM issues attack orders on enemies inside the keep radius;
- user-issued attacks stay in Stand and do not chase;
- the root returns after WASD release while stationary;
- movement keys keep the root removed and attacks run while moving;
- `UnitTestState(hero, c_unitStateMoveSuppressed)` is the state readback.

`MoveSpeedMultiplier` is not a movement lock. It only changes speed. A unit can
still receive and execute movement from an attack order. `SuppressMoving`
immediately interrupts movement and prevents new movement.

### 2.3 Outgoing attack event

`TriggerAddEventUnitStartedAttack2(trigger, unitref, weapon)` fires when a unit
starts an attack. Use `EventUnit()` for the attacker and `EventUnitGetWeapon()`
for the weapon. This is the primary cooldown source.

`TriggerAddEventUnitAttacked2(trigger, unitref, weapon)` fires when a unit is
attacked. Its `EventUnitTarget()` is the attacking unit. It measures received
attacks and is not used for cooldown.

## 3. State model

State is per hero in `gv_sCOBAFSM[8]`.

| Constant | Value | Meaning |
| --- | --- | --- |
| `c_SCOBA_FSM_IDLE` | 0 | No auto intent. |
| `c_SCOBA_FSM_HOLD` | 1 | Stand, holding position. |
| `c_SCOBA_FSM_ATTACK` | 2 | Stand, enemy inside keep radius. |
| `c_SCOBA_FSM_CHASE` | 3 | Walk, attacking or moving to a target. |
| `c_SCOBA_FSM_MANUAL` | 4 | Manual attack owns the unit. |
| `c_SCOBA_FSM_MOVING` | 5 | WASD or order mode owns the unit. |

Map init sets Stand on and auto off.

The FSM does not copy the toggle flags. It derives them on every step:

- auto on if `UnitBehaviorCount(hero, "SCOBAAutoAttackBehavior") > 0`;
- stand if `UnitBehaviorCount(hero, "SCOBARightClickStandBehavior") > 0`.

The FSM stores intent:

- `gv_sCOBAFSM[8]`;
- `gv_sCOBAAutoTarget[8]`;
- `gv_sCOBAManualTarget[8]`;
- `gv_sCOBAAutoOrder[8]`;
- `gv_sCOBAManualOrder[8]`.

## 4. Transition table

| From | Event | Condition | To | Action |
| --- | --- | --- | --- | --- |
| any | map init | no auto behavior | IDLE | none |
| IDLE | auto on | stand | HOLD | lock movement |
| IDLE | auto on | walk | CHASE | acquire target |
| HOLD | enemy in keep | stand | ATTACK | issue attack order |
| ATTACK | enemy leaves keep | stand | HOLD | issue Stop |
| ATTACK | target dies | stand | HOLD | clear target |
| CHASE | enemy in chase | walk | CHASE | issue attack order |
| CHASE | no enemy | walk | IDLE | clear target |
| CHASE | enemy beyond keep | walk | CHASE | attack order continues |
| any auto | auto off | auto order active | IDLE | issue Stop |
| any auto | auto off | manual order active | MANUAL | no Stop |
| HOLD or ATTACK | stand off | auto on | CHASE | clear auto order |
| CHASE | stand on | auto on | HOLD | cancel auto order, lock movement |
| CHASE or HOLD | manual attack | any | MANUAL | cancel auto order, issue attack |
| MANUAL | target dead | any | IDLE | clear manual target |
| any | WASD start | any | MOVING | keep targets, remove root |
| MOVING | attack tick | auto or manual target | MOVING | issue native attack while moving |
| MOVING | WASD end | auto on | IDLE | next tick resumes |
| MOVING | WASD end | manual target | MANUAL | reissue attack order |
| any | order mode enter | any | MOVING | cancel auto order |
| MOVING | order mode exit | auto on | IDLE | next tick resumes |
| any | hero dead | any | IDLE | clear target and orders |

Target clearing in the auto rows clears `gv_sCOBAAutoTarget`.
It does not clear `gv_unitTarget` on idle, Stop, or move completion.
`gv_unitTarget` clears on target death, removal, ground left click, or explicit clear.

## 5. Module layout

| Module | Responsibility |
| --- | --- |
| `systems/combat_fsm.galaxy` | states, transitions, step, cancel, manual attack |
| `systems/combat_tick.galaxy` | periodic trigger, diagnostics, call `gf_CombatStep` |
| `systems/combat_attack.galaxy` | toggle handlers and attack event registration |
| `systems/combat_cooldown.galaxy` | outgoing attack measurement and status cooldown |
| `systems/targeting.galaxy` | right-click enemy calls `gf_CombatManualAttack` |
| `systems/controls.galaxy` | control mode toggle and action mode left-click attack |
| `systems/movement.galaxy` | WASD and order mode notify the FSM |
| `core/globals.galaxy` | FSM and cooldown globals |
| `core/constants.galaxy` | state constants and period bounds |

## 6. Algorithms

### 6.1 Combat step

`gf_CombatStep(int lp_player)` runs every 0.5 seconds.

1. Read `lv_hero`.
2. If invalid or dead, call `gf_CombatReset`.
3. If order mode is on, cancel auto and manual, call `gf_CombatBeginMove`, return.
4. If any movement key is held, remove the root, set `MOVING`, return.
   Movement loops own moving shots through `gf_CombatRunGunStep`.
5. If state is `MOVING`, set `IDLE`.
6. If a manual target is alive, reissue its attack order and return.
7. If auto is off, call `gf_CombatCancelAuto`, set `IDLE`, return.
8. Read stance.
9. If stand, call `gf_CombatStand`.
10. If walk, call `gf_CombatWalk`.

### 6.1.1 Moving attack

Weapon data is the native movement gate. Map overrides set
`CWeaponLegacy AllowedMovement = Moving` on `Tosh`, `RazorTalons`, and
`QueenOfBladesPsiBlast`. This is the same mechanism used by native air units
that fire while moving.

Movement loops own moving shots. They call `gf_CombatRunGunStep` before each
move order. The helper synchronously holds the loop for one shot.

`gf_CombatMovingTarget(int lp_player)`:

1. Prefer a live manual target.
2. Otherwise use the live auto target inside stance radius.
3. Otherwise acquire the closest enemy inside stand keep radius or walk
   chase radius.
4. Clear and return null when no valid target exists.

`gf_CombatRunGunStep(int lp_player)`:

1. Return when auto is off and no manual target exists.
2. Return when `gf_WeaponReady` is false.
3. Get the target from `gf_CombatMovingTarget`.
4. Return when the target is missing or out of weapon range.
5. Issue exactly one native attack order.
6. Wait until the weapon cooldown starts, or `c_SCOBA_RUNGUN_TIMEOUT`.
7. Keep the movement loop blocked for at least `c_SCOBA_RUNGUN_HOLD`.

The wait covers the weapon damage point and muzzle flash. The movement loop then
issues the next move order. The combat tick never issues moving attacks.

Stand moving attacks never chase. Walk moving attacks never replace movement.
Attack-order spam is forbidden. One shot equals one attack order.

### 6.2 Stand

`gf_CombatStand`:

1. Add `SCOBAStandRoot`.
2. Find the closest enemy inside `c_SCOBA_KEEP_RADIUS`.
3. If none, clear the auto target, issue Stop when an auto order is active,
   and set state `HOLD`.
4. If a target exists, issue an attack order unless the hero is already
   attacking that target.
5. Set state `ATTACK`.

`SCOBAStandRoot` sets `ModifyFlags SuppressMoving`. The attack order cannot move
the hero. The hero never chases in Stand.

The root depends on the Stand behavior only. Auto on and auto off do not change
it. User-issued attack orders in Stand stay under the root and do not chase.

Player movement removes the root and runs moving attacks. The next stationary
combat tick re-adds it while Stand is active. WASD therefore remains responsive
and can fire on the move.

`gf_CombatSyncRoot` is the single root enforcement point:

1. Remove the root when a movement key or order mode is active.
2. Add the root when `SCOBARightClickStandBehavior` is present.
3. Remove the root otherwise.

The map test verifies Stand attack, no displacement, root presence,
`c_unitStateMoveSuppressed`, root removal on movement, root return on release,
and root persistence during manual attack.

Manual attack calls `gf_CombatSyncRoot` before issuing the attack order. The
combat step calls it before the manual-order early return.

### 6.3 Walk

`gf_CombatWalk`:

1. Read `gv_sCOBAAutoTarget`.
2. If the target is valid, alive, hostile, and inside `c_SCOBA_KEEP_RADIUS`,
   and the hero has no attack order, issue an attack order and set
   `gv_sCOBAAutoOrder = true`, state `CHASE`.
3. If the target is invalid, clear it.
4. Find the closest enemy inside `c_SCOBA_CHASE_RADIUS`.
5. If none, clear target and order, set state `IDLE`.
6. Issue an attack order on the target and set `gv_sCOBAAutoOrder = true`,
   state `CHASE`.

An attack order is the StarCraft II primitive that chases when the hero is
stationary. While a movement key is held, `gf_CombatMoveAttack` starts the shot
and movement input keeps control of position.

### 6.4 Manual attack

`gf_CombatManualAttack(int lp_player, unit lp_target)`:

1. Validate the target and the hero.
2. Call `gf_CombatCancelAuto`.
3. Call `gf_CombatSyncRoot`.
4. Store `gv_sCOBAManualTarget = lp_target`.
5. Set `gv_sCOBAManualOrder = true`.
6. Set state `MANUAL`.
7. Return when a movement key is held. The movement loop fires the shot.
8. Issue `OrderTargetingUnit(AbilityCommand("attack", 0), lp_target)` with
   `c_orderQueueReplace`.

The root is present before the attack order only while stationary in Stand.
Movement removes the root and uses `gf_CombatRunGunStep`. The manual target
persists until it dies or is cleared.

`gf_CombatOnIdle(int lp_player)` clears `gv_sCOBAManualOrder`, clears the manual
target, clears the auto target, and sets state `IDLE`.

### 6.5 Auto off

`gf_CombatCancelAuto(int lp_player)`:

1. Clear `gv_sCOBAAutoTarget`.
2. If `gv_sCOBAAutoOrder` is true and `gv_sCOBAManualOrder` is false, issue
   `Order(AbilityCommand("stop", 0))`.
3. Set `gv_sCOBAAutoOrder` to false.

Auto off does not remove `SCOBAStandRoot`. Stand holds with auto on or off.

### 6.6 Stance toggle

The toggle ability is the only writer of `SCOBAAutoAttackBehavior` and
`SCOBARightClickStandBehavior`. The handlers do not add or remove behaviors.
They observe the result, update the FSM, and update the command card.

`gf_CombatSetStance(int lp_player, bool lp_stand)`:

1. Read the actual behavior count after the ability resolves.
2. Call `gf_CombatCancelAuto`.
3. Call `gf_CombatStep(lp_player)` when auto is on.

### 6.6.1 Toggle button faces

StarCraft displays the Off command while a toggle behavior is active, and the
On command while it is inactive.

Layout buttons therefore map as follows:

| Layout index | Command | Face |
| --- | --- | --- |
| 51 | auto On | `SCOBAAutoAttackOff` |
| 52 | auto Off | `SCOBAAutoAttackOn` |
| 53 | chase On | `SCOBARightClickMove` |
| 54 | chase Off | `SCOBARightClickStand` |

This makes the visible face, name, and tooltip match the current state.

### 6.6.2 Control mode toggle

`SCOBAActionModeBehavior` is the only control mode state.
RPG mode is the absence of the behavior.
The control mode button sits at top row column 2.

`CAbilBehavior SCOBAActionModeToggle`:

- On command face: `SCOBAActionModeRPG`.
- Off command face: `SCOBAActionModeActions`.
- Toggle flag: on.
- Transient flag: on.
- Behavior: `SCOBAActionModeBehavior`.

Layout buttons:

| Layout index | Command | Face |
| --- | --- | --- |
| 55 | action On | `SCOBAActionModeRPG` |
| 56 | action Off | `SCOBAActionModeActions` |

The On command face is shown while RPG mode is active.
The Off command face is shown while action mode is active.
Names are `Controls: RPG` and `Controls: Actions`.

The toggle handlers call `gf_ActionModeApply` after the behavior changes.
They do not call the combat controller.
They do not change auto-attack, chase stance, cooldown, or the combat FSM.

Action mode left click resolves a hostile at `CameraGetTarget` and calls
`gf_CombatManualAttack`. Ground clicks do nothing. Alt UI clicks do nothing.
Action mode right hold calls aim mode and does not call the combat controller.

### 6.7 Cooldown

`gt_CombatStartedAttack` is registered per hero with
`TriggerAddEventUnitStartedAttack2`.

Handler:

1. `lv_player = gf_HeroPlayerFromUnit(EventUnit())`.
2. If invalid, return.
3. `lv_now = TimerGetElapsed(gv_sCOBA_Clock)`.
4. `lv_delta = lv_now - gv_sCOBALastAttackAt[lv_player]`.
5. If the previous time is greater than zero and `lv_delta` is between
   `c_SCOBA_MIN_ATTACK_PERIOD` and `c_SCOBA_MAX_ATTACK_PERIOD`, set
   `gv_sCOBAAttackPeriod[lv_player] = lv_delta`.
6. Set `gv_sCOBALastAttackAt[lv_player] = lv_now`.
7. Set `lv_period = gv_sCOBAAttackPeriod[lv_player]`. If zero, use
   `c_SCOBA_INITIAL_WEAPON_PERIOD`.
8. Call `UnitAbilityReset(hero, AbilityCommand("SCOBAAutoAttackStatus", 0),
   c_spendLocationAbility)`.
9. Call `UnitAbilityAddCooldown(hero, "SCOBAAutoAttackStatus",
   "Abil/SCOBAAutoAttackStatus", lv_period)`.

The cooldown is written once per outgoing attack. No periodic trigger rewrites
it. Removing and re-adding it every 0.1 seconds restarts the command-card ring.

`UnitAbilityGetCooldown` and `UnitCheckAbilCmdState` are the test readbacks.

The first attack uses `c_SCOBA_INITIAL_WEAPON_PERIOD`. The second attack replaces
it with the measured interval.

### 6.8 Weapon Attack button

`SCOBAAutoAttackStatus` becomes the Weapon Attack targeted ability:

- ability type: `CAbilEffectTarget`;
- target filters: enemy units and structures;
- range: 500;
- effect: empty `CEffectSet`;
- cooldown link: `Abil/SCOBAAutoAttackStatus`;
- cooldown location: `Ability`;
- cooldown time use: `2.0`, the maximum ring duration;
- button name: `Weapon Attack`;
- icon: `btn-command-attack.dds`;
- tooltip: manual attack and weapon cooldown.

Click behavior:

1. The button enters standard SC attack-target mode.
2. The player clicks an enemy target.
3. A trigger listens for `SCOBAAutoAttackStatus` at stage `Execute`.
4. The target comes from `EventUnitTargetUnit()`.
5. The handler clears the click-started cooldown with
   `UnitAbilityReset(hero, AbilityCommand("SCOBAAutoAttackStatus", 0),
   c_spendLocationAbility)`.
6. A valid enemy target calls `gf_CombatManualAttack`.
7. Cancelling target mode does nothing and starts no cooldown.

Button state:

- visible while auto-attack is on or off;
- enabled when the weapon cooldown is ready;
- disabled by the ability cooldown while recharging;
- the cooldown ring is the active animation;
- the face never represents auto-attack state.

### 6.9 Click targeting

Right-click targeting is specified in
[SPEC-MOUSE-CONTROLS](SPEC-MOUSE-CONTROLS.md).

The right command runs on clean right-button release. It uses the unit from the
native per-player `UnitClick` event. The same `UnitClick` unit serves RPG left
target, right attack, and order-mode right click. Action-mode left click uses
`gf_UnitTargetAtPoint` at the camera target. Unit Highlight may also supply the press-time Unit Target candidate but is never used for ability targeting.

Right command flow:

1. Right-click enemy: set target and call `gf_CombatManualAttack`.
2. Right-click ground in Stand: issue Stop and keep the root.
3. Right-click ground in Walk: issue Move.
4. Order mode: use the same target resolver at the press point.
5. A right drag runs no command.

A ground right click does not clear `gv_unitTarget`.
Hero idle, Stop, and move-order completion do not clear `gv_unitTarget`.
Only target death, removal, ground left click, or an explicit clear removes it.

`gt_DisableClickMove` blocks move orders only in Stand with no movement key held.
It allows move orders in Walk, during WASD, and in action mode.
It does not cancel the RPG Walk custom move.

### 6.10 Right-hold aim interaction

Right-hold aim is owned by [SPEC-MOUSE-CONTROLS](SPEC-MOUSE-CONTROLS.md).

Aim mode does not call the combat controller. It does not cancel auto-attack,
issue combat orders, change FSM state, or touch cooldown. The right command
still runs only from `gf_MouseReleaseRight` after the drag and cancel checks.

In action mode, right hold enters aim and runs no right command.
Action mode left click on the hostile at `CameraGetTarget` calls
`gf_CombatManualAttack`.
Action mode left click on ground, and any Alt UI click, does not call the
combat controller.

Aim animation layers, facing updates, and aim movement do not call the combat
controller. Aim movement is owned by `gt_AimMoveTick`; it never enters a combat
FSM state or issues a combat order. Their implementation is specified in
[SPEC-CHARACTER-ANIMATION](SPEC-CHARACTER-ANIMATION.md).

## 7. Event registration

| Event | Owner | Action |
| --- | --- | --- |
| `TriggerAddEventMapInit` | init | build heroes, set Stand on, auto off |
| `TriggerAddEventUnitAbility` stage On | auto toggle | read behavior, call step, refresh button |
| `TriggerAddEventUnitAbility` stage Off | auto toggle | read behavior, cancel auto, refresh button |
| `TriggerAddEventUnitAbility` stage On | chase toggle | read behavior, call stance, refresh button |
| `TriggerAddEventUnitAbility` stage Off | chase toggle | read behavior, call stance, refresh button |
| `TriggerAddEventUnitAbility` stage On | control toggle | apply action mode, refresh button |
| `TriggerAddEventUnitAbility` stage Off | control toggle | apply RPG mode, refresh button |
| `TriggerAddEventUnitAbility` stage Execute | Weapon Attack | manual attack |
| `TriggerAddEventUnitBehaviorChange` | auto behavior | sync auto state, step or cancel |
| `TriggerAddEventUnitBehaviorChange` | Stand behavior | sync root and stance |
| `TriggerAddEventTimePeriodic` 0.5 | combat tick | `gf_CombatStep` |
| `TriggerAddEventUnitStartedAttack2` | cooldown | measure hero attack and set combat cooldown; mirror aim-shooter native cooldown to hero |
| `TriggerAddEventUnitBecomesIdle` | FSM | clear manual, resume |
| `TriggerAddEventMouseClicked` fire down | targeting | save press state |
| `TriggerAddEventMouseClicked` fire up | targeting | run clean-click right command |
| `TriggerAddEventMouseClicked` cursor down and up | targeting | left target and button state |
| WASD key start and end | movement | keep targets, remove root, run moving attack or resume |
| order mode enter and exit | orders | cancel auto, set MOVING or resume |

## 8. Constants

| Constant | Value | Meaning |
| --- | --- | --- |
| `c_SCOBA_KEEP_RADIUS` | 12.0 | Stand attack radius |
| `c_SCOBA_CHASE_RADIUS` | 10.0 | Walk acquisition radius |
| `c_SCOBA_MIN_ATTACK_PERIOD` | 0.1 | Reject same-frame bursts |
| `c_SCOBA_MAX_ATTACK_PERIOD` | 2.0 | Reject stale intervals |
| `c_SCOBA_INITIAL_WEAPON_PERIOD` | 0.75 | First attack ring estimate |
| `c_SCOBA_AIM_SHOOTER_TOSH` | `SCOBAAimShooterTosh` | Hidden Tosh aim shooter |
| `c_SCOBA_AIM_SHOOTER_KERRIGAN` | `SCOBAAimShooterKerrigan` | Hidden Kerrigan aim shooter |

Mouse constants live in
[SPEC-MOUSE-CONTROLS](SPEC-MOUSE-CONTROLS.md).

## 9. Tests

The harness resets the hero to a fixed anchor before every scenario. It removes
all enemies before every scenario. It spawns exactly one enemy at a recorded
distance. It records elapsed time for every sample.

| Scenario | Spawn offset | Samples | Required result |
| --- | --- | --- | --- |
| Startup | none | 0.0 | auto 0, Stand 1, root 1, no attack order |
| Auto off | 3.0 east | +3.0 | no attack order, no damage, no displacement |
| Stand in range | 3.0 east | +0.5, +1.5, +2.5 | root 1, move suppressed, attack order, damage, displacement <= 1 |
| Stand out of weapon range | 11.0 east | +1.0, +2.5 | root 1, move suppressed, no damage, displacement <= 1 |
| Stand outside keep | 13.0 east | +2.0 | root 1, no attack order, displacement <= 1 |
| Stand movement wake | none | held key, before and after `gf_CombatBeginMove`, release | root 1 then 0, move suppressed then clear, move order moves hero, root returns after release |
| Stand move-and-shoot | 3.0 east | hold key +3.0 | displacement > 1, native attack event, damage, root 0, cooldown resets once |
| Walk move-and-shoot | 3.0 east | hold key +3.0 | displacement > 1, native attack event, damage, root 0, cooldown resets once |
| Manual move-and-shoot | 3.0 east | right-click enemy, hold key +3.0 | displacement > 1, manual target persists, native attack event, damage |
| Moving aim shot | 3.0 east | hold key, press aim shot | movement continues, hidden shooter attacks, hero has no attack order |
| Aim shooter cooldown | 3.0 east | press aim shot | shooter cooldown starts and mirrors to the hero weapon |
| Stand auto off manual | 9.0 east | manual attack +2.0 | root 1, no displacement |
| Stand repeated clicks | 9.0 east | 5 manual attacks | root stays, no displacement |
| Right press resolve | 3.0 east | press, release | enemy returned from shared resolver |
| Right ground outside radius | 3.0 east | hover enemy, press ground, release | no attack order, ground command by stance |
| Right drag cancel | 3.0 east | press, camera yaw change, release | no attack order |
| Right target select | 3.0 east | clean click enemy | target set, attack order |
| Target persists | 3.0 east | target, idle, Stop, idle | target remains set |
| Walk ground click | none | clean ground right click in Walk | hero moves |
| Stand ground click | none | clean ground right click in Stand | hero stops, root present |
| Walk chase | 9.0 east | +1.0, +3.0 | root 0, distance decreases, attack order, damage |
| Walk idle | 13.0 east | +2.0 | root 0, no movement, no attack order |
| Weapon attack | 3.0 east | +0.1, +0.2, +0.5, +1.0 | cooldown positive, command cooldown true, attack order, damage |
| Control default | none | map init | RPG behavior absent, RPG button shown |
| Control action on | none | toggle action | behavior present, Actions button shown |
| Control action attack | 3.0 east | left click enemy in action mode | manual attack, target set |
| Control action ground | none | left click ground in action mode | no order, no target change |
| Control action Alt | 3.0 east | hold Alt, left click enemy | no attack, no target change |
| Control action right | 3.0 east | right hold in action mode | aim active, no combat order |
| Control RPG return | none | toggle to RPG | behavior absent, RPG button shown, aim exited |

The harness writes position, distance, root count, move suppression, order state,
HP, cooldown remaining, command cooldown state, and elapsed time to the bank.

The command-card ring is a visual check. The bank proves the engine cooldown and
command state only.

## 10. Invariants

- Only one source of truth exists for auto and chase state.
- Stand never chases when stationary.
- Moving attacks use native `AllowedMovement` weapon data.
- Moving attacks never replace movement input after the shot starts.
- A pending shot issues one attack order and suspends move-order replacement.
- Walk uses attack orders only when stationary.
- Manual orders are never cancelled by auto off.
- Cooldown uses outgoing attack events only.
- The FSM step is the only place that issues automatic moving attacks.
- Control mode state lives only in `SCOBAActionModeBehavior`.
- Control mode changes never alter combat state.
- Action mode right hold never calls the combat controller.
- Action mode left click on ground never calls the combat controller.
- Alt UI clicks never call the combat controller.
- Every Galaxy file stays below 512 lines.

## 11. Rollout

1. Add constants and globals.
2. Add `systems/combat_fsm.galaxy`.
3. Rewrite `combat_tick.galaxy` to call the FSM.
4. Rewrite `combat_attack.galaxy` handlers so the toggle abilities own the
   behaviors.
5. Rename the status button and add the Weapon Attack execute handler.
6. Set `SCOBAStandRoot` to `ModifyFlags SuppressMoving`.
7. Set cooldown `TimeUse` and `Location` on the Weapon Attack ability.
8. Rewrite `combat_cooldown.galaxy` to set one cooldown per started attack.
9. Clear the click-started cooldown in the Weapon Attack handler.
10. Wire movement and targeting callbacks.
11. Add the button-state refresh function.
12. Rewrite the test harness with isolated enemy scenarios.
13. Build twice and compare hashes.
14. Run the map test.
15. Run the in-game command card check.
16. Run pre-commit and push.

## 12. Open validation points

- Outgoing attack event cadence for multi-target heroes.
- Command card stage events for both toggles in game.
- Stand lock interaction with knockback and displacement effects.
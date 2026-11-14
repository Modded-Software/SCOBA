# REQ-POINT-AND-CLICK: WASD / Point & Click Mode

**Date:** 2026-11-14
**Status:** Requirements decided by the operator on 2026-11-14. Partly
implemented. The specification lists the state of each requirement.

## 1. Scope

This contract binds the control mode named `WASD / Point & Click` (short: PNC).
It was called `RPG` before.

In scope:

- mouse clicks: UI target, attack, move, follow, cancel;
- the Attack toggle (`single` / `auto`) and the Chase toggle (`stand` / `move`);
- the `Weapon Attack` button and its cooldown clock;
- WASD movement and attacking while moving;
- mouse holds: camera orbit and character direction;
- order mode;
- separation from Action mode.

Out of scope, next phase: Action mode (`WASD / TPS`), aim, aim shots. This
phase MUST NOT remove or break the code that phase builds on.

Implementation lives in
[SPEC-POINT-AND-CLICK](../specifications/SPEC-POINT-AND-CLICK.md).

## 2. Definitions

- **Hero**: the character unit the player controls.
- **UI target**: the unit shown in the boss bar. It is script state. It is not
  the engine selection.
- **Engine target**: the target of the hero's current attack order.
- **Click**: press and release without a hold gesture.
- **Hold**: press, then drag past the hold threshold before release.
- **Attack toggle**: `single` or `auto`.
- **Chase toggle**: `stand` or `move`. It governs automatic movement only.
- **Cooldown clock**: the countdown overlay the engine draws on a command-card
  button while its cooldown runs.
- **In range**: the hero can hit the target from where it stands.
- **Order mode**: the player commands an owned unit instead of the hero. It is
  entered with F, Ctrl + E, or the Order button.

## 3. Requirements

### 3.1 Design rule

| ID | Requirement |
| --- | --- |
| R-PNC-1 | Attack, acquisition, chase, move, follow, hold, attack while moving, and the attack cooldown MUST use native engine behavior wherever the engine provides it. |
| R-PNC-2 | Script MUST NOT run a parallel system that duplicates or overrides an engine behavior. Script MUST NOT fire, time, or re-issue attacks. |
| R-PNC-3 | Where the engine has no native behavior, the script addition MUST be the smallest one that works, and the specification MUST name it. |

### 3.2 UI target

| ID | Requirement |
| --- | --- |
| R-PNC-10 | A left click on any unit or building MUST make it the UI target and show the boss bar. |
| R-PNC-11 | A left click MUST NOT leave any unit other than the hero engine-selected. |
| R-PNC-12 | A left click on a unit MUST NOT issue an order to the hero. An ongoing attack continues. |
| R-PNC-13 | A left click on the ground MUST cancel (section 3.4). |
| R-PNC-14 | When the UI target dies or is removed, the boss bar MUST hide. |
| R-PNC-15 | An enemy that attacks the hero MUST become the UI target. |

### 3.3 Right click

| ID | Requirement |
| --- | --- |
| R-PNC-20 | A right click on an enemy MUST make it the UI target and issue an attack on it. |
| R-PNC-21 | Attack `single`: the right click MUST produce exactly one shot. The hero MUST NOT attack again without a new attack command. |
| R-PNC-22 | Attack `auto`: the hero MUST keep attacking the clicked enemy until it dies or the attack is cancelled. |
| R-PNC-23 | Chase `move`, enemy out of range: the hero MUST walk until the enemy is in range, then attack. |
| R-PNC-24 | Chase `stand`, enemy out of range: the hero MUST NOT move and MUST NOT attack. One `Out of range` floater MUST appear at the enemy. |
| R-PNC-25 | Chase `move`: a right click on the ground MUST issue a move order to that point and show the ground target model effect. |
| R-PNC-26 | Chase `move`: a right click on a friendly unit MUST issue a move-follow on that unit. |
| R-PNC-27 | Chase `stand`: a right click on the ground or on a friendly unit MUST NOT move the hero. Nothing is shown for the friendly click. |
| R-PNC-28 | A right click on the ground MUST cancel (section 3.4) in both Chase states. In Chase `move` the move order follows the cancel. |

### 3.4 Cancel

| ID | Requirement |
| --- | --- |
| R-PNC-30 | A cancel MUST clear the UI target, hide the boss bar, clear the engine target, and stop any ongoing attack. |
| R-PNC-31 | A left click on the ground and a right click on the ground MUST each cancel. |
| R-PNC-32 | Ctrl + C MUST exit order mode when order mode is active. Otherwise it MUST cancel. |
| R-PNC-33 | After a cancel with Attack `single`, the hero MUST NOT attack until the next attack command. |
| R-PNC-34 | After a cancel with Attack `auto`, the engine MAY acquire again. |

### 3.5 Attack toggle and Weapon Attack button

| ID | Requirement |
| --- | --- |
| R-PNC-40 | Attack `auto`: the hero MUST acquire the closest enemy using the engine's acquisition logic. |
| R-PNC-41 | Attack `single`: the hero MUST NOT acquire or attack on its own. This includes when it is attacked. |
| R-PNC-42 | Attack `single`: each attack MUST be commanded explicitly, by a right click on an enemy or by the `Weapon Attack` button. |
| R-PNC-43 | Switching to `single` MUST stop an ongoing attack. |
| R-PNC-44 | The toggle state MUST survive hero switch and mode switch. |
| R-PNC-45 | The `Weapon Attack` command-card button MUST stay. Pressing it and clicking an enemy MUST act exactly as a right click on that enemy. |
| R-PNC-46 | The `Weapon Attack` button MUST show the hero attack cooldown as the cooldown clock. The clock MUST start with every shot, however the shot was started, and MUST end when the weapon is ready. It MUST be driven by game data. Script MUST NOT set or time it. |
| R-PNC-47 | At map start the Attack toggle MUST be `single` and the Chase toggle MUST be `stand`. |
| R-PNC-48 | Each toggle button MUST show the current state of its toggle. The button and the hero MUST agree at map start, after every toggle, after a hero switch, and after a mode switch. |
| R-PNC-49 | A press of `Weapon Attack` that fires no shot MUST NOT start the cooldown clock. |

### 3.6 Chase toggle and movement

| ID | Requirement |
| --- | --- |
| R-PNC-50 | Chase `stand`: the hero MUST hold its ground. It MUST NOT move for an attack, an acquired target, or a right click. |
| R-PNC-51 | Chase `stand` with Attack `auto`: the hero MUST attack enemies that are in range without moving. |
| R-PNC-52 | Chase `move` with Attack `auto`: the hero MUST walk to an acquired enemy until it is in range, then attack. |
| R-PNC-53 | WASD MUST move the hero in both Chase states. The Chase toggle governs automatic movement only. |
| R-PNC-54 | The hero MUST attack while WASD moves it. The engine weapon MUST do this. Script MUST NOT. |
| R-PNC-55 | With no mouse button held, W and S MUST follow the camera view and the hero MUST face its travel direction. |
| R-PNC-56 | Left and right mouse buttons held together MUST walk the hero forward. |

### 3.7 Mouse holds

| ID | Requirement |
| --- | --- |
| R-PNC-60 | A left hold MUST orbit the camera around the hero. |
| R-PNC-61 | The left-hold orbit MUST NOT turn the hero and MUST NOT change the direction WASD moves it. |
| R-PNC-62 | A middle hold MUST orbit the camera and set the hero direction to the camera view. |
| R-PNC-63 | During a middle hold, WASD directions MUST be fixed to the camera view and the hero MUST face its travel direction. There is no backpedal. S MUST walk the hero toward the camera, facing the camera. |
| R-PNC-64 | A right hold MUST orbit the camera and keep the hero facing the camera view direction. |
| R-PNC-65 | During a right hold, WASD directions MUST be relative to the camera view and MUST NOT change the hero facing. S MUST backpedal. A and D MUST strafe. |
| R-PNC-66 | A hold MUST NOT run the click action of the same button on release. |
| R-PNC-67 | A click MUST NOT move the camera. |
| R-PNC-68 | The right-hold walk MUST turn at the middle-hold turn speed and MUST animate at the middle-hold walk rate. |

### 3.8 Mode separation and naming

| ID | Requirement |
| --- | --- |
| R-PNC-70 | PNC and Action mode MUST have separate mouse handlers. One mode's handler MUST NOT run in the other mode. |
| R-PNC-71 | Behavior both modes need MUST exist once and be called by both: UI target, toggles, attack cooldown, WASD key state, floaters. |
| R-PNC-72 | Switching modes MUST leave no input state from the previous mode active. |
| R-PNC-73 | Every player-visible `RPG` label MUST read `WASD / Point & Click`. |
| R-PNC-74 | The toggle buttons MUST read `Attack: Auto`, `Attack: Single`, `Chase: Move`, `Chase: Stand`. Each label names the current state, not the action. Their tooltips MUST describe this contract. |
| R-PNC-75 | Order mode MUST keep working in PNC. |

## 4. Acceptance Criteria

| ID | Criterion |
| --- | --- |
| AC-PNC-1 | Left click an enemy, a friendly unit, and a building: each shows the boss bar. The hero stays the only selected unit. The hero gets no order. |
| AC-PNC-2 | Left click the ground: the boss bar hides and an ongoing attack stops. |
| AC-PNC-3 | Attack `single`, right click an in-range enemy: one shot that deals its full damage, then the hero idles. |
| AC-PNC-4 | Attack `single`, three right clicks spaced past the weapon period: three shots. |
| AC-PNC-5 | Attack `auto`, right click an enemy: the hero attacks it until it dies. |
| AC-PNC-6 | Chase `move`, right click an out-of-range enemy: the hero walks into range and attacks. |
| AC-PNC-7 | Chase `stand`, right click an out-of-range enemy: no movement, no shot, `Out of range` appears. |
| AC-PNC-8 | Chase `move`, right click the ground: the hero walks there, the ground marker shows, the boss bar hides. |
| AC-PNC-9 | Chase `move`, right click a friendly unit that then moves: the hero follows it. |
| AC-PNC-10 | Chase `stand`, right click the ground: the hero does not move and the boss bar hides. Right click a friendly: nothing happens. |
| AC-PNC-11 | During an attack, outside order mode, press Ctrl + C: the attack stops and the boss bar hides. |
| AC-PNC-12 | In order mode, press Ctrl + C: order mode ends. The UI target stays. |
| AC-PNC-13 | Attack `single`, an enemy attacks the hero: the hero does not fight back. The boss bar shows that enemy. |
| AC-PNC-14 | Attack `auto`, Chase `stand`, enemy in range: the hero attacks without moving. Enemy out of range: the hero does nothing. |
| AC-PNC-15 | Attack `auto`, Chase `move`, enemy nearby: the hero walks into range and attacks. |
| AC-PNC-16 | Switch Attack from `auto` to `single` during an attack: the attack stops. |
| AC-PNC-17 | Chase `stand`, hold W: the hero walks. |
| AC-PNC-18 | Attack `auto`, enemy in range, hold W: the hero keeps firing while it walks. |
| AC-PNC-19 | No mouse button held, press S: the hero turns and walks toward the camera. |
| AC-PNC-20 | Hold left and right together: the hero walks forward. |
| AC-PNC-21 | Left hold and drag: the camera orbits. The hero does not turn. W moves the hero the way it faced before the drag. |
| AC-PNC-22 | Middle hold and drag: the hero turns with the camera. S walks the hero toward the camera, facing it. |
| AC-PNC-23 | Right hold and drag: the hero turns with the camera. S backpedals. A and D strafe. The hero keeps facing the view direction. |
| AC-PNC-24 | Release after a right hold: no move order and no attack order is issued. |
| AC-PNC-25 | Press `Weapon Attack`, click an enemy: the hero attacks as for a right click, in both Attack states. |
| AC-PNC-26 | Shots started by right click, by `Weapon Attack`, and by engine acquisition, with each hero weapon: the cooldown clock on the button starts with each shot and ends when the weapon is ready. |
| AC-PNC-27 | The mode button and its tooltips show `WASD / Point & Click`. No `RPG` text is visible. The toggles read as in R-PNC-74. |
| AC-PNC-28 | Switch to Action mode and back during a hold: no orbit, movement, or target state is left stuck. |
| AC-PNC-29 | Switch hero with Attack `single` and Chase `stand`: both stay set. |
| AC-PNC-30 | Enter order mode, command an owned unit, exit: the hero controls work as before. |
| AC-PNC-31 | Start the map: the buttons read `Attack: Single` and `Chase: Stand`. An enemy in range is not attacked. |
| AC-PNC-32 | Press the Attack toggle: the button reads `Attack: Auto` and the hero attacks an enemy in range. Press it again: it reads `Attack: Single` and the attack stops. |
| AC-PNC-33 | Switch hero with Attack `auto` and Chase `move`: both buttons still read `Attack: Auto` and `Chase: Move`, and the new hero behaves that way. |
| AC-PNC-34 | Chase `stand`, press `Weapon Attack` on an out-of-range enemy: no shot and no cooldown clock. |

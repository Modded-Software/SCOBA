# REQ-COMBAT-CONTROLS: Combat Controls

**Date:** 2026-11-09
**Status:** Active binding requirement

## 1. Scope

This contract binds combat controls:

- auto-attack;
- Stand and Walk chase stance;
- manual and Stand attack;
- Weapon Attack and cooldown;
- WASD and order-mode interaction;
- control mode interaction.

Implementation lives in
[SPEC-COMBAT-CONTROLS](../specifications/SPEC-COMBAT-CONTROLS.md).

## 2. Definitions

- **Auto-attack**: target selection and attack orders without a player click.
- **Stand**: the hero holds position when idle and attacks inside the keep radius.
- **Walk**: the hero moves toward enemies inside the chase radius and attacks when idle.
- **Run-and-gun**: the hero attacks while a movement key controls position.
- **Manual attack**: a player right-click on an enemy or a Weapon Attack click.
- **Keep radius**: maximum Stand attack distance.
- **Chase radius**: maximum Walk acquisition distance.
- **Cooldown**: real-time interval between two outgoing hero attacks.

## 3. Requirements

### 3.1 Auto-attack

| ID | Requirement |
| --- | --- |
| R-AA-1 | Auto-attack MUST start off at map init. |
| R-AA-2 | Auto on MUST select targets and issue attack orders. |
| R-AA-3 | Auto off MUST issue no automatic attack orders and MUST keep a manual attack. |
| R-AA-4 | Auto state MUST have one source of truth. |
| R-AA-5 | The auto toggle MUST work from the command card for every hero. |
| R-AA-6 | The auto button face, name, and tooltip MUST match the current state. |

### 3.2 Chase stance

| ID | Requirement |
| --- | --- |
| R-CH-1 | Stand MUST hold position when idle and MUST not chase. |
| R-CH-2 | Walk MUST move toward enemies inside the chase radius and attack them. |
| R-CH-3 | Stand MUST attack enemies inside the keep radius when idle and stop when they leave. |
| R-CH-4 | Player movement MUST move the hero and release the Stand root. |
| R-CH-5 | Stand MUST restore the root after WASD release and after manual attack. |
| R-CH-6 | User attacks in Stand MUST stay in Stand and MUST not chase. |
| R-CH-7 | Chase state MUST have one source of truth. |
| R-CH-8 | The chase toggle MUST work from the command card for every hero. |
| R-CH-9 | The chase button face, name, and tooltip MUST match the current stance. |
| R-CH-10 | Entering Stand MUST clear an earlier move order. |
| R-CH-11 | Stand and Walk MUST attack while a movement key is held. |
| R-CH-12 | Movement input MUST own position while attacking. |
| R-CH-13 | A moving attack MUST NOT chase in Stand and MUST NOT replace movement in Walk. |
| R-CH-14 | Moving attacks MUST use native attack orders and MUST respect weapon cooldown. |
| R-CH-15 | Tosh, RazorTalons, and QueenOfBladesPsiBlast weapons MUST allow movement while firing. |
| R-CH-16 | A pending shot MUST suspend movement-order replacement until the native attack event or timeout. |
| R-CH-17 | Each moving shot MUST issue exactly one native attack order. |

### 3.3 Manual attack

| ID | Requirement |
| --- | --- |
| R-MA-1 | A right-click on an enemy MUST target it, move the boss-bar target, and issue attack. Native unit selection MUST NOT change. |
| R-MA-2 | Right targeting MUST use the native per-player `UnitClick` unit. |
| R-MA-3 | A right drag MUST issue no attack order. |
| R-MA-4 | A right click on ground MUST move in Walk and stop in Stand. |
| R-MA-5 | Ground right clicks, idle, and Stop MUST keep the left-click target. |
| R-MA-6 | Manual attack MUST work with auto on and off. |
| R-MA-7 | Manual attack MUST take priority over auto-attack until it ends. |
| R-MA-8 | Auto-attack MUST resume after a manual order completes. |
| R-MA-9 | Auto off MUST not issue Stop during a manual attack. |
| R-MA-10 | Weapon Attack MUST enter standard attack-target mode. |
| R-MA-11 | The attacked enemy MUST come from the ability target. |
| R-MA-12 | Cancelling target mode MUST do nothing and start no cooldown. |
| R-MA-13 | Stand move orders MUST be blocked only with no movement key held. |
| R-MA-14 | Manual attack MUST work while a movement key is held. |
| R-MA-15 | Moving manual attacks MUST keep the manual target until it dies or is cleared. |

### 3.4 Weapon Attack and cooldown

| ID | Requirement |
| --- | --- |
| R-WA-1 | The button MUST be named `Weapon Attack`. |
| R-WA-2 | The button MUST be clickable when ready and disabled while recharging. |
| R-WA-3 | The button MUST show the active cooldown animation. |
| R-WA-4 | The button icon MUST show the attack state. |
| R-WA-5 | Cooldown MUST derive from outgoing hero attacks. |
| R-WA-6 | Cooldown MUST update in real time. |
| R-WA-7 | Cooldown MUST use the measured outgoing-attack interval after the second attack. |
| R-WA-8 | Cooldown MUST apply to Stand, Walk, and manual attacks. |
| R-WA-9 | The Weapon Attack button MUST stay visible while auto is off. |
| R-WA-10 | The ability MUST show a real cooldown. |
| R-WA-11 | The cooldown MUST reset once per outgoing attack. |
| R-WA-12 | A Weapon Attack click MUST clear any click-started cooldown before issuing the order. |

### 3.5 State precedence

| ID | Requirement |
| --- | --- |
| R-SP-1 | Combat MUST use one explicit finite state machine per hero. |
| R-SP-2 | Manual attack and WASD MUST take priority over auto-attack. |
| R-SP-3 | Auto off MUST not block manual attack. |
| R-SP-4 | Order mode MUST suspend auto-attack. |
| R-SP-5 | Leaving WASD or order mode MUST let auto-attack resume on the next tick. |
| R-SP-6 | A dead or invalid hero MUST return to idle and clear its auto target. |
| R-SP-7 | WASD MUST cancel an auto-attack order and MUST keep a held manual attack. |
| R-SP-8 | Order mode entry MUST cancel auto-attack. |

### 3.6 Command card

| ID | Requirement |
| --- | --- |
| R-UI-1 | Every combat button MUST reflect its state. |
| R-UI-2 | The auto button MUST show ON only when auto is on. |
| R-UI-3 | The chase button MUST show Stand only in Stand. |
| R-UI-4 | Button names and tooltips MUST match the shown state. |
| R-UI-5 | The control mode button MUST show the current mode and sit at top row column 2. |

### 3.7 Aim interaction

| ID | Requirement |
| --- | --- |
| R-AIM-1 | Right-hold aim MUST leave combat state, orders, auto-attack, stance, and cooldown unchanged. |
| R-AIM-2 | In RPG mode, the right command MUST run once on clean release. |
| R-AIM-3 | Aim animation and facing MUST leave the combat state machine unchanged. |
| R-AIM-4 | Aim movement MUST not call the combat controller. |
| R-AIM-5 | Aim movement MUST be owned by `gt_AimMoveTick` and MUST not enter a combat FSM state. |

### 3.8 Control mode

| ID | Requirement |
| --- | --- |
| R-CM-1 | RPG mode MUST be the default at map init and hero spawn. |
| R-CM-2 | The control mode button MUST show the current mode and appear before auto-attack. |
| R-CM-3 | Toggling control mode MUST leave auto-attack, stance, and cooldown unchanged. |
| R-CM-4 | RPG return MUST exit aim without a right command. |
| R-CM-5 | Action left-click attack MUST use the combat controller. |
| R-CM-6 | Action ground click, Alt click, and right hold MUST not call the combat controller. |
| R-CM-7 | Control mode MUST have one source of truth. |

## 4. Acceptance criteria

| ID | Check |
| --- | --- |
| AC-1 | Map init starts with auto off and the button showing OFF. |
| AC-2 | Auto off with an enemy nearby issues no automatic attack. |
| AC-3 | Auto off still allows manual attack. |
| AC-4 | Stand attacks inside the keep radius with no displacement. |
| AC-5 | Stand does not move toward an enemy outside the keep radius. |
| AC-6 | Walk attacks and closes distance inside the chase radius. |
| AC-7 | Walk issues no attack with no enemy in the chase radius. |
| AC-8 | Two outgoing attacks produce a measured cooldown near the observed interval. |
| AC-9 | The Weapon Attack cooldown starts positive and reaches zero when ready. |
| AC-10 | Manual attack is not replaced by auto-attack. |
| AC-11 | WASD cancels auto-attack and release lets it resume. |
| AC-12 | Both toggle buttons change behavior when clicked. |
| AC-13 | Weapon Attack is named correctly and clickable when ready. |
| AC-14 | Weapon Attack enters attack-target mode. |
| AC-15 | The Weapon Attack button shows cooldown animation and disables while recharging. |
| AC-16 | Combat button faces, names, and tooltips match state. |
| AC-17 | Auto off with no manual order issues no attack. |
| AC-18 | Stand sets move suppression and Walk clears it. |
| AC-19 | Each combat test resets the hero and uses one enemy at a recorded distance. |
| AC-20 | A recharging Weapon Attack reports cooldown and returns ready when done. |
| AC-21 | Stand with auto off keeps the root and does not chase. |
| AC-22 | Repeated Stand right clicks keep the hero in place. |
| AC-23 | Stand after WASD release restores the root. |
| AC-24 | Walk ground click moves and Stand ground click stops. |
| AC-25 | Right targeting uses the shared click resolver. |
| AC-26 | Right click on an enemy targets and attacks it. |
| AC-27 | Right drag issues no attack. |
| AC-28 | Ground right click, idle, and Stop keep the left-click target. |
| AC-29 | RPG Walk move orders pass and Stand move orders are blocked. |
| AC-30 | Aim state and movement leave the combat state machine unchanged. |
| AC-31 | The control mode button appears before auto-attack. |
| AC-32 | A new hero starts in RPG mode. |
| AC-33 | Action mode shows the Actions name; RPG mode shows the RPG name. |
| AC-34 | Control mode changes leave auto-attack, stance, and cooldown unchanged. |
| AC-35 | RPG return exits aim without a right command. |
| AC-36 | Action left click on an enemy attacks; on ground it issues no order. |
| AC-37 | Alt click and action right hold issue no combat order. |
| AC-38 | Stand move-and-shoot displaces the hero and fires without the root. |
| AC-39 | Walk move-and-shoot displaces the hero and fires without stopping. |
| AC-40 | A moving attack does not cancel the held movement input. |

## 5. Non-functional requirements

- The build MUST remain deterministic and idempotent.
- Every Galaxy file MUST stay below 512 lines.
- The combat controller MUST be testable from the map test harness.
- Cooldown MUST derive from outgoing attacks.
- New scripts MUST be wired into the build pipeline.

## 6. Out of scope

- Ability talent trees and level-up effects.
- Enemy unit behavior.
- Camera and UI layout.
- Network latency compensation.

## 7. References

- Button, ability, behavior, and unit data in `Base.SC2Data`.
- Galaxy unit orders, attack events, and hold position behavior.
- StarCraft II automatic targeting and hold position references.
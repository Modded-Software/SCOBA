# REQ-COMBAT-CONTROLS: Combat Controls

**Date:** 2026-11-09
**Status:** Active binding requirement

## 1. Scope

This contract binds the combat controls of the SCOBA map:

- auto-attack toggle;
- chase stance toggle (Stand and Walk);
- manual attack;
- stand attack;
- auto-attack cooldown display;
- interaction with WASD movement and order mode.

It defines required behavior. It does not define module layout or Galaxy
implementation details. Those live in
[SPEC-COMBAT-CONTROLS](../specifications/SPEC-COMBAT-CONTROLS.md).

## 2. Definitions

- **Auto-attack**: the custom system that selects enemies and issues attack
  orders without a direct player click.
- **Stand**: the hero holds position and attacks enemies inside the keep
  radius. The hero MUST NOT chase.
- **Walk**: the hero moves toward enemies inside the chase radius and attacks
  them.
- **Manual attack**: a player right-click on an enemy unit, or a click on the
  Weapon Attack button while an enemy is targeted.
- **Weapon Attack button**: the command-card button that issues a standard
  attack-target order and shows the weapon cooldown.
- **Keep radius**: the maximum distance at which a Stand hero attacks.
- **Chase radius**: the maximum distance at which a Walk hero acquires a new
  enemy.
- **Cooldown**: the real-time interval between two outgoing hero attacks.

## 3. Requirements

### 3.1 Auto-attack

| ID | Requirement |
| --- | --- |
| R-AA-0 | Auto-attack MUST start off at map init. |
| R-AA-1 | Auto on MUST add `SCOBAAutoAttackBehavior`. Auto off MUST remove it. |
| R-AA-2 | Auto on MUST enable automatic target selection and attack orders. |
| R-AA-3 | Auto off MUST NOT issue automatic attack orders. |
| R-AA-4 | Auto off MUST NOT cancel a manual attack order. |
| R-AA-5 | Auto state MUST be read from `SCOBAAutoAttackBehavior`. No boolean mirror may exist. |
| R-AA-6 | The auto toggle command MUST work from the command card for every hero. |
| R-AA-7 | The auto button face, name, and tooltip MUST match the actual auto behavior state. |
| R-AA-8 | The hero MUST NOT auto-attack while `SCOBAAutoAttackBehavior` is absent. |

### 3.2 Chase stance

| ID | Requirement |
| --- | --- |
| R-CH-1 | Stand MUST add `SCOBARightClickStandBehavior`. Walk MUST remove it. |
| R-CH-1A | Stand movement lock MUST use `SCOBAStandRoot`, not the stance behavior. |
| R-CH-1B | `SCOBAStandRoot` MUST set `ModifyFlags SuppressMoving`. It MUST NOT use `MoveSpeedMultiplier`. |
| R-CH-1C | Stand root MUST depend on the Stand behavior, not on auto-attack state. |
| R-CH-2 | Stand MUST hold position. The hero MUST NOT move toward an enemy. |
| R-CH-2A | Player movement MUST remove the root and move the hero. |
| R-CH-2B | User-issued attacks in Stand MUST stay in Stand and MUST NOT chase. |
| R-CH-2C | Stand MUST restore the root after WASD release and after manual attack. |
| R-CH-3 | Stand MUST attack enemies that enter the keep radius. |
| R-CH-4 | Stand MUST stop attacking and remain in place when the enemy leaves the keep radius. |
| R-CH-5 | Walk MUST acquire enemies inside the chase radius and attack them. |
| R-CH-6 | Walk MUST move the hero toward the target while it is outside weapon range. |
| R-CH-7 | Chase state MUST be read from `SCOBARightClickStandBehavior`. No boolean mirror may exist. |
| R-CH-8 | The chase toggle command MUST work from the command card for every hero. |
| R-CH-9 | The chase button face, name, and tooltip MUST show the current stance. |

### 3.3 Stand attack

| ID | Requirement |
| --- | --- |
| R-SA-1 | Stand attack adds the suppression root and issues attack orders. The hero attacks in range and never chases. |
| R-SA-2 | Stand attack MUST work while auto-attack is on. |
| R-SA-3 | Stand attack MUST NOT move the hero toward the target. |
| R-SA-4 | Stand attack MUST continue until the target dies or leaves the keep radius. |
| R-SA-5 | Entering Stand MUST not leave an earlier move order active. |

### 3.4 Manual attack

| ID | Requirement |
| --- | --- |
| R-MA-1 | A right-click on an enemy unit MUST issue an attack order. |
| R-MA-1A | Right-click target selection MUST use the hover unit saved at press time. |
| R-MA-1B | A right-click on ground MUST move the hero in Walk. |
| R-MA-1C | A right-click on ground MUST stop the hero in Stand. |
| R-MA-1D | A right-click on an enemy MUST select it and move the boss-bar target. |
| R-MA-1E | A right drag MUST NOT issue an attack order. |
| R-MA-1F | A ground right click MUST NOT clear the left-click target. |
| R-MA-2 | Manual attack MUST work while auto-attack is on or off. |
| R-MA-3 | Manual attack MUST take priority over auto-attack until the target dies, the player moves, or the unit becomes idle. |
| R-MA-4 | Auto-attack MUST resume after a manual order completes. |
| R-MA-5 | Auto off MUST not issue Stop while a manual attack is active. |
| R-MA-6 | A Weapon Attack click MUST enter standard SC attack-target mode. |
| R-MA-7 | The clicked enemy MUST come from the ability target, not cursor hover. |
| R-MA-8 | Cancelling target mode MUST do nothing and MUST NOT start cooldown. |

### 3.5 Weapon Attack button and cooldown

| ID | Requirement |
| --- | --- |
| R-WA-1 | The button name MUST be `Weapon Attack`. |
| R-WA-2 | The button MUST be enabled and clickable when the hero is not attacking and the cooldown is ready. |
| R-WA-3 | The button MUST show an active cooldown animation while the weapon is recharging. |
| R-WA-4 | The button MUST be disabled while the cooldown animation is active. |
| R-WA-5 | The button icon MUST show the attack state, not an auto-attack state. |
| R-WA-6 | Cooldown MUST be derived from outgoing hero attacks, not from attacks received by the hero. |
| R-WA-7 | Cooldown MUST update in real time. |
| R-WA-8 | Cooldown period MUST be measured from the interval between two outgoing attacks. |
| R-WA-9 | The measured period MUST replace the initial period after the second outgoing attack. |
| R-WA-10 | The cooldown MUST apply to Stand attacks, Walk attacks, and manual attacks. |
| R-WA-11 | The Weapon Attack button MUST remain visible while auto-attack is off. |
| R-WA-12 | Ability cost MUST set `Cooldown TimeUse` greater than zero and `Location="Ability"`. |
| R-WA-13 | The cooldown MUST be reset and set once per outgoing attack with `UnitAbilityReset` and `UnitAbilityAddCooldown`. |
| R-WA-14 | The cooldown MUST NOT be removed and re-added on a periodic timer. |
| R-WA-15 | A Weapon Attack click MUST clear the click-started cooldown before issuing the attack order. |

### 3.6 State precedence

| ID | Requirement |
| --- | --- |
| R-SP-1 | The combat controller MUST be an explicit finite state machine per hero. |
| R-SP-2 | Manual attack and WASD movement MUST take priority over auto-attack. |
| R-SP-3 | Auto off MUST NOT block manual attack. |
| R-SP-4 | Order mode MUST suspend auto-attack. |
| R-SP-5 | Leaving WASD or order mode MUST let auto-attack resume on the next tick. |
| R-SP-6 | A dead or invalid hero MUST return to the idle state and clear its auto target. |

### 3.7 Inputs

| ID | Requirement |
| --- | --- |
| R-IN-1 | WASD input MUST cancel an active auto-attack order. |
| R-IN-2 | WASD input MUST NOT cancel a manual attack while the key is held. |
| R-IN-3 | Order mode entry MUST cancel an active auto-attack order. |
| R-IN-4 | Order mode exit MUST leave the hero idle until the next combat tick. |

### 3.8 Single source of truth

| ID | Requirement |
| --- | --- |
| R-SS-1 | Auto state lives only in `SCOBAAutoAttackBehavior`. |
| R-SS-2 | Chase state lives only in `SCOBARightClickStandBehavior`. |
| R-SS-3 | The state machine stores orders and targets. It MUST NOT store copies of the two toggle flags. |

### 3.9 Command card reflection

| ID | Requirement |
| --- | --- |
| R-UI-1 | Every combat button MUST reflect the current behavior state. |
| R-UI-2 | The auto button MUST show ON only when `SCOBAAutoAttackBehavior` is present. |
| R-UI-3 | The chase button MUST show Stand only when `SCOBARightClickStandBehavior` is present. |
| R-UI-4 | Button names and tooltips MUST match the state shown. |
| R-UI-5 | The UI state MUST NOT depend on engine toggle state alone. |

## 4. Acceptance criteria

| ID | Check |
| --- | --- |
| AC-1 | Map init starts with auto off and the auto button showing OFF. |
| AC-2 | Auto off with an enemy nearby produces no automatic attack order over time. |
| AC-3 | Auto off with a manual attack produces an attack order. |
| AC-4 | Stand with an enemy inside the keep radius produces an attack and no displacement. |
| AC-5 | Stand with an enemy outside the keep radius produces no displacement. |
| AC-6 | Walk with an enemy inside the chase radius produces an attack and reduces the distance. |
| AC-7 | Walk with no enemy in the chase radius produces no attack order. |
| AC-8 | Two outgoing attacks produce a measured period within 20 percent of the observed interval. |
| AC-9 | The Weapon Attack cooldown is positive after an outgoing attack and reaches zero when the weapon is ready. |
| AC-10 | Manual attack prevents auto-attack from replacing the order. |
| AC-11 | WASD start cancels auto-attack; WASD release lets it resume. |
| AC-12 | Both toggle buttons change behavior when clicked in the command card. |
| AC-13 | The Weapon Attack button is named `Weapon Attack` and is clickable when ready. |
| AC-14 | A Weapon Attack click issues a standard attack-target order. |
| AC-15 | The Weapon Attack button shows an active cooldown animation while recharging and is disabled. |
| AC-16 | Auto and chase button faces, names, and tooltips match the actual behavior state. |
| AC-17 | The hero does not attack while auto is off and no manual order exists. |
| AC-18 | Stand sets `c_unitStateMoveSuppressed`; Walk and player movement clear it. |
| AC-19 | Every test scenario resets the hero and uses exactly one enemy at a recorded distance. |
| AC-20 | A recharging Weapon Attack reports `c_cmdStateCooldown` true and returns false when ready. |
| AC-21 | Stand with auto off keeps the root and does not chase on manual attack. |
| AC-22 | Repeated Stand right-clicks keep the hero in place. |
| AC-23 | Stand after WASD release restores the root before the next manual attack. |
| AC-24 | Walk right-click on ground moves the hero; Stand right-click on ground stops. |
| AC-25 | Right-click target selection uses the press-time hover unit. |
| AC-26 | A right-click on an enemy selects it and issues attack. |
| AC-27 | A right drag issues no attack order. |
| AC-28 | A ground right click keeps the left-click target. |

## 5. Non-functional requirements

- The build MUST remain deterministic and idempotent.
- Every Galaxy file MUST stay below 512 lines.
- The combat controller MUST be testable from the map test harness.
- The controller MUST NOT rely on `UnitWeaponPeriod` for cooldown.
- The controller MUST NOT use `TriggerAddEventUnitAttacked` to measure outgoing attacks.
- All new scripts MUST be wired into `scripts/expand_map.py` or the Galaxy
  include tree.

## 6. Out of scope

- Ability talent trees and level-up effects.
- Enemy unit behavior.
- Camera and UI layout.
- Network latency compensation.

## 7. References

- Button tooltips: `src/SCOBA.SC2Map/Base.SC2Data/GameData/ButtonData.xml`.
- Toggle abilities: `src/SCOBA.SC2Map/Base.SC2Data/GameData/AbilData.xml`.
- Behavior flags: `src/SCOBA.SC2Map/Base.SC2Data/GameData/BehaviorData.xml`.
- Unit layout: `src/SCOBA.SC2Map/Base.SC2Data/GameData/UnitData.xml`.
- Galaxy `UnitIssueOrder`: https://mapster.talv.space/galaxy/reference/unit-issue-order
- Galaxy `TriggerAddEventUnitStartedAttack2`: https://mapster.talv.space/galaxy/reference/trigger-add-event-unit-started-attack2
- Galaxy `TriggerAddEventUnitAttacked2`: https://mapster.talv.space/galaxy/reference/trigger-add-event-unit-attacked2
- Hold Position and automatic targeting: https://liquipedia.net/starcraft2/Automatic_Targeting
- Hold Position command behavior: https://news.blizzard.com/en-us/article/4552956/game-guide-basic-unit-controls
- Move ability command order: `mods/core.sc2mod/base.sc2data/gamedata/AbilData.xml`
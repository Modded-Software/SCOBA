# REQ-MOUSE-CONTROLS: Mouse Controls

**Date:** 2026-11-09
**Status:** Active binding requirement

## 1. Scope

This contract binds mouse camera control, right-click commands, and
both-button movement for SCOBA heroes:

- right-button camera and character turn;
- middle-button camera and character turn;
- click versus drag detection;
- right-click unit targeting and ground commands;
- left and right held together as Move Forward;
- native smart-click suppression.

Combat state rules live in
[REQ-COMBAT-CONTROLS](REQ-COMBAT-CONTROLS.md).
Galaxy layout lives in
[SPEC-MOUSE-CONTROLS](../specifications/SPEC-MOUSE-CONTROLS.md).

## 2. Definitions

- **Press point**: the UI and world position at mouse button down.
- **Drag**: cursor movement at or above the drag threshold during one button
  hold.
- **Clean click**: a button press and release with no drag.
- **Right command**: the action run by a clean right click.
- **Hover unit**: `gv_sCOBAHover[player]`, set by the engine unit highlight
  event. This is the same source used by left-click selection.
- **Both-button hold**: left and right mouse buttons held together.

## 3. Requirements

### 3.1 Camera and character turn

| ID | Requirement |
| --- | --- |
| R-MC-1 | A right-button press MUST start camera and character turn. |
| R-MC-2 | A middle-button press MUST start camera and character turn. |
| R-MC-3 | Right and middle button camera behavior MUST be the same. |
| R-MC-4 | A held right button MUST turn the camera and character while the mouse moves. |
| R-MC-5 | A held middle button MUST turn the camera and character while the mouse moves. |
| R-MC-6 | A button release MUST stop camera rotation when no other turn button is held. |
| R-MC-7 | Camera lock and cursor visibility MUST return after the last turn button is released. |
| R-MC-8 | Camera turn MUST work in normal mode and order mode. |

### 3.2 Click versus drag

| ID | Requirement |
| --- | --- |
| R-MC-9 | Right-button drag MUST NOT run the right command. |
| R-MC-9A | Left-button drag MUST NOT select a target. |
| R-MC-9B | Left-button selection MUST run on clean release. |
| R-MC-10 | Right-button clean click MUST run the right command on release. |
| R-MC-11 | Drag detection MUST use cursor movement and camera movement. |
| R-MC-12 | The cursor drag threshold MUST be 4 UI pixels. |
| R-MC-13 | The camera drag threshold MUST be 5 degrees of yaw or pitch. |
| R-MC-14 | A both-button hold MUST cancel the pending right command. |

### 3.3 Right command

| ID | Requirement |
| --- | --- |
| R-MC-15 | Right command targeting MUST use the hover unit saved at press time. |
| R-MC-16 | Right command MUST NOT use a flat ground distance as its primary target source. |
| R-MC-17 | The hover unit MUST be alive and hostile to the hero player. |
| R-MC-18 | A right click on an enemy MUST select it and issue a manual attack. |
| R-MC-19 | A right click on an enemy MUST move the boss-bar target. |
| R-MC-20 | A right click on ground in Walk MUST issue a Move order. |
| R-MC-21 | A right click on ground in Stand MUST issue a Stop order and keep the root. |
| R-MC-22 | A ground right click MUST NOT clear the left-click target. |
| R-MC-23 | Order-mode right click MUST use the same target resolver as normal mode. |
| R-MC-23A | A Walk ground right click MUST show the built-in move target effect at the press point. |
| R-MC-23B | The move target effect MUST use the player race model. |
| R-MC-24 | The selected left-click target MAY be used when the press point is inside its unit radius. |
| R-MC-25 | Point picking MAY be used only when the hover unit is absent. Point picking MUST use `c_unitPropRadius`. |

### 3.4 Both-button movement

| ID | Requirement |
| --- | --- |
| R-MC-26 | Holding left and right buttons together MUST start Move Forward. |
| R-MC-27 | Both-button Move Forward MUST behave like the W key. |
| R-MC-28 | Both-button Move Forward MUST steer by camera yaw while a turn button is held. |
| R-MC-29 | Releasing either button MUST end both-button Move Forward. |
| R-MC-30 | Both-button Move Forward MUST NOT cancel a held W key. |
| R-MC-31 | Releasing W MUST NOT end both-button Move Forward. |
| R-MC-32 | Both-button Move Forward MUST NOT select a target. |

### 3.5 Engine smart click

| ID | Requirement |
| --- | --- |
| R-MC-33 | Engine smart click MUST be disabled for all players. |
| R-MC-34 | Right commands MUST be the only source of right-click orders. |
| R-MC-35 | Ability target mode MUST remain engine handled. |
| R-MC-36 | Left-click selection MUST remain custom and MUST use the hover unit. |

### 3.6 State

| ID | Requirement |
| --- | --- |
| R-MC-37 | Right button down MUST NOT change combat state. |
| R-MC-38 | Right command MUST change combat state once, on clean release. |
| R-MC-39 | A right drag MUST NOT change combat state. |
| R-MC-40 | Combat state mutations MUST be shared with the combat controller. |

## 4. Acceptance criteria

| ID | Check |
| --- | --- |
| AC-MC-1 | Right hold turns camera and character. |
| AC-MC-2 | Middle hold turns camera and character in the same way. |
| AC-MC-3 | Right drag under 4 pixels runs one right command. |
| AC-MC-4 | Right drag over 4 pixels runs no right command. |
| AC-MC-5 | Right drag with camera yaw change runs no right command. |
| AC-MC-6 | Right clean click on an enemy selects it and issues attack. |
| AC-MC-7 | Right clean click on ground in Walk issues Move. |
| AC-MC-8 | Right clean click on ground in Stand issues Stop and keeps the root. |
| AC-MC-8A | Walk ground right click shows the built-in move target model at the press point. |
| AC-MC-9 | Left and right held together start Move Forward. |
| AC-MC-10 | Releasing either mouse button stops both-button Move Forward. |
| AC-MC-11 | Holding W then adding both buttons keeps Move Forward after both buttons release. |
| AC-MC-12 | Holding both buttons then pressing and releasing W keeps Move Forward while both buttons remain held. |
| AC-MC-13 | Both-button Move Forward does not change the left-click target. |
| AC-MC-14 | Engine smart click is disabled at map init. |

## 5. Non-functional requirements

- The build MUST remain deterministic and idempotent.
- Every Galaxy file MUST stay below 512 lines.
- Mouse handlers MUST be testable from the map test harness.
- New globals and constants MUST live in the existing core modules.
- New scripts MUST be wired into `scripts/expand_map.py` or the Galaxy
  include tree when added.

## 6. Out of scope

- Mouse sensitivity settings.
- Minimap and UI panel clicks.
- Ability target-mode visuals.
- Network latency compensation.

## 7. References

- WoW right-button camera and context click behavior: `TurnOrActionStart`,
  `TurnOrActionStop`.
- WoW click versus drag behavior: right press starts camera, clean release
  runs the context action.
- WoW both-button movement: left and right held together move forward and
  steer with the camera.
- Galaxy `UISetCommandAllowed`: `c_uiCommandAllowSmartClick`.
- Galaxy unit highlight event: `TriggerAddEventUnitHighlight`.
- Galaxy mouse events: `TriggerAddEventMouseClicked`, `EventMouseClickedPosXUI`,
  `EventMouseClickedPosYUI`.
- Unit radius: `c_unitPropRadius`.
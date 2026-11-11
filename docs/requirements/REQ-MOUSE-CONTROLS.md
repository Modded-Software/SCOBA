# REQ-MOUSE-CONTROLS: Mouse Controls

**Date:** 2026-11-10
**Status:** Active binding requirement

## 1. Scope

This contract binds mouse camera control, right-click commands, right-hold aim,
and both-button movement:

- left-button camera orbit;
- right and middle button camera and character turn;
- action mode right-hold aim;
- click versus drag;
- right-click unit and ground commands;
- left and right held together as Move Forward;
- smart-click suppression;
- RPG and action control modes;
- action mode mouse look, Alt UI cursor, aim, and attack.

Combat state lives in [REQ-COMBAT-CONTROLS](REQ-COMBAT-CONTROLS.md).
Animation lives in [REQ-CHARACTER-ANIMATION](REQ-CHARACTER-ANIMATION.md).
Implementation lives in
[SPEC-MOUSE-CONTROLS](../specifications/SPEC-MOUSE-CONTROLS.md).

## 2. Definitions

- **Press point**: UI and world position at mouse button down.
- **Drag**: cursor movement at or above the drag threshold during one hold.
- **Clean click**: a press and release with no drag.
- **Right command**: the action run by a clean right click.
- **Hover unit**: the unit highlighted at press time.
- **Both-button hold**: left and right buttons held together.
- **Aim mode**: the state entered by a right hold in action mode.
- **Aim cursor**: the native selection cursor pinned to screen center.
- **RPG mode**: the default mode with right-click commands and no aim.
- **Action mode**: mouse look stays active, right hold aims, left click attacks.
- **Alt pause**: Alt held in action mode; mouse look pauses and the UI cursor moves freely.

## 3. Requirements

### 3.1 Camera and character turn

| ID | Requirement |
| --- | --- |
| R-MC-1 | In RPG mode, right hold MUST turn camera and character. |
| R-MC-2 | In RPG mode, middle hold MUST turn camera and character. |
| R-MC-3 | Right and middle hold MUST behave the same in RPG mode. |
| R-MC-4 | A left press MUST orbit the camera without turning the character. |
| R-MC-5 | Releasing the last turn button MUST stop rotation and restore camera lock and cursor visibility. |
| R-MC-6 | Camera turn MUST work in normal and order modes. |

### 3.2 Click versus drag

| ID | Requirement |
| --- | --- |
| R-MC-7 | A right drag MUST run no right command. |
| R-MC-8 | A left drag MUST select no target. |
| R-MC-9 | Left selection MUST run on clean release. |
| R-MC-10 | RPG right clean click MUST run the right command on release. |
| R-MC-11 | Drag detection MUST use press and release UI distance. |
| R-MC-12 | Mouse-relative mode MUST pin the real cursor to screen center. |
| R-MC-13 | The cursor MUST stay hidden outside aim and action mode. |
| R-MC-14 | Aim mode MUST show the native cursor at screen center. |
| R-MC-15 | A both-button hold MUST cancel a pending right command. |

### 3.3 Right command

| ID | Requirement |
| --- | --- |
| R-MC-16 | Right targeting MUST use a hover unit saved at press time when the press point is inside its radius. |
| R-MC-17 | A stale hover unit outside the press-point radius MUST be rejected. |
| R-MC-18 | The hover unit MUST be alive and hostile to the hero player. |
| R-MC-19 | A right click on an enemy MUST select it and issue a manual attack. |
| R-MC-20 | A right click on an enemy MUST move the boss-bar target. |
| R-MC-21 | A right click on ground in Walk MUST issue Move. |
| R-MC-22 | A right click on ground in RPG Stand MUST issue Stop and keep the root. |
| R-MC-23 | Ground and move commands MUST NOT clear the left-click target. |
| R-MC-24 | The left-click target MUST clear only on replacement, ground left click, death, removal, or explicit clear. |
| R-MC-25 | Order mode MUST use the same right target resolver as normal mode. |
| R-MC-26 | A Walk ground right click MUST show the built-in move target effect at the press point. |
| R-MC-27 | The move target effect MUST use the player race model. |
| R-MC-28 | The selected left-click target MAY be used when the press point is inside its radius. |
| R-MC-29 | Point picking MUST use unit radius when the hover unit is absent or outside the press-point radius. |

### 3.4 Both-button movement

| ID | Requirement |
| --- | --- |
| R-MC-30 | Left and right held together MUST start Move Forward. |
| R-MC-31 | Both-button Move Forward MUST behave like the W key. |
| R-MC-32 | Both-button Move Forward MUST steer by camera yaw while a turn button is held. |
| R-MC-33 | Releasing either button MUST end both-button Move Forward. |
| R-MC-34 | Independent W press and release MUST NOT change both-button Move Forward. |
| R-MC-35 | Both-button Move Forward MUST NOT select a target. |

### 3.5 Engine smart click

| ID | Requirement |
| --- | --- |
| R-MC-36 | Engine smart click MUST be disabled for all players. |
| R-MC-37 | Right commands MUST be the only source of right-click orders. |
| R-MC-38 | Ability target mode MUST stay engine handled. |
| R-MC-39 | Left selection MUST use the hover unit first and the press world point second. |

### 3.6 Combat state

| ID | Requirement |
| --- | --- |
| R-MC-40 | Right button down MUST leave combat state unchanged. |
| R-MC-41 | A clean right command MUST change combat state once, on release. |
| R-MC-42 | A right drag MUST leave combat state unchanged. |
| R-MC-43 | Combat state changes MUST go through the combat controller. |

### 3.7 Right-hold aim mode

| ID | Requirement |
| --- | --- |
| R-MC-44 | In action mode, a right hold MUST enter aim mode. |
| R-MC-45 | Aim mode MUST use the splitbody weapon-ready animation group. |
| R-MC-46 | Aim mode MUST use an over-the-shoulder camera with a lateral focus offset. |
| R-MC-47 | Aim mode MUST narrow the field of view once on entry. |
| R-MC-48 | Aim mode MUST show the native cursor at screen center with engine hover colors. |
| R-MC-49 | Right release MUST exit aim mode. |
| R-MC-50 | Aim exit MUST restore idle animation, centered follow camera, and field of view. |
| R-MC-51 | Aim mode MUST keep the scroll camera distance. |
| R-MC-52 | Aim mode MUST leave combat state unchanged. |
| R-MC-53 | Aim mode MUST run no right command. |
| R-MC-54 | Left drag MUST stay camera-only during and after aim. |
| R-MC-55 | The middle button MUST keep its turn behavior during aim. |
| R-MC-56 | A right drag MUST exit aim without running a right command. |
| R-MC-57 | Aim camera motion MUST stay smooth while the hero moves and turns. |
| R-MC-58 | Aim mode MUST render one splitbody group with concurrent upper and lower STCs. Separate render brackets MUST NOT play during aim. |
| R-MC-59 | Aim mode MUST keep lower-body walk or stand motion inside the splitbody lower STC. |
| R-MC-60 | Aim MUST hold one fixed weapon-ready upper pose from the Attack start keyframe. |
| R-MC-61 | The upper aim tracks MUST NOT loop the attack swing while aim is held. |
| R-MC-62 | Aim facing MUST follow camera yaw while stationary and moving. |
| R-MC-63 | Aim movement MUST keep unit facing on camera yaw and MUST NOT turn the unit toward the travel direction. |
| R-MC-64 | Aim movement MUST select one of eight lower-body directions. |
| R-MC-100 | Aim release MUST clear the aim group and restore baseline idle animation. |
| R-MC-101 | Aim backward movement MUST use reversed backpedal animation. |
| R-MC-102 | Aim torso-to-lower twist MUST NOT exceed 65 degrees in either direction while strafing. |
| R-MC-103 | Aim attack animation is DEFERRED to a later stage; this stage MUST NOT add an aim attack overlay. |

### 3.8 Control modes

| ID | Requirement |
| --- | --- |
| R-MC-65 | The command card MUST show a control mode toggle at top row column 2. |
| R-MC-66 | RPG mode MUST be active at map init and hero spawn. |
| R-MC-67 | The toggle MUST show `Controls: RPG` in RPG mode and `Controls: Actions` in action mode. |
| R-MC-68 | The toggle MUST work for every hero. |
| R-MC-69 | Control mode changes MUST leave combat state and cooldown unchanged. |
| R-MC-70 | Action mode MUST keep mouse look active without a held button. |
| R-MC-71 | Action mode MUST keep the native cursor at screen center. |
| R-MC-72 | Action mode MUST turn hero facing from camera yaw when not moving and not aiming. |
| R-MC-73 | Alt MUST pause mouse look, pause character turn, and show a free UI cursor. |
| R-MC-74 | Alt release MUST restore mouse look and the centered cursor. |
| R-MC-75 | A right hold in action mode MUST enter aim mode. |
| R-MC-76 | A right release in action mode MUST exit aim mode. |
| R-MC-77 | A right click in action mode MUST run no right command. |
| R-MC-78 | A left click in action mode MUST select and attack a hostile unit under the cursor. |
| R-MC-79 | A left click on ground in action mode MUST issue no Move or Stop. |
| R-MC-80 | Any click while Alt is held MUST interact with the UI and run no game order. |
| R-MC-81 | RPG return MUST restore RPG mouse, cursor, right-click behavior, field of view, and centered follow. |
| R-MC-82 | RPG return MUST exit aim mode. |
| R-MC-83 | Control mode changes MUST clear Alt pause and pending press state. |
| R-MC-84 | Action attack MUST use the combat controller. |
| R-MC-85 | Normal action movement MUST use path-checked native move orders and MUST set hero facing toward the movement direction. |
| R-MC-86 | Aim movement MUST use a camera-relative heading with path-checked native move orders while unit facing stays on camera yaw. |
| R-MC-87 | Action mode MUST keep the current follow camera and scroll distance. |
| R-MC-88 | Action right hold MUST apply the aim camera and restore the action camera on release. |
| R-MC-89 | RPG right hold MUST NOT enter aim mode. |
| R-MC-90 | RPG and action mode MUST use different custom toggle icons. |
| R-MC-91 | Aim entry, control mode change, and hero reassignment MUST reset animation state. |
| R-MC-92 | Aim movement MUST use the move target, retarget, and heading values in the implementation specification. |
| R-MC-93 | Facing changes MUST use `UnitSetFacing` with a duration. Aim uses `c_ANIM_AIM_TURN_DURATION`. |
| R-MC-94 | Turning MUST use native baseline turn animation and no upper turn overlay. |
| R-MC-95 | Aim MUST write camera facing every animation tick, independent of movement orders, and MUST NOT use a turn deadband. |
| R-MC-104 | Aim MUST add `SCOBAAimNoTurn` with `SuppressTurning` on entry and remove it on exit. It MUST NOT disable `Turnable` or zero turning rates. |
| R-MC-105 | Tosh and Kerrigan MUST use high `StationaryTurningRate` and `TurningRate` so aim facing does not lag. |
| R-MC-106 | Movement MUST NOT write facing during aim. `gf_AnimFacingTick` is the only aim facing writer. |
| R-MC-96 | Aim entry without a movement key MUST stop stale movement and restore idle. |
| R-MC-97 | Normal action A/D MUST turn the hero left or right and move. |
| R-MC-98 | Normal action S MUST turn the hero around and move. |
| R-MC-99 | Normal action movement MUST NOT use lateral strafe behavior. |

## 4. Acceptance criteria

| ID | Check |
| --- | --- |
| AC-MC-1 | Right hold turns camera and character. |
| AC-MC-2 | Middle hold behaves like right hold. |
| AC-MC-3 | RPG right clean click runs one right command. |
| AC-MC-4 | Right drag runs no right command. |
| AC-MC-5 | Left drag selects no target. |
| AC-MC-6 | Right click on an enemy selects and attacks it. |
| AC-MC-7 | Walk ground right click issues Move and shows the move target effect. |
| AC-MC-8 | Stand ground right click issues Stop and keeps the root. |
| AC-MC-9 | Both-button hold starts Move Forward and releasing either button stops it. |
| AC-MC-10 | Independent W press and release do not change both-button Move Forward. |
| AC-MC-11 | Engine smart click is disabled at map init. |
| AC-MC-12 | Aim entry uses the weapon-ready pose, shoulder camera, narrower field of view, and centered native cursor. |
| AC-MC-13 | Aim exit restores idle, follow camera, field of view, and scroll distance. |
| AC-MC-14 | Aim drag exits aim and runs no right command. |
| AC-MC-15 | Aim does not change combat state. |
| AC-MC-16 | Aim keeps lower-body walk and stand motion correctly inside one splitbody group. |
| AC-MC-17 | Aim holds one fixed upper pose without an attack loop or restart. |
| AC-MC-18 | Aim facing tracks camera yaw at rest and in motion. |
| AC-MC-19 | Aim movement stops at unpathable points. |
| AC-MC-20 | Aim lateral movement shows Walk with advancing lower frame IDs. |
| AC-MC-20 | RPG mode is active at map init and hero spawn. |
| AC-MC-21 | The toggle shows the correct label for each mode. |
| AC-MC-22 | Action mode mouse look, centered cursor, and facing work without a held button. |
| AC-MC-23 | Alt pauses mouse look, pauses turn, and shows the UI cursor. |
| AC-MC-24 | Right hold enters aim and right release exits it. |
| AC-MC-25 | Action right click runs no right command. |
| AC-MC-26 | Action left click attacks a hostile unit and ignores ground. |
| AC-MC-27 | Alt click interacts with UI and runs no game order. |
| AC-MC-28 | RPG return restores RPG behavior and exits aim. |
| AC-MC-29 | Control mode changes leave combat state and cooldown unchanged. |
| AC-MC-30 | Normal action movement turns the hero toward the movement direction and stops at unpathable points. |
| AC-MC-31 | Action movement keeps camera and scroll distance. |
| AC-MC-32 | Control mode changes clear Alt and pending press state. |
| AC-MC-33 | RPG right hold does not enter aim. |
| AC-MC-34 | RPG and action mode show different icons. |
| AC-MC-35 | A left-click target survives idle, Stop, and move completion. |
| AC-MC-36 | A stale hover unit does not hijack a ground click. |
| AC-MC-37 | Ground right clicks do not clear the left-click target. |
| AC-MC-38 | Aim movement uses one periodic movement loop with native move orders. |
| AC-MC-39 | Aim entry and control mode changes reset animation state. |
| AC-MC-40 | Idle action facing reaches camera yaw and no upper turn overlay starts. |
| AC-MC-41 | Aim movement runs without stop and go bursts. |
| AC-MC-42 | Aim entry without a movement key shows the idle splitbody aim group. |
| AC-MC-43 | Non-aim action A/D turns left or right and moves without strafing. |
| AC-MC-44 | Non-aim action S turns around and moves. |
| AC-MC-45 | Aim movement shows eight distinct lower directions. |
| AC-MC-46 | Aim backward movement shows a reversed backpedal clip. |
| AC-MC-47 | Aim twist stays at or below 65 degrees while strafing. |
| AC-MC-48 | Aim movement with real W/A/S/D and diagonals keeps unit facing within tolerance of camera yaw. |
| AC-MC-49 | Aim S moves opposite camera forward while facing camera yaw and plays the reversed backpedal lower clip. |
| AC-MC-50 | Aim facing follows camera rotation without perceptible lag. |
| AC-MC-51 | Aim adds and removes `SCOBAAimNoTurn` without changing `Turnable` or turning rates. |
| AC-MC-50 | Aim attack animation is not implemented in this stage. |

## 5. Non-functional requirements

- The build MUST remain deterministic and idempotent.
- Every Galaxy file MUST stay below 512 lines.
- Mouse handlers MUST be testable from the map test harness.
- New globals and constants MUST live in the existing core modules.
- New scripts MUST be wired into the build pipeline.

## 6. Out of scope

- Mouse sensitivity settings.
- Minimap and UI panel behavior outside the Alt UI cursor path.
- Ability target-mode visuals.
- Network latency compensation.

## 7. References

- WoW right-button camera and context click behavior.
- WoW click versus drag behavior.
- WoW both-button movement behavior.
- Galaxy unit highlight and mouse events.
- Unit radius and smart-click suppression.
- Splitbody animation group and directional aim references.
- Native cursor and free UI cursor references.
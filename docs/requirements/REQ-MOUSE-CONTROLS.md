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
- **Drag**: camera yaw or pitch change at or above the drag threshold during one hold.
- **Clean click**: a press and release with no drag.
- **Right command**: the action run by a clean right click.
- **Unit Highlight**: the engine hover unit and `PreSelection` ring under the cursor. It is informational only.
- **Unit Target**: the RPG boss-bar target chosen by a clean left or right click. This is not engine selection.
- **Unit Select**: native engine selection. Only the Order button changes it to a non-hero unit.
- **Ability target**: engine ability target mode. It is separate from Unit Target.
- **Both-button hold**: left and right buttons held together.
- **Aim mode**: the state entered by a right hold in action mode.
- **Aim cursor**: the screen-center image overlay drawn with native cursor textures.
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
| R-MC-5 | Releasing the last turn button MUST stop rotation and restore free cursor visibility. It MUST NOT enable camera input lock. |
| R-MC-6 | Camera turn MUST work in normal and order modes. |

### 3.2 Click versus drag

| ID | Requirement |
| --- | --- |
| R-MC-7 | A right drag MUST run no right command. |
| R-MC-8 | A left drag MUST set no target. |
| R-MC-9 | Left target selection MUST run on clean release. It MUST NOT change native unit selection. |
| R-MC-10 | RPG right clean click MUST run the right command on release. |
| R-MC-11 | Drag detection MUST use camera yaw or pitch change from press to release. It MUST NOT use release UI distance. |
| R-MC-12 | Mouse-relative mode MUST hide the free cursor and show the screen-center reticle. |
| R-MC-13 | The reticle MUST be hidden outside aim and action mode. |
| R-MC-14 | Aim mode MUST show the screen-center reticle using native cursor textures. |
| R-MC-15 | A both-button hold MUST cancel a pending right command. |

### 3.3 Right command

| ID | Requirement |
| --- | --- |
| R-MC-16 | Every RPG Unit Target MUST come from the click under the cursor for the clicking player, using `UnitClick` first, then press-time Unit Highlight, then press-point geometry. |
| R-MC-17 | `UnitClick` and Unit Highlight events MUST be registered per player. `EventPlayer` MUST NOT be used to infer the clicking player. |
| R-MC-18 | Right targeting MUST accept only alive hostile units. |
| R-MC-19 | A right click on an enemy MUST target it and issue a manual attack. It MUST NOT change native unit selection. |
| R-MC-20 | A right click on an enemy MUST move the boss-bar target. |
| R-MC-21 | A right click on ground in Walk MUST issue Move. |
| R-MC-22 | A right click on ground in RPG Stand MUST issue Stop and keep the root. |
| R-MC-23 | Ground and move commands MUST NOT clear the left-click target. |
| R-MC-24 | The left-click target MUST clear only on replacement, ground left click, death, removal, or explicit clear. |
| R-MC-25 | Order mode MUST use the same right target resolver as normal mode. |
| R-MC-26 | A Walk ground right click MUST show the built-in move target effect at the press point. |
| R-MC-27 | The move target effect MUST use the player race model. |
| R-MC-28 | RPG Unit Target clicks MUST prefer the engine `UnitClick` unit, then the press-time highlighted unit, then press-point geometry. |
| R-MC-29 | Action-mode attacks MAY use `gf_UnitTargetAtPoint`; RPG left, right, and order clicks MUST use the same Unit Target candidate order. |

### 3.4 Both-button movement

| ID | Requirement |
| --- | --- |
| R-MC-30 | Left and right held together MUST start Move Forward. |
| R-MC-31 | Both-button Move Forward MUST behave like the W key. |
| R-MC-32 | Both-button Move Forward MUST steer by camera yaw while a turn button is held. |
| R-MC-33 | Releasing either button MUST end both-button Move Forward. |
| R-MC-34 | Independent W press and release MUST NOT change both-button Move Forward. |
| R-MC-35 | Both-button Move Forward MUST NOT set a target. |

### 3.5 Engine smart click

| ID | Requirement |
| --- | --- |
| R-MC-36 | Engine smart click MUST be disabled for all players. |
| R-MC-37 | Right commands MUST be the only source of right-click orders. |
| R-MC-38 | Ability target mode MUST stay engine handled. |
| R-MC-39 | RPG left, right, and order clicks MUST use the same Unit Target candidate order for the clicking player. |

### 3.5.1 Selection and order button

| ID | Requirement |
| --- | --- |
| R-MC-125 | Every unit and building MUST remain native selectable so the engine can draw the custom `PreSelection` hover ring. |
| R-MC-126 | A left click on a unit or building MUST set the left-click target and MUST NOT change native unit selection. |
| R-MC-127 | A left click on ground MUST clear the left-click target only. It MUST NOT change native unit selection. |
| R-MC-128 | The hero MUST remain natively selected outside order mode. |
| R-MC-129 | Ctrl+C MUST cancel order mode when active. It MUST NOT clear native selection. |
| R-MC-130 | The Order button MUST be visible when the left-click target is valid and owned by the player. |
| R-MC-131 | The Order button MUST be the only action that changes native selection to a non-hero unit. |
| R-MC-132 | Order entry MUST clear native selection, select the order unit, and enter order mode. |
| R-MC-133 | Order exit or cancel MUST clear the order-unit selection and restore hero selection. |
| R-MC-134 | Target changes and order exit MUST NOT set any unit `Selectable=false`. |
| R-MC-135 | Unit Highlight MUST drive hover rings and may provide the press-time Unit Target candidate. Ability targeting is never derived from it. |
| R-MC-136 | Map camera data MUST set `BorderSizeX=0`, `BorderSizeY=0`, `MaxScrollRate Follow=0`, `MaxScrollDistance Follow=0`, and `FollowScrollLimit=0` on `CCamera id="Dflt"`. Screen-edge scrolling MUST NOT move the camera. |
| R-MC-137 | Order-mode right click MUST attack a resolved enemy or move the order unit. It MUST keep order mode active. |
| R-MC-138 | Every unit type on the map MUST clear `FlagArray[Unclickable]` and `FlagArray[Unhighlightable]` at map init and on creation. |
| R-MC-139 | `UnitClick` and Unit Highlight MUST be registered separately for each hero player; each callback MUST hard-code its clicking player. |
| R-MC-140 | A new press MUST clear the old Unit Target candidate. A clean release MUST consume and clear the candidate so later ground clicks cannot reuse it. |
| R-MC-141 | The click handler MUST immediately reselect the hero outside order mode. The hero reselect MUST NOT wait for the 0.1 s poll. |
| R-MC-142 | Native unit selection flash from a click MUST last at most the current event tick. |

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
| R-MC-48 | Aim mode MUST show the screen-center reticle with native cursor textures and hostile/friendly/neutral color. |
| R-MC-49 | Right release MUST exit aim mode. |
| R-MC-50 | Aim exit MUST restore idle animation, centered follow camera, and field of view. |
| R-MC-51 | Aim mode MUST shorten the camera arm by `c_SCOBA_AIM_ARM_SCALE` and restore the saved scroll distance on exit. |
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
| R-MC-71 | Action mode MUST keep the screen-center reticle visible. |
| R-MC-72 | Action mode MUST turn hero facing from camera yaw when not moving and not aiming. |
| R-MC-73 | Alt MUST pause mouse look, pause character turn, and show a free UI cursor. |
| R-MC-74 | Alt release MUST restore mouse look and the centered cursor. |
| R-MC-75 | A right hold in action mode MUST enter aim mode. |
| R-MC-76 | A right release in action mode MUST exit aim mode. |
| R-MC-77 | A right click in action mode MUST run no right command. |
| R-MC-78 | A left click in action mode MUST target and attack a hostile unit under the cursor. |
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
| R-MC-107 | Camera collision MUST clamp only `c_cameraValueDistance`. It MUST NOT write pitch or yaw. |
| R-MC-108 | Camera collision MUST keep a desired scroll distance and restore it when terrain clears. |
| R-MC-109 | Camera collision MUST sweep from the camera target toward the desired eye with a camera radius. |
| R-MC-110 | Camera collision MUST shorten distance with a short blend and restore it with a slower blend. Neither transition may snap. |
| R-MC-111 | Camera collision MUST apply the safety clamp on every tick, including while pitch or yaw is changing. |
| R-MC-112 | Scroll input MUST animate the distance change with `c_SCOBA_ZOOM_BLEND`. It MUST NOT install a zero-duration distance change. |
| R-MC-113 | Camera collision MUST check terrain height along the sweep. |
| R-MC-114 | `gf_ControlApply` MUST be the only writer of camera mouse-rotate, mouse-relative, and cursor visibility state. It MUST NOT enable camera input lock in RPG idle. |
| R-MC-115 | Mouse press/release handlers MUST own held button state. Targeting MUST read that state and MUST NOT write it. |
| R-MC-116 | Control state MUST derive from control mode, aim state, Alt state, and held buttons. It MUST NOT depend on trigger execution order. |
| R-MC-117 | Releasing a mouse button MUST restore RPG cursor mode even when targeting release is skipped or reordered. |
| R-MC-118 | Map init, control mode changes, Alt changes, and aim entry/exit MUST route through `gf_ControlApply`. |
| R-MC-119 | RPG hover MUST be set from the engine `UnitHighlight` event and cleared when that unit is no longer highlighted. |
| R-MC-120 | RPG click points MUST come from the engine `EventMouseClickedPosXWorld` and `EventMouseClickedPosYWorld` values. |
| R-MC-121 | Aim mode camera origin MUST translate slightly left of the hero, using `c_SCOBA_AIM_SHOULDER_ANGLE`. It MUST NOT rotate the camera away from hero heading and MUST NOT sit directly behind the hero. |
| R-MC-122 | The reticle MUST use `cursor-target-none.dds` for every state. Neutral is white, hostile is red, friendly is blue, and hostile out of range is gray. It MUST NOT use the native `storm_ui_cursor_default_*` arrow cursors. |
| R-MC-123 | The reticle MUST resolve at the aim crosshair point every 0.01 s and show enemy, friendly, or neutral art. |
| R-MC-124 | The reticle MUST hide in RPG mode and while Alt shows the free UI cursor. |
| R-MC-99 | Normal action movement MUST NOT use lateral strafe behavior. |

## 4. Acceptance criteria

| ID | Check |
| --- | --- |
| AC-MC-1 | Right hold turns camera and character. |
| AC-MC-2 | Middle hold behaves like right hold. |
| AC-MC-3 | RPG right clean click runs one right command. |
| AC-MC-4 | Right drag runs no right command. |
| AC-MC-5 | Left drag sets no target. |
| AC-MC-6 | Right click on an enemy targets and attacks it. |
| AC-MC-7 | Walk ground right click issues Move and shows the move target effect. |
| AC-MC-8 | Stand ground right click issues Stop and keeps the root. |
| AC-MC-9 | Both-button hold starts Move Forward and releasing either button stops it. |
| AC-MC-10 | Independent W press and release do not change both-button Move Forward. |
| AC-MC-11 | Engine smart click is disabled at map init. |
| AC-MC-12 | Aim entry uses the weapon-ready pose, shoulder camera, narrower field of view, and centered reticle. |
| AC-MC-13 | Aim exit restores idle, follow camera, field of view, and scroll distance. |
| AC-MC-14 | Aim drag exits aim and runs no right command. |
| AC-MC-15 | Aim does not change combat state. |
| AC-MC-16 | Aim keeps lower-body walk and stand motion correctly inside one splitbody group. |
| AC-MC-17 | Aim holds one fixed upper pose without an attack loop or restart. |
| AC-MC-18 | Aim facing tracks camera yaw at rest and in motion. |
| AC-MC-19 | Aim movement stops at unpathable points. |
| AC-MC-20 | Aim lateral movement shows Walk with advancing lower frame IDs. |
| AC-MC-51 | RPG mode is active at map init and hero spawn. |
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
| AC-MC-36 | A click outside the unit radius does not target that unit. |
| AC-MC-37 | RPG left and right click target resolution works after a fresh launch. |
| AC-MC-38 | A right-click release restores cursor mode and hover state. |
| AC-MC-39 | Control mode, Alt, and aim transitions leave one consistent cursor state. |
| AC-MC-40 | Held button state is released even when targeting release runs late. |
| AC-MC-58 | RPG hover follows the engine `UnitHighlight` event and shows the `PreSelection` ring. |
| AC-MC-59 | RPG clicks resolve a Unit Target for the clicking player from `UnitClick`, press-time Unit Highlight, or press-point geometry. |
| AC-MC-60 | Scroll zoom and collision distance changes animate instead of snapping. |
| AC-MC-61 | Aim camera origin is translated slightly left of the hero without rotating the camera. |
| AC-MC-52 | Ground right clicks do not clear the left-click target. |
| AC-MC-53 | Aim movement uses one periodic movement loop with native move orders. |
| AC-MC-54 | Aim entry and control mode changes reset animation state. |
| AC-MC-55 | Idle action facing reaches camera yaw and no upper turn overlay starts. |
| AC-MC-56 | Aim movement runs without stop and go bursts. |
| AC-MC-57 | Aim entry without a movement key shows the idle splitbody aim group. |
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
| AC-MC-66 | All units and buildings remain selectable and show the `PreSelection` hover ring. |
| AC-MC-67 | Left clicking a unit or building sets the target without changing native selection. |
| AC-MC-68 | Left clicking ground clears the target and leaves the hero selected. |
| AC-MC-69 | The Order button appears for an owned target and is hidden for hostiles and neutral units. |
| AC-MC-70 | Pressing Order selects the order unit; exit or cancel restores hero selection. |
| AC-MC-71 | Order-mode right click attacks or moves the order unit and keeps order mode active. |
| AC-MC-72 | Target changes and order exit do not set `Selectable=false`. |
| AC-MC-73 | Moving the cursor to a screen edge does not move the camera. |
| AC-MC-74 | A ground click after a unit click clears the target and does not reuse the old unit. |
| AC-MC-75 | A left click on an enemy, neutral, owned unit, or building does not leave that unit natively selected past the event tick. |
| AC-MC-76 | Right-click attack works on enemies owned by players other than the clicking player. |

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
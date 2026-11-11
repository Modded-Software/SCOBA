# SPEC-MOUSE-CONTROLS: Mouse Controls

**Date:** 2026-11-10
**Status:** Active implementation specification
**Requirements:** [REQ-MOUSE-CONTROLS](../requirements/REQ-MOUSE-CONTROLS.md)

## 1. Purpose

This document specifies mouse look, right-click commands, right-hold aim mode,
Actions and RPG control modes, Alt UI pause, splitbody aim animation,
native turn animation,
aim facing, and both-button movement. It also specifies the event order that
prevents right-click state races.

## 2. Module layout

- `systems/camera.galaxy`: camera and character turn state.
- `systems/aim.galaxy`: right-hold state, aim camera offset, aim field of view,
  aim animation requests, and native cursor visibility.
- `systems/animation_fsm.galaxy`: splitbody aim selection, direction selection,
  turn state, and action-mode facing.
- `systems/targeting.galaxy`: mouse press, release, drag detection, right
  command, and left selection.
- `systems/movement.galaxy`: forward movement loop, both-button alias, and aim
  movement.
- `systems/controls.galaxy`: control mode toggle, action mode mouse look, Alt
  pause, and action mode clicks.
- `systems/gui_environment.galaxy`: engine smart-click suppression.
- `core/animation.galaxy`: animation state IDs and config tables.
- `core/globals.galaxy`: mouse, aim, and animation state globals.
- `core/constants.galaxy`: drag, radius, scan, aim, and animation constants.

## 3. Globals

| Global | Type | Purpose |
| --- | --- | --- |
| `gv_mOUSELEFT` | `bool[8]` | Left button is held |
| `gv_mOUSERIGHT` | `bool[8]` | Right button is held |
| `gv_mOUSEFORWARD` | `bool[8]` | Both-button Move Forward is active |
| `gv_kEYFORWARD` | `bool[8]` | W key is held |
| `gv_mOUSERIGHTCANCEL` | `bool[8]` | Pending right command is cancelled |
| `gv_mOUSEPRESSXUI` | `int[8]` | Press UI X |
| `gv_mOUSEPRESSYUI` | `int[8]` | Press UI Y |
| `gv_mOUSEPRESSX` | `fixed[8]` | Press world X |
| `gv_mOUSEPRESSY` | `fixed[8]` | Press world Y |
| `gv_sCOBAPRESSUNIT` | `unit[8]` | Hover unit at right press |
| `gv_sCOBALEFTPRESSUNIT` | `unit[8]` | Hover unit at left press |
| `gv_mOUSELEFTCANCEL` | `bool[8]` | Left selection is cancelled |
| `gv_mOUSELEFTPRESSXUI` | `int[8]` | Left press UI X |
| `gv_mOUSELEFTPRESSYUI` | `int[8]` | Left press UI Y |
| `gv_mOUSELEFTPRESSX` | `fixed[8]` | Left press world X |
| `gv_mOUSELEFTPRESSY` | `fixed[8]` | Left press world Y |
| `gv_mOUSERIGHTPRESSX` | `fixed[8]` | Right press world X |
| `gv_mOUSERIGHTPRESSY` | `fixed[8]` | Right press world Y |
| `gv_aIMACTIVE` | `bool[8]` | Right-hold aim mode is active |
| `gv_cAMERAFOV` | `fixed[8]` | Field of view without aim mode |
| `gv_animUpperState` | `int[8]` | Active logical upper state |
| `gv_animLowerState` | `int[8]` | Active lower-body state |
| `gv_animAimClip` | `string[hero][state][direction]` | Aim group name per lower state and direction |
| `gv_animAimDir` | `int[8]` | Active aim movement direction |
| `gv_animFullState` | `int[8]` | Active splitbody aim state |

| `gv_animAimMoving` | `bool[8]` | Aim movement is active |
| `gv_actionAlt` | `bool[8]` | Alt pause is active |
| `gv_actionPressed` | `bool[8]` | Action mode button press is pending |

## 4. Constants

| Constant | Value | Purpose |
| --- | --- | --- |
| `c_SCOBA_CLICK_DRAG_PIXELS` | 4 | Click versus drag threshold |
| `c_SCOBA_CLICK_SCAN_RADIUS` | 8.0 | Point pick search radius |
| `c_SCOBA_CLICK_MARGIN` | 0.75 | Point pick radius margin |
| `c_SCOBA_AIM_FOV` | 45.0 | Field of view while aiming |
| `c_SCOBA_AIM_SHOULDER_OFFSET` | 1.0 | Camera focus offset to the weapon shoulder |
| `c_ANIM_TURN_DURATION` | 0.1 | Engine facing interpolation duration |
| `c_ANIM_TURN_DEADBAND` | 3.0 | Non-aim yaw change that writes a new facing target |
| `c_ANIM_MOVE_TARGET` | 30.0 | Continuous move order target distance |
| `c_ANIM_MOVE_RETARGET` | 2.0 | Remaining distance that refreshes the target |
| `c_ANIM_MOVE_HEADING` | 12.0 | Heading change that refreshes the target |
| `c_ANIM_MOVE_TICK` | 0.015 | Aim movement loop interval |
| `c_ANIM_AIM_TURN_DURATION` | 0.05 | Aim facing interpolation duration |
| `SCOBAAimNoTurn` | buff | Suppresses native turn-to-travel during aim |
| `c_SCOBA_ACTION_ROW` | 0 | Control mode button row |
| `c_SCOBA_ACTION_COLUMN` | 2 | Control mode button column |
| `c_SCOBA_ACTION_BEHAVIOR` | `SCOBAActionModeBehavior` | Action mode state |
| `c_SCOBA_ACTION_KEY` | `c_keyAlt` | Alt pause key |

Flat point distance is never the primary target source.

## 5. Event registration

| Event | Trigger | Action |
| --- | --- | --- |
| Left mouse down | `gt_TargetClick` | Set left state; save press point; cancel on both-button |
| Left mouse up | `gt_TargetRelease` | Clear left state; stop both-button forward; select on clean release |
| Right mouse down | `gt_TargetClick` | Set right state; snapshot press; cancel on both-button |
| Right mouse up | `gt_TargetRelease` | Clear right state; run clean-click command; stop both-button forward |
| Right mouse down | `gt_CursorStart` | RPG: start camera turn. Action: start aim mode |
| Right mouse up | `gt_CursorEnd` | RPG: stop camera turn. Action: stop aim mode |
| Middle mouse down | `gt_CursorStart` | Start camera turn |
| Middle mouse up | `gt_CursorEnd` | Stop camera turn |
| Left mouse down | `gt_CursorStart` | Start camera orbit |
| Left mouse up | `gt_CursorEnd` | Stop camera orbit |
| Alt down | `gt_ActionAltStart` | Pause action mode mouse look and show UI cursor |
| Alt up | `gt_ActionAltEnd` | Resume action mode mouse look and center cursor |
| Action toggle On | `gt_ActionModeOn` | Apply action mode camera and cursor |
| Action toggle Off | `gt_ActionModeOff` | Restore RPG camera and cursor |
| Periodic 0.05s | `gt_AnimTick` | Select animation layers and update facing |
| Movement loop | forward, backward, lateral loops | Normal action uses RPG move-and-turn. Aim per-key loops only set flags. |
| Aim movement loop | `gt_AimMoveTick` | Sole aim move-order owner at `c_ANIM_MOVE_TICK`. |

`gt_TargetClick` is registered before `gt_CursorStart`. Press state is saved
before camera state changes.

## 6. Left press and release

On left-button down:

1. Set `gv_mOUSELEFT[player] = true`.
2. Set `gv_mOUSELEFTCANCEL[player]` to the current right-button state.
3. Save `EventMouseClickedPosXUI` and `EventMouseClickedPosYUI`.
4. Save `EventMouseClickedPosXWorld` and `EventMouseClickedPosYWorld`.
5. Save `CameraGetYaw` and `CameraGetPitch`.
6. Save `gv_sCOBAHover[player]` as `gv_sCOBALEFTPRESSUNIT[player]`.
7. Set `gv_mOUSERIGHTCANCEL[player] = true` when the right button is held.

On left-button up:

1. Set `gv_mOUSELEFT[player] = false`.
2. Stop both-button forward.
3. Compute UI pixel distance from the press point.
4. Set drag when the pixel distance is at least
   `c_SCOBA_CLICK_DRAG_PIXELS`.
5. When the click is clean and not cancelled:
   - exit order mode;
   - select `gv_sCOBALEFTPRESSUNIT[player]` when it is inside the press-point radius;
   - resolve the unit at the saved press world point when the hover unit is absent or outside that radius;
   - clear the target when no unit resolves.
6. Clear `gv_mOUSELEFTCANCEL[player]`.

The left-click target remains active after hero idle, Stop, and move-order
completion. It changes only on replacement, ground left click, death, removal,
or an explicit clear.

Camera orbit starts in `gt_CursorStart` after press state is saved. Left
orbit changes the camera only. It does not change character heading.

In action mode, camera look is already active. Left click does not start orbit.
A clean left click resolves a hostile under the cursor and
calls `gf_CombatManualAttack`. It does not run the RPG left selection path.
While Alt is held, the click goes to the UI and no game action runs.

## 7. Right press

On right-button down:

1. Read player.
2. Stop when the player is not a hero player.
3. Set `gv_mOUSERIGHT[player] = true`.
4. Save `EventMouseClickedPosXUI`, `EventMouseClickedPosYUI`,
   `EventMouseClickedPosXWorld`, and `EventMouseClickedPosYWorld` as
   `gv_mOUSERIGHTPRESSX` and `gv_mOUSERIGHTPRESSY`.
5. Save `CameraGetYaw` and `CameraGetPitch`.
6. Save `gv_sCOBAHover[player]` as `gv_sCOBAPRESSUNIT[player]` when the press point is inside that unit's radius.
7. Set `gv_sCOBAPRESSUNIT[player]` to null when the hover unit is outside the press-point radius.
8. Set `gv_mOUSERIGHTCANCEL[player] = false`.
9. If `gv_mOUSELEFT[player]` is true, set the cancel flag and start
   both-button forward.
10. Return without changing combat state.

Camera turn starts in `gt_CursorStart` after press state is saved.

In action mode, right down enters aim mode.
The release exits aim and runs no right command.

## 8. Right release

On right-button up:

1. Read player.
2. Set `gv_mOUSERIGHT[player] = false`.
3. Stop both-button forward when the both-button hold has ended.
4. Read release UI position.
5. Compute UI pixel distance from the press point.
6. Set drag when the pixel distance is at least
   `c_SCOBA_CLICK_DRAG_PIXELS`.
7. Return when the cancel flag is set.
8. Return when drag is set.
9. Run `gf_RightClickExecute` with the saved press point and saved hover unit.

In RPG mode, camera turn stops in `gt_CursorEnd` after the command decision.

In action mode, right up exits aim mode and returns before
`gf_RightClickExecute`. No right command runs.

## 9. Right command resolver

`gf_ResolveClickEnemy(int lp_player, point lp_point)`:

1. Return `gv_sCOBAPRESSUNIT[lp_player]` when it is alive, hostile, and
   `lp_point` is inside its unit radius plus `c_SCOBA_CLICK_MARGIN`.
2. Return `gv_tARGET[lp_player]` when it is alive and hostile and
   `lp_point` is inside its unit radius plus `c_SCOBA_CLICK_MARGIN`.
3. Search enemies inside `c_SCOBA_CLICK_SCAN_RADIUS` around `lp_point`.
4. Return the closest enemy whose distance from `lp_point` is no more than
   `UnitGetPropertyFixed(unit, c_unitPropRadius, c_unitPropNormal)` plus
   `c_SCOBA_CLICK_MARGIN`.
5. Return null.

Step 1 is the engine hit-test source used by left-click selection.
A saved hover unit outside the press-point radius falls through to steps 2
and 3. Step 3 is the last check and does not override a valid hover unit.

## 10. Right command execution

`gf_RightClickExecute(int lp_player, point lp_point, unit lp_unit)`:

1. Set `lp_unit = gf_ResolveClickEnemy(lp_player, lp_point)`.
2. When `lp_unit` is valid:
   - call `gf_ShowTarget(lp_player, lp_unit)`;
   - call `gf_CombatManualAttack(lp_player, lp_unit)`;
   - return.
3. Call `gf_CombatCancelAuto(lp_player)`.
4. Set `gv_sCOBAManualOrder[lp_player] = false`.
5. Call `gf_CombatSyncRoot(lp_player)`.
6. When RPG Stand is active:
   - issue `Order(AbilityCommand("stop", 0))`;
   - set `gv_sCOBAFSM[lp_player]` to `c_SCOBA_FSM_IDLE`.
7. Otherwise, in RPG Walk:
   - issue `OrderTargetingPoint(AbilityCommand("move", 0), lp_point)`;
   - set `gv_sCOBAFSM[lp_player]` to `c_SCOBA_FSM_MOVING`;
   - call `gf_ShowMoveMarker(lp_player, lp_point)`.
8. Do not change `gv_tARGET[lp_player]`.
9. Do not run this function in action mode.

`gf_ShowMoveMarker` uses the built-in waypoint model:

- `CommandUIHarnessMoveTerran` for Terr;
- `CommandUIHarnessMoveZerg` for Zerg;
- `CommandUIHarnessMoveProtoss` for Prot.

It calls `libNtve_gf_CreateModelAtPoint` at the press point. It destroys the
actor after 0.6 seconds. This restores the built-in on-ground move target
effect without engine smart click.

## 11. Both-button movement

On left down while right is held, or right down while left is held:

1. Set `gv_mOUSERIGHTCANCEL[player] = true`.
2. Set `gv_mOUSEFORWARD[player] = true`.
3. When `gv_fORWARD[player]` is false, call `gf_ForwardBegin(player)`.

On either button up:

1. Set `gv_mOUSEFORWARD[player] = false`.
2. When `gv_kEYFORWARD[player]` is false, set
   `gv_fORWARD[player] = false`.
3. When no movement key is held, issue a stop order in action or aim mode and
   set the combat state to idle.

`gf_ForwardBegin` is the shared forward loop used by the W key and by the
both-button alias. It uses camera yaw while either turn button is held.

## 12. W key coordination

W down:

1. Set `gv_kEYFORWARD[player] = true`.
2. When `gv_fORWARD[player]` is false, call `gf_ForwardBegin(player)`.

W up:

1. Set `gv_kEYFORWARD[player] = false`.
2. When `gv_mOUSEFORWARD[player]` is false, set
   `gv_fORWARD[player] = false`.

The forward loop runs while `gv_fORWARD` is true.

## 13. Camera events

`gt_CursorStart` sets turn state for right and middle buttons. It sets camera
orbit state for the left button. It then applies mouse-relative camera control
when any camera button is active.

`gt_CameraTurnTick` turns the character to the camera yaw in RPG mode while a
right or middle button is held. It does nothing for left-button orbit and does
nothing in action mode.

`gt_CursorEnd` clears state for the released button. It keeps mouse-relative
camera control active while any camera button remains held. It restores cursor
visibility and camera lock when all camera buttons are released.

Right and middle buttons use the same state and the same camera calls. Left
orbit uses the same camera calls but does not turn the character.

Outside aim mode, normal action movement, and RPG camera turns, the character
turn tick is not a facing writer. Left orbit never writes hero facing.

During action mode, `gf_AnimFacingTick` writes a facing target from camera yaw
without a held button when the hero is not moving. Alt pause stops those writes.
It calls `gf_TurnToYaw` only when the yaw change exceeds
`c_ANIM_TURN_DEADBAND`.
Normal action movement writes facing toward the movement direction.
The engine interpolates facing over `c_ANIM_TURN_DURATION` and plays the
native full-body turn clips.
No upper turn state is selected.

During aim mode, the character turn tick does not write hero facing.
`gf_AnimFacingTick` is the only writer of hero facing while aim is active.
Aim facing is camera yaw at rest and while moving.
Aim does not use `c_ANIM_TURN_DEADBAND`.
Aim writes `UnitSetFacing` with `c_ANIM_AIM_TURN_DURATION` every 0.05 seconds.
Aim facing is independent of movement orders.
One aim movement loop owns travel.
It issues a path-checked native move order along one camera-relative travel
heading per tick.
`gf_AimBegin` adds `SCOBAAimNoTurn` (`SuppressTurning`).
`gf_AimEnd` removes it.
The unit's `Turnable` flag and turning rates are not changed by the buff.
Tosh and Kerrigan use high `StationaryTurningRate` and `TurningRate`.
Per-key movement loops only set input flags during aim.

## 14. Right-hold aim mode

In action mode, `gt_CursorStart` calls `gf_AimBegin(player)` on a right-button
press.
In action mode, `gt_CursorEnd` calls `gf_AimEnd(player)` on a right-button
release.
RPG right-button input never calls `gf_AimBegin` or `gf_AimEnd`.

`gf_AimBegin`:

1. Return when the player is not a hero player.
2. Return when aim mode is already active.
3. Return when the hero is invalid.
4. Set `gv_aIMACTIVE[player] = true`.
5. Add `SCOBAAimNoTurn` to suppress native turn-to-travel.
6. Call `gf_AnimReset(player)`.
7. Clear stale splitbody and baseline animation during that reset.
8. Request the splitbody aim state from `gf_AnimTick`.
9. Set the field of view to `c_SCOBA_AIM_FOV` once.
10. Compute the shoulder focus point with
    `PointWithOffsetPolar(heroPos, c_SCOBA_AIM_SHOULDER_OFFSET, CameraGetYaw(player) + 90.0)`.
11. Look the camera at the shoulder focus point once.
12. Re-apply unit follow with the offset retained by passing `true` for
    `isOffset`.
13. Show the native cursor with `UISetCursorVisible`.
14. Do not write `c_cameraValueDistance`.

`gf_AimEnd`:

1. Return when aim mode is not active.
2. Clear the aim movement state.
3. Set hero facing to camera yaw.
4. Remove `SCOBAAimNoTurn`.
5. Set `gv_aIMACTIVE[player] = false`.
6. Clear the aim group and restore baseline animation.
7. Set the field of view to `gv_cAMERAFOV[player]` once.
8. Re-apply centered unit follow with `isOffset` false.
9. Hide the native cursor.
10. Restore the mouse-relative cursor pin for the next camera hold.
11. Do not write `c_cameraValueDistance`.

`gt_AnimTick` runs every 0.05 seconds while the map is running.
During aim mode it:

1. Selects the aim group from the active lower-body state and direction.
2. Computes movement heading relative to camera yaw.
3. Snaps heading to one of eight directions.
4. Calls `gf_AnimFacingTick`.
5. Calls `gf_AnimFullSet` with the selected aim group.

One aim movement loop runs every `c_ANIM_MOVE_TICK` seconds while aim movement
is active.
It is the sole aim move-order owner and issues at most one order per tick.
It uses native path-checked move orders.
It never writes facing.
Normal action movement uses the RPG move-and-turn path.

The aim group uses one actor animation group.
It sends an actor message only when the lower state or direction changes.
The upper STC stays frozen at the Attack start key while aim is held.
The lower STC keeps Stand or Walk animating.
The lower STC changes across eight movement directions.
Backward movement uses a reversed backpedal lower STC.
Torso-to-lower twist stays at or below 65 degrees in either strafe direction.
No 180-degree lower turn with planted feet is allowed.
Separate render brackets are not played during aim.

Aim movement uses one camera-relative travel heading per tick.
W moves camera-forward, S camera-backward, and A/D camera-left/right.
Diagonals preserve both components.
S backpedals without turning the unit.
A/D strafe without turning the unit.
Aim facing is applied every animation tick, independent of movement orders.
The splitbody lower STC keeps the legs and feet moving in the travel direction.
Hero facing stays on camera yaw during aim.
Normal action movement uses `UnitSetFacing` toward movement with `c_ANIM_TURN_DURATION`.

Aim mode does not write camera values on the animation tick.
Camera values change only on entry, exit, and camera input.

Aim mode never writes `c_cameraValueDistance`. Scroll changes during aim mode
therefore remain in force after aim mode exits.

Aim mode never calls `CameraSetBounds`. Camera bounds caused the camera origin
to orbit and snap. The shoulder offset comes from the retained follow offset,
not from bounds.

The aim pose uses one splitbody group per lower state and direction. Tosh and
Kerrigan use generated splitbody aim groups. Firebat uses its shipped model and
baseline animation.
The animation implementation is specified in
[SPEC-CHARACTER-ANIMATION](SPEC-CHARACTER-ANIMATION.md).

The aim cursor is the native StarCraft II selection cursor. Mouse-relative mode
already pins the cursor to screen center. Aim mode only makes that cursor
visible. The cursor therefore keeps the engine hostile and neutral color
changes. Aim mode uses no dialog, no image panel, and no custom cursor texture.

## 14A. Actions and RPG control modes

The command card toggle lives at top row column 2, before the auto-attack
button. The button face and name follow the current mode:

| Mode | Behavior | Button face | Button name |
| --- | --- | --- | --- |
| RPG | `SCOBAActionModeBehavior` absent | `SCOBAActionModeRPG` | `Controls: RPG` |
| Actions | `SCOBAActionModeBehavior` present | `SCOBAActionModeActions` | `Controls: Actions` |

The RPG face uses `Assets\Textures\SCOBAModeRPG.dds`.
The action face uses `Assets\Textures\SCOBAModeActions.dds`.
The two textures have different pixels and different file hashes.
`scripts/control_mode_icons.py` generates both textures.
The script is idempotent, reversible, and wired into
`scripts/expand_map.py`.

The toggle uses a `CAbilBehavior` with `SCOBAActionModeBehavior`.
The behavior is the only control mode state.
No boolean mirror is stored.

`gf_ActionModeActive(player)` reads
`UnitBehaviorCount(hero, "SCOBAActionModeBehavior") > 0`.

At map init and hero spawn, `gf_ActionModeEnsureRPG(player)` removes the
behavior and applies RPG camera and cursor state.

`gf_ActionModeApply(player)`:

1. Return when the hero is invalid.
2. Clear `gv_actionPressed[player]`.
3. Clear `gv_actionAlt[player]`.
4. Clear `gv_mOUSERIGHTCANCEL[player]` and `gv_mOUSELEFTCANCEL[player]`.
5. Clear left and right button state and saved press units.
6. Call `gf_AnimReset(player)`.
7. When action mode is active:
   - call `CameraSetMouseRotates(player, true)`;
   - call `CameraForceMouseRelative(player, true)`;
   - call `CameraLockInput(player, false)`;
   - call `UISetCursorVisible(PlayerGroupSingle(player), true)`;
   - call `UISetCursorAutoHide(PlayerGroupSingle(player), false, 0.0)`.
8. When RPG mode is active:
   - call `gf_AimEnd(player)` when aim is active;
   - restore `c_cameraValueFieldOfView` to the non-aim value;
   - restore centered unit follow;
   - clear camera turn and orbit state;
   - call `CameraSetMouseRotates(player, false)`;
   - call `CameraForceMouseRelative(player, false)`;
   - call `CameraLockInput(player, true)`;
   - call `UISetCursorVisible(PlayerGroupSingle(player), true)`;
   - call `UISetCursorAutoHide(PlayerGroupSingle(player), false, 0.0)`.

Action mode mouse look runs without a held mouse button.
It keeps the current third-person follow camera, field of view, and scroll
distance.
`gf_AnimFacingTick` on `gt_AnimTick` writes a facing target from
`CameraGetYaw` every 0.05 seconds in action mode when the hero is not moving.
It calls `gf_TurnToYaw` when the yaw change exceeds `c_ANIM_TURN_DEADBAND`.
Normal action movement writes facing toward the movement direction.
Aim `gf_AnimFacingTick` writes camera facing every 0.05 seconds with no
deadband and no dependence on movement orders.
The engine interpolates non-aim facing over `c_ANIM_TURN_DURATION` and aim
facing over `c_ANIM_AIM_TURN_DURATION`, then plays the native full-body turn
clips.
RPG mode keeps the existing right and middle button facing behavior.

Action mode right hold calls `gf_AimBegin` and applies the aim camera.
Action mode right release calls `gf_AimEnd` and restores the action camera.
Scroll distance survives both transitions.

Alt down in action mode:

1. Set `gv_actionAlt[player] = true`.
2. Call `CameraSetMouseRotates(player, false)`.
3. Call `CameraForceMouseRelative(player, false)`.
4. Call `CameraLockInput(player, true)`.
5. Call `UISetCursorVisible(PlayerGroupSingle(player), true)`.
6. Call `UISetCursorAutoHide(PlayerGroupSingle(player), false, 0.0)`.
7. Stop the action mode facing writer.

Alt up in action mode:

1. Set `gv_actionAlt[player] = false`.
2. Call `gf_ActionModeApply(player)`.

Alt events are ignored in RPG mode.

Action mode mouse input:

| Input | Result |
| --- | --- |
| Right down | Call `gf_AimBegin` and set action aim state |
| Right up | Call `gf_AimEnd` |
| Left down, Alt not held | Resolve hostile at `CameraGetTarget` and call `gf_CombatManualAttack` |
| Left up, Alt not held | Clear action press state |
| Any click, Alt held | UI handles the click; no game attack, aim, or order |
| Right clean click | No right command |
| Ground left click | No Move or Stop |

Action mode left attack resolves the enemy at `CameraGetTarget` with
`gf_ResolveClickEnemy`. When an enemy resolves, it calls `gf_ShowTarget` and
`gf_CombatManualAttack`. When no enemy resolves, nothing changes.

Action mode does not call `gf_RightClickExecute`.
Action mode does not issue a right command.

Normal action movement uses the RPG movement path.
It issues a short path-checked native move order.
It calls `UnitSetFacing` toward the movement direction.
Non-aim action A/D turn the hero left or right and walk.
Non-aim action S turns the hero around and walks.
Non-aim action movement does not strafe.
Aim movement uses one camera-relative travel heading per tick.
It uses `c_ANIM_MOVE_TARGET`, `c_ANIM_MOVE_RETARGET`, and
`c_ANIM_MOVE_HEADING` for native path-checked move orders.
Aim S backpedals, A/D strafe, and diagonals preserve both components.
Aim movement never turns the unit toward travel because `SCOBAAimNoTurn`
suppresses native turning.
Aim facing is written independently every 0.05 seconds.
Alt pause stops action movement and facing updates.

The toggle ability handlers update camera mode, cursor state, and button faces.
They do not change combat state, aim cooldown, or cooldown.

## 15. Engine smart click

`gt_GUIEnvironmentSetup_Func` calls:

`UISetCommandAllowed(PlayerGroupAll(), c_uiCommandAllowSmartClick, false);`

This removes the engine right-click order. The custom handler is then the only
source of hero right-click orders. Ability target mode is unchanged.

## 16. Tests

| Scenario | Setup | Action | Assertions |
| --- | --- | --- | --- |
| left clean click | enemy under cursor | left down, left up, no camera motion | target selected |
| left clean click world point | enemy under cursor, no hover event | left down, left up | target resolved from press world point |
| left target persists | selected enemy | hero idle and Stop | target remains selected |
| left drag camera | enemy under cursor | left down, camera yaw change, left up | no target selected |
| right press | hero, enemy | right down | press unit saved, combat state unchanged |
| RPG right clean click | enemy under press | right down, right up, no camera motion | attack order, target selected |
| right drag camera | enemy under press | right down, camera yaw change, right up | no attack order, no state change |
| right ground Walk | RPG Walk | clean right click ground | move order, move target model created |
| right ground RPG Stand | RPG Stand | clean right click ground | stop order, root present, no displacement |
| right stale hover | stale enemy hover, ground press | clean right click ground | move or stop by stance, no attack |
| target kept | selected enemy | clean right click ground | `gv_tARGET` unchanged |
| both forward | none | left down, right down | Move Forward starts |
| both release left | none | both down, left up | Move Forward stops |
| both release right | none | both down, right up | Move Forward stops |
| W plus both | none | W down, both down, both up | Move Forward continues |
| both plus W release | none | both down, W down, W up | Move Forward continues |
| both target | enemy under cursor | both down | no target change |
| smart click | map init | read setup | smart click is disabled |
| aim start | hero | right down | aim active, aim animation plays, FOV is narrower |
| aim camera | hero | right down | shoulder follow offset is active, distance is unchanged |
| aim cursor | enemy at center | right down | native cursor visible, engine hostile color |
| aim neutral | ground at center | right down | native cursor visible, engine neutral color |
| aim release | aim active | right up | aim inactive, idle pose, centered follow, FOV restored, cursor hidden |
| aim scroll | aim active | wheel change, right up | scroll distance survives release |
| aim drag | aim active | right down, camera yaw change, right up | aim exits, no right command |
| aim click | aim active | aim drag then clean right click | no right command |
| aim smooth | hero moving and turning | right hold | no camera origin orbit or snap |
| aim no UI | hero | right down | no dialog or custom crosshair image |
| aim layers | hero | right down | splitbody idle aim group is active |
| aim walk | hero | right down, forward held | splitbody walk group and leg motion are active |
| aim directions | hero | right down, each WASD direction | eight distinct lower clips are selected |
| aim backpedal | hero | right down, S held | reversed backpedal lower clip is active |
| aim twist | hero | right down, lateral/back movement | torso-to-lower twist stays at or below 65 degrees |
| aim attack move | hero | right down, attack, forward held | deferred; no aim attack overlay in this stage |
| aim fixed pose | hero | right down, camera pitch change | upper aim tracks do not loop or restart |
| aim facing rest | hero | right down, camera yaw change | hero facing moves toward camera yaw |
| aim facing move | hero | right down, forward held, camera yaw change | hero facing moves toward camera yaw |
| action idle turn | action mode, idle | camera yaw change | hero facing reaches camera yaw with no upper turn state |
| action A turn | action mode, idle | hold A | hero turns left and walks |
| action D turn | action mode, idle | hold D | hero turns right and walks |
| action S turn | action mode, idle | hold S | hero turns around and walks |
| aim release layers | aim active | right up | aim group clears and baseline idle is restored |
| action default | new hero | read command card | RPG button is shown |
| action toggle | hero | click action toggle | action mode behavior is present |
| action mouse look | action mode | move mouse, no button | camera yaw changes and facing follows |
| action cursor | action mode | read cursor | native cursor is centered |
| action alt | action mode | hold Alt | mouse look pauses and UI cursor is free |
| action alt release | action mode, Alt held | release Alt | mouse look resumes and cursor recenters |
| action aim | action mode | real right hold | aim mode is active and no right command runs |
| action aim distance | action mode | real right hold | scroll distance is unchanged |
| action aim reset | action mode, stale lower state | real right hold | lower state resyncs and no stale clip remains |
| action movement smooth | action mode, forward held | sample position each tick | no zero displacement while moving |
| action to RPG reset | action mode, moving | toggle to RPG | lower idle state is reached and aim is inactive |
| action attack | action mode, enemy at cursor | left click | manual attack is issued |
| action ground | action mode, ground at cursor | left click | no Move or Stop |
| action alt click | action mode, enemy at cursor | hold Alt, left click | no attack, UI click is handled |
| action to RPG | action mode, aim active | click action toggle | RPG behavior is restored, aim exits, FOV is restored |
| RPG right hold | RPG mode | right hold | aim stays inactive and FOV stays unchanged |
| RPG right click ground | RPG mode | clean right click ground | move order runs |
| RPG right drag | RPG mode | right drag | no right command runs |
| toggle icons | RPG and action mode | read button faces | two different custom DDS files |

The map test harness calls the mouse functions with synthetic press and
release data for logic checks. Real input injection covers camera, both-button,
click, hover, and right-hold aim paths.
Aim tests read `gv_aIMACTIVE`, `CameraGetTarget`, `CameraGetDistance`,
animation layer state, hero facing, and screenshots of the native
cursor at screen center.

## 17. Invariants

- Left drag never selects a target.
- Both-button forward never selects a target.
- Right down never changes combat state.
- A right drag never changes combat state.
- One clean right click produces at most one right command.
- The hover unit at press is the primary right-click target only inside its radius.
- A stale hover unit never becomes the click target.
- Ground right clicks never clear the left-click target.
- Hero idle, Stop, and move completion never clear the left-click target.
- RPG Stand ground right click stops and keeps the root.
- RPG Walk ground right click moves and shows the move marker.
- Both-button forward ends when either button is released.
- The W key and both-button forward share one forward loop.
- Right and middle camera behavior use the same state and calls.
- Engine smart click is disabled for all players.
- In action mode, aim mode starts on right press and ends on right release.
- RPG right press never enters aim mode.
- Aim mode never writes the scroll camera distance.
- Aim mode never changes combat state.
- Aim mode holds one fixed upper pose from the Attack start key.
- Aim mode keeps lower-body locomotion in one splitbody group while the upper body aims.
- Aim lower direction comes from camera-relative movement across eight directions.
- Aim S backpedals, A/D strafe, and diagonals preserve both components.
- Aim backward movement uses reversed backpedal animation.
- Aim torso-to-lower twist stays at or below 65 degrees in either strafe direction.
- Aim unit facing stays on camera yaw while moving.
- Action mode writes facing targets from camera yaw only when idle.
- Non-aim action movement turns the hero toward the movement direction.
- Non-aim action A/D turns left or right and walks.
- Non-aim action S turns around and walks.
- Non-aim action movement does not strafe.
- Action mode uses engine turn duration and native baseline turn clips.
- Action mode creates no upper turn overlay.
- Aim mode moves with one camera-relative travel heading per tick and no turn deadband.
- Aim mode uses the native selection cursor and keeps engine hover colors.
- Aim mode never uses camera bounds.
- Aim mode never writes camera values on a periodic timer.
- Aim release restores centered follow and the non-aim field of view.
- RPG mode is the default on map init and hero spawn.
- Switching to RPG restores the non-aim field of view and centered follow.
- RPG and action mode use distinct custom toggle icons.
- Control mode state lives only in `SCOBAActionModeBehavior`.
- Control mode changes reset animation state and clear pending press state.
- Action mode keeps mouse look active without a held button.
- Action mode keeps the native cursor centered.
- Action mode turns hero facing from camera yaw when idle.
- Action mode keeps the current follow camera and scroll distance.
- Action mode right hold applies aim camera and release restores action camera.
- Normal action movement uses the RPG move-and-turn path.
- Aim movement uses one camera-relative travel heading per tick.
- Aim movement uses path-checked native move orders and the move target constants.
- Aim adds `SCOBAAimNoTurn` (`SuppressTurning`) on entry and removes it on exit.
- Tosh and Kerrigan use high turning rates so aim facing does not lag.
- Alt pauses action mode mouse look and shows a free UI cursor.
- Action mode right hold aims and never runs the right command.
- Action mode left click attacks the hostile under the cursor.
- Action mode left click on ground changes no order.
- Alt left click does not attack.

## 18. Open validation points

- Confirm in-game feel of left orbit and right/middle character turn.
- Confirm both-button forward steering matches W steering.
- Confirm ability target mode still works with smart click disabled.
- Confirm the shoulder offset direction places the weapon shoulder on screen.
- Confirm Firebat baseline animation plays on its shipped model.
- Confirm generated splitbody aim groups play on Tosh and Kerrigan.
- Confirm action A/D/S turn-to-move feels like RPG mode.
- Confirm action idle turning feels smooth at `c_ANIM_TURN_DURATION`.
- Confirm aim movement is smooth with native orders and keeps camera facing.
- Confirm aim facing rotation keeps up with camera rotation.
- Confirm the native cursor is visible while mouse-relative mode is active.
- Confirm offset unit follow keeps the shoulder view without camera orbit.
- Confirm Alt reaches the map while action mode mouse look is active.
- Confirm the UI cursor can click command card buttons while Alt is held.
- Confirm action mode left click hits the unit under the centered cursor.
- Confirm left and right click world points match the visible cursor in RPG mode.
- Confirm control mode toggle faces and names match the current mode.
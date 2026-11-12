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
  command, and Unit Target resolution.
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
| `gv_mOUSELEFTCANCEL` | `bool[8]` | Left target click is cancelled |
| `gv_mOUSELEFTPRESSXUI` | `int[8]` | Left press UI X |
| `gv_mOUSELEFTPRESSYUI` | `int[8]` | Left press UI Y |
| `gv_mOUSELEFTPRESSX` | `fixed[8]` | Left press world X |
| `gv_mOUSELEFTPRESSY` | `fixed[8]` | Left press world Y |
| `gv_mOUSERIGHTPRESSX` | `fixed[8]` | Right press world X |
| `gv_mOUSERIGHTPRESSY` | `fixed[8]` | Right press world Y |
| `gv_unitClickCandidate` | `unit[8]` | Unit from the native `UnitClick` event for that player |
| `gv_unitHighlight` | `unit[8]` | Current Unit Highlight for that player |
| `gv_unitPressHighlight` | `unit[8]` | Unit Highlight snapshotted at left press |
| `gv_unitRightPressHighlight` | `unit[8]` | Unit Highlight snapshotted at right press |
| `gv_unitTarget` | `unit[8]` | Current Unit Target for the boss bar |
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
| `c_SCOBA_CLICK_DRAG_ANGLE` | 2.0 | Click versus drag camera-angle threshold in degrees |
| `c_SCOBA_CLICK_SCAN_RADIUS` | 8.0 | Point pick search radius |
| `c_SCOBA_CLICK_MARGIN` | 0.75 | Point pick radius margin |
| `c_SCOBA_AIM_FOV` | 45.0 | Field of view while aiming |
| `c_SCOBA_AIM_SHOULDER_OFFSET` | 2.0 | Camera focus offset to the weapon shoulder |
| `c_SCOBA_AIM_SHOULDER_ANGLE` | -90.0 | Shoulder origin offset from hero heading, left of center |
| `c_SCOBA_ZOOM_BLEND` | 0.18 | Scroll zoom distance blend duration |
| `c_SCOBA_COLLISION_CLAMP_BLEND` | 0.06 | Collision shorten blend duration |
| `c_SCOBA_COLLISION_RESTORE_BLEND` | 0.28 | Collision restore blend duration |
| `c_ANIM_TURN_DURATION` | 0.1 | Engine facing interpolation duration |
| `c_ANIM_TURN_DEADBAND` | 3.0 | Non-aim yaw change that writes a new facing target |
| `c_ANIM_MOVE_TARGET` | 30.0 | Continuous move order target distance |
| `c_ANIM_MOVE_RETARGET` | 2.0 | Remaining distance that refreshes the target |
| `c_ANIM_MOVE_HEADING` | 12.0 | Heading change that refreshes the target |
| `c_ANIM_MOVE_TICK` | 0.015 | Aim movement loop interval |
| `c_ANIM_AIM_TURN_DURATION` | 0.03 | Aim facing interpolation duration |
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
| Left mouse up | `gt_TargetRelease` | Clear left state; stop both-button forward; set target on clean release |
| Right mouse down | `gt_TargetClick` | Set right state; snapshot press; cancel on both-button |
| Right mouse up | `gt_TargetRelease` | Clear right state; run clean-click command; stop both-button forward |
| Unit clicked | `gt_UnitClick[player]` | Store the click candidate for the hard-coded player; engine-select the hero |
| Unit highlighted | `gt_UnitHighlightOn[player]` | Store the Unit Highlight for the hard-coded player |
| Unit unhighlighted | `gt_UnitHighlightOff[player]` | Clear the matching Unit Highlight for the hard-coded player |
| Unit engine-selected | `gt_HeroReselect[player]` | Immediate hero engine reselect for the hard-coded player |
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
6. Set `gv_mOUSERIGHTCANCEL[player] = true` when the right button is held.

On left-button up:

1. Set `gv_mOUSELEFT[player] = false`.
2. Stop both-button forward.
3. Compute camera yaw and pitch change from the press point.
4. Set drag when the yaw or pitch change is at least `c_SCOBA_CLICK_DRAG_ANGLE`.
5. When the click is clean and not cancelled:
   - exit order mode;
   - read `gv_unitClickCandidate[player]`, then the press-time Unit Highlight, then press-point geometry;
   - when one is valid, set `gv_unitTarget` to it;
   - when none is valid, clear `gv_unitTarget`;
   - clear both candidates;
   - do not change native unit selection;
   - reselect the hero.
6. Clear `gv_mOUSELEFTCANCEL[player]`.

`gt_UnitClick[player]` stores `EventUnit()` and immediately engine-selects the hero.
The Unit Target candidate order is `UnitClick`, then the press-time Unit
Highlight, then press-point geometry.

The left-click target remains active after hero idle, Stop, and move-order
completion. It changes only on replacement, ground left click, death, removal,
or an explicit clear.

Camera orbit starts in `gt_CursorStart` after press state is saved. Left
orbit changes the camera only. It does not change character heading.

In action mode, camera look is already active. Left click does not start orbit.
A clean left click resolves a hostile under the cursor and
calls `gf_CombatManualAttack`. It does not run the RPG left target path.
While Alt is held, the click goes to the UI and no game action runs.

## 6A. Selection and order button

The hero remains natively selected outside order mode.
The hero reselect poll restores hero selection every 0.1 s as a final safety net.
A left click on a unit or building only sets `gv_unitTarget`.
It does not call `UnitClearSelection` or `UnitSelect` on the clicked unit.
A left click on ground only clears `gv_unitTarget`.
The left-click path immediately reselects the hero.
Ctrl+C cancels order mode. It does not clear native selection.
Every unit type clears `FlagArray[Unclickable]` and
`FlagArray[Unhighlightable]`.
Every unit and building stays `Selectable=true` so the engine can emit
`UnitHighlight`, `UnitClick`, and the custom `PreSelection` ring.
A selected non-hero unit triggers an immediate per-player hero reselect outside
order mode. The reselect does not wait for the 0.1 s poll.

`UnitClick` and `UnitSelected` are unit events. `EventPlayer()` can return the
unit owner, not the clicking player. The implementation MUST register both
events separately for players 1 through 6. Each callback MUST hard-code its
player and MUST NOT read `EventPlayer()`.

`gf_UnitTargetSet`:

1. Update the target info panel and boss bar.
2. Show the Order button only when the target is valid and owned by the player.
3. Hide the Order button for hostile and neutral targets.
4. Leave native selection unchanged.
5. Never set any unit `Selectable=false`.

`gf_OrderEnter` is the only path that changes native selection to a
non-hero unit:

1. Require a valid owned target.
2. Clear native selection.
3. Select the order unit.
4. Set order mode and store the order unit.
5. Toggle the Order button on.

`gf_OrderExit`:

1. Clear order mode, order unit, and manual order.
2. Clear native selection.
3. Toggle the Order button off.
4. Never set the target `Selectable=false`.
5. Let the hero reselect poll restore hero selection.

## 7. Right press

On right-button down:

1. Read player.
2. Stop when the player is not a hero player.
3. Set `gv_mOUSERIGHT[player] = true`.
4. Save `EventMouseClickedPosXUI`, `EventMouseClickedPosYUI`,
   `EventMouseClickedPosXWorld`, and `EventMouseClickedPosYWorld` as
   `gv_mOUSERIGHTPRESSX` and `gv_mOUSERIGHTPRESSY`.
5. Save `CameraGetYaw` and `CameraGetPitch`.
6. Set `gv_mOUSERIGHTCANCEL[player] = false`.
7. If `gv_mOUSELEFT[player]` is true, set the cancel flag and start
   both-button forward.
8. Return without changing combat state.

Camera turn starts in `gt_CursorStart` after press state is saved.

In action mode, right down enters aim mode.
The release exits aim and runs no right command.

## 8. Right release

On right-button up:

1. Read player.
2. Set `gv_mOUSERIGHT[player] = false`.
3. Stop both-button forward when the both-button hold has ended.
4. Read release camera yaw and pitch.
5. Compute the absolute yaw and pitch change from the press point.
6. Set drag when either change is at least `c_SCOBA_CLICK_DRAG_ANGLE`.
7. Return when the cancel flag is set.
8. Return when drag is set.
9. When `gv_unitClickCandidate[player]` is valid, run the right command with it.
10. When it is not valid, run the ground command.

In RPG mode, camera turn stops in `gt_CursorEnd` after the command decision.

In action mode, right up exits aim mode and returns before
`gf_RightClickExecute`. No right command runs.

## 9. Click resolver

RPG left, right, and order clicks resolve one Unit Target candidate.

1. Clear the old candidate on every press.
2. Register `TriggerAddEventUnitClick` and Unit Highlight separately for players
   1 through 6. Each callback hard-codes its player.
3. Use the press-time Unit Highlight as the second candidate.
4. Use `gf_UnitTargetAtPoint` at the press point as the final candidate.
5. Reject invalid, dead, hidden, missile, and hero units through
   `gf_UnitTargetValid`. Right and order clicks additionally require a hostile
   unit.
6. Consume and clear both candidates on clean release.

`gf_UnitTargetAtPoint(int lp_player, point lp_point, bool lp_enemyOnly)` also
serves action-mode screen-center attacks and engine-independent test paths.

1. Build one group from `UnitGroup(null, c_playerAny, RegionCircle(...))`.
2. Reject missiles, dead units, hidden units, invalid units, and the hero.
3. When `lp_enemyOnly` is true, reject non-hostile units.
4. Reject units outside `unit radius + c_SCOBA_CLICK_MARGIN`.
5. Return the closest valid unit or building.
6. Return null when none match.

Call sites:

- RPG left target: `UnitClick`, press-time Unit Highlight, then press-point geometry.
- RPG right attack: `UnitClick`, right-press Unit Highlight, then press-point geometry.
- Order-mode right attack: the same three-step candidate order.
- Action-mode left attack: `gf_UnitTargetAtPoint(player, CameraGetTarget(player), true)`.

Engine Unit Highlight drives hover rings and supplies the press-time Unit Target
candidate. It never supplies an ability target.

RPG click resolution never changes native selection.

## 10. Right command execution

`gf_RightClickExecute(int lp_player, point lp_point, unit lp_pressUnit)`:

1. Set `lp_unit = lp_pressUnit`.
2. When `lp_unit` is valid:
   - call `gf_UnitTargetSet(lp_player, lp_unit)`;
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
8. Do not change `gv_unitTarget[lp_player]`.
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

## 12A. Camera collision

Camera collision owns only `c_cameraValueDistance`.

It never writes camera pitch, camera yaw, camera target, or the camera data
object.

1. Read the camera target, yaw, pitch, and current distance.
2. Normalize wrapped pitch above 180 degrees for collision math only.
3. Compute the desired eye from the target, yaw, pitch, and desired distance.
4. Sweep from the target to the desired eye.
5. Use a probe radius that covers the camera near plane.
6. Ignore obstacles closer than the minimum pivot distance of `0.8`.
7. Sample terrain height along the sweep.
8. Use the camera target height plus the authored height offset, raised to terrain height when lower.
9. Find the earliest blocked fraction.
10. Safe distance is `max(minDistance, hitDistance - probeRadius)`.
11. Keep `gv_cameraDistanceDesired` owned by scroll input.
12. Apply a shorter distance with `c_SCOBA_COLLISION_CLAMP_BLEND`.
13. Restore the desired distance slowly with `c_SCOBA_COLLISION_RESTORE_BLEND`.
14. Never infer desired distance from a collision-shortened distance.
15. Apply the clamp on every collision tick, including while pitch or yaw is changing.

Collision runs on a 0.02 s periodic tick. Do not write distance from a camera
move event; that can recurse and bounce.

Scroll input recomputes the safe distance on every wheel event and writes
`min(desired, safe)` with `c_SCOBA_ZOOM_BLEND`.

## 13. Camera events

`gt_CursorStart` sets turn state for right and middle buttons. It sets camera
orbit state for the left button. It then applies mouse-relative camera control
when any camera button is active.

Screen-edge scrolling is disabled in `Base.SC2Data/GameData/CameraData.xml`.
`CCamera id="Dflt"` sets `BorderSizeX=0`, `BorderSizeY=0`,
`MaxScrollRate Follow=0`, `MaxScrollDistance Follow=0`, and
`FollowScrollLimit=0`.
This blocks screen-edge scrolling while native camera follow stays smooth.
Do not use camera input lock toggles for edge scrolling.

`gt_CameraTurnTick` turns the character to the camera yaw in RPG mode while a
right or middle button is held. It does nothing for left-button orbit and does
nothing in action mode.

`gt_CursorEnd` clears state for the released button. It keeps mouse-relative
camera control active while any camera button remains held. It restores free
cursor visibility when all camera buttons are released. It never enables
camera input lock in RPG idle.

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
10. Compute the proxy point on the ground plane at twice the shoulder offset:
    `x = heroX + cos(yaw + c_SCOBA_AIM_SHOULDER_ANGLE) * c_SCOBA_AIM_SHOULDER_OFFSET * 2`,
    `y = heroY + sin(yaw + c_SCOBA_AIM_SHOULDER_ANGLE) * c_SCOBA_AIM_SHOULDER_OFFSET * 2`.
11. Create one hidden `InvisibleTargetDummy` at that point.
12. Follow the unit group containing the hero and the proxy.
13. Move the proxy each 0.02 s. Engine follow tracks the group center, which sits at the shoulder offset.
14. The engine `TargetSmooth` path smooths the camera. Do not pan on top of follow.
15. Show the native cursor with `UISetCursorVisible`.
16. Do not write `c_cameraValueDistance`.

`gf_AimEnd`:

1. Return when aim mode is not active.
2. Clear the aim movement state.
3. Set hero facing to camera yaw.
4. Remove `SCOBAAimNoTurn`.
5. Set `gv_aIMACTIVE[player] = false`.
6. Clear the aim group and restore baseline animation.
7. Send `AnimBlendTimeRemove` to the main actor and model.
8. Set `SCOBAUp` time scale back to `1.0` on the main actor and model.
9. Set the field of view to `gv_cAMERAFOV[player]` once.
10. Remove the proxy unit and follow the hero alone.
11. Hide the native cursor.
12. Restore the mouse-relative cursor pin for the next camera hold.
13. Do not write `c_cameraValueDistance`.

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

The aim cursor is a screen-center image overlay drawn with the native
StarCraft II cursor textures `storm_ui_cursor_default_base.dds`,
`storm_ui_cursor_default_enemy.dds`, and
`storm_ui_cursor_default_friendly.dds`. `gt_AimCursorTick` runs every 0.01 s,
resolves the unit at `CameraGetTarget`, and shows the matching image. The
reticle is visible in action and aim mode and hidden in RPG mode or while Alt
shows the free UI cursor. The engine cursor stays hidden.

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
5. Clear left, right, and middle button state.
6. Call `gf_AnimReset(player)`.
7. Call `gf_ControlApply(player)`.

`gf_ControlApply(player)` is the only writer of cursor and camera-input state.
It derives state from control mode, aim state, Alt state, and held buttons:

1. Return when the hero is invalid.
2. Set `gv_rOTATEUNIT` from held right or middle buttons.
3. Set `gv_rOTATECAMERA` from the held left button.
4. In action mode, enable relative mouse unless Alt is held.
5. In RPG mode, enable relative mouse only while a mouse button is held.
6. Force relative mouse while aim is active.
7. Set `gv_cONTROLRELATIVE` to the derived value.
8. Call `CameraSetMouseRotates` and `CameraForceMouseRelative` from that value.
9. Make the cursor visible with auto-hide disabled.
10. Never call `CameraLockInput(true)` in RPG idle.

Mouse press and release handlers in `camera.galaxy` own the held button state.
They update that state and call `gf_ControlApply`.
Targeting handlers read held state and never write it.
No trigger-order dependency is allowed.

Unit Highlight uses the per-player engine highlight events.
Each `gt_UnitHighlightOn[player]` handler stores `EventUnit()` under its
hard-coded player.
Each `gt_UnitHighlightOff[player]` handler clears the matching Unit Highlight
under its hard-coded player.
No custom mouse-position raycast writes hover.

RPG click points record `EventMouseClickedPosXWorld` and
`EventMouseClickedPosYWorld` for ground commands and drag checks.
RPG Unit Targets come from the native per-player `UnitClick` event, then the press-time Unit Highlight, then press-point geometry.

At map init and on control-mode changes, call `gf_ControlApply`.

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
2. Call `gf_ControlApply(player)`.
3. Stop the action mode facing writer.

Alt up in action mode:

1. Set `gv_actionAlt[player] = false`.
2. Call `gf_ControlApply(player)`.

Alt events are ignored in RPG mode.

Action mode mouse input:

| Input | Result |
| --- | --- |
| Right down | Call `gf_AimBegin` and set action aim state |
| Right up | Call `gf_AimEnd` |
| Left down, Alt not held | Set action press state |
| Left up, Alt not held | Resolve `CameraGetTarget` and call `gf_CombatManualAttack` |
| Any click, Alt held | UI handles the click; no game attack, aim, or order |
| Right clean click | No right command |
| Ground left click | No Move or Stop |

Action mode left attack resolves the hostile at `CameraGetTarget`.
When the centered target is hostile, it calls `gf_UnitTargetSet` and
`gf_CombatManualAttack`. When no hostile centered target exists, nothing
changes.

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
| left clean click | enemy under cursor | left down, left up, no camera motion | Unit Target set from the candidate order, hero still engine-selected |
| left click no flash | owned unit under cursor | left down, left up | unit is not selected past the event tick |
| ground click after unit click | unit clicked, then ground clicked | two clean clicks | ground click clears target and does not reuse stale unit |
| left owned building | owned building under cursor | left down, left up | target set, Order button visible, hero still selected |
| left ground | ground under cursor | left down, left up | target cleared, hero still selected |
| left target persists | selected enemy | hero idle and Stop | target remains set |
| left drag camera | enemy under cursor | left down, camera yaw change, left up | no target set |
| selectability | mixed units and buildings | map init | every unit and building is selectable, `PreSelection` ring available |
| hover ring | selectable unit under cursor | native highlight fires | `PreSelection` ring is shown |
| order button hostile | hostile target | read Order button | button hidden |
| order button owned | owned target | read Order button | button visible |
| order entry | owned target | press Order button | order unit selected, hero not selected |
| order exit | order mode active | cancel order | order unit deselected, hero reselected |
| clear selection key | no order mode | Ctrl+C | no selection change |
| right press | hero, enemy | right down | press point saved, combat state unchanged |
| RPG right clean click | enemy under press | right down, right up, no camera motion | attack order, target set |
| right drag camera | enemy under press | right down, camera yaw change, right up | no attack order, no state change |
| right ground Walk | RPG Walk | clean right click ground | move order, move target model created |
| right ground RPG Stand | RPG Stand | clean right click ground | stop order, root present, no displacement |
| right ground outside radius | enemy hover, ground press | clean right click ground | move or stop by stance, no attack |
| target kept | target enemy | clean right click ground | `gv_unitTarget` unchanged |
| both forward | none | left down, right down | Move Forward starts |
| both release left | none | both down, left up | Move Forward stops |
| both release right | none | both down, right up | Move Forward stops |
| W plus both | none | W down, both down, both up | Move Forward continues |
| both plus W release | none | both down, W down, W up | Move Forward continues |
| both target | enemy under cursor | both down | no target change |
| smart click | map init | read setup | smart click is disabled |
| aim start | hero | right down | aim active, aim animation plays, FOV is narrower |
| aim camera | hero | right down | shoulder follow offset is active, distance is unchanged |
| aim cursor | enemy at center | right down | enemy cursor image visible at screen center |
| aim neutral | ground at center | right down | base cursor image visible at screen center |
| aim release | aim active | right up | aim inactive, idle pose, centered follow, FOV restored, cursor hidden |
| aim scroll | aim active | wheel change, right up | scroll distance survives release |
| aim drag | aim active | right down, camera yaw change, right up | aim exits, no right command |
| aim click | aim active | aim drag then clean right click | no right command |
| aim smooth | hero moving and turning | right hold | no camera origin orbit or snap |
| aim no UI | hero | right down | reticle uses native cursor textures, no button icon |
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
| action cursor | action mode | read cursor | screen-center reticle is visible |
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
| edge scroll | RPG idle | move cursor to each screen edge | camera does not move, follow stays smooth |
| toggle icons | RPG and action mode | read button faces | two different custom DDS files |
| control state RPG rest | RPG mode, no buttons | read `gv_cONTROLRELATIVE` | relative off, cursor free, camera input lock off |
| control state RPG right | RPG mode, right held | read `gv_cONTROLRELATIVE` | relative on, unit rotate on |
| control state RPG release | RPG mode, right released | read `gv_cONTROLRELATIVE` | relative off, rotate off |
| control state action | action mode | read `gv_cONTROLRELATIVE` | relative on, cursor centered |
| control state alt | action mode, Alt held | read `gv_cONTROLRELATIVE` | relative off, cursor free |
| control state aim | action mode, aim active | read `gv_cONTROLRELATIVE` | relative on |
| hover highlight | enemy under cursor | native highlight fires | `gv_unitHighlight` is the enemy |
| hover clear | pointer leaves enemy | native unhighlight fires | matching hover is cleared |
| click player | enemy owned by another player | left click | Unit Target resolves for the clicking hero player |
| right click enemy | enemy owned by another player | right click | attack issued without changing native selection |

The map test harness calls the mouse functions with synthetic press and
release data for logic checks. Real input injection covers camera, both-button,
click, and right-hold aim paths.
Synthetic pointer warps do not emit engine highlight events, so hover is
verified in live play.
Aim tests read `gv_aIMACTIVE`, `CameraGetTarget`, `CameraGetDistance`,
animation layer state, hero facing, and screenshots of the screen-center
reticle.

## 17. Invariants

- Left drag never sets a target.
- Both-button forward never sets a target.
- A left click sets or clears the target only; it never changes native selection.
- The hero stays natively selected outside order mode.
- Ctrl+C cancels order mode and never clears native selection.
- The Order button is the only path that changes native selection to a non-hero unit.
- Order exit or cancel restores hero selection.
- Every unit and building stays selectable so `PreSelection` hover rings work.
- A selected non-hero unit triggers an immediate hero reselect outside order mode.
- Target changes and order exit never set `Selectable=false`.
- The Order button is visible only for a valid owned target.
- Right down never changes combat state.
- A right drag never changes combat state.
- One clean right click produces at most one right command.
- RPG left, right, and order clicks use `UnitClick`, then press-time Unit Highlight, then press-point geometry.
- `EventPlayer` never determines the RPG clicking player.
- A new press clears the old Unit Target candidate; a clean release consumes it.
- A left click never leaves a non-hero unit natively selected past the event tick.
- Action-mode attacks use `gf_UnitTargetAtPoint` at the camera target.
- Engine Unit Highlight may become the press-time Unit Target candidate; ability targeting never uses it.
- Ground right clicks never clear the left-click target.
- Hero idle, Stop, and move completion never clear the left-click target.
- RPG Stand ground right click stops and keeps the root.
- RPG Walk ground right click moves and shows the move marker.
- Both-button forward ends when either button is released.
- The W key and both-button forward share one forward loop.
- Right and middle camera behavior use the same state and calls.
- Only `gf_ControlApply` writes camera mouse-rotate, mouse-relative, and cursor visibility state.
- `gf_ControlApply` never enables camera input lock in RPG idle.
- Held button state is owned by mouse press/release handlers.
- Targeting never writes held button state.
- Cursor mode never depends on trigger execution order.
- Releasing a button always restores the derived cursor mode.
- `gv_unitHighlight` is written only by the per-player engine highlight handlers.
- Engine highlight hide clears only the matching Unit Highlight.
- RPG Unit Targets use per-player `UnitClick`, then press-time Unit Highlight, then press-point geometry.
- Click press points still come from engine mouse-click world coordinates for ground commands and drag checks.
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
- Aim mode uses the screen-center reticle and keeps engine hover colors.
- Aim mode never uses camera bounds.
- Aim mode never writes camera values on a periodic timer.
- Aim release restores centered follow and the non-aim field of view.
- RPG mode is the default on map init and hero spawn.
- Switching to RPG restores the non-aim field of view and centered follow.
- RPG and action mode use distinct custom toggle icons.
- Control mode state lives only in `SCOBAActionModeBehavior`.
- Control mode changes reset animation state and clear pending press state.
- Action mode keeps mouse look active without a held button.
- Action mode keeps the screen-center reticle visible.
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
- Confirm the screen-center reticle is visible while mouse-relative mode is active.
- Confirm offset unit follow keeps the shoulder view without camera orbit.
- Confirm Alt reaches the map while action mode mouse look is active.
- Confirm the UI cursor can click command card buttons while Alt is held.
- Confirm action mode left click hits the unit under the centered cursor.
- Confirm left and right clicks target the unit under the visible cursor in RPG mode.
- Confirm hover rings render on every selectable unit and building.
- Confirm left click sets the target and does not leave the clicked unit selected.
- Confirm Ctrl+C does not clear hero selection.
- Confirm the Order button appears only for owned targets and restores hero selection on exit.
- Confirm control mode toggle faces and names match the current mode.
# SPEC-MOUSE-CONTROLS: Mouse Controls

**Date:** 2026-11-09
**Status:** Active implementation specification
**Requirements:** [REQ-MOUSE-CONTROLS](../requirements/REQ-MOUSE-CONTROLS.md)

## 1. Purpose

This document specifies mouse look, right-click commands, and both-button
movement. It also specifies the event order that prevents right-click state
races.

## 2. Module layout

- `systems/camera.galaxy`: camera and character turn state.
- `systems/targeting.galaxy`: mouse press, release, drag detection, right
  command, and left selection.
- `systems/movement.galaxy`: forward movement loop and both-button alias.
- `systems/gui_environment.galaxy`: engine smart-click suppression.
- `core/globals.galaxy`: mouse state globals.
- `core/constants.galaxy`: drag, radius, and scan constants.

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
| `gv_mOUSEPRESSYAW` | `fixed[8]` | Camera yaw at press |
| `gv_mOUSEPRESSPITCH` | `fixed[8]` | Camera pitch at press |
| `gv_sCOBAPRESSUNIT` | `unit[8]` | Hover unit at right press |
| `gv_sCOBALEFTPRESSUNIT` | `unit[8]` | Hover unit at left press |
| `gv_mOUSELEFTCANCEL` | `bool[8]` | Left selection is cancelled |
| `gv_mOUSELEFTPRESSXUI` | `int[8]` | Left press UI X |
| `gv_mOUSELEFTPRESSYUI` | `int[8]` | Left press UI Y |

## 4. Constants

| Constant | Value | Purpose |
| --- | --- | --- |
| `c_SCOBA_CLICK_DRAG_PIXELS` | 4 | WoW-style click versus drag threshold |
| `c_SCOBA_DRAG_DEGREES` | 5.0 | Camera drag threshold |
| `c_SCOBA_CLICK_SCAN_RADIUS` | 8.0 | Point pick search radius |
| `c_SCOBA_CLICK_MARGIN` | 0.75 | Point pick radius margin |

Flat point distance is never the primary target source.

## 5. Event registration

| Event | Trigger | Action |
| --- | --- | --- |
| Left mouse down | `gt_TargetClick` | Set left state; save press point; cancel on both-button |
| Left mouse up | `gt_TargetRelease` | Clear left state; stop both-button forward; select on clean release |
| Right mouse down | `gt_TargetClick` | Set right state; snapshot press; cancel on both-button |
| Right mouse up | `gt_TargetClick` | Clear right state; run clean-click command; stop both-button forward |
| Right mouse down | `gt_CursorStart` | Start camera turn |
| Right mouse up | `gt_CursorEnd` | Stop camera turn |
| Middle mouse down | `gt_CursorStart` | Start camera turn |
| Middle mouse up | `gt_CursorEnd` | Stop camera turn |
| Left mouse down | `gt_CursorStart` | Start camera orbit |
| Left mouse up | `gt_CursorEnd` | Stop camera orbit |

`gt_TargetClick` is registered before `gt_CursorStart`. Press state is saved
before camera state changes.

## 6. Left press and release

On left-button down:

1. Set `gv_mOUSELEFT[player] = true`.
2. Set `gv_mOUSELEFTCANCEL[player]` to the current right-button state.
3. Save `EventMouseClickedPosXUI` and `EventMouseClickedPosYUI`.
4. Save `gv_sCOBAHover[player]` as `gv_sCOBALEFTPRESSUNIT[player]`.
5. Set `gv_mOUSERIGHTCANCEL[player] = true` when the right button is held.

On left-button up:

1. Set `gv_mOUSELEFT[player] = false`.
2. Stop both-button forward.
3. Compute the UI drag distance from the left press point.
4. When the click is clean and not cancelled:
   - exit order mode;
   - select `gv_sCOBALEFTPRESSUNIT[player]`.
5. Clear `gv_mOUSELEFTCANCEL[player]`.

## 7. Right press

On right-button down:

1. Read player.
2. Stop when the player is not a hero player.
3. Set `gv_mOUSERIGHT[player] = true`.
4. Save `EventMouseClickedPosXUI`, `EventMouseClickedPosYUI`,
   `EventMouseClickedPosXWorld`, and `EventMouseClickedPosYWorld`.
5. Save `CameraGetYaw` and `CameraGetPitch`.
6. Save `gv_sCOBAHover[player]` as `gv_sCOBAPRESSUNIT[player]`.
7. Set `gv_mOUSERIGHTCANCEL[player] = false`.
8. If `gv_mOUSELEFT[player]` is true, set the cancel flag and start
   both-button forward.
9. Return without changing combat state.

Camera turn starts in `gt_CursorStart` after press state is saved.

## 8. Right release

On right-button up:

1. Read player.
2. Set `gv_mOUSERIGHT[player] = false`.
3. Stop both-button forward when the both-button hold has ended.
4. Read release UI position.
5. Compute `dx` and `dy` from the press UI position.
6. Set drag when `dx * dx + dy * dy` is at least
   `c_SCOBA_CLICK_DRAG_PIXELS * c_SCOBA_CLICK_DRAG_PIXELS`.
7. Compute yaw and pitch change from the press camera values.
8. Set drag when either camera angle changed by at least
   `c_SCOBA_DRAG_DEGREES`.
9. Return when the cancel flag is set.
10. Return when drag is set.
11. Run `gf_RightClickExecute` with the saved press point and saved hover unit.

Camera turn stops in `gt_CursorEnd` after the command decision.

## 9. Right command resolver

`gf_ResolveClickEnemy(int lp_player, point lp_point)`:

1. Return `gv_sCOBAPRESSUNIT[lp_player]` when it is alive and hostile.
2. Return `gv_tARGET[lp_player]` when it is alive and hostile and
   `lp_point` is inside its unit radius.
3. Search enemies inside `c_SCOBA_CLICK_SCAN_RADIUS` around `lp_point`.
4. Return the closest enemy whose distance from `lp_point` is no more than
   `UnitGetPropertyFixed(unit, c_unitPropRadius, c_unitPropNormal)` plus
   `c_SCOBA_CLICK_MARGIN`.
5. Return null.

Step 1 is the engine hit-test source used by left-click selection.
Step 3 is the last check and MUST NOT override a valid hover unit.

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
6. When Stand is active:
   - issue `Order(AbilityCommand("stop", 0))`;
   - set `gv_sCOBAFSM[lp_player]` to `c_SCOBA_FSM_IDLE`.
7. Otherwise:
   - issue `OrderTargetingPoint(AbilityCommand("move", 0), lp_point)`;
   - set `gv_sCOBAFSM[lp_player]` to `c_SCOBA_FSM_MOVING`;
   - call `gf_ShowMoveMarker(lp_player, lp_point)`.
8. Do not change `gv_tARGET[lp_player]`.

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
3. When no movement key is held, set the combat state to idle.

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
when any turn state is active.

`gt_CursorEnd` clears turn state for the released button. It stops
mouse-relative camera control when no turn state remains. It restores cursor
visibility and camera lock.

Right and middle buttons use the same state and the same camera calls.

## 14. Engine smart click

`gt_GUIEnvironmentSetup_Func` calls:

`UISetCommandAllowed(PlayerGroupAll(), c_uiCommandAllowSmartClick, false);`

This removes the engine right-click order. The custom handler is then the only
source of hero right-click orders. Ability target mode is unchanged.

## 15. Tests

| Scenario | Setup | Action | Assertions |
| --- | --- | --- | --- |
| left clean click | enemy under cursor | left down, left up | target selected |
| left drag | enemy under cursor | left down, 6 pixel move, left up | no target selected |
| right press | hero, enemy | right down | press unit saved, combat state unchanged |
| right clean click | enemy under press | right down, right up, no motion | attack order, target selected |
| right drag pixels | enemy under press | right down, 6 pixel move, right up | no attack order, no state change |
| right drag camera | enemy under press | right down, camera yaw change, right up | no attack order |
| right ground Walk | none | clean right click ground | move order, move target model created |
| right ground Stand | none | clean right click ground | stop order, root present |
| target kept | selected enemy | clean right click ground | `gv_tARGET` unchanged |
| both forward | none | left down, right down | Move Forward starts |
| both release left | none | both down, left up | Move Forward stops |
| both release right | none | both down, right up | Move Forward stops |
| W plus both | none | W down, both down, both up | Move Forward continues |
| both plus W release | none | both down, W down, W up | Move Forward continues |
| both target | enemy under cursor | both down | no target change |
| smart click | map init | read setup | smart click is disabled |

The map test harness calls the mouse functions with synthetic press and
release data. Real input injection covers the camera and both-button paths.

## 16. Invariants

- Left drag never selects a target.
- Both-button forward never selects a target.
- Right down never changes combat state.
- A right drag never changes combat state.
- One clean right click produces at most one right command.
- The hover unit at press is the primary right-click target.
- Ground right clicks never clear the left-click target.
- Both-button forward ends when either button is released.
- The W key and both-button forward share one forward loop.
- Right and middle camera behavior use the same state and calls.
- Engine smart click is disabled for all players.

## 17. Open validation points

- Confirm SC2 reports useful UI release positions while camera is
  mouse-relative.
- Confirm camera yaw and pitch deltas catch drags when the cursor is warped.
- Confirm both-button forward steering matches W steering.
- Confirm ability target mode still works with smart click disabled.
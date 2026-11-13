# SPEC-HERO-SWITCH: Controlled Hero Switching

## 1. Overview

Player 1 controls one hero at a time.
Tosh and Kerrigan both exist from map start.
`Alt+1` activates Tosh and `Alt+2` activates Kerrigan.
The inactive hero is parked off-screen, hidden, unselectable, and stopped.

## 2. State

New globals:

- `unit gv_heroTosh` - map Tosh unit.
- `unit gv_heroKerrigan` - map Kerrigan unit.
- `unit gv_heroActive` - hero controlled by player 1.
- `point gv_heroPark` - off-screen parking point.
- `bool gv_heroSwitchReady` - switch enabled after map setup.

Player 1 state stays in `gv_tPSUNIT[1]`.
`gv_tPSUNIT[1]` MUST equal `gv_heroActive`.

## 3. Initialization

After map init selection:

1. Resolve Tosh with `UnitFromId(622754155)`.
2. Resolve Kerrigan with `UnitFromId(649131550)`.
3. Set `gv_heroActive = gv_heroTosh`.
4. Set `gv_heroPark` to a dedicated off-map point.
5. Park Kerrigan.
6. Set `gv_heroSwitchReady = true`.

Map init MUST NOT park Tosh.

## 4. Activation

`gf_HeroSwitchTo(unit lp_target)`:

1. Return if switching is not ready.
2. Return if player 1 is invalid.
3. Return if the target is invalid, dead, or already active.
4. Call `gf_AimEnd(1)`.
5. Call `gf_OrderExit(1)` if order mode is active.
6. Save the old hero position and facing.
7. Clear player 1 selection.
8. Remove `UnitDirectControl` from the old hero.
9. Issue a stop order to the old hero.
10. Call `gf_CombatReset(1)` and `gf_AnimReset(1)`.
11. Park the old hero.
12. Set the target owner to player 1.
13. Move the target to the saved position and facing.
14. Reveal the target and make it selectable and highlightable.
15. Add `UnitDirectControl` to the target.
16. Set `gv_heroActive` and `gv_tPSUNIT[1]`.
17. Reset combat and animation for player 1.
18. Apply custom toggles, control mode, and RPG mode.
19. Apply camera distance for the hero type.
20. Follow the target with the camera.
21. Select only the target.

## 5. Parking

`gf_HeroPark(unit lp_unit)`:

1. Issue a stop order.
2. Clear the selection entry.
3. Set `c_unitStateSelectable` false.
4. Set `c_unitStateHighlightable` false.
5. Set `c_unitStateHidden` true.
6. Move the unit to `gv_heroPark`.

Parking is the paused state for this feature.
A parked hero does not receive direct control and does not participate in player loops.

## 6. Reveal

`gf_HeroReveal(unit lp_unit)`:

1. Set `c_unitStateHidden` false.
2. Set `c_unitStateSelectable` true.
3. Set `c_unitStateHighlightable` true.
4. Set status bar off.

## 7. Selection

`gf_HeroUnit(1)` MUST return `gv_heroActive`.
Other player IDs keep the existing lookup.
`gt_KeepHeroSelected` keeps `gv_tPSUNIT[1]` on the active hero.
The map-init and new-unit selection loops MUST skip a parked hero.

## 8. Input

New trigger module: `systems/hero_switch.galaxy`.

Keys:

- `c_key1` with Alt required -> `gf_HeroSwitchTo(gv_heroTosh)`.
- `c_key2` with Alt required -> `gf_HeroSwitchTo(gv_heroKerrigan)`.

Only player 1 handles the keys.

## 9. Camera

After activation:

- Tosh: `c_cameraValueDistance` 1.5, height offset 0.9.
- Kerrigan: `c_cameraValueDistance` 2.5, height offset 0.9.

Update `gv_cameraDistanceDesired[1]`.
Call `CameraFollowUnitGroup` with the active hero.
Call `gf_ControlApply(1)`.

## 10. Toggles

The active hero MUST have these abilities enabled and shown:

- `SCOBAAutoAttackStatus`
- `SCOBAAutoAttackToggle`
- `SCOBAActionModeToggle`
- `SCOBARightClickToggle`

The active hero MUST receive `SCOBARightClickToggle` and `gf_ActionModeEnsureRPG(1)`.

## 11. Error Handling

Invalid or dead targets are ignored.
A missing parking point uses the map origin.
A failed owner change aborts the switch and leaves the old hero active.

## 12. Tests

1. `Alt+1` activates Tosh.
2. `Alt+2` activates Kerrigan.
3. Repeating the active key is a no-op.
4. Parked hero is hidden and off-screen.
5. Parked hero cannot be selected.
6. Active hero is selected and followed.
7. Switching while aiming exits aim.
8. Switching while in order mode exits order mode.
9. Attack, aim, and movement work on both heroes.
10. No duplicate actor or model appears.
11. Animation reset runs on every switch.
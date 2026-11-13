# Agent Guidelines

> The agent is FORBIDDEN from running tests. The user runs tests and reports feedback. The agent only modifies code.

## Procedural map changes

- Every map modification lives in a persistent, deterministic script under `scripts/`.
- Wire each modification into `scripts/expand_map.py`.
- Scripts must be idempotent and reversible.
- `out/SCOBA256.SC2Map` is rebuilt from `src/SCOBA.SC2Map`; the packed baseline is `original/SCOBA.SC2Map`.
- Provide `--revert` or document the revert command.
- Never hand-edit generated files in `out/` without a script.

## Build and launch

- `scripts/playtest.sh` is the only build, test, launch, and dock-icon entrypoint.
- Never launch `src/SCOBA.SC2Map` for gameplay.
- Never use a pre-existing `out/SCOBA256.SC2Map`.
- All wrappers delegate to `scripts/playtest.sh` unless `SC2_PLAYTEST_ACTIVE=1`.
- The GNOME dock entry must execute `scripts/playtest.sh launch`.

## Test ownership

- The agent does not run tests, builds, or launches.
- The user runs tests and reports feedback.
- The agent only edits source code.
- Test profiles and run artifacts are the user's responsibility.

## Project docs

- Requirements and specifications live in `docs/requirements/` and `docs/specifications/`.
- Audits and remediation plans live in `docs/`.
- Keep docs in sync with code when changing behavior.

## Existing procedural scripts

- `scripts/expand_map.py` - 128→256 upscale pipeline.
- `scripts/doodad_occlusion.py` - disable doodad auto-transparency.
- `scripts/props_expand.py` - tree and fluff scaling.
- `scripts/spore_scale.py` - Spore unit and projectile scaling.
- `scripts/water_splashes.py` - water terrain squibs for ground units.
- `scripts/character_anim_assets.py` - splitbody aim groups and attack clips.
- `scripts/character_anim_m3.py` - M3 clone, freeze, reverse, and splitbody helpers.
- `scripts/animation_tokens.py` - allowed animation tokens and clip name checks.
- `scripts/control_mode_icons.py` - RPG and Action command-card icons.
- `scripts/bootstrap_galaxy.py` - minimal `MapScript.galaxy` bootstrap.
- `scripts/strip_gui_triggers.py` - replace GUI triggers with one empty category.
- `scripts/migrate_galaxy_modules.py` - one-time generator for `scripts/app/`.
- `scripts/terrain/` - one-off inspection tools, not part of the build.

## Command card

- Auto-attack state lives only in `SCOBAAutoAttackBehavior`.
- Chase state lives only in `SCOBARightClickStandBehavior`.
- Read state with `UnitHasBehavior`. Do not add boolean mirrors.
- Do not register toggle handlers with `c_unitAbilStageAll`.

## Combat and movement

- RPG Stand holds position when idle and attacks inside the keep radius. It never chases.
- RPG Stand and Walk attack while a movement key is held. Movement input owns position.
- Tosh, RazorTalons, and QueenOfBladesPsiBlast weapons set `AllowedMovement=Moving`.
- Movement loops own moving shots through one native order. Never issue attack then move.
- The combat tick never issues moving attacks. No pending-shot race.
- Aim entry clears `SCOBAStandRoot`; otherwise walk plays without displacement.
- Aim movement writes camera facing immediately before each move order.
- `gf_AnimFacingTick` skips facing while a movement key is held.
- Aim shots never stop, pause, or restart hero locomotion. No aim shot hold.
- Movement input owns hero position during aim shots.
- RPG Stand ground right click stops and keeps the root.
- RPG Walk ground right click moves and shows the move marker.
- RPG right click never aims. Aim only starts on Action mode right hold.
- Action mode right clean click runs no right command.
- Non-aim lower body uses native Stand, Walk, and turn. Do not drive it with `SCOBALo`.
- Non-aim attack uses the root-excluded upper attack on `SCOBAAimAtk` and target pitch on `SCOBAUp`.
- RPG attack torso pitch follows the hero-to-target vector. Action aim pitch follows the camera.
- Gameplay uses clean unit types `ToshSCOBA` and `KerriganSCOBA`.
- Native `Tosh` and `QueenOfBlades` units and actors stay untouched.

## Aim and animation

- Aim uses one splitbody group per lower state and direction, two concurrent STCs per group.
- The upper STC is frozen at the Attack start keyframe. The lower STC animates Stand or Walk.
- Aim uses eight lower-body directions from the camera-relative travel vector.
- Aim facing and upper body stay locked to camera yaw while moving.
- Aim torso-to-lower twist must not exceed 65 degrees.
- Aim S backpedals, A/D strafe, and diagonals preserve both components.
- Aim must not turn 180 degrees toward travel or show planted-feet twist.
- Aim attack uses the root-excluded upper attack on `SCOBAAimAtk`; aim pitch stays on `SCOBAUp`.
- Aim shots resolve from the crosshair point, not the mouse world point.
- Every aim shot issues a native attack from a hidden aim shooter, never from the hero.
- The aim shooter is pinned to the hero position, faces camera yaw, and carries the hero weapon.
- Targetless shots use one invisible attackable proxy at the crosshair, or at crosshair height for air.
- Shooter cooldown mirrors to the hero weapon cooldown.
- Aim shots are ignored until `UnitWeaponPeriodRemaining` reaches zero.
- Native cooldown, muzzle flash, launch effect, and sound must run for enemy, ground, and air shots.
- Select the attack clip from `EventUnitGetWeapon`: Tosh `Attack Arm Alternate 01`, Kerrigan `RazorTalons` `Attack Arm Alternate 01`, `QueenOfBladesPsiBlast` `Spell Arm Alternate 01`.
- Attack playback starts at `c_ANIM_ATTACK_START_TIME`.
- Attack clips bake a 0.5 s weapon-shoulder kickback at the firing frame.
- Tosh uses `BoneShoulderR`; Kerrigan uses `Box04`. Never write the spine or pitch root.
- Attack clips keep only weapon shoulder chains and the head chain.
- Upper attack STCs set `runsConcurrent=1`; upper priority stays 10. Root-excluded clips use priority 12.
- Clean actors define no `Abil.attack.*`, `WeaponStart.*`, `WeaponStop.*`, or `Abil.attack.ReadyStart` events.
- Do not use stop timers, per-tick stop spam, empty native tracks, or token renaming to fight native attack events.
- Aim uses two concurrent animation instances: `SCOBAUp` for aim pitch and `SCOBALo` for locomotion.
- Aim hold must not loop the attack swing. Non-spine upper tracks hold one key.
- Aim hold produces one upper pitch start event.
- Aim upper pitch follows camera pitch: 80 degrees down and 60 degrees up. The clip sweeps -95..50 with rest -13.
- The aim base pose is the Attack frame at 350 ms.
- Aim pitch pivots the upper body around one lower-back spine bone. Never rotate the lower body or model root.
- Aim pitch uses densely spaced keyframes and the nearest target time from `CameraGetPitch`.
- Galaxy angles are degrees. Normalize wrapped camera pitch above 180 degrees.
- Aim pitch plays `SCOBAUp` on the main actor and sets `AnimSetTime` there.
- On pitch change: unpause `SCOBAUp`, send `AnimSetTime`, then pause.
- Freeze only after the camera-matched frame is applied.
- Never use `AnimSetPaused` on `SCOBALo`.
- `SCOBALo` keeps Stand or Walk playing while the upper is held.
- Aim idle uses `Attack,Stand`; aim turn uses `Attack,Stand,Left` or `Attack,Stand,Right`.
- Keep `c_ANIM_AIM_PITCH_REST` fixed. Never capture the aim-entry pitch as rest.
- Drive pitch updates from `TriggerAddEventCameraMove` and a periodic timer.
- On aim exit, send `AnimBlendTimeRemove`, unpause `SCOBAUp`, and clear it.
- Tosh and Kerrigan `CActorModel` entries set `AnimBlendTime` to 0.
- Aim entry starts at the current camera pitch without blending from idle.
- Aim pitch must not use actor root or whole-model rotation.
- Aim adds `SCOBAAimNoTurn` on entry and removes it on exit.
- Do not disable `Turnable` or permanently zero turning rates.
- Tosh and Kerrigan use high `StationaryTurningRate` and `TurningRate`.
- Turning uses native full-body `Stand Left` and `Stand Right`. No generated turn clips.
- Use `c_ANIM_TURN_DEADBAND` only outside aim.
- Facing changes use `c_ANIM_TURN_DURATION` outside aim and `c_ANIM_AIM_TURN_DURATION` during aim.
- Use one camera-relative travel heading per aim movement tick.
- Use native path-checked aim move orders with `c_ANIM_MOVE_TARGET`, `c_ANIM_MOVE_RETARGET`, and `c_ANIM_MOVE_HEADING`.
- Use `c_ANIM_MOVE_TICK` 0.015 as the aim movement interval.
- Aim entry without a movement key issues Stop and restores native idle.
- Reset animation state on aim entry, control mode change, and hero reassignment.
- Clearing the aim group resets splitbody and upper state in the same call.

## Camera

- Aim shortens the camera arm by `c_SCOBA_AIM_ARM_SCALE`. Exit restores the saved scroll distance.
- Aim camera sits slightly left of hero center. Offset the origin; do not rotate the camera.
- The offset follows a hero plus hidden-proxy group. Never pan on top of follow.
- Camera collision owns only `c_cameraValueDistance`. It never writes pitch or yaw.
- SC2 camera pitch is degrees down from horizontal.
- Scroll zoom animates with `c_SCOBA_ZOOM_BLEND` on every wheel event.
- Collision checks terrain height along the sweep and includes the camera height offset.
- Keep one desired scroll distance. Collision never overwrites it.
- Sweep from camera target to desired eye with a camera radius.
- Ignore obstacles closer than the minimum pivot distance.
- Shorten with `c_SCOBA_COLLISION_CLAMP_BLEND`; restore with `c_SCOBA_COLLISION_RESTORE_BLEND`.
- Collision runs on a 0.02 s tick, including while pitch or yaw changes.
- Screen-edge scroll is disabled: `BorderSizeX=0`, `BorderSizeY=0`, `MaxScrollRate Follow=0`, `MaxScrollDistance Follow=0`, `FollowScrollLimit=0`.

## Mouse, targeting, and selection

- Action and aim use one screen-center crosshair, `cursor-target-none.dds`.
- Neutral is white, hostile red, friendly blue, out-of-range hostile gray.
- Never use `storm_ui_cursor_default_*` arrow cursors.
- `gt_AimCursorTick` resolves `gf_AimCrosshairPoint` every 0.01 s.
- Hide the reticle in RPG mode and while Alt shows the free UI cursor.
- Unit Highlight is the hover ring. Unit Target is the boss-bar target. Unit Select is native selection.
- Action mode shows the crosshair-hovered unit status bar override; clear it when hover leaves.
- RPG clicks resolve Unit Target from `UnitClick`, then press-time Unit Highlight, then press-point geometry.
- Register `UnitClick`, `UnitSelected`, and Unit Highlight separately per hero player.
- Every unit type must clear `FlagArray[Unclickable]` and `FlagArray[Unhighlightable]`.
- Action attacks use `gf_UnitTargetAtPoint` at the camera target.
- Clear the Unit Target candidate on press and consume it on clean release.
- Left click sets or clears the target only. It never changes native selection past the event tick.
- `UnitClick` immediately reselects the hero outside order mode.
- Left click on ground clears the target only. The hero stays selected.
- Ctrl+C cancels order mode. It never clears native selection.
- The Order button is the only path that changes native selection to a non-hero unit.
- The Order button is visible only for a valid owned target.
- Order entry clears selection and selects the order unit. Exit or cancel restores the hero.
- Every unit and building stays selectable so the `PreSelection` hover ring renders.
- Never set any unit `Selectable=false`.
- Aim must not change combat FSM state or issue combat orders.
- `Alt+1` controls Tosh and `Alt+2` controls Kerrigan for player 1.
- The inactive hero is stopped, hidden, unselectable, and parked off-screen.
- Only the active hero is owned by player 1 and has `UnitDirectControl`.
- Switching exits aim and order mode, resets combat and animation, and moves the new hero to the old position and facing.
- `gf_ControlApply` is the only writer of mouse-relative and cursor visibility.
- It never enables camera input lock in RPG idle.
- Mouse press/release handlers own held button state.
- Targeting reads held state only.
- Control mode changes, Alt changes, aim entry/exit, and map init route through `gf_ControlApply`.
- Left-click target persists through idle, Stop, and move completion.
- Reject action-mode clicks outside the unit radius.
- Detect a drag from camera yaw or pitch change, not release UI distance.

## Resource tools

- `tools/stormex` - CASC reader for SC2 name search, list, extract, and regex filters.
- `scripts/sc2res` - project CLI for SC2 resources.
- Overrides: `SC2_PATH` for the install directory, `STORMEX` for the reader binary.
- Default output root: `/mnt/ws-fast/sc2res`.

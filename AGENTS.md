# Agent Guidelines

## Procedural map changes

- Every procedural modification to the map must live in a persistent script in `scripts/`.
- Wire each modification into the build pipeline (`scripts/expand_map.py`) so rebuilding reproduces the map.
- Scripts must be idempotent: running them again on the same target must not double-apply.
- Scripts must be reversible when possible:
  - Preferred: `out/SCOBA256.SC2Map` is derived from `src/SCOBA.SC2Map`; rebuilding reverts everything.
  - The original packed baseline is `original/SCOBA.SC2Map`.
  - Provide `--revert` or document the revert command in the script.
- Never hand-edit generated files in `out/` without a corresponding script.
- Keep scripts deterministic (fixed seeds) so rebuilds are stable.

## Verification

- Rebuild with `scripts/playtest.sh build`.
- Confirm idempotency (run twice, compare hashes).
- Launch via the `scoba.desktop` shortcut to check in game.

## Existing procedural scripts

- `scripts/expand_map.py` - 128→256 upscale pipeline.
- `scripts/doodad_occlusion.py` - disable doodad auto-transparency (idempotent, wired into the pipeline).
- `scripts/props_expand.py` - 1.5× trees, 2× fluff, tree scale remapped to max 8 (idempotent, reversible, wired into the pipeline).
- `scripts/spore_scale.py` - scale SporeCannon/SporeCrawler units 3× and projectile speed 1.5× (idempotent, reversible, wired into the pipeline).
- `scripts/character_anim_assets.py` - generate splitbody aim groups for Tosh and Kerrigan while preserving full-body baseline Stand, Walk, Stand Left, and Stand Right (idempotent, reversible, wired into the pipeline). Each aim group has a frozen upper STC and one of eight directional lower STCs, including reversed backpedal. Generated animation group names and actor clip references must use allowed SC2 animation tokens; validation rejects unknown token names.
- `scripts/character_anim_m3.py` - M3 clone, freeze, reverse, and splitbody group helpers used by the asset generator.
- `scripts/animation_tokens.py`: allowed SC2 animation tokens and clip name checks used by asset generation and `scripts/validate-map.py`.
- `scripts/terrain/` - one-off terrain, heightmap, pathing, cell attribute, and sync inspection tools. These are not part of the build pipeline.
- `scripts/control_mode_icons.py` - generate distinct RPG and Action command-card icons (idempotent, reversible, wired into the pipeline).
- `scripts/bootstrap_galaxy.py` - write the minimal `MapScript.galaxy` bootstrap (idempotent, wired into the pipeline).
- `scripts/strip_gui_triggers.py` - replace the GUI trigger graph with one empty category (idempotent, reversible from git, wired into the pipeline).
- `scripts/migrate_galaxy_modules.py` - one-time generator for `scripts/app/`; it refuses to run after the source monoliths are removed.

## Project docs

- `docs/requirements/REQ-COMBAT-CONTROLS.md` - binding combat control requirements.
- `docs/specifications/SPEC-COMBAT-CONTROLS.md` - combat FSM implementation specification.
- `docs/requirements/REQ-MOUSE-CONTROLS.md` - binding mouse control requirements.
- `docs/specifications/SPEC-MOUSE-CONTROLS.md` - mouse control implementation specification.
- `docs/requirements/REQ-CHARACTER-ANIMATION.md` - binding character animation requirements.
- `docs/specifications/SPEC-CHARACTER-ANIMATION.md` - character animation implementation specification.
- `docs/requirements/REQ-TEST-FRAMEWORK.md`: binding test framework requirements.
- `docs/specifications/SPEC-TEST-FRAMEWORK.md`: test framework implementation specification.
- `docs/AUDIT.md` - full audit of command-card and repository changes.
- `docs/REMEDIATION.md` - phased remediation plan and test matrix.
- `docs/PIPELINE_AUDIT.md` - build, staging, cache, and launch audit.
- `docs/PIPELINE_REMEDIATION.md` - pipeline remediation plan.
- `docs/requirements/REQ-BUILD-ENTRYPOINT.md` - binding single-entrypoint requirements.
- `docs/specifications/SPEC-BUILD-ENTRYPOINT.md` - single-entrypoint implementation specification.

## Build pipeline

- `scripts/playtest.sh` - the ONLY build, test, launch, and dock-icon entrypoint. It always rebuilds fresh first.
- `scripts/build.sh` - low-level atomic build, normalization, stamping, validation.
- `scripts/validate-map.py` - required-file, XML, dimension, catalog, and stamp checks.
- `scripts/kill-sc2.py` - stop old SC2 processes before staging.
- `scripts/launch-scoba.sh` - clears cache, stages `out/SCOBA256.SC2Map`, verifies copy, launches.
- `scripts/launch-and-check.sh` - launches and verifies runtime stamp and logs.
- Never launch `src/SCOBA.SC2Map` for gameplay tests. Launch the freshly built map.
- Never use a pre-existing `out/SCOBA256.SC2Map` for tests or launches.
- All build, test, and launch wrappers delegate to `scripts/playtest.sh` unless `SC2_PLAYTEST_ACTIVE=1`.
- Use `make map-build`, `make map-launch`, `make combat`, `make aim`, `make motion`, or `make controls`.
- The GNOME dock entry MUST execute `scripts/playtest.sh launch`.

## Test framework

- `scripts/playtest.sh <profile>` - canonical profile test command with a fresh rebuild.
- `scripts/playtest.sh aimfreeze` - 10-second upper aim freeze and pitch-change check.
- `scripts/testmap.py` - generic build and run command for test profiles.
- `scripts/build-test-map.py` - build the combat test map.
- `scripts/run-map-test.py` - run the combat test profile.
- `scripts/build-aim-test-map.py` - build the aim test map.
- `scripts/run-aim-test.py` - run the aim test profile.
- `scripts/build-controls-test-map.py` - build the controls test map.
- `scripts/run-controls-test.py` - run the controls test profile.
- `scripts/build-motion-test-map.py` - build the motion test map.
- `scripts/run-motion-test.py` - run the motion test profile.
- `scripts/dump_m3_clip_metrics.py` - write `SCOBACLIPMETRICS` from any M3 model.
- The probe records model-derived frames from M3 metrics.
- The probe does not claim live actor time.
- Each profile uses its own map, bank, and run folder.
- Run artifacts go to `out/test-runs/<profile>/<timestamp>/`.
- Framework unit tests: `uv run python -m unittest discover -s scripts/testkit/tests -t scripts`.

## Command card

- Auto-attack state lives only in `SCOBAAutoAttackBehavior`.
- Chase state lives only in `SCOBARightClickStandBehavior`.
- Read state with `UnitHasBehavior`. Do not add boolean mirrors.
- Do not register toggle handlers with `c_unitAbilStageAll`.
- `tools/stormex` is a local helper and is ignored by git.
- `scripts/sc2res*` and `scripts/sc2-check-logs*` are optional project tools.
- Launch with `scripts/launch-and-check.sh` to include log checks.

## Gameplay rules

- RPG Stand holds position and attacks inside the keep radius. It never chases.
- RPG Stand ground right click stops and keeps the root.
- RPG Walk ground right click moves and shows the move marker.
- RPG right click never aims. Aim only starts on Action mode right hold.
- Action mode right clean click runs no right command.
- Aim must not write camera distance. Scroll distance survives aim entry and exit.
- Aim camera sits slightly left of the hero center, never directly behind it. Offset the camera origin; do not rotate the camera.
- Aim applies the offset by following a hero plus hidden-proxy group; the group center is the shoulder pivot. Never pan on top of follow.
- Action and aim use a screen-center reticle overlay with `storm_ui_cursor_default_base/enemy/friendly.dds`.
- `gt_AimCursorTick` resolves `CameraGetTarget` every 0.01 s and selects enemy, friendly, or neutral art.
- Hide the reticle in RPG mode and while Alt shows the free UI cursor.
- Terminology: Unit Highlight is the hover ring. Unit Target is the boss-bar target. Unit Select is native engine selection. Ability targeting is separate.
- RPG left, right, and order clicks resolve a Unit Target from `UnitClick`, then the press-time Unit Highlight, then press-point geometry.
- Register `UnitClick`, `UnitSelected`, and Unit Highlight separately for each hero player. Never use `EventPlayer` to infer the clicker.
- Every unit type must clear `FlagArray[Unclickable]` and `FlagArray[Unhighlightable]`.
- Action-mode attacks use `gf_UnitTargetAtPoint` at the camera target.
- Unit Highlight drives hover rings and the press-time target candidate. Never use it for ability targeting.
- Clear the Unit Target candidate on press and consume it on clean release.
- Left click sets or clears the target only. It never changes native selection past the event tick.
- `UnitClick` must immediately reselect the hero outside order mode.
- Left click on ground clears the target only. The hero stays selected.
- The hero stays natively selected outside order mode.
- Ctrl+C cancels order mode. It never clears native selection.
- The Order button is the only path that changes native selection to a non-hero unit.
- The Order button is visible only for a valid owned target.
- Order entry clears selection and selects the order unit. Order exit or cancel restores hero selection.
- Every unit and building stays selectable so the `PreSelection` hover ring renders.
- Left click must not leave the clicked unit selected.
- The hero stays natively selected outside order mode.
- The Order button is the only lasting native selection change to a non-hero unit.
- Never set any unit `Selectable=false`.
- Aim must not change combat FSM state or issue combat orders.
- `gf_ControlApply` is the only writer of mouse-relative and cursor visibility. It never enables camera input lock in RPG idle. Mouse press/release handlers own held button state. Targeting only reads it.
- Screen-edge camera scroll is disabled in map camera data: `CCamera id="Dflt"` sets `BorderSizeX=0`, `BorderSizeY=0`, `MaxScrollRate Follow=0`, `MaxScrollDistance Follow=0`, and `FollowScrollLimit=0`. Do not re-add camera input lock hacks. Native follow stays smooth.
- Control mode changes, Alt changes, aim entry/exit, and map init route through `gf_ControlApply`.
- Left-click target persists through hero idle, Stop, and move completion.
- Reject action-mode clicks outside the unit radius.
- Detect a drag from camera yaw or pitch change, not release UI distance.
- Aim uses one splitbody group per lower state and direction. Each group has two concurrent STCs.
- The upper STC is frozen at the Attack start keyframe. The lower STC animates Stand or Walk.
- Aim uses eight lower-body directions. Lower direction comes from the camera-relative travel vector.
- Aim unit facing and upper body stay locked to camera yaw while moving.
- Aim torso-to-lower twist must not exceed 65 degrees in either strafe direction.
- Aim S backpedals, A/D strafe, and diagonals preserve both components.
- Aim backward movement uses reversed backpedal animations.
- Aim must not turn 180 degrees toward travel or show a planted-feet torso twist.
- Aim attack animation is deferred; do not add an aim attack overlay in this stage.
- Non-aim A/D/S movement turns the hero toward the movement direction and uses the Walk lower clip.
- Normal action movement uses the RPG move-and-turn path. Only aim uses the aim movement path.
- One aim movement loop owns travel. Per-key loops only set flags during aim.
- Aim facing is independent of order issuance. Never require facing before a move order.
- Aim must not use the turn deadband. Apply camera facing every animation tick.
- Aim adds `SCOBAAimNoTurn` (`SuppressTurning`) on entry and removes it on exit.
- Do not disable `Turnable` or permanently zero turning rates.
- Tosh and Kerrigan use high `StationaryTurningRate` and `TurningRate` so camera facing does not lag.
- Aim uses two concurrent brackets: `SCOBAUp` for upper aim pitch and `SCOBALo` for lower locomotion.
- Aim hold must not loop the attack swing. Non-spine upper tracks are held at one key across the clip duration.
- Aim hold produces one upper pitch start event and no repeated upper start events.
- Aim upper pitch follows camera pitch over the camera range: 80 degrees down and 60 degrees up. The clip sweeps -95..50 degrees with fixed rest -13.
- The aim base pose is the Attack frame at 350 ms, where the gun is near horizontal.
- Aim pitch pivots the whole upper body around one lower-back spine bone, including the head, shoulders, and arms. Do not rotate the lower body or model root.
- Aim pitch uses densely spaced keyframes and sends the nearest target time when camera pitch changes.
- Aim pitch selects the nearest `SCOBAUp` target time from `CameraGetPitch`.
- Galaxy angles are degrees. Normalize wrapped camera pitch above 180 degrees to signed pitch before mapping.
- Aim pitch plays `SCOBAUp` on the main actor and sets `AnimSetTime` there.
- On each pitch change, unpause `SCOBAUp`, send `AnimSetTime`, then pause `SCOBAUp`.
- Freeze only after the camera-matched frame is applied. Never pause before setting the frame.
- Do not use `AnimSetPaused` on `SCOBALo`.
- The lower `SCOBALo` bracket must keep its Stand or Walk animation playing while the upper is held.
- Aim idle uses `Attack,Stand`; aim in-place turn uses `Attack,Stand,Left` or `Attack,Stand,Right`.
- Keep `c_ANIM_AIM_PITCH_REST` fixed. Never capture the aim-entry camera pitch as rest.
- Drive pitch updates from `TriggerAddEventCameraMove` and a periodic timer.
- On aim exit, send `AnimBlendTimeRemove`, unpause `SCOBAUp`, and clear it.
- Tosh and Kerrigan `CActorModel` entries set `AnimBlendTime` to 0.
- Aim entry must start at the current camera pitch without blending from idle.
- Aim pitch must not use actor root rotation or whole-model rotation.
- Camera collision owns only `c_cameraValueDistance`. It never writes pitch or yaw.
- SC2 camera pitch is degrees down from horizontal. Positive pitch places the eye above the target.
- Scroll zoom animates with `c_SCOBA_ZOOM_BLEND` on every wheel event.
- Camera collision checks terrain height along the sweep and includes the camera height offset.
- Keep one desired scroll distance. Collision never overwrites it with a shortened distance.
- Sweep the arm from the camera target to the desired eye with a camera radius.
- Ignore obstacles closer than the minimum pivot distance.
- Shorten distance with `c_SCOBA_COLLISION_CLAMP_BLEND`. Restore with `c_SCOBA_COLLISION_RESTORE_BLEND`.
- The collision tick applies the clamp on every tick, including while pitch or yaw is changing.
- Collision runs on a 0.02 s periodic tick. Never write distance from a camera move event.
- Aim movement keeps lower frame IDs advancing.
- Facing changes use `UnitSetFacing` with `c_ANIM_TURN_DURATION` outside aim and `c_ANIM_AIM_TURN_DURATION` during aim.
- Aim facing is written only by `gf_AnimFacingTick`; movement never writes facing.
- Turning uses native full-body `Stand Left` and `Stand Right` baseline clips.
- No upper turn overlay or generated turn clips.
- Use `c_ANIM_TURN_DEADBAND` only outside aim.
- Use one camera-relative travel heading per aim movement tick.
- Use native path-checked aim move orders with `c_ANIM_MOVE_TARGET`, `c_ANIM_MOVE_RETARGET`, and `c_ANIM_MOVE_HEADING`.
- Use `c_ANIM_MOVE_TICK` 0.015 as the aim movement loop interval.
- Aim entry without a movement key issues Stop and restores native idle.
- Reset animation state on aim entry, control mode change, and hero reassignment.
- Clearing the aim group must reset the splitbody state and upper state in the same call.
- Use movement intent plus a hold timer for lower walk and idle selection. Select the aim group from that lower state and direction.
- Controls tests must cover real clicks, target persistence, click radius, aim distance, movement tick, animation reset, immediate zoom, and collision clamp/restore.

## Resource tools

- `tools/stormex` - CASC reader. Supports SC2, name search, list, extract, and regex filters.
- `scripts/sc2res` - project CLI for SC2 resources.

Examples:

```bash
bash scripts/sc2res paths
bash scripts/sc2res list btn-command --ext dds
bash scripts/sc2res list "ability.*blink" --regex --ext dds
bash scripts/sc2res extract "mods\\liberty.sc2mod\\base.sc2assets\\assets\\textures\\btn-command-move.dds" --out /mnt/ws-fast/sc2res/icons --exact
bash scripts/sc2res preview btn-command-holdposition --out /mnt/ws-fast/sc2res/icons --html
```

Overrides: `SC2_PATH` for the install directory, `STORMEX` for the reader binary.

Default output root: `/mnt/ws-fast/sc2res` (preview, extract, tmp).

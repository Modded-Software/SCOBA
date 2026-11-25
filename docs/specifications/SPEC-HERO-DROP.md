# SPEC-HERO-DROP: Hero Drop After Death

**Date:** 2026-11-16
**Requirements:** [REQ-HERO-DROP](../requirements/REQ-HERO-DROP.md)

## 1. Requirement state

States: `[tested]` = a check in the `herodrop` profile backs it; `[build]` =
the map validator backs it; `[operator]` = only a person can judge it.

| ID | State | Backed by |
| --- | --- | --- |
| R-DROP-1 | [tested] | `drop_main tdead`: not alive, `Pending`, `Deaths` +1; `twait`: `Pods` unchanged; `drop_alive`: no pod, no landing; `drop_main tnext`: no second pod |
| R-DROP-2 | [tested] [operator] | `tdead CamToDeath100` < 100 (the pan's window, T26); later reads raw; that the view holds: AC-DROP-1 |
| R-DROP-3 | [tested] | `podType` `SCOBAHeroPod`; `fall`: first height 38..40.5 above the ground, never rising, last loop <= 3; `landMs` 2076..2386 |
| R-DROP-4 | [tested] [operator] | `fall`: applied camera height minus base within 1.6 of the pod height every loop; first loop camera target on the pod; `midCamDist100` 1500..2000; XY lock after that loop and the view: AC-DROP-1, 2 |
| R-DROP-5 | [operator] | `gf_PodImpactNow` at touchdown; the shake and the open doors: AC-DROP-3 |
| R-DROP-6 | [tested] [operator] | Start state (2026-11-20): [tested] `herodrop/20261120-213652` `drop_land`, `drop_main tafter`. TPS goes on through the toggle command (`gf_HeroDropTpsOn`, at touchdown and in the restore loops), not by adding the behavior: that left the toggle off and a TPS-off order did nothing (`herodrop/20261120-210634`). `drop_land`: `tpsOnOrders` > 0, off command shown, a TPS-off order leaves TPS, on again. `tland`, `tafter`: alive, same `Tag`, same `Level`, `HeroToPod100` < 150, `Direct` 1, `TpsMode`, `HeroActive`, `HeroTps`; `tland Life` = `LifeMax`; `tafter Single` = 1 as before death (negative: the default is 0); `tland`, `tafter`: pod part `DropCam100` 0, jump part 0; `tafter CamApplied100` = base + quake part within 2 (the 2.5 s pod quake still shakes 1 s after touchdown); camera follow on the hero: AC-DROP-3 |
| R-DROP-7 | [tested] | `twait`: `Blocked` +1, Tosh still active |
| R-DROP-8 | [tested] | `herodrop/20261118-203207` `drop_twice`: three deaths by enemy damage (`ByDamage` true), three fresh returns, old unit gone each time, type and current life max (350) kept |
| R-DROP-9 | [tested] | `herodrop/20261118-203207` `drop_seat2`: seat 2 pod and return owned by 2; seat 1 hero same, alive, not held, yaw delta 0 |
| R-DROP-10 | [planned] [operator] | `herodrop drop_main` and `intro deploy`: phase trace WAIT → ARM → ZOOM → FALL → IDLE; pod valid at the go and at the zoom start; Birth read before the zoom (`ArmLate` 0, `ClipAtZoom` 0..500 ms); `drop_main`: engine yaw unchanged in ARM (built 2026-11-20, not run); the same zoom rows (script FOV, engine pitch, yaw, distance) and the same scene flags (`SceneDrop`, `Cinematic`, `InputHeld`, `Dialogs` 0) in ZOOM and FALL; after touchdown scene off, dialogs back, input free. The look: AC-DROP-4 |
| R-DROP-11 | [planned] [build] | `scripts/hitvolumes/drop_path_check.py` (build): drop camera, scene and pod calls only in `systems/hero_drop.galaxy` and `systems/scene.galaxy`; no `c_INTRO_ROW_ZOOM`, no `gf_HeroDropStart` caller outside the drop; the intro calls only `gf_HeroDropBegin` and `gf_HeroDropGo` |
| R-DROP-12 | [tested] [operator] | `herodrop/20261120-175525` `drop_land tafter`: `PodSoundValid` (`CatalogEntryIsValid` on `SCOBAHeroPodFall`), `PodSounds` +1 per drop. Design: CSound `SCOBAHeroPodFall` (parent `Ghost_DropPodImpact`, liberty.sc2mod, 2D), played for the seat in `gf_HeroDropGo` with Birth. Audible: operator check |
| R-DROP-13 | [tested] | `herodrop/20261120-175348` `drop_spot`: 72 picks in lanes 1..6, engine reads: `blockedCells` 0, `units` 0, `minGap100` >= 400; `none` unchanged. Negative: a Supply Depot on a picked spot blocks cells (`depotCellsBlocked` > 0, `depotSpotFree` false); 24 later picks, `onDepot` 0. Design: `gf_DropPodPoint` (`systems/spawns.galaxy`): 24 random snapped spots, the free one farthest from the used pods; none: rings from the region center out to the region radius + 12; none at all: the center, counted (`gv_podSpotNone`) |
| R-DROP-14 | [tested] | `herodrop/20261120-210434` `drop_escort` (and the full suite `20261120-210634`): one escort wave per drop; hero pod travel 224.99 (southwest); the `TerranDropPod` units face as the hero pod (`podTurn100` 0 over 124 reads); pods 9.4 from the hero pod, 13.5 apart; after the landing the wave's own 8 units (4 Marines, Goliath, 2 Marauders, Firebat) alive, the seat's, shown, with a lane order; no pod left. The older `LanePods` 0 checks of `drop_main`, `drop_loop`, `drop_seat2` now allow the escort pods (at most 2). Negative: a go with the hero alive, no wave, no pod. Design: `gf_HeroDropGo` calls `gf_DropEscort` (`systems/spawns.galaxy`); its own thread runs the lane wave (`gf_TerranLaneWave`, `gf_ZergLaneWave`, shared with the reinforcement) at free spots off the hero pod, the points facing as the hero pod. Always a Goliath (operator 2026-11-20): `gf_TerranLaneWave` takes `lp_goliath`; the escort passes true, the reinforcement false. The `drop_escort` case now gives the seat a Goliath first and wants exactly one more in the wave; this is not run yet. The Zerg wave is unchanged (its Queen only while the seat has none). Not tested: a Zerg seat (the Zerg pod model's travel offset is not measured) |

R-DROP-6 "same `Tag`" changes with the fresh-unit return (3.1): the check
becomes same type, same level, old unit gone.

## 2. Facts

| ID | Fact | Source |
| --- | --- | --- |
| F1 | `droppodfalling.m3` Birth lowers the root from z 19.02 (0 ms) to 1.14 (1600 ms) to 0 (2200 ms). Stand is the landed pose, no fall. Death opens the doors. | `/mnt/ws-fast/inspect/pod.txt` |
| F2 | The stock `TerranDropPod` actor plays Birth only on a suppressed birth (`UnitBirth.*.Suppressed`); a plain `UnitCreate` shows Stand. | liberty campaign ActorData |
| F3 | Stock heroes stay as dead units with `DeathTime -1` (Dehaka); `UnitRevive` brings such a unit back. | swarm campaign UnitData; `herodrop/20261116-224935` |
| F4 | `UnitRevive` gives 1 life. | `herodrop/20261116-224935` `tland Life` 1 |
| F5 | The unit died event comes after the engine removed the hero's behaviors: TPS mode read off at the event. | `herodrop/20261116-225220` `savedTps` False |
| F6 | `CameraGetTarget` is right in the loop after a `CameraPan`. After that it reads (12.0, 8.0), with or without a unit follow (T26 of SPEC-TPS). | `herodrop/20261116-225510` `camXY0..3` |
| F7 | A toggle order (`gf_ToggleSet`) in the loop of the revive does not take. | `herodrop/20261116-225854` `tafter Single` 0 |
| F8 | `c_unitPropXP` cannot be set from script on the hero; it reads 0. The hero level is the script level `gv_lEVEL`. | `herodrop/20261116-224935` |
| F9 | The stock `TerranDropPod` actor and its model live in `liberty.sc2campaign`, which VoidStory does not load. The map's `TerranDropPod` actor had no parent and no model, so it drew the engine's stand-in sphere. `DropPodFalling` (same .m3) is in `liberty.sc2mod`. | campaign and mod ActorData, ModelData; operator 2026-11-17 |
| F10 | A unit lifted by `UnitSetHeight` shows the pod's Stand pose: a landed pod in the air (operator 2026-11-17). | operator |
| F11 | Birth's root bone `Dummy19` has no parent; its location keys are model space, linear (m3 `interpolationType` 1): (−9.8702, 9.4498, 19.0215) at 0 ms, (−0.5977, 0.5727, 1.1443) at 1600 ms, (0.0005, 0, −0.0091) at 2200 ms, then a bounce under 0.07. The path is one straight diagonal to the origin. | `scripts/hitvolumes/pod_birth.py --extract` |
| F12 | Model −y is the unit's facing: world = Rz(facing + 90) × model. | `systems/hit_volumes.galaxy`, tps `pick` group |
| F13 | No Galaxy getter reads a bone, an actor position or the clip time. | natives |
| F14 | After one `UnitRevive`, the hero's next death removes the unit: `dead1Valid` 0 0.5 s after the second kill. No script removes it. Cause unknown. The operator saw the same on a natural death after a return. | `herodrop` `drop_twice`, 2026-11-18; operator |
| F15 | The death sets `AnimSetTimeScaleGlobal 0.125` on the Tosh actor (Kerrigan 0.5); a revive keeps it. | `ActorData.xml` `ToshSCOBAUnit` |
| F17 | A revive pod after a death 140 cells from the spawn, with the wave's lane pods, plays Birth in the engine: 36 reads, 0 misses, touchdown 2250 ms. The engine clip read cannot tell whether the model is drawn on screen. | `herodrop/20261119-154016` `drop_far` |
| F18 | `CameraFollowUnitGroup(p, g, false, …)` removes only the units of `g`; with an empty group it stops nothing. The drop called it with `UnitGroupEmpty()`, so the engine kept following the dead hero (`DeathTime -1`) from death through the zoom and fall (`FollowDropHero` True, `FollowN` 1), holding the camera off the pod line; after touchdown the group held 2 units. Fix: `gf_CameraFollowStop` (`systems/camera/camera.galaxy`) removes the group the engine holds. | `herodrop/20261119-170732` probe; operator 2026-11-19 |
| F16 | A spent stat point changes the current property, not the normal one: `t0LifeMax` 350, `t0LifeMaxBase` 300. A self-inflicted `UnitDamage` did not kill the hero (`ByDamage` False). | `herodrop/20261118-202228` |

## 3. Design: multiplayer (SPEC-ROSTER 3.4)

- `systems/hero_drop`: per seat, alive / waiting / dropping, and the fall
  below (pod, clip clock, camera shot). Not split into more files: it stays
  under 512 lines.
- `systems/hero_return` (built): touchdown makes a fresh unit of the dead
  hero's type at the pod (`gf_HeroReturn`), facing `c_DROP_YAW`; default
  and learned abilities, the 5 stat properties kept every loop while alive
  (`gf_HeroStatsKeep`, current values: a spent point sets the current value,
  F16), full life and energy; the dead unit removed;
  player 1's switch handles follow; `gf_HeroBindPlayer(p, unit)`. No
  `UnitRevive`: it avoids F14 and F15.
- Death trigger and tick (built): one trigger for every played seat
  (`gv_tPSUNIT[p]`, hero types only); the tick runs every played seat.
- Not split into separate `hero_life` / `pod_ride` files yet.
- Input hold per seat (built): `gv_inputHeld[p]`, checked by every
  trigger of `gf_SceneTrigger` (`systems/scene.galaxy`, was
  `gf_IntroTrigger`); none is disabled. Build check:
  `scripts/input_gate_check.py`.
- The quake tick skips an invalid hero (`UnitIsValid`): it read a removed
  hero (ScriptError 2026-11-18 19.31.01).

## 3a. Design: one drop sequence (R-DROP-10, R-DROP-11)

Operator 2026-11-19: the revive drop looked different from the intro
drop. Cause in the code before this change: only the pod create, the fall
camera and the touchdown were shared. The intro alone ran the crash zoom
(its shot table row `c_INTRO_ROW_ZOOM`), had cinematic mode, hid the UI
and dialogs, and restored them in `gf_IntroEnd`. The revive cut from the
death spot straight to the pod, with UI and no cinematic mode. The old
text "one drop path, no difference" (2026-11-18) was true for the fall
only.

Design: the drop sequence is one module, outside the intro.

- **Files.** `core/hero_drop.galaxy`: constants, state.
  `systems/hero_drop.galaxy`: the sequence. `core/scene.galaxy` and
  `systems/scene.galaxy`: the scene (below). The intro and the
  reinforcement only start the sequence.
- **Phases** (`gv_dropPhase[p]`): `IDLE` 0 → `WAIT` 1 → `ARM` 4 →
  `ZOOM` 2 → `FALL` 3 → `IDLE` (trace `14230`). `gv_dropPending[p]` is
  `WAIT`, `ARM`, `ZOOM` or `FALL`. `ARM` added 2026-11-20 (operator: the
  view changed with no FOV and DOF and sat still before the pod existed;
  the pod must be birthing before the camera changes).
- **API.**
  - `gf_HeroDropBegin(p, hero)`: `WAIT`. Callers: the death trigger
    (`gf_HeroDropDied`), the intro deploy.
  - `gf_HeroDropGo(p, avoidA, avoidB)`: from `WAIT` only, else nothing.
    Picks the drop point in the seat's lane spawn region
    (`gf_DropPodPoint(gv_sPAWNLOCATIONS[gf_RosterLaneOf(p)], avoidA,
    avoidB)`), enters the scene, creates the pod and starts Birth, starts
    `ARM`. No camera write. Callers: the intro deploy
    (`null, null`), the reinforcement (`gt_TerranSpawn`, the wave's two
    lane pod points, called before the lane pods as before).
  - Everything else is internal to the module.
- **Scene on** (`gf_SceneEnter(p, c_SCENE_DROP)`), in `gf_HeroDropGo`:
  input held, cinematic mode, UI fullscreen, minimap hidden, map dialogs
  hidden. It writes no camera value.
- **ARM** (`gf_HeroDropArmStep`, every drop tick): the engine clip read
  (`gf_HeroDropClipRead`). The first Birth read anchors the clip clock and
  starts `ZOOM` (`gv_dropArmMs`). No Birth read within `c_DROP_ARM_MAX`
  0.5 s: `ZOOM` starts on the script clock and `gv_dropArmLate` counts it.
  The camera is left as it is: the death spot, or the intro shot, which
  keeps moving without its sounds (`gv_introCamHeld`, cleared by
  `gf_IntroCameraRelease` at the zoom start).
- **ZOOM** (`gf_HeroDropZoomBegin`; values unchanged except the end): the
  follow ends; the end is the fall camera at the clip time the zoom ends
  on, clip0 + `c_DROP_ZOOM_LENGTH` (`gv_dropZoomAt1`, `gv_dropZoomDist1`,
  `gf_HeroDropAimCalc`). A cut to that target at yaw `c_DROP_YAW`, pitch
  `c_DROP_ZOOM_PITCH` 55 → `c_POD_BIRTH_PITCH`, arm `c_DROP_ZOOM_DIST` 60
  → `gv_dropZoomDist1`, FOV `c_DROP_ZOOM_FOV0` 60 → `c_DROP_ZOOM_FOV1`
  12, height offset the base `c_SCOBA_CAMERA_HEIGHT_OFFSET`, the drop DOF
  (`gf_HeroDropDof`) from the first frame (was the default DOF). Crash easing:
  1 − (1 − w)³, w = t / `c_DROP_ZOOM_MOVE` 0.3, held to
  `c_DROP_ZOOM_LENGTH` 0.35 s. One camera write per tick, over one tick.
  Script state for tests: `gv_dropZoomFov`, `gv_dropZoomDist`.
- **FALL**: the camera on the pod (below), joined at the current clip
  time. Starts in the first tick at or after `c_DROP_ZOOM_LENGTH`. If the
  pod unit is not created in `gf_HeroDropGo`, the phase stays `WAIT` and
  the scene is left: the next reinforcement starts the sequence again.
- **Touchdown order** (one order for every drop): impact, hero back (a
  dead hero as a fresh unit, a hidden one revealed), life full, at the
  pod facing `c_DROP_YAW`; phase `IDLE`; `gf_IntroEnd(p)` (it ends only
  the intro's own parts and does nothing outside an intro); scene off
  (`gf_SceneLeave(p, c_SCENE_DROP)`); bind; TPS back; the pod killed;
  toggles restored over 8 loops.
- **The intro's own parts**: the shot loop, the prompt, the countdown,
  the theme music, the S4 and S9 sounds, its state. The theme plays on
  through the drop and stops in `gf_IntroEnd`. A revive has no music.
- **What still differs, by design** (R-DROP-10): the starter; the points
  the drop point avoids; the hero before touchdown (intro: alive, hidden;
  revive: dead, then a fresh unit); the intro's music; the camera before
  the zoom (the zoom starts with a cut, so it does not carry over).
- **Timing with the wave**: the reinforcement creates the hero pod before
  the lane pods, in the same call.
- **Replaced**: `gf_HeroDropStart(p, at)` as a public call (now internal
  to `ZOOM` → `FALL`); the intro's `ZOOM` and `FALL` states, its
  `gf_IntroFall`, its zoom row; `gf_HeroDropCinematic` (2026-11-19, never
  tested) folded into the scene.

### 3b. Scene (`systems/scene.galaxy`)

One implementation of the cinematic scene, used by the intro loop and the
drop sequence. Owners per seat (`gv_sceneOwners[p]`, bits
`c_SCENE_INTRO`, `c_SCENE_DROP`).

- `gf_SceneEnter(p, owner)`: adds the owner. On the first owner:
  `gv_inputHeld[p]` true and mouse-relative off (was `gf_InputHold`),
  `CinematicMode` on, `UISetMode` fullscreen, minimap hidden, the kept
  dialog flags cleared, then `gf_SceneDialogsEnforce`.
- `gf_SceneLeave(p, owner)`: removes the owner. On the last one: DOF
  default values, dialogs back to their kept visibility, `UISetMode`
  console, minimap shown, `CinematicMode` off over
  `c_SCENE_LETTERBOX_OUT` 0.5 s, input released (was `gf_InputRelease`).
- `gf_SceneDialogsEnforce(p)`: every map dialog visible to the seat is
  marked kept and hidden. Called on enter and by `gt_SceneTick` every
  loop while the scene is on.
- `gf_SceneActive(p)`: any owner. The DOF tick, the refollow watchdog and
  the XP panel show skip a seat in the scene.
- `gf_SceneDialog(p, i)` and `gf_SceneTrigger(i)`: the dialog list and the
  input-gated trigger list (were `gf_IntroDialog`, `gf_IntroTrigger`).
- The intro enters the scene with `c_SCENE_INTRO` at map init and leaves
  it in `gf_IntroEnd`. At an intro touchdown both owners leave in the
  same touchdown step, so the restore runs once, as after a revive.

- Yaw: fixed `c_DROP_YAW` 225 for every drop; the zoom ends on it.
  Operator view 2026-11-18: drops at yaw 225 and 135 rode the pod, a drop
  at yaw 90 did not (herodrop/20261118-184252). The cause of the yaw 90
  miss is not known.
- Side arm `c_DROP_CAM_SIDE` 4 to the right of the travel, as the TPS aim
  shoulder; arm `c_DROP_POD_ARM` 8 (operator: 20, then 12 too long). Touchdown
  keeps `c_DROP_CAM_DISTANCE` 20.
- Tracking: every loop while the hero lives, its Single, Stand and TPS
  states are kept (F5).
- Death: drop state on, the death point kept, aim, strafe hold, order mode
  and the pending shot ended. The camera follow ends and the camera pans to
  the death point.
- Pod: `SCOBAHeroPod` drops as the stock pod (`libVCMI_gf_CreateDropPod`):
  `UnitCreate` on the ground, facing `c_DROP_YAW` − travel, then `Birth`
  on the default slot, non-looping, default time. No height, time or
  speed change. The script reads the facing back (`UnitGetFacing`).
- Camera: no unit follow, no height offset. The script replays the Birth
  root (F11) in the world: pod position + 4.5 (actor scale) × Rz(facing +
  90) (F12) × key at the clip time. Yaw = travel, pitch = descent pitch
  (54.32). `gf_HeroDropAim`: target = where the look ray through the root
  meets the ground, then the side arm (`gf_HeroDropSide`); arm =
  `c_DROP_POD_ARM` 8 + root height / sin(pitch).
- Clip clock: the engine clip time anchors a steady game clock once
  (`gv_dropClipBase`); re-anchor only past `c_DROP_CLIP_DRIFT` 0.15 s (the
  per-loop read jitters up to 80 ms).
- Camera moves: one move per Birth leg (keys 0→1.6 s, 1.6→2.2 s), to the
  leg's end key over the clip time left (`gv_dropLeg`). Operator-approved
  motion (podbirth/20261117-120310). The camera collision clamp is skipped
  while the pod exists.
- FOV: `c_DROP_FOV_START` 30 at the Birth start, one move to
  `c_DROP_FOV_END` 90 at touchdown (operator 2026-11-17); the fall joins
  this line at its clip time. No FOV getter: operator check.
- Not verified: side alignment (pod behind the camera) and smoothness are
  operator checks; the podbirth look-ray, target-back and even-speed checks
  fail against this motion (4 failures, podbirth/20261117-123254) and wait
  on an operator decision.
  Keys: `data/pod_birth.galaxy`, generated by `scripts/hitvolumes/pod_birth.py`; the
  build checks the file and the actor scale; `test_pod_birth.py` checks
  the keys against the model.
- Assumption under test: the clip starts in the create loop and runs in
  game time. The `herodrop` and `intro` `deploy` checks compare the engine
  camera target and the applied height with the root recomputed on the host
  from the engine pod position and facing.
- Touchdown, the first loop at or after the land key (2.2 s, F11): camera
  part 0, `gf_PodImpactNow`, a dead hero back as a fresh unit
  (`gf_HeroReturn`, no `UnitRevive`), `gf_HeroReveal`, life 100 %, the hero
  moved to the pod facing the camera yaw, camera pan to the hero, then the
  touchdown order of 3a (intro end, scene off, bind). Start state
  (operator 2026-11-20): pitch blends to `c_DROP_LAND_PITCH` 0 over 0.5 s
  (no other writer); after the bind (it starts in Point & Click with the
  arm by unit height) the TPS behavior is always added and the desired arm
  set to `c_DROP_LAND_ARM` 1.0. The collision tick then moves the engine
  distance there with its own blends (0.06 s in, 0.28 s out), not 0.5 s.
  `gv_dropTps` is still recorded, no longer used. The pod is
  killed: its death clip opens it. Over the next 8 loops the toggles are
  set again through their commands (F7; the validator forbids adding
  toggle behaviors).
- `gf_HeroBind` (`systems/hero_switch.galaxy`) is the part of the hero
  switch that makes a unit the hero. The switch calls it and refuses while
  a drop waits (R-DROP-7).
- Data: `SCOBAHeroPod` (UnitData, parent `TerranDropPod`, no collision, no
  footprint) and its actor (ActorData, parent `TerranDropPod`). The map's
  `TerranDropPod` actor has parent `GenericUnitStandardNoAutoSoundLinks`
  and model `DropPodFalling` (F9); `scripts/hitvolumes/validate_pod_actor.py` checks
  this at build. `ToshSCOBA` and `KerriganSCOBA` have `DeathTime -1`.
- How the pod looks (model, clip, no sphere) is an operator check: no
  getter reads the drawn model or the clip time.

## 4. Files

| File | Role |
| --- | --- |
| `scripts/app/core/hero_drop.galaxy` | Constants (incl. the zoom), state, phases |
| `scripts/app/systems/hero_drop.galaxy` | The drop sequence: death, wait, go, zoom, fall, touchdown |
| `scripts/app/core/scene.galaxy`, `scripts/app/systems/scene.galaxy` | The scene: owners, enter, leave, dialog enforce, dialog and trigger lists, tick |
| `scripts/hitvolumes/drop_path_check.py` | Build check R-DROP-11 (in `scripts/validate-map.py`) |
| `scripts/testkit/tests/test_drop_zoom.py`, `test_drop_path.py` | Host tests: zoom constants and ground clearance; the build check |
| `scripts/app/systems/hero_switch.galaxy` | `gf_HeroBindPlayer`, `gf_HeroBind` (player 1), switch block, seat heroes |
| `scripts/app/systems/hero_return.galaxy` | Fresh-unit return: abilities, stats, handles |
| `scripts/app/core/input_hold.galaxy` | Per-player input hold flag (`gf_InputHeld`) |
| `scripts/app/systems/roster.galaxy` | Leave |
| `scripts/app/systems/camera/collision.galaxy` | Collision clamp skipped while the pod falls |
| `scripts/app/systems/camera/dof.galaxy` | DOF skipped while the pod falls |
| `scripts/hitvolumes/pod_birth.py`, `scripts/app/data/pod_birth.galaxy` | Birth root keys, travel, pitch |
| `scripts/testkit/galaxy/podbirth.galaxy`, `scripts/testkit/profiles/podbirth.py` | Birth, drop camera, DOF tests |
| `scripts/app/systems/podimpact.galaxy` | `gf_PodImpactNow` |
| `Base.SC2Data/GameData/UnitData.xml`, `ActorData.xml` | Pod unit and actor, hero `DeathTime` |
| `scripts/testkit/galaxy/herodrop.galaxy`, `scripts/testkit/profiles/herodrop.py` | Tests |
| `scripts/testkit/galaxy/herodrop_land.galaxy`, `scripts/testkit/profiles/herodrop_parts/herodrop_land.py` | Touchdown start state: camera snap, reset, `drop_land` |

## 5. Tests

`scripts/playtest.sh herodrop [group]`, one group per scenario: `main`
(`drop_main`), `land` (`drop_land`), `alive`, `loop`, `seat2`, `leave`, `wave` (`drop_far`).
The harness pauses `gv_sPAWNTIMER` and starts every drop with
`gf_HeroDropGo`, the one entry point the wave and the intro use: one hero
pod, no lane pods (`LanePods` 0, live `TerranDropPod` units, asserted).
Only `wave` fires the real timer expiry (restarted at 0.1 s), to prove the
wave starts the drop.

| Scenario | Asserts | Negative case |
| --- | --- | --- |
| `drop_alive` | A reinforcement with the hero alive. | No pod, no landing, no death. |
| `drop_main` | Tosh in TPS with Single on dies, waits 2.5 s, a reinforcement starts the sequence; phase trace; the zoom per loop (script FOV and arm, engine pitch, yaw, distance); the fall per loop; touchdown; 1 s later; a second reinforcement. Scene in ZOOM and FALL: `SceneDrop`, `Cinematic`, `InputHeld`, `Dialogs` 0. | No scene, pod or zoom before the reinforcement; no switch while dead; hero dead during the fall; no second sequence with the hero alive; drop point not the death point; scene off and dialogs back after touchdown; player 2 not held, no trigger disabled. |
| `drop_land` | Reset: pitch 30, arm by unit height. Tosh in Point & Click dies, one drop. 1.5 s after touchdown: `TpsMode`, `CamDesired100` 100, engine `CamDist100` 90..105, engine pitch within 2 of 0 (raw values printed). `drop_main` `tafter` asserts the same. | Before: not TPS, `SavedTps` false, desired arm above 1.0, pitch 30. |
| `drop_far` | Tosh dies at the Zerg spawn, the real wave drops the pod; per loop the engine clip read (raw trace). | No Birth misses; death point more than 30 cells from the pod. |
| `drop_loop` | Five deaths by damage in a row (operator 2026-11-19: consistency). Each cycle: the zoom rows, scene on in zoom and fall, phase trace, one hero pod, Birth every loop (0 misses), land time in the window, fresh unit of the same type, full life, spent life max carried. The five land times within two loops. | Old unit gone after each return; no lane pod; scene off after each touchdown. |
| `drop_seat2` | Seat 2 played by the harness: its hero dies, the lane 2 wave drops its pod, it returns as seat 2's hero. | Seat 1: no pending, no hold, same hero, camera yaw unchanged. |
| `drop_leave` | Seat 2 leaves mid-fall (`gf_RosterLeave`). | Pod gone, scene off, hold off, no landing. |

Same sequence for the intro (R-DROP-10): `intro deploy` records the same
phase trace, zoom rows and scene flags; `profiles/herodrop.py`
`zoom_follow` checks both against the same constants
(`core/hero_drop.galaxy`). Both harnesses record the zoom with
`gf_DbgZoomTrace` and the scene with `gf_DbgSceneSnap`
(`scripts/testkit/galaxy/common.galaxy`).

Host tests: `scripts/testkit/tests/test_drop_zoom.py` reads the zoom
constants from the map script (no copy) and checks the end on the fall's
first frame, the held easing, no zoom row in the intro table, and that the
zoom eye clears the ground over the three Terran lane spawn regions
(center and 8 edge points; negative: the same zoom pitched below the
horizon). `scripts/testkit/tests/test_drop_path.py` checks
`scripts/hitvolumes/drop_path_check.py` on the source and on injected violations.

## 6. Known limits

- The camera XY lock after the first fall loop and the camera follow on the
  hero after touchdown are operator checks (F6).
- Kerrigan uses the same path; only Tosh is tested (Kerrigan is a proof of
  concept).
- The pod fall sound is the stock pod impact set (R-DROP-12). A whoosh
  fall loop is not in the loaded mods.
- The hero pod point and the lane reinforcement pod points are chosen
  independently in the same region; they can land close to each other.

## 7. Runs

- `herodrop/20261116-224935`: first run, 6 failures (XP not settable, life
  1 after revive, TPS off, camera target stale).
- `herodrop/20261116-225510`: 5 failures; raw `CameraGetTarget` reads
  (12.0, 8.0) after the pan's loop (F6).
- `herodrop/20261116-225854`: 2 failures, `Single` 0 after the revive (F7).
- `herodrop/20261116-230121`: 0 failures. Camera arm 20.
- `herodrop/20261117-020416`: 1 failure, `tafter CamApplied100` 92 against
  base 89: the pod quake part, not the pod part. Test fixed (R-DROP-6 row).
- `herodrop/20261117-020606`, `herodrop/20261117-020715`: 0 failures.
- `herodrop/20261118-190738`: 0 failures. One drop path, fixed yaw 225,
  side arm 4, arm 12, input held in the fall. Engine getters show a set
  one loop late (yaw 90 and distance 1.5 in the create loop), so yaw and
  arm are checked from row 1. Clip-rate and slot probes were tried and
  dropped: the engine's own stand and walk clips are on no queryable slot
  (`Default`, `SCOBALo`, `SCOBAUp` read 0 before death too).
- `herodrop/20261119-154016`: 0 failures. `drop_far` added (F17);
  `drop_main` sets its own off yaw (an earlier drop leaves 225).
- `herodrop/20261119-165906` (group `main`): 0 failures. One drop sequence
  (scene, zoom, fall), direct `gf_HeroDropGo`, one hero pod, 0 lane pods.
- `herodrop/20261119-170201` (group `loop`): 0 failures. 5 cycles, arm 8,
  each 35 reads, 0 misses, touchdown 2187 ms.
- `herodrop/20261119-170732` (group `main`): 0 failures; probe: the
  camera followed the dead hero through the drop (F18).
- `herodrop/20261119-170924` (`main`), `herodrop/20261119-171041` (`loop`):
  0 failures with `gf_CameraFollowStop`: follow group empty from death to
  touchdown, the new hero only after, in all 5 cycles.
- `intro/20261119-171213` (group `deploy`): 0 failures; the same zoom and
  scene checks as `herodrop`.
- Host tests: 583 OK.
- `podbirth/20261118-191358`: 5 failures, as `podbirth/20261117-132801`
  (the 4 above, plus `pb_dof after10`).
- Regressions on the same build: `combat/20261116-230236` (group `switch`)
  0 failures; `jump/20261116-230339` (group `hero`) 0 failures;
  `tps/20261116-230444` full, 0 failures; host tests 402 OK.
- `combat/20261116-230954` full: 4 failures, all from the 0.25 s Tosh
  period read late (`single_shot t0500 CooldownMs: got=0 want>0`,
  `ButtonCdMs`; `weapon_button t0500 ButtonCdMs`, `CooldownMs`). Not from
  this change; open since `067ffff`.

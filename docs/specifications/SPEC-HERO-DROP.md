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
| R-DROP-6 | [tested] [operator] | `tland`, `tafter`: alive, same `Tag`, same `Level`, `HeroToPod100` < 150, `Direct` 1, `TpsMode`, `HeroActive`, `HeroTps`; `tland Life` = `LifeMax`; `tafter Single` = 1 as before death (negative: the default is 0); `tland`, `tafter`: pod part `DropCam100` 0, jump part 0; `tafter CamApplied100` = base + quake part within 2 (the 2.5 s pod quake still shakes 1 s after touchdown); camera follow on the hero: AC-DROP-3 |
| R-DROP-7 | [tested] | `twait`: `Blocked` +1, Tosh still active |

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

## 3. Design

- `core/hero_drop.galaxy`: constants and state. `systems/hero_drop.galaxy`:
  logic. Triggers: unit died (any unit; acts on `gv_heroActive` only),
  `gv_sPAWNTIMER` expiry, a periodic tick of one game loop.
- Tracking: every loop while the hero lives, its Single, Stand and TPS
  states are kept (F5).
- Death: drop state on, the death point kept, aim, strafe hold, order mode
  and the pending shot ended. The camera follow ends and the camera pans to
  the death point.
- Reinforcement: if the hero waits and no pod falls, `SCOBAHeroPod` drops
  as the stock pod (`libVCMI_gf_CreateDropPod`): created on the ground at
  `gf_DropPodPoint(gv_sPAWNLOCATIONS[1])` with
  `libNtve_gf_CreateUnitsAtPoint2`, then `Birth` on the default slot,
  non-looping, default time. No height, time or speed change. The facing
  is the stock one; the script reads it back (`UnitGetFacing`).
- Camera: no unit follow, no height offset. The script replays the Birth
  root (F11) in the world: pod position + 4.5 (actor scale) × Rz(facing +
  90) (F12) × key at the clip time. Yaw = travel, pitch = descent pitch
  (54.32). `gf_HeroDropAim`: target = where the look ray through the root
  meets the ground; arm = `c_DROP_CAM_DISTANCE` 20 + root height / sin(pitch),
  so the eye stays 20 behind the pod on its line.
- Clip clock: the engine clip time anchors a steady game clock once
  (`gv_dropClipBase`); re-anchor only past `c_DROP_CLIP_DRIFT` 0.15 s (the
  per-loop read jitters up to 80 ms).
- Camera moves: one move per Birth leg (keys 0→1.6 s, 1.6→2.2 s), to the
  leg's end key over the clip time left (`gv_dropLeg`). Operator-approved
  motion (podbirth/20261117-120310). The camera collision clamp is skipped
  while the pod exists.
- FOV: `c_DROP_FOV_START` 30 at the start, one move to `c_DROP_FOV_END` 90
  at touchdown (operator 2026-11-17). No FOV getter: operator check.
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
- Touchdown, the first loop at or after the land key (2.2 s, F11): camera part 0,
  `gf_PodImpactNow`, `UnitRevive`, life 100 % (F4), the hero moved to the
  pod facing the camera yaw, camera pan to the hero, `gf_HeroBind`. The
  TPS behavior is added back after the bind (the bind starts in Point &
  Click). The pod is killed: its death clip opens it. Over the next 8 loops
  the toggles are set again through their commands (F7; the validator
  forbids adding toggle behaviors).
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
| `scripts/app/core/hero_drop.galaxy` | Constants, state |
| `scripts/app/systems/hero_drop.galaxy` | Death, drop, fall, touchdown |
| `scripts/app/systems/hero_switch.galaxy` | `gf_HeroBind`, switch block |
| `scripts/app/systems/camera.galaxy` | Collision clamp and DOF skipped while the pod falls |
| `scripts/hitvolumes/pod_birth.py`, `scripts/app/data/pod_birth.galaxy` | Birth root keys, travel, pitch |
| `scripts/testkit/galaxy/podbirth.galaxy`, `scripts/testkit/profiles/podbirth.py` | Birth, drop camera, DOF tests |
| `scripts/app/systems/podimpact.galaxy` | `gf_PodImpactNow` |
| `Base.SC2Data/GameData/UnitData.xml`, `ActorData.xml` | Pod unit and actor, hero `DeathTime` |
| `scripts/testkit/galaxy/herodrop.galaxy`, `scripts/testkit/profiles/herodrop.py` | Tests |

## 5. Tests

`scripts/playtest.sh herodrop`. The reinforcement is the real timer expiry:
the harness pauses `gv_sPAWNTIMER` and restarts it at 0.1 s.

| Scenario | Asserts | Negative case |
| --- | --- | --- |
| `drop_alive` | A reinforcement with the hero alive. | No pod, no landing, no death. |
| `drop_main` | Tosh in TPS with Single on dies, waits 2.5 s, a reinforcement drops the pod; the fall per loop; touchdown; 1 s later; a second reinforcement. | No pod before the reinforcement; no switch while dead; hero dead during the fall; no second pod with the hero alive; drop point not the death point. |

## 6. Known limits

- The camera XY lock after the first fall loop and the camera follow on the
  hero after touchdown are operator checks (F6).
- Kerrigan uses the same path; only Tosh is tested (Kerrigan is a proof of
  concept).
- The pod has no fall sound (O-DROP-1). Its creation plays the stock
  `TerranDropPodImpact` sound at the start of the fall.
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
- Regressions on the same build: `combat/20261116-230236` (group `switch`)
  0 failures; `jump/20261116-230339` (group `hero`) 0 failures;
  `tps/20261116-230444` full, 0 failures; host tests 402 OK.
- `combat/20261116-230954` full: 4 failures, all from the 0.25 s Tosh
  period read late (`single_shot t0500 CooldownMs: got=0 want>0`,
  `ButtonCdMs`; `weapon_button t0500 ButtonCdMs`, `CooldownMs`). Not from
  this change; open since `067ffff`.

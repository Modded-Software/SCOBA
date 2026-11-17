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

## 3. Design

- `core/hero_drop.galaxy`: constants and state. `systems/hero_drop.galaxy`:
  logic. Triggers: unit died (any unit; acts on `gv_heroActive` only),
  `gv_sPAWNTIMER` expiry, a periodic tick of one game loop.
- Tracking: every loop while the hero lives, its Single, Stand and TPS
  states are kept (F5).
- Death: drop state on, the death point kept, aim, strafe hold, order mode
  and the pending shot ended. The camera follow ends and the camera pans to
  the death point.
- Reinforcement: if the hero waits and no pod falls, `SCOBAHeroPod` is
  created at `gf_DropPodPoint(gv_sPAWNLOCATIONS[1])`, facing the camera
  yaw, at height `c_DROP_HEIGHT` 40. The camera pans to the pod, follows
  it, and the arm goes to `c_DROP_CAM_DISTANCE` 20.
- Fall: each loop the pod is set to the height of the next loop over that
  loop's time, on the stock curve scaled to 40 (linear 1 to 0.06 by 1.6 s,
  then to 0 at 2.2 s). The camera height part `gv_dropCamHeight` gets the
  same value and time through `gf_CameraHeightApply`. The stock height
  (19.02 x scale 4.5) is not used: the fall would be 85 high.
- Touchdown, the first loop at or after 2.2 s: pod height 0, camera part 0,
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
  footprint) and its actor (ActorData, parent `TerranDropPod`). `ToshSCOBA`
  and `KerriganSCOBA` have `DeathTime -1`.

## 4. Files

| File | Role |
| --- | --- |
| `scripts/app/core/hero_drop.galaxy` | Constants, state |
| `scripts/app/systems/hero_drop.galaxy` | Death, drop, fall, touchdown |
| `scripts/app/systems/hero_switch.galaxy` | `gf_HeroBind`, switch block |
| `scripts/app/systems/camera.galaxy` | Pod part of the camera height |
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

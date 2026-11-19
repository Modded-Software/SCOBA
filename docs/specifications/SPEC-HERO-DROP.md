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
| R-DROP-8 | [tested] | `herodrop/20261118-203207` `drop_twice`: three deaths by enemy damage (`ByDamage` true), three fresh returns, old unit gone each time, type and current life max (350) kept |
| R-DROP-9 | [tested] | `herodrop/20261118-203207` `drop_seat2`: seat 2 pod and return owned by 2; seat 1 hero same, alive, not held, yaw delta 0 |

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
  trigger of `gf_IntroTrigger`; none is disabled. Build check:
  `scripts/input_gate_check.py`.
- The quake tick skips an invalid hero (`UnitIsValid`): it read a removed
  hero (ScriptError 2026-11-18 19.31.01).

## 3a. Design: current code

- `core/hero_drop.galaxy`: constants and state. `systems/hero_drop.galaxy`:
  logic. Triggers: unit died (any unit; acts on `gv_heroActive` only), a
  periodic tick of one game loop. No timer trigger of its own.
- One drop path (operator 2026-11-18): the intro deploy and the revive
  drop are the same code. `gf_HeroDropBegin(player, hero)` marks the hero
  as waiting (death: `gf_HeroDropDied`; intro: `gf_IntroFall`).
  `gf_HeroDropStart(player, at)` drops the pod; nothing when no hero
  waits. Callers: the reinforcement drop (`gt_TerranSpawn`, before the
  lane pods: `libVCMI_gf_CreateDropPod` waits, and a hero that died in
  that wait got that wave's pod, herodrop/20261118-190259) and the intro.
  The hero pod point avoids the wave's two lane pods; the three land
  together.
- Input hold (`gf_InputHold` / `gf_InputRelease`, `systems/intro_ui`): the
  intro's trigger list off and mouse rotation off, from the pod start
  (or the intro start) to touchdown. Idempotent: only the first hold keeps
  the trigger states.
- Yaw: fixed `c_DROP_YAW` 225 for every drop; the intro zoom ends on it.
  Operator view 2026-11-18: drops at yaw 225 and 135 rode the pod, a drop
  at yaw 90 did not (herodrop/20261118-184252). The cause of the yaw 90
  miss is not known.
- Side arm `c_DROP_CAM_SIDE` 4 to the right of the travel, as the TPS aim
  shoulder; arm `c_DROP_POD_ARM` 12 (operator: 20 too long). Touchdown
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
  `c_DROP_POD_ARM` 12 + root height / sin(pitch).
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
  `gf_PodImpactNow`, `UnitRevive` when dead, `gf_HeroReveal`, the actor's
  clip rate set back to 1 (`AnimSetTimeScaleGlobal 1`: the death sets the
  slow-death rate on the actor; operator 2026-11-18: animations frozen
  after the revive; unverified, no getter reads the engine's stand and
  walk clips), life 100 % (F4), the hero moved to the pod facing the
  camera yaw, camera pan to the hero, input released, `gf_HeroBind`,
  `gf_IntroEnd` (it checks for an intro). The
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
| `scripts/app/systems/hero_switch.galaxy` | `gf_HeroBindPlayer`, `gf_HeroBind` (player 1), switch block, seat heroes |
| `scripts/app/systems/hero_return.galaxy` | Fresh-unit return: abilities, stats, handles |
| `scripts/app/core/input_hold.galaxy`, `systems/intro_ui.galaxy` | Per-player input hold |
| `scripts/app/systems/roster.galaxy` | Leave |
| `scripts/app/systems/camera/collision.galaxy` | Collision clamp skipped while the pod falls |
| `scripts/app/systems/camera/dof.galaxy` | DOF skipped while the pod falls |
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
| `drop_main` | Tosh in TPS with Single on dies, waits 2.5 s, a reinforcement drops the pod; the fall per loop; touchdown; 1 s later; a second reinforcement. | No pod before the reinforcement; no switch while dead; hero dead during the fall; no second pod with the hero alive; drop point not the death point; player 2 not held, no trigger disabled. |
| `drop_twice` | Three deaths by damage, each with a pod and a return: fresh unit of the same type, full life, spent life max carried. | Old unit gone after each return. |
| `drop_seat2` | Seat 2 played by the harness: its hero dies, the lane 2 wave drops its pod, it returns as seat 2's hero. | Seat 1: no pending, no hold, same hero, camera yaw unchanged. |
| `drop_leave` | Seat 2 leaves mid-fall (`gf_RosterLeave`). | Pod gone, hold off, no landing. |

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
- `herodrop/20261118-190738`: 0 failures. One drop path, fixed yaw 225,
  side arm 4, arm 12, input held in the fall. Engine getters show a set
  one loop late (yaw 90 and distance 1.5 in the create loop), so yaw and
  arm are checked from row 1. Clip-rate and slot probes were tried and
  dropped: the engine's own stand and walk clips are on no queryable slot
  (`Default`, `SCOBALo`, `SCOBAUp` read 0 before death too).
- `podbirth/20261118-191358`: 5 failures, as `podbirth/20261117-132801`
  (the 4 above, plus `pb_dof after10`).
- Regressions on the same build: `combat/20261116-230236` (group `switch`)
  0 failures; `jump/20261116-230339` (group `hero`) 0 failures;
  `tps/20261116-230444` full, 0 failures; host tests 402 OK.
- `combat/20261116-230954` full: 4 failures, all from the 0.25 s Tosh
  period read late (`single_shot t0500 CooldownMs: got=0 want>0`,
  `ButtonCdMs`; `weapon_button t0500 ButtonCdMs`, `CooldownMs`). Not from
  this change; open since `067ffff`.

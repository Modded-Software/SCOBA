# SPEC-INTRO: Intro Sequence and Deploy

**Date:** 2026-11-17
**Requirements:** [REQ-INTRO](../requirements/REQ-INTRO.md)
**Shooting script:** [SCRIPT-INTRO](SCRIPT-INTRO.md)

## 1. Requirement state

States: `[planned]` = designed here, no code yet; `[tested]` = a check in
the `intro` profile backs it; `[host]` = a host test backs it;
`[build]` = the map validator backs it; `[operator]` = only a person can
judge it.

No code exists yet. Every requirement is `[planned]`. The column "Backed
by" names the check that will back it.

| ID | State | Backed by (planned) |
| --- | --- | --- |
| R-INTRO-1 | [planned] | `boot t0`: `IntroState` = LOOP, `Shot` 0 within 0.2 s of game start |
| R-INTRO-2 | [planned] [operator] | `boot t0`: every map dialog of player 1 `DialogIsVisible` false, `Cinematic` 1; how it looks: AC-INTRO-1 |
| R-INTRO-3 | [planned] | `wrap`: `Shot` 7 → 0, `Pass` +1; `shots` odd-pass rows read the variant values |
| R-INTRO-4 | [planned] | `shots`: engine yaw, pitch, distance per row and loop inside windows; FOV and height from script state |
| R-INTRO-5 | [planned] [host] | `test_intro_shots.py`: eye clearance ≥ 0.5 on 41 samples per shot, targets in bounds |
| R-INTRO-6 | [planned] [operator] | `shots`: `Dof` 1 only in S2 rows, 0 elsewhere and after deploy; visible blur: AC-INTRO-4 |
| R-INTRO-7 | [planned] [host] [operator] | host: invariant on the table; `shots S8`: engine distance × tan(script FOV / 2) within 3 %; the look: AC-INTRO-5 |
| R-INTRO-8 | [planned] [operator] | `boot`, `deploy`: prompt `DialogIsVisible` 1 in the loop, 0 after SPACE; legibility: AC-INTRO-3 |
| R-INTRO-9 | [planned] | `gate`: hero hidden, paused, not selectable; injected W, 1 and F keys: hero position, orders and camera values unchanged |
| R-INTRO-10 | [planned] [operator] | `deploy`: real SPACE; `Zoom` state seen ≤ 0.4 s; pod created, fall trace as `herodrop`; the snap: AC-INTRO-6 |
| R-INTRO-11 | [planned] | `deploy`: `JumpCount` unchanged; second SPACE: `Pods` = 1; `boot`: a reinforcement in the loop, `Pods` 0 |
| R-INTRO-12 | [planned] | `deploy tafter`: alive, `Direct` 1, toggles at the no-intro defaults, `Cinematic` 0, dialogs restored, `IntroState` = DONE, `CamLock` 0 |
| R-INTRO-13 | [planned] | `boot`: at 1 s, ≥ 1 Terran (owner 1) and ≥ 1 Zerg (owner 4) unit within 16 of X; at 6 s, damage taken on both sides; no extra units near regions 7 and 9 |
| R-INTRO-14 | [planned] | `boot`: `gv_sCOBA_Clock` and `gv_sPAWNTIMER` advance in the loop |
| R-INTRO-15 | [planned] [build] [operator] | build: the soundtrack id resolves in a dependency; `boot`: `Music` 1; audible: AC-INTRO-7 |

## 2. Facts

Confirmed by reading files on 2026-11-17.

| ID | Fact | Source |
| --- | --- | --- |
| F1 | The camera pitch range is 300 to 80 (−60° to 80°): the camera can look up. | `Base.SC2Data/GameData/CameraData.xml`, `Dflt` |
| F2 | Camera target bounds are (0, 0) to (254, 254). | `MapScript.galaxy` `CameraSetBounds` |
| F3 | Water level 7.15. The river runs (30, 230) to (230, 10). Landmark cells and grounds are in SCRIPT-INTRO §2. | Survey of `out/SCOBA256.SC2Map` with `scripts/flora/terrain.py` |
| F4 | Draft shot values clear the terrain and water by ≥ 0.92 and stay in bounds. S1 is the tightest (0.92, over water). | Same survey, 21 samples per shot |
| F5 | Getters exist for camera target, pitch, yaw and distance. There is no getter for field of view or height offset. | `natives.galaxy` lines 752-755 |
| F6 | Depth-of-field values exist: `c_cameraValueDepthOfField` 9, `FocalDepth` 10, `FalloffStart` 11, `FalloffEnd` 12, `FalloffStartNear` 13, `FalloffEndNear` 14. | `natives.galaxy` lines 672-677 |
| F7 | `CinematicMode`, `DialogIsVisible`, `WorldHeight`, `SoundtrackPlay` exist. | `natives.galaxy` lines 883, 1429, 1752, 3283 |
| F8 | `swarm.sc2mod` defines soundtracks `ZZerus01MusicMain`, `ZZerus02MusicMain`, `ZZerus03MusicMain`, parent `Music`. | `mods/swarm.sc2mod/base.sc2data/gamedata/soundtrackdata.xml`, extracted with `scripts/sc2res.py` |
| F9 | `CameraGetTarget` reads right only in the loop after a `CameraPan`. | SPEC-HERO-DROP F6 |
| F10 | The center lane Terran creep belongs to player 1, the Zerg creep to player 4. Both go through `gf_OrderSpawnGroup(group, side, 1)`. | `systems/spawns.galaxy` |
| F11 | SPACE is also the jump key (`gv_jUMP = c_keySpace`). | `core/constants.galaxy` |
| F12 | `gt_GUIEnvironmentSetup` shows engine frames at map init after a 0.01 s wait. | `systems/gui_environment.galaxy` |

Unconfirmed. Each has a probe that records raw values.

| ID | Assumption | Probe |
| --- | --- | --- |
| U1 | Yaw 90 looks toward +y; the eye sits behind the target. | `shots`: raw `CameraGetYaw` recorded. S4 depends on it: its yaw comes from the bramble-to-Hybrid geometry. The operator confirms S4 frames the Hybrid (AC-INTRO-1). |
| U2 | Map dialogs stay visible under `CinematicMode`. | `boot`: raw `DialogIsVisible` of the prompt. Fallback: two black dialog images as bars, no `CinematicMode`. |
| U3 | The camera height offset is measured from `WorldHeight(c_heightMapGround)` at the target with height smoothing off. | `shots`: raw ground under each target. |
| U4 | Depth-of-field values draw blur in this build. | Operator, AC-INTRO-4. |
| U5 | `ZZerus01MusicMain` loads with this map's dependencies (VoidStory). | Build check and AC-INTRO-7. |
| U6 | A per-loop `CameraSetValue` with duration = one loop gives a smooth move. | Same pattern as the pod fall (SPEC-HERO-DROP). Operator. |

## 3. Design

### 3.1 Modules

| File | Role |
| --- | --- |
| `scripts/intro_shots.py` | The shot table. Single source. Writes `data/intro_shots.galaxy`. Also the host checks' input. |
| `scripts/app/data/intro_shots.galaxy` | Generated. Shot arrays. Never hand-edited. |
| `scripts/app/core/intro.galaxy` | Constants, states, globals. `c_INTRO_ENABLED`. |
| `scripts/app/systems/intro.galaxy` | Loop, tick, prompt, UI hide and restore, creep seed, music, deploy. |
| `scripts/app/systems/hero_drop.galaxy` | New entry `gf_HeroDropDeploy`; touchdown reveals a living hero. |
| `scripts/testkit/galaxy/intro.galaxy`, `profiles/intro.py` | Tests. |
| `scripts/testkit/tests/test_intro_shots.py` | Host tests on the table. |

### 3.2 States

`OFF` → `LOOP` → `ZOOM` → `FALL` → `DONE`. `gv_introState`.

- `OFF`: `c_INTRO_ENABLED` false. Nothing runs. The game starts as today.
- `LOOP`: shots play. SPACE goes to `ZOOM`.
- `ZOOM`: the crash zoom, 0.35 s. Then `FALL`.
- `FALL`: the hero pod falls (hero drop code). Touchdown goes to `DONE`.
- `DONE`: the intro is over. All gates open.

`gv_introActive` is true in `LOOP`, `ZOOM`, `FALL`.

### 3.3 Start

At map init, after `gt_MapInit` binds the hero and after
`gt_GUIEnvironmentSetup` (F12), in one trigger:

1. `CameraLockInput(1, true)`. `CinematicMode(player 1, true, 0)`.
2. Hide every map dialog of player 1 and the boss bars. Keep their
   visibility to restore it.
3. Hero: hidden, paused, not selectable, at its start cell. Not killed.
4. `CinematicFade` in from black over 1.5 s.
5. `SoundtrackPlay(all, music, "ZZerus01MusicMain", any, any, true)`.
6. Creep seed (3.7).
7. Prompt shown. Shot 0, pass 0.

### 3.4 Shot table

Values are cells, degrees and seconds. `z` is the absolute target height;
the height offset is `z − WorldHeight(ground, target)` (U3). Eye =
target − distance × (cos pitch × (cos yaw, sin yaw), −sin pitch).

| Shot | Len | Ease | Target start → end | z start → end | Yaw | Pitch | Dist | FOV | DOF | Variant |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S1 Pride | 12 | E | (113.7, 143.3) → (103.8, 153.2) | 7.6 → 17.0 | 135 | 3 → −12 | 9 → 34 | 38 → 62 | off | none |
| S2 Line | 12 | L | (119.6, 113.1) → (131.0, 124.5) | 8.35 | 135 | 6 | 16 | 50 | on, focus 16 | target reversed |
| S3 Map | 10 | E | (125.3, 118.8) | ground | 45 → 75 | 80 | 150 | 22 | off | none |
| S4 Brambles | 6 | S | (194.4, 193.1) | ground + 3 | 90.8 | −7.5 | 27.5 | 70 | off | none |
| S5 Shackled | 4 | E | (194.4, 193.1) | ground + 4 | 90.8 | 8 | 18 → 12 | 48 → 44 | off | none |
| S6 Hive | 6 | A | (21.0, 9.0) | ground + 3 | 205 → 245 | 18 | 22 | 55 | off | yaw reversed |
| S7 Worm | 3 | O | (59.0, 59.0) | ground + 6 → + 12 | 225 | −20 → −35 | 9 | 80 | off | none |
| S8 Decimator | 6 | Z | (240.0, 248.0) | ground + 4 | 45 | 10 | from FOV | 70 → 24 | off | none |
| Zoom | 0.35 | C | hero drop point | ground | 225 | 55 | 60 | 60 → 12 | off | none |

S2 `z` is water level 7.15 + 1.2. Pass length 59 s.

Easings, `u` = time in shot / length:

- `E` smoothstep: 3u² − 2u³.
- `L` linear: u.
- `S` static: values applied once at the cut.
- `A` arc: linear with smoothstep over the first and last 10 %.
- `O` out: 1 − (1 − u)³.
- `Z` dolly zoom: FOV by `E`; distance = 14 × tan 35° / tan(FOV / 2).
  Start 14.0, end 46.1.
- `C` crash: FOV by `O` over 0.3 s, then held 0.05 s.

### 3.5 Tick

A periodic trigger every game loop (0.0625 s, as `c_DROP_TICK`). In
`LOOP` and `ZOOM`:

1. Shot time `t` = clock − shot start. If `t ≥ length`: next shot (wrap
   to 0, pass +1), `t` = 0, and the cut values go on with duration 0.
2. Values at the next loop, `u` = (t + tick) / length, eased.
3. `CameraPan` to the target, `CameraSetValue` for yaw, pitch, distance,
   height offset and FOV, each over one tick (U6). DOF values only at
   cuts.
4. Script state for tests: `gv_introShot`, `gv_introPass`,
   `gv_introFov`, `gv_introHeight`, `gv_introDof`.

One trigger writes the camera in the intro. Every other camera writer
returns while `gv_introActive`: `gt_CameraTurnTick`,
`gt_CameraCollisionTick`, `gt_AimCameraTick`, `gt_CameraFollowDistance`,
`gt_CameraDebugMove`, the quake roll, and the hero drop camera until
`FALL`.

### 3.6 Depth of field

At the cut into S2: depth of field on, focal depth 16, far falloff 4 to
18, near falloff 1 to 6. At the cut out of S2: the `Dflt` values. The
values are a first guess for the operator to tune (U4).

### 3.7 Creep seed

At map init, before the first frame:

- Terran, player 1: 4 Marine, 1 Goliath at X + (3.5, 3.5).
- Zerg, player 4: 8 Zergling, 2 Roach at X − (3.5, 3.5).
- Each group: `gf_OrderSpawnGroup(group, side, 1)`. The groups meet at
  once and fight. Survivors go on along the center lane.

No units are seeded on lanes 2 and 3. The spawn timer is not changed.

### 3.8 Input gates

While `gv_introActive`, these return at once: jump, the four move keys,
order key and button, order cancel, target clicks, unit click, hero
switch, TPS toggle, zoom, cursor and orbit keys, the abilities and stats
dialog keys. `CameraLockInput` stops camera moves by the player. The hero
is paused and hidden, so engine orders cannot reach it either.

### 3.9 Deploy

SPACE (`TriggerAddEventKeyPressed`, player 1, `c_keySpace`) in `LOOP`:

1. State `ZOOM`. Prompt hidden.
2. Drop point = `gf_DropPodPoint(gv_sPAWNLOCATIONS[1], null, null)`.
3. Cut to the Zoom row on the drop point. Crash zoom over 0.3 s.
4. At 0.35 s: state `FALL`; `gf_HeroDropDeploy(1, point)`.

`gf_HeroDropDeploy` sets `gv_dropPending`, `gv_dropHero` = the hero,
`gv_dropIntro` = true, and calls the pod start of `gf_HeroDropStart` at
the given point. The fall is the hero drop fall, unchanged.

Touchdown (`gf_HeroDropLand`): if `gv_dropIntro`, the hero is alive and
hidden. It is revealed, unpaused and moved to the pod; `UnitRevive` is not
called. The rest is the same. Then the intro ends:

- `CinematicMode(player 1, false, 0.5)`, `CameraLockInput(1, false)`;
- dialogs back to their kept visibility; boss bars as before;
- state `DONE`, `gv_introActive` false.

The jump trigger sees `gv_introActive` true on the deploy SPACE and
returns. A second SPACE in `ZOOM` or `FALL` does nothing. A spawn timer
expiry in `LOOP` finds `gv_dropPending` false and drops no pod.

### 3.10 Prompt

One dialog, 900 × 48, anchored bottom, offset 24: inside the bottom
letterbox bar. One label, "Press SPACE to deploy", white, size 22,
centred. A fade between 0 and 55 % transparency, 0.8 s each way, while
the state is `LOOP`.

### 3.11 Tests off

`c_INTRO_ENABLED` is a constant in `core/intro.galaxy`, true in the map.
The test map builder writes it false for every profile but `intro`. Old
profiles keep their premise: the hero alive and bound at start.

### 3.12 Build checks

`scripts/validate-map.py`:

- `data/intro_shots.galaxy` equals the output of `scripts/intro_shots.py`;
- the soundtrack id is defined in a dependency's SoundtrackData;
- `c_INTRO_ENABLED` is true in `out/SCOBA256.SC2Map`.

## 4. Tests

### 4.1 Host: `scripts/testkit/tests/test_intro_shots.py`

On the table and the built terrain:

- eye clearance ≥ 0.5 above ground or water at 41 samples per shot and
  per variant (R-INTRO-5);
- targets in (0, 254), eyes in (0, 256);
- no jump in yaw, pitch, distance or FOV between two samples of one shot
  beyond its eased step (P14 of SCRIPT-INTRO);
- S8: distance × tan(FOV / 2) constant within 0.1 % (R-INTRO-7);
- DOF on in S2 rows only (R-INTRO-6);
- lengths sum to 59 s; each shot ≥ 3 s (minimum shot length);
- S4 yaw, pitch and distance match the bramble-to-Hybrid geometry.

### 4.2 In game: profile `intro`

`scripts/playtest.sh intro [group]`. Harness `gf_IntroGoto(shot, t)`
jumps to a shot time, so groups stay near one minute.

| Group | Scenario | Asserts | Negative case |
| --- | --- | --- | --- |
| `boot` | Map start, no input. | State LOOP by 0.2 s; dialogs hidden; `Cinematic` 1; hero hidden, paused, not selectable; prompt visible; `Music` 1; creep at X at 1 s; damage both sides by 6 s; clock and spawn timer advance. | No units added near regions 7, 9; a reinforcement fired by the harness drops no hero pod; no hero orders. |
| `shots` | For each row and variant: goto at u = 0.1, 0.5, 0.9; read one loop after. | Engine yaw, pitch, distance within ±2° / ±2° / ±3 % of the eased value; target within 1.0 (loop after the pan, F9); `Dof` per row; S8 invariant on engine distance. Raw values recorded. | `Dof` 0 outside S2. |
| `wrap` | Goto S8 at t = 5.5, wait 1 s. | `Shot` 0, `Pass` +1; S2 next reads the variant. | No cut before the row length (± 2 loops). |
| `gate` | In S3: inject W for 1 s, `1`, `F`, mouse-free; read state. | Hero position unchanged, no order, state LOOP, camera values still the row's. | Each key, one at a time. |
| `deploy` | Inject SPACE in S5. Inject SPACE again in ZOOM and in FALL. | ZOOM seen, FALL ≤ 0.4 s after SPACE; one pod; fall trace as `herodrop`; at touchdown hero alive at the pod, `Direct` 1, defaults; `Cinematic` 0; dialogs restored; `CamLock` 0; DONE; `Dof` 0. | `JumpCount` unchanged; `Pods` 1 after both extra SPACEs; prompt hidden from SPACE on. |

Key injection uses `scripts/testkit/input_driver.py`. No mouse input.

### 4.3 Regressions

`herodrop`, `jump hero`, `tps`, `combat switch`, and the full `combat`
run, with the intro off (3.11).

## 5. Known limits

- Tree and doodad occlusion is not checked (O-INTRO-3).
- FOV and height offset have no engine getter (F5). They are checked
  through script state; the dolly zoom through engine distance.
- The look of every shot is an operator check (REQ-INTRO §4).

## 6. Runs

None yet.

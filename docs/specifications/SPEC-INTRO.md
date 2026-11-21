# SPEC-INTRO: Intro Sequence and Deploy

**Date:** 2026-11-17
**Requirements:** [REQ-INTRO](../requirements/REQ-INTRO.md)
**Shooting script:** [SCRIPT-INTRO](SCRIPT-INTRO.md)

## 1. Requirement state

States: `[planned]` = designed here, no code yet; `[tested]` = a check in
the `intro` profile backs it; `[host]` = a host test backs it;
`[build]` = the map validator backs it; `[operator]` = only a person can
judge it.

Code exists. `[tested]` entries passed in run `intro/20261117-024914`
(full profile, `failures: 0`). The `[operator]` parts are not done.

| ID | State | Backed by |
| --- | --- | --- |
| R-INTRO-1 | [tested] | `boot`: `earlyState` LOOP, `firstCutMs` 625 (< 1500); `t0` State 1 |
| R-INTRO-2 | [tested] [operator] | `boot t0/t1/t6`: `Dialogs` 0 (15 dialogs checked, incl. the wallet HUD), `Cinematic` true; how it looks: AC-INTRO-1 |
| R-INTRO-3 | [tested] | `wrap`: `Shot` 7 → 0, `Pass` +1, S8 cut at 3.0 s; `shots` S2 and S6 pass 1 read the variant values |
| R-INTRO-4 | [tested] | `shots`: engine yaw, pitch, distance per row inside windows; FOV, target and height from script state against the table. The engine target is raw only (F13) |
| R-INTRO-5 | [host] | `test_intro_shots.py`: eye clearance, bounds, S1/S2 absolute heights on the survey ground |
| R-INTRO-6 | [tested] [operator] | `shots`: `dof` 1 only in S2 rows; `deploy tland/tafter`: `Dof` false; visible blur: AC-INTRO-4 |
| R-INTRO-7 | [host] [tested] [operator] | host: invariant on the table; `shots S8`: engine distance × tan(script FOV / 2) within 3 %; the look: AC-INTRO-5 |
| R-INTRO-8 | [tested] [operator] | `boot`: `Prompt` true; `deploy tzoom`: `Prompt` false; legibility: AC-INTRO-3 |
| R-INTRO-9 | [tested] | `gate tw/t1/tf`: hero position, tag, orders, pods, state unchanged; camera values still the row's; `TrigOn` 0 |
| R-INTRO-10 | [planned] [operator] | `deploy`: injected SPACE; countdown trace `321`; the drop sequence starts 2.5..4 s after SPACE (intro state `DROP`, drop phase `ZOOM`); then the drop's own checks (SPEC-HERO-DROP R-DROP-10). Build: the intro holds no drop code (R-DROP-11). The snap and the pod look: AC-INTRO-6 |
| R-INTRO-11 | [tested] | `deploy`: `JumpPresses` 0, `Pods` 1, `SpaceIgnored` 2; `boot treinf`: `Pods` 0 |
| R-INTRO-12 | [tested] | `deploy tland/tafter`: alive, shown, `Direct` 1, `Single` 1, `Stand` 1, `TpsMode` false, `Cinematic` false, `Dialogs` 10, `TrigOn` 41, state DONE |
| R-INTRO-13 | [tested] | `intro/20261118-203746` `boot` (meet 13.5 s, both hurt by 19.2 s in `20261118-203358`): 5 Terran and 10 Zerg seeded `c_INTRO_SEED_BACK` (50) back; at 1 s none hurt and both centers > 16 from X (negative); polled until both have a unit within 16 of X and both are hurt, at most 40 s; `laneUnits6` 0 |
| R-INTRO-14 | [tested] | `boot t6`: `Clock100` 600, `SpawnLeft100` 3350 |
| R-INTRO-15 | [tested] [operator] | `boot`: `MusicValid`, `SilenceValid` true (in game, `CatalogEntryIsValid`), `Music` true; `deploy`: `Music` true in ZOOM and FALL, false at touchdown; audible and muted: AC-INTRO-7. Per-seat music: [tested], `intro/20261118-203746` `seats` (`Music` per seat). |
| R-INTRO-16 | [tested] | `intro/20261118-203746` group `seats` (`testkit/galaxy/intro_seats.galaxy`): seat 2 deploys and lands; seat 1 stays in LOOP with prompt, music, cinematic, hold, hidden hero, and the same pod count (negative case). Design: state and camera arrays per seat (`gv_introState[p]` ...), `gt_IntroDeploy` with `c_playerAny` and `EventPlayer()`, dialogs and prompt per player group, the seed once (SPEC-ROSTER 3.4). |
| R-INTRO-17 | [host] [tested] [operator] | Host: `test_intro_shots.py`, the tree 0.5 behind the S2 start eye and far from the odd-pass eye (negative); constants in `data/intro_shots.galaxy`. `herodrop spot` `treeSet`: the actor exists (run at the earlier 3.0 and 275 %; not run at the current values). Design: `gf_IntroTreePlace` (`systems/visual_tuning.galaxy`), model actor `ZerusTree` at (131.21, 101.49) (operator 2026-11-21: 0.5 behind, closer to the camera path; was 1.0, (131.56, 101.14); 2.0, (132.27, 100.43); 3.0, (132.97, 99.73)), variation by the actor message `ModelSwap ZerusTree 4`, scale 3.1875 x 3.1875 x 4.4625 (map actor scale 5, z 1.4, times 0.6375: 15 % smaller, operator 2026-11-21; was times 0.75, 1.0, 2.0, 2.75, 3). Second tree (`gv_introTree2`, `s2_tree2()`): (137.40, 106.62) (was (137.22, 106.79), (136.87, 107.15), (137.22, 106.80)), 8.0 from the first along the first-pass camera path and 1.25 from the eye path (`TREE2_BACK`; operator 2026-11-21: further than the first's 0.5; was 1.0) (45 degrees; was 2.0, (133.68, 101.84)), scale 2.3906 x 2.3906 x 3.3469 (75 % of the first tree; was 2.8125), variation 7 (`c_INTRO_TREE2_VARIATION`, operator 2026-11-21; was 4, the first's), facing 135 by `libNtve_gf_MakeModelFaceAngle` (the first keeps facing 0). Host: `test_s2_second_tree_down_the_camera_path` (behind the eye at the start, middle and end of the pass). In game: `tree2Set`, not run yet. An actor's facing cannot be read back: the rotation is an operator check. Overlap (operator 2026-11-21): `scripts/hitvolumes/intro_trees.py`. A map tree (`ObjectDoodad` `ZerusTree*`) overlaps when its trunk is closer than both canopies together; canopy = 0.5 x scale, the estimate of `flora/treevary.py` (placed trees: 1.594 and 1.195). `apply_intro_tree_clearing` removes such trees from `Objects` in `expand_map.py`, before the scaled footprints and flora, so no blocker stays and flora plans with the same trees `check_flora` re-plans from (removing after flora broke that check). Side effect: flora's seeded scatter re-rolls; against a reference build without the step, 2,465 flora doodads differ in position, scale or rotation (operator 2026-11-21: accepted). `intro_trees.problems` (through `intro_problems` in `validate-map.py`) fails the build when a tree overlaps in the built map. Removed at the current spots (build `5cada69f13ab-ba018b67c323d1aa`): tree 13 at (133.00, 103.00), 2.34 from tree 1, and its clone at (130.89, 101.31), 0.37 from tree 1, both scale 4.41; none near tree 2. Plants, grass and fog stay. Host: `IntroTreeClearingTest`. Variation, size and look: operator check |
| R-INTRO-18 | [operator] | Not run in game. Design: `gf_IntroChatHide` (`systems/intro.galaxy`), on in `gf_IntroStartSeat`, off in `gf_IntroEnd`, per seat. It hooks the stock frame `UIContainer/FullscreenUpperContainer/ChatDisplay` (`DialogControlHookupStandard`) and hides it for the seat, mutes the seat's `Alert` sound channel, and clears the chat area on both edges. Facts: no chat frame type exists for `UISetFrameVisible`; the stock AI scripts do not send the lines, the engine does behind `c_diffSupportsBeacons` (`baseai.galaxy` line 121); all 279 `AICommunication_*` sounds have the parent `HoS_Alert`, category `Alert`. In game: `intro deploy` keys `ChatHidden`, `ChatFrame`, `ChatShown` (`DialogControlIsVisible`): hidden at `t0`, `tzoom`, `tfall`, shown at `tland`, `tafter` (negative). Limits: the muted channel also drops every other alert sound for that seat during the intro; before `gf_IntroStart` (map init, black screen) the frame is not hidden yet; that the AI's lines land in this frame is unconfirmed. No text on screen and no voice: operator check |
| R-INTRO-19 | [operator] | Not run in game. Design (changed 2026-11-21): `gf_IntroMouseHide` (`systems/intro_flow.galaxy`) hides the cursor as TPS does: `CameraForceMouseRelative` on, `CameraSetMouseRotates` off. On in `gf_IntroStartSeat`, off in `gf_IntroEnd`, then `gf_ControlForceSend`, so the drop's bind sends the control mode in full. The intro sends no `UISetCursorVisible`. The first design sent a cursor hide in cinematic mode; after touchdown the TPS free cursor stayed hidden, also with a forced send on the click (operator 2026-11-21). In game: `intro deploy` key `MouseHidden` true at `t0`, `tzoom`, `tfall`; at `tland`, `tafter` false, `SentCursor` equal to `CursorRule`, `SentRelative` its opposite (negative). Limits: that relative mode hides the cursor in cinematic mode is unconfirmed; no native reads the cursor state; before `gf_IntroStart` (black screen) the cursor is not hidden yet. Cursor on screen in the intro and the free cursor after it: operator check |

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
| F7 | `CinematicMode`, `DialogIsVisible`, `WorldHeight`, `SoundtrackPlay`, `SoundtrackStop` exist. | `natives.galaxy` lines 883, 1429, 1752, 3283, 3287 |
| F8 | `swarm.sc2mod` defines soundtracks `ZZerus01MusicMain`, `ZZerus02MusicMain`, `ZZerus03MusicMain`, parent `Music`. | `mods/swarm.sc2mod/base.sc2data/gamedata/soundtrackdata.xml`, extracted with `scripts/sc2res.py` |
| F9 | `CameraGetTarget` reads right only in the loop after a `CameraPan`. | SPEC-HERO-DROP F6 |
| F10 | The center lane Terran creep belongs to player 1, the Zerg creep to player 4. Both go through `gf_OrderSpawnGroup(group, side, 1)`. | `systems/spawns.galaxy` |
| F11 | SPACE is also the jump key (`gv_jUMP = c_keySpace`). | `core/constants.galaxy` |
| F12 | `gt_GUIEnvironmentSetup` shows engine frames at map init after a 0.01 s wait. | `systems/gui_environment.galaxy` |
| F13 | In the intro, `CameraGetTarget(1)` reads (12, 8), also in the tick right after the pan. Pitch reads 0..360: −5 reads 355. | `intro/20261117-024416` raw values |
| F14 | `WorldHeight(c_heightMapGround, p)` reads 0 at X, the hero cell and the Hybrid. `c_heightMapAir` reads 8.0 at X. `UnitGetHeight` of a seeded Marine reads 0. The survey ground at X is 3.87. | `intro/20261117-024416` raw values; `scripts/flora/terrain.py` |
| F15 | The soundtrack category is `c_soundtrackCategoryMusic`. `c_soundCategoryMusic` is a sound category and gives a runtime error. | ScriptError in an earlier `intro` run |
| F16 | `CameraLockInput` is banned in the map (SPEC-TPS: it kept the cursor captured). | `scripts/validate_aim_shot.py` |

Unconfirmed. Each has a probe that records raw values.

| ID | Assumption | Probe |
| --- | --- | --- |
| U1 | Yaw 90 looks toward +y; the eye sits behind the target. | `shots`: raw `CameraGetYaw` recorded. S4 depends on it: its yaw comes from the bramble-to-Hybrid geometry. The operator confirms S4 frames the Hybrid (AC-INTRO-1). |
| U2 | Map dialogs stay visible under `CinematicMode`. | `boot`: raw `DialogIsVisible` of the prompt. Fallback: two black dialog images as bars, no `CinematicMode`. |
| U3 | The camera height offset is measured from the ground under the target. `WorldHeight` cannot confirm it (F14). | `shots`: raw ground recorded. The operator confirms S1 and S2 sit just over the water (AC-INTRO-1). |
| U4 | Depth-of-field values draw blur in this build. | Operator, AC-INTRO-4. |
| U5 | `ZZerus01MusicMain` loads with this map's dependencies (VoidStory). | Build check and AC-INTRO-7. |
| U6 | A per-loop `CameraSetValue` with duration = one loop gives a smooth move. | Same pattern as the pod fall (SPEC-HERO-DROP). Operator. |

## 3. Design

### 3.1 Modules

| File | Role |
| --- | --- |
| `scripts/hitvolumes/intro_shots.py` | The shot table. Single source. Writes `data/intro_shots.galaxy`. Also the host checks' input. |
| `scripts/app/data/intro_shots.galaxy` | Generated. Shot arrays. Never hand-edited. |
| `scripts/app/core/intro.galaxy` | Constants, states, globals. `c_INTRO_ENABLED`. |
| `scripts/app/systems/intro.galaxy` | Per seat: shots, camera, prompt, UI hide and restore, creep seed, countdown. |
| `scripts/app/systems/intro_flow.galaxy` | Per seat: start, deploy, end, tick; the triggers (`gt_IntroDeploy` on `c_playerAny`). |
| `scripts/app/systems/intro_ui.galaxy` | `gf_IntroEnabled`. |
| `scripts/app/systems/scene.galaxy` | The scene the intro loop runs in (SPEC-HERO-DROP 3b): enter at map init, leave in `gf_IntroEnd`. |
| `scripts/app/systems/hero_drop.galaxy` | The drop sequence. The deploy calls `gf_HeroDropBegin` and `gf_HeroDropGo` only. |
| `scripts/testkit/galaxy/intro.galaxy`, `intro_seats.galaxy`, `profiles/intro.py` | Tests. |
| `scripts/testkit/tests/test_intro_shots.py` | Host tests on the table. |

### 3.2 States

`OFF` → `LOOP` → `DROP` → `DONE`. `gv_introState`.

- `OFF` (0): `c_INTRO_ENABLED` false. Nothing runs. The game starts as today.
- `LOOP` (1): shots play. SPACE starts the countdown; at 0: `DROP`.
- `DROP` (2): the hero drop sequence runs (SPEC-HERO-DROP 3a: zoom, fall,
  touchdown). The intro tick writes nothing. Touchdown calls `gf_IntroEnd`.
- `DONE` (3): the intro is over.

`gv_introActive` is true in `LOOP` and `DROP`. Changed 2026-11-19: the
`ZOOM` and `FALL` states moved to the drop as its phases.

### 3.3 Start

First action of `gt_MapInit`, before any wait:
`UISetMode(all, c_uiModeFullscreen, 0)` and the minimap panel hidden.
`gt_GUIEnvironmentSetup` leaves the minimap hidden while
`c_INTRO_ENABLED` (operator 2026-11-17). Not verified.

At map init, after `gt_MapInit` binds the hero and after
`gt_GUIEnvironmentSetup` (F12), in one trigger:

1. `gf_SceneEnter(p, c_SCENE_INTRO)` (SPEC-HERO-DROP 3b): input held,
   `CinematicMode` on, UI fullscreen, minimap hidden. No
   `CameraLockInput` (F16).
2. The 15 map dialogs (`gf_SceneDialog`): the scene tick hides any the
   seat sees and keeps it for the restore (`gf_SceneDialogsEnforce`).
   `systems/xp.galaxy` skips its stats and abilities show while
   `gf_SceneActive`.
3. Hero: hidden, paused, not selectable, at its start cell. Not killed.
4. `CinematicFade` in from black over 4 s (`c_INTRO_FADE_IN`, operator 2026-11-18).
5. `CatalogEntryIsValid` for the theme and the hum (sound catalog) and
   `Music_Silence` (soundtrack catalog), kept for tests. `Music_Silence`
   becomes the default soundtrack for all. Each seat then gets
   `SoundPlay("SCOBAIntroTheme")`, kept in `gv_introMusicSound[p]`. The
   soundtrack route did not play (operator 2026-11-18). `SCOBAIntroTheme` is
   a SoundData sound (parent `MUSIC`, `LoopCount` -1: it loops until touchdown), file
   `Assets\Sounds\SCOBA_IntroTheme.ogg`. The build encodes
   `res/audio/*.wav` to Ogg Vorbis there (`import_audio`,
   `scripts/expand_helpers.py`, cache `out/audio`).
   S9 hum: `gf_IntroCut` calls `gf_IntroHum`, on for row 8 (S9), off on
   any other cut, at deploy and at touchdown. Sound `SCOBAPsiHum`: the
   stock `PsiDecimator_Amb_Lp` loop, mode 2D (operator 2026-11-18).
   S4 quiet: `gf_IntroQuiet` sets the seat's Doodad sound channel to 15 %
   in S4 (the caged Ultralisk's stock idle sounds,
   `Doodad_HybridUltraliskShackled_*`) and back to 100 % on any other
   cut, at deploy and at touchdown (operator 2026-11-18).
6. Creep seed (3.7).
7. Prompt shown. Shot 0, pass 0.

### 3.4 Shot table

Values are cells, degrees and seconds. `z` below is the target height
asked for. The table stores the height offset above the ground. For
"ground + n" that is n. S1 and S2 ask for absolute heights; no engine
getter gives the ground (F14), so the table stores `z − survey ground`
(S1: 5.67 → 5.59, S2: 4.16 → 4.17). A host test pins the sum. Eye =
target − distance × (cos pitch × (cos yaw, sin yaw), −sin pitch).

| Shot | Len | Ease | Target start → end | z start → end | Yaw | Pitch | Dist | FOV | DOF | Variant |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S1 Pride | 12 | E | eye 1.0 left of the Brakk (14.96, 113.36) facing (operator 2026-11-20; was 0.5), looking at the BC (103.8, 153.2) from the new eye | 14 | 23.56 | −25 → −45 | 8 → 14 | 50 → 40 | off | none |
| S2 Line | 12 | L | (119.6, 113.1) → (131.0, 124.5) | 8.35 | 135 | 6 | 16 | 50 | on, focus 16 | target reversed |
| S3 Map | 10 | E | (125.3, 118.8) | ground | 45 → 75 | 80 | 225 (operator 2026-11-18: was 150) | 14.8 (was 22; same framing) | off | none |
| S4 Brambles | 6 | E | (194.4, 193.1); eye exactly at (193.5, 164.5, 10.2) (operator 2026-11-18) | ground + 3 | 88.2 | −3.12 | 28.66 | 70 → 45 | off | none |
| S5 Shackled | 4 | E | (194.4, 193.1) | ground + 4 | 90.8 | 8 | 18 → 12 | 48 → 44 | off | none |
| S6 Overmind | 6 | A | (21.0, 9.0) | ground + 3 | 215 → 235 (half rate, operator 2026-11-18) | 18 | 99 (operator 2026-11-18: was 66) | 38.3 (was 55; same framing) | off | yaw reversed |
| S7 Worm | 7 (operator 2026-11-18: was 3, then 5) | O | (59.0, 59.0) | ground + 6 → + 12 | 225 | −20 → −35 | 9 | 80 | off | none |
| S8 Jungle | 7 (operator 2026-11-18: was 8, then 7.5) | L | (120.0, 150.0) → (120.0, 167.5), Terran jungle, 2.5 cells/s | ground + 2 | 90 | 12 | 6 | 60 | off | none |
| S9 Decimator | 8 | Z | (240.0, 248.0) | ground + 4 | 45 | 10 | from FOV | 70 → 24 | off | none |
S2 `z` is water level 7.15 + 1.2. Pass length 72 s.

The crash zoom is not an intro shot since 2026-11-19: it is the drop
sequence's `ZOOM` phase, with the same values (SPEC-HERO-DROP 3a).

Easings, `u` = time in shot / length:

- `E` smoothstep: 3u² − 2u³.
- `L` linear: u.
- `S` static: values applied once at the cut.
- `A` arc: linear with smoothstep over the first and last 10 %.
- `O` out: 1 − (1 − u)³.
- `Z` dolly zoom: FOV by `E`; distance = 14 × tan 35° / tan(FOV / 2).
  Start 14.0, end 46.1.

### 3.5 Tick

A periodic trigger every game loop (0.0625 s, as `c_DROP_TICK`). In
`LOOP` only:

1. Shot time `t` = clock − shot start. If `t ≥ length`: next shot (wrap
   to 0, pass +1), `t` = 0, and the cut values go on with duration 0.
2. Values at the next loop, `u` = (t + tick) / length, eased.
3. `CameraPan` to the target, `CameraSetValue` for yaw, pitch, distance,
   height offset and FOV, each over one tick (U6). DOF values only at
   cuts.
4. Script state for tests: `gv_introShot`, `gv_introPass`,
   `gv_introFov`, `gv_introHeight`, `gv_introDof`.

One trigger writes the camera in the loop. The other camera writers are
gated by the input hold (3.8). In `DROP` the drop sequence writes the
camera; the intro tick writes nothing. The dialog enforce is the scene
tick's (SPEC-HERO-DROP 3b).

### 3.6 Depth of field

At the cut into S2: depth of field on, focal depth 16, far falloff 4 to
18, near falloff 1 to 6. At the cut out of S2: the `Dflt` values. The
values are a first guess for the operator to tune (U4).

### 3.7 Creep seed

At map init, before the first frame:

- Terran, player 1: 4 Marine, 1 Goliath at X + (3.5, 3.5), then 50 back toward spawn 1.
- Zerg, player 4: 8 Zergling, 2 Roach at X − (3.5, 3.5), then 50 back toward spawn 4.
- Each group: made by `gf_CreateSpawnGroup`, 50 back toward its spawn.
  Ordered by `gf_IntroSeedOrder`: attack-move to the X center first, so
  the paths cross on X and the groups fight there; then the enemy gate
  and spawn (queued). Survivors go on along the center lane.

No units are seeded on lanes 2 and 3. The spawn timer is not changed.

### 3.8 Input gates

The scene's input hold gates 44 triggers (`gf_SceneTrigger`, SPEC-HERO-DROP
3b; none is disabled, each checks `gf_InputHeld`; text below is the
original list; the 44th is the slow walk Alt press, REQ-SLOW-WALK): jump, the move
keys, order key and button, order cancel, target clicks, unit click,
hero switch, TPS toggle, zoom, cursor and orbit keys, the abilities and
stats dialog keys, and the camera writers. Their `TriggerIsEnabled`
state is kept and restored at the end. No early returns are added to
those triggers. The hero is paused and hidden, so engine orders cannot
reach it either.

### 3.9 Deploy

SPACE (`TriggerAddEventKeyPressed`, player 1, `c_keySpace`) in `LOOP`:

At the end of the countdown (`gf_IntroDeployGo`):

1. State `DROP`. Prompt hidden. S9 hum and S4 quiet off. The theme plays
   on (operator 2026-11-18).
2. `gf_HeroDropBegin(p, hero)`, then `gf_HeroDropGo(p, null, null)`. That
   is all the intro does for the drop (R-DROP-11). The drop sequence picks
   the point, zooms, drops the pod and lands it (SPEC-HERO-DROP 3a).

Touchdown runs the drop's touchdown order. Its intro step,
`gf_IntroEnd(p)`, ends the intro's own parts only:

- `gf_IntroMusicStop`: `SoundStop` of the seat's theme, with fade;
  `gv_introMusic` = false. No music plays after touchdown (O-INTRO-1);
- prompt hidden, hum and quiet off;
- `gf_SceneLeave(p, c_SCENE_INTRO)`;
- state `DONE`, `gv_introActive` false; the intro tick and pulse off when
  no seat is in an intro.

The drop's scene leave right after it restores UI, minimap, dialogs,
cinematic mode and input, the same as after a revive.

The jump trigger is gated by the input hold on the deploy SPACE. A second
SPACE outside `LOOP` does nothing. A spawn timer expiry in `LOOP` finds
the drop in `IDLE` and starts nothing.

### 3.10 Prompt

One dialog, 900 × 48, anchored bottom, offset 24: inside the bottom
letterbox bar. One label, "Press SPACE to deploy", white, size 22,
centred. A fade between 0 and 55 % transparency, 0.8 s each way, while
the state is `LOOP`.

### 3.11 Tests off

`c_INTRO_ENABLED` is a constant in `core/intro.galaxy`, true in the map.
The test map builder (`patch_intro` in `scripts/testkit/map_builder.py`)
writes it false for every profile but `intro`. Old profiles keep their
premise: the hero alive and bound at start.

### 3.12 Build checks

`scripts/validate-map.py` (`check_intro`):

- `data/intro_shots.galaxy` equals the output of `scripts/hitvolumes/intro_shots.py`;
- `c_INTRO_ENABLED` is true in the map;
- `main.galaxy` includes the three intro files and calls `gt_Intro_Init`;
  `gt_MapInit` calls `gf_IntroStart`.

The soundtrack ids are checked in game (`MusicValid`, `SilenceValid`),
not at build.

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
| `boot` | Map start, no input. | State LOOP by 0.2 s; dialogs hidden; `Cinematic` 1; hero hidden, paused, not selectable; prompt visible; `Music` 1; seed groups polled until both reach X and both are hurt (at most 40 s); clock and spawn timer advance. | At 1 s no seed unit hurt and both group centers > 16 from X; no units added near regions 7, 9; a reinforcement fired by the harness drops no hero pod; no hero orders. |
| `shots` | For each row and variant: goto at u = 0.1, 0.5, 0.9; read two loops after. Table window: 4 loops (two waits, event order, the tick's one-loop lead). | Engine yaw, pitch (0..360, F13), distance within ±2° / ±2° / ±3 % of the eased value; script target, FOV and height against the table; `Dof` per row; S8 invariant on engine distance. Raw engine target and ground recorded (F13, F14). | `Dof` 0 outside S2. |
| `wrap` | Goto the last shot (S9) 0.5 s before its end, wait 1 s. | `Shot` 0, `Pass` +1; S2 next reads the variant; `Hum` 1 in S9. | No cut before the row length (± 2 loops); `Hum` 0 after the cut to S1. |
| `gate` | In S3: inject W for 1 s, `1`, `F`, mouse-free; read state. | Hero position unchanged, no order, state LOOP, camera values still the row's. | Each key, one at a time. |
| `seats` | Harness plays seat 2, starts its intro, presses its deploy. | Seat 2: LOOP, FALL with pod, DONE; hold, cinematic; music on in FALL, off at the end; hero shown and alive. | Seat 1 through seat 2's fall and touchdown: LOOP, active, held, cinematic, music, prompt, hero hidden, no deploy, no pod. |
| `deploy` | Inject SPACE in S5, a second 150 ms later (countdown). A third timed from the measured key latency to reach the engine 1 s into the fall. | Countdown 2.5..4 s from the engine press (`gv_introCountAt`); intro `DROP` while the drop runs; third press arrived with intro state `DROP`; `Beeps` +3 by the deploy (2026-11-20), `BeepValid`; the pod valid in `ARM` and at the zoom start, Birth read before the zoom (`zoom_armed`); `CamHeld` in `ARM`, cleared in `FALL`; `FALL` ≤ 0.5 + 0.4 s after the deploy; the zoom rows and scene flags as `herodrop` (`zoom_follow`); one pod; fall trace as `herodrop`; at touchdown hero alive at the pod, `Direct` 1, toggle defaults; `tafter` TPS, desired arm 1.0, engine distance 0.9..1.05, pitch 0 within 2 (operator 2026-11-20, was Point & Click and 1.5); scene off; dialogs and triggers restored; DONE. | `JumpPresses` 0; `Pods` 1 after both extra SPACEs; prompt hidden from SPACE on; `Music` 1 in ZOOM and FALL, 0 at touchdown; no beep and no camera hold before SPACE. The beep sound is an operator check. |

Key injection uses `scripts/testkit/input_driver.py`. No mouse input.

### 4.3 Regressions

`herodrop`, `jump hero`, `tps`, `combat switch`, and the full `combat`
run, with the intro off (3.11).

## 5. Known limits

- Tree and doodad occlusion is not checked (O-INTRO-3).
- No unit silhouettes behind buildings (operator 2026-11-18). Build step
  `disable_unit_silhouettes` (`scripts/doodad_occlusion.py`) sets
  `Occlusion` None on every model whose Occlusion resolves to Show or is
  unset, in the dependencies (`scripts/data/silhouette_models.json`, from
  `doodad_occlusion.py --refresh`) and in the map. Engine assumption: an
  unset Occlusion draws a silhouette. The look is an operator check.
- FOV and height offset have no engine getter (F5). They are checked
  through script state; the dolly zoom through engine distance.
- The engine target cannot be read in the intro (F13). The framed target
  is an operator check.
- The ground cannot be read in game (F14). S1 and S2 heights rest on the
  survey; a terrain edit under them needs the table updated.
- The look of every shot is an operator check (REQ-INTRO §4).

## 6. Runs

All on 2026-11-17, each `failures: 0`.

| Run | Scope |
| --- | --- |
| `intro/20261117-024804` | `shots` group |
| `intro/20261117-024914` | full `intro` (boot, shots, wrap, gate, deploy) |
| `herodrop/20261117-025042` | regression |
| `jump/20261117-025155` | regression, `hero` group |
| `tps/20261117-025303` | regression |
| `combat/20261117-025736` | regression, full |

Host: `testkit.tests.test_intro_shots` and `testkit.tests.test_profiles`,
24 tests OK.

2026-11-18, per-seat intro (R-INTRO-16):

- `intro/20261118-202955` (`seats`): all 35 seat checks pass; 4 boot seed
  failures (stale test: seed groups start 50 back, R-INTRO-13 revised).
- `intro/20261118-203358` (full): 30 failures, down from 34. Seed and
  seats pass. Left: 26 `dof` (every scene has near DOF, the test expects
  the far flag: the per-shot DOF work of the other session), S9 table
  distance 133.99 against 133.94 (window missed the tick's lead), countdown
  5750 ms (measured from the host request, which includes the host key latency), `tafter
  JumpPresses` 1 (the third SPACE reached the engine after touchdown). The
  last three are test fixes; rerun below.
- `intro/20261118-203746` (full): 27 failures, all 27 `dof` (above, not
  this change). Countdown 3000 ms from the engine press; key latency
  2812 ms raw; third SPACE arrived in FALL (`thirdState` 3), `JumpPresses`
  0; S9 table distance passes. No ScriptError.

## DOF (operator 2026-11-17)

- Every intro scene has near DOF (`gf_IntroSceneDof`): focus = the shot's `focus` or else its
  arm d, near falloffs (1..6) x d / 16 / (0.5 x the shot's `near`):
  falloffs are distances from the focal plane, smaller = more blur. Shot `far` > 0: far blur from far x d past the focus,
  full at 3 x that. S1: near 2.0, focus 60 instead of the arm (operator 2026-11-18: blur the trees 26..58 ahead; the BC at about 97 stays sharp). A row's `focus` (0 = arm) sets the focal depth and scales its near falloffs. S3: near 1.3. S9: near 2.0. S5: near 0.3, far 0.15. S6 (Overmind orbit): near 1.5
  (operator 2026-11-18: 4.0 was too much), far 0.3. S7: near 6.0 (operator 2026-11-18: 2.0, 4.0, then 6.0). S8: near 2.0, far 1.5.
  Far DOF (4..18) only on rows flagged `dof`; other rows push it past the far clip.
- The hero drop has near and far DOF: focus `c_DROP_POD_ARM` (the pod),
  near 1..6, far 4..18. The scene leave sets the default values; the
  in-game DOF tick takes over after touchdown.
- How the blur looks is an operator check.


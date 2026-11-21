# REQ-INTRO: Intro Sequence and Deploy

**Date:** 2026-11-17
**Status:** Revised 2026-11-19 (operator): the deploy is the hero drop
sequence of REQ-HERO-DROP, not intro code (R-INTRO-10, R-INTRO-12).
Stated by the operator on 2026-11-17. The game opens on a loop
of in-map camera shots of the map's best views, with no UI and one line
low on screen: "Press SPACE to deploy". SPACE starts the hero drop-pod
sequence. Operator choices the same day:

- the "Pride of Augustgrad" is the `MengskBC` in the river;
- the world is live behind the shots; at 00:00 two creep groups already
  fight at the center X, and only there;
- letterbox bars, provisional (O-INTRO-2);
- the SCOBA intro theme plays during the loop and the drop, and stops at
  touchdown: no music
  after deploy;
- depth of field on one tracking shot only.

The shots are described in [SCRIPT-INTRO](../specifications/SCRIPT-INTRO.md).
The implementation and the state of each requirement are in
[SPEC-INTRO](../specifications/SPEC-INTRO.md).

## 1. Scope

In scope:

- the intro loop for each played seat (REQ-ROSTER), from map start to
  that seat's SPACE (operator 2026-11-18: each player has their own);
- the shot list, its order, timing and camera values;
- the prompt line;
- the creep fight at the center X at 00:00;
- the music;
- the deploy: SPACE and the countdown; then the intro starts the hero
  drop sequence of [REQ-HERO-DROP](REQ-HERO-DROP.md) (R-DROP-10). The
  crash zoom, the pod fall, touchdown and the return to play (UI, input,
  camera, hero) belong to that sequence, not to the intro (R-DROP-11,
  operator 2026-11-19).

Out of scope:

- unplayed seats;
- a skip or replay option;
- camera collision with trees and doodads (terrain and water only);
- the look of each shot: an operator check (section 4).

## 2. Definitions

- **Intro**: the time from map start to touchdown of the deploy pod.
- **Loop**: the part of the intro before SPACE, when the shots repeat.
- **Shot**: one camera set-up with a start, an end, a length and an
  easing. Shot values are in the SPEC-INTRO shot table.
- **Pass**: one run through all shots. Passes count from 0.
- **Cut**: the change from one shot to the next in one game loop.
- **Eye**: the camera position: target, pitch, yaw and distance.
- **Center X**: region 8, the center lane crossing, at (125.3, 118.8).
- **Creep**: lane units: Terran units of player 1 and Zerg units of
  player 4 on the center lane.
- **Deploy**: what SPACE starts: the countdown, then the hero drop
  sequence (REQ-HERO-DROP R-DROP-10).

## 3. Requirements

| ID | Requirement |
| --- | --- |
| R-INTRO-1 | At map start the intro MUST run for player 1 before any input. The view opens from black. |
| R-INTRO-2 | During the intro no game UI MUST show: no engine UI frames, no map dialogs (boss bars, player bars, HUD buttons, order dialog, resources HUD). Letterbox bars MUST show. |
| R-INTRO-3 | The loop MUST play the shots in table order and restart after the last one, until SPACE. Odd passes MUST play the variant of each shot that has one (reversed move). |
| R-INTRO-4 | Each shot MUST follow its table row: target, height, yaw, pitch, distance, field of view, length and easing. |
| R-INTRO-5 | In every shot, at every moment, the eye MUST stay at least 0.5 above the ground or water under it, and the target inside the camera bounds. |
| R-INTRO-6 | Depth of field MUST be on in shot S2 only. It MUST be off in every other shot and after the intro. |
| R-INTRO-7 | The dolly-zoom shot S8 MUST keep distance × tan(FOV / 2) constant, so its subject keeps its size on screen. |
| R-INTRO-8 | The line "Press SPACE to deploy" MUST show low on screen during the whole loop, and MUST NOT show outside it. |
| R-INTRO-9 | During the intro the hero MUST NOT be in the world: hidden, paused, not selectable. Player input MUST NOT move, jump, aim, shoot, order, switch the hero or move the camera. |
| R-INTRO-10 | SPACE during the loop MUST start a 3 s countdown on the prompt line, one line: "Deploying in 3...", "Deploying in 2...", "Deploying in 1..." (operator 2026-11-17). Each number MUST play one beep for the seat (added 2026-11-20 by the operator). The loop keeps playing; further SPACE presses are ignored. Then the deploy MUST hide the prompt and start the hero drop sequence (REQ-HERO-DROP R-DROP-10): the pod births while the intro shot keeps moving, then the crash zoom (0.35 s), pod fall, touchdown. The pod MUST be birthing before the intro camera is replaced (changed 2026-11-20 by the operator; was: the zoom within 0.4 s of the deploy). The intro MUST NOT contain drop code (R-DROP-11, operator 2026-11-19). |
| R-INTRO-11 | The SPACE press that deploys MUST NOT make the hero jump. A second SPACE during the deploy MUST NOT drop a second pod. A reinforcement during the loop MUST NOT drop the hero pod. |
| R-INTRO-12 | At touchdown the hero MUST stand alive at the pod, bound as R-DROP-6: in TPS, camera arm 1.0, pitch 0 (changed 2026-11-20 by the operator), with the toggles a game without intro starts with. Letterbox MUST go, the game UI MUST come back as before the intro, input and camera control MUST return to the player. The drop sequence's scene restore does this, the same as after a revive (R-DROP-10); the intro only ends its own parts (prompt, sounds, state). |
| R-INTRO-13 | At 00:00 one Terran creep group and one Zerg creep group MUST start back from the center X, toward their own spawns, so they do not fight at once (operator 2026-11-17). They MUST walk to the X and fight there. After the fight the survivors MUST go on along the center lane. No other lane MUST get extra units. |
| R-INTRO-14 | The world MUST run during the intro: game clock, spawn timer, waves and fights as without intro. |
| R-INTRO-15 | The SCOBA intro theme (`res/audio/SCOBA_IntroTheme.wav`) MUST start with the intro. It MUST play on after SPACE, through the countdown, the zoom and the pod fall. The pod's touchdown MUST stop it. No music MUST play after touchdown. Per seat: the music stops for the seat that lands only (changed 2026-11-18 by the operator: was a Zerus theme stopped at SPACE). |
| R-INTRO-16 | Each played seat MUST have its own intro state, prompt, countdown, camera and deploy. One seat's SPACE, deploy and touchdown MUST NOT change another seat's intro. The world parts (creep seed, center fight) MUST run once per game. |
| R-INTRO-17 | At map init one Zerus tree, variation 4, at 63.75 % of the editor doodad scale (operator 2026-11-21: 15 % smaller; was 75 %, 100 %, 200 %, 275 %, 300 %), MUST stand 0.5 cells behind the eye of the S2 first-pass start, on the view line, so its leaves come into close view (operator 2026-11-21: closer to the camera path; was 1 cell, 2 cells, 3 cells). A second Zerus tree MUST stand 8 cells further down the camera's path (operator 2026-11-21; was 2 cells, too close to the first), still behind the camera, 1.25 cells from the camera path (operator 2026-11-21: further than the first; was 1.0, 0.5), at 75 % of the first tree's scale (47.81 % of the editor doodad scale; was 56.25 %) and with a different rotation (operator 2026-11-20) and a different variation, 7 (operator 2026-11-21; was 4, as the first). No other tree of the map may overlap either of the two: an overlapping map tree MUST be removed (operator 2026-11-21). |
| R-INTRO-18 | While a seat is in the intro, from the loop to touchdown, it MUST NOT see chat messages and MUST NOT hear the AI players' voice lines. This includes the AI players' own messages. After touchdown chat MUST work again, and a message sent during the intro MUST NOT show up then (operator 2026-11-21). |
| R-INTRO-19 | While a seat is in the intro, from the loop to touchdown, its mouse cursor MUST be hidden. After touchdown the cursor MUST follow the control rules again (R-TPS-31: hidden in TPS, shown in the free-cursor state and in PNC) (operator 2026-11-21). |

## 4. Acceptance

Operator checks. A person judges them; no test claims them.

| ID | Check |
| --- | --- |
| AC-INTRO-1 | Each shot reads as SCRIPT-INTRO describes it: subject, angle, move, feeling. |
| AC-INTRO-2 | No shot clips into a tree, a doodad or a unit. |
| AC-INTRO-3 | The prompt is legible in the bottom bar and pulses slowly. |
| AC-INTRO-4 | Depth of field is visible in S2: the fight sharp, foreground and far bank soft. |
| AC-INTRO-5 | S8 reads as a dolly zoom: the PsiDecimator holds still, the world behind it swells. |
| AC-INTRO-6 | The crash zoom reads as one snap, then the pod ride. |
| AC-INTRO-7 | The Zerus theme is audible from the first frame, and muted from deploy on. |
| AC-INTRO-8 | Cuts land on rhythm; the loop does not feel repetitive on the second pass. |

## 5. Open points

| ID | Point |
| --- | --- |
| O-INTRO-1 | Closed 2026-11-17: the operator chose no music after deploy. Changed 2026-11-18: the soundtrack stops at touchdown (R-INTRO-15). |
| O-INTRO-2 | Letterbox is provisional. A later choice may drop it. |
| O-INTRO-3 | Tree and doodad occlusion is not tested (AC-INTRO-2). |
| O-INTRO-4 | A skip of the loop on later games, and the intro on a hero death, are not asked for. |

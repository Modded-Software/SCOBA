# REQ-HERO-DROP: Hero Drop After Death

**Date:** 2026-11-16
**Status:** Stated by the operator on 2026-11-16: drop the hero with the
next reinforcement when it dies, in a dedicated drop pod, with the TPS
camera locked to the pod while it falls. Operator choices the same day: own
pod unit with a script fall; the hero that died; the camera stays at the
death spot until the drop; the same unit revives with its level. After
play: the camera arm was too close to the pod (R-DROP-4). Revised
2026-11-18 (operator): every played seat has its own drop
([REQ-ROSTER](REQ-ROSTER.md)); the hero may come back as a fresh unit with
its stats carried; a hero that died naturally after a return did not come
back (R-DROP-8). Revised 2026-11-19 (operator): the revive drop looked
different from the intro deploy drop (no Birth fall to follow); one drop
sequence, one code path, no redundancy, not part of the intro (R-DROP-10,
R-DROP-11). The specification lists the state of each requirement and
the run that backs it.

## 1. Scope

In scope:

- the death of the active hero of each played seat (REQ-ROSTER);
- the wait until the next reinforcement;
- the drop sequence: scene, crash zoom, the hero's own pod, its fall,
  its touchdown, the scene restored;
- the intro deploy: it is the same drop sequence (REQ-INTRO R-INTRO-10);
- the camera during the wait and the fall;
- the hero coming back: its type, level, toggles and control mode;
- every later death of the same seat.

Out of scope:

- a death of the parked hero (hidden and paused, it takes no damage);
- unplayed seats (no hero, REQ-ROSTER R-ROSTER-5);
- a respawn timer of its own: the reinforcement timer is the clock;
- pod sound and look beyond the stock Terran pod model.

Implementation lives in
[SPEC-HERO-DROP](../specifications/SPEC-HERO-DROP.md).

## 2. Definitions

- **Hero**: the unit a played seat controls (`gv_tPSUNIT[p]`).
- **Reinforcement**: an expiry of the spawn timer `gv_sPAWNTIMER` (every
  40 s), when the lane spawns drop.
- **Pod**: the hero's own drop pod unit (`SCOBAHeroPod`).
- **Pod height**: the pod height above the ground, as the engine reports it
  (`UnitGetHeight`).
- **Drop sequence**: scene on, crash zoom onto the drop point, pod fall,
  touchdown, scene off. One sequence for every drop.
- **Scene**: cinematic mode (letterbox), no game UI and no map dialogs,
  the seat's input held. Shared by the intro loop and the drop sequence.
- **Starter**: what starts a drop sequence: the intro deploy (SPACE) or a
  reinforcement while the hero is dead.

## 3. Requirements

| ID | Requirement |
| --- | --- |
| R-DROP-1 | When the hero dies, it MUST wait for the next reinforcement. A reinforcement while the hero lives MUST NOT drop a pod. |
| R-DROP-2 | While the hero waits, the camera MUST stay where the hero died. |
| R-DROP-3 | At the next reinforcement one pod MUST appear above a point of the seat's spawn region and fall to the ground, never rising, in about 2.2 s, on the stock pod fall curve. The pod MUST be the hero's own: no reinforcement unit rides in it. |
| R-DROP-4 | While the pod falls, the camera MUST be locked to the pod: on its point, with the pod height in the camera height offset in the same loop time as the pod, and an arm long enough for the pod model. Revised 2026-11-16: an arm of 8 was too close. |
| R-DROP-5 | At touchdown the pod MUST hit the ground as a reinforcement pod does (crush impacts, quake) and open. |
| R-DROP-6 | At touchdown the hero MUST come back alive at the pod: same unit type, full life, its level, and its Attack and Chase toggles. It MAY be a fresh unit (operator 2026-11-18). The camera MUST return to the hero with no pod height. Changed 2026-11-20 by the operator: after every touchdown the hero MUST be in TPS, whatever mode it died in; the camera arm MUST be the minimum distance to the target (1.0, the mouse-wheel minimum); the camera pitch MUST be 0 (level, straight ahead). The target height stays as R-TPS-90. Was: the mode the hero died in, the hero arm, pitch 30. |
| R-DROP-7 | While the hero waits or the pod falls, the hero switch MUST NOT change the hero. |
| R-DROP-8 | Every death of a returned hero MUST start the same wait and drop again, with no limit on the count. |
| R-DROP-9 | One seat's death, wait, fall and return MUST NOT change another seat's hero, camera or input. |
| R-DROP-10 | Every drop MUST run the one drop sequence (operator 2026-11-19): scene on; the pod created and playing Birth; once the engine reports Birth, the crash zoom onto the drop point at the drop yaw, ending on the fall camera at the pod's clip time, with the drop FOV and DOF from its first frame (changed 2026-11-20 by the operator: the camera MUST NOT change before the pod is ready and birthing; was: the zoom first, the pod at its end); the pod fall of R-DROP-3, R-DROP-4; touchdown R-DROP-5, R-DROP-6; scene off. The intro deploy and a revive MUST produce the same scene, zoom, camera values, fall and restore. They MAY differ only in the starter, the drop point's spawn region and the points it avoids, the hero's state before touchdown (hidden or dead), and what the intro owns (its music). |
| R-DROP-11 | The drop sequence MUST exist once in code, outside the intro (operator 2026-11-19: one code path, zero redundancy). The intro and the reinforcement MUST only start it. No camera, scene or pod call of a drop MUST exist outside it. |
| R-DROP-12 | A pod fall sound MUST play for the seat when the pod is created and starts Birth (operator 2026-11-20: the drop had no sound). |
| R-DROP-13 | Every pod, hero and lane, MUST land on a free 4x4 cell square in or near the spawn region: all cells ground pathable on one cliff level, no building or doodad footprint, no ground unit within 2.5, at least 4 from the other pods of the wave (operator 2026-11-20: pods landed on buildings). Was: a random point of the region. |
| R-DROP-14 | Every hero drop, intro deploy and revive, MUST bring one extra land creep wave of the seat's lane, in pods (operator 2026-11-20). The hero pod falls toward the southwest; the escort pods MUST fall in the same direction. A reinforcement while the hero lives MUST NOT bring an escort. A Terran escort wave MUST always have a Goliath, also when the seat already has one (operator 2026-11-20); the reinforcement wave keeps its rule (a Goliath only while the seat has none). |

## 4. Acceptance

| ID | Check |
| --- | --- |
| AC-DROP-1 | Die in TPS: the camera holds at the death spot. At the next reinforcement the letterbox comes in, the view crash-zooms onto the drop point, then rides the pod down, as the intro deploy does. |
| AC-DROP-4 | The intro deploy and a revive drop look the same: letterbox, no UI, zoom, pod Birth fall, touchdown (`scripts/playtest.sh dropview`). |
| AC-DROP-2 | The pod fits in the view during the fall and the landing. |
| AC-DROP-3 | At touchdown the ground shakes, the pod opens, the hero stands at the pod in TPS. |

## 5. Open points

| ID | Point |
| --- | --- |
| O-DROP-1 | Closed 2026-11-20: R-DROP-12. |
| O-DROP-2 | A respawn countdown on screen: the reinforcement countdown already shows in the player bars. |

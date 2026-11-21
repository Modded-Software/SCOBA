# SPEC-SCENERY: permanent scenery

Implements `docs/requirements/REQ-SCENERY.md`. Code:
`src/SCOBA.SC2Map/scripts/app/systems/scenery.galaxy`.

## 1. State

| ID | State | Evidence |
| --- | --- | --- |
| R-SCN-1 | [tested] [operator] | `herodrop/20261120-204450` `scenery`: `stormCount` 6, 6 actors, all in the playable map, farthest 30.4 from the Overmind unit (negative: none past 32), actor id valid. Look and sound: AC-SCN-1 |
| R-SCN-2 | [tested] [host] [operator] | Same run: `s6Made` 3, 3 `ZergDropPod` units; negative: a second call makes none. Host: `test_intro_shots.py` `test_s6_pods_in_the_near_view`. The call from the S6 cut in a live intro is not run. Look: AC-SCN-2 |
| R-SCN-3 | [tested] [operator] | Same run: 2 neutral `SCOBAWraith`, alive, invulnerable, no life lost, inside the map; each sweeps more than a lap in 18 s in its own direction (565 and -619 degrees); ellipse residual 0.76..0.79; nearest 1.7, farthest 26.6 and 21.3 from the Psi Destroyer. Negative: the Terran air creep count does not include them. Look: AC-SCN-3 |
| R-SCN-5 | [host] [operator] | Not run in game. Design: `ActorData.xml` `CActorDoodad ZerusTree`: `On ActorCreation`, `AnimSetTimeScaleGlobal 0.25`. The 209 `ZerusTreeFp*` clones and `ZerusTreeScobaBorder` have `parent="ZerusTree"` in the built map and inherit it. The two intro trees are model actors (`libNtve_gf_CreateModelAtPoint`), not doodads: `gf_IntroTreePlace` sends the same message, `c_TREE_ANIM_SPEED` 0.25. Host: `test_treevary.py` `TreeSwayTest` (the event, no source tree actor of its own, both intro sends). Unconfirmed: that the event reaches doodad actors, and that `ModelSwap` before it keeps the speed. Particles: the actor time scale does not reach them (operator 2026-11-21). Of the 15 stock variations only `zerustree_09` and `zerustree_10` have particles: two emitters each, speed 0.55..0.77, life 2..5 s, rate 10, no gravity, no drag. `slow_death_assets.py` `SLOW_SIMULATIONS` writes both to `Assets/Doodads/ZerusTree/ZerusTree_09.m3` and `_10.m3` (the stock path; the map file replaces the variation, ModelData unchanged) with simulation stretch 4: speed / 4, life x 4, rate / 4, keyframes unchanged, so the vapour rises 4x slower to the same height and density. Host: `test_slow_death.py` `test_tree_particles_match_the_tree_speed`. Build: `check_slow_simulations` (both files, with particles). Unconfirmed: that the map copy replaces the stock variation. The sway and the vapour on screen: operator check |

## 2. Design

- **Storms.** `gf_StormsPlace` at map init: `c_STORM_COUNT` (6) actors
  `ThunderLightning` (liberty.sc2mod doodad actor,
  `libNtve_gf_CreateActorAtPoint`) at points uniform over the disc of radius
  32 around the Overmind unit. A point outside the playable map is drawn
  again (the Overmind stands in a map corner).
- **S6 pods.** `scripts/hitvolumes/intro_shots.py` `s6_pods()` gives three
  points 64, 70 and 76 cells ahead of the S6 eye at the middle yaw, -4, +4
  and 0 to the side. `gf_IntroCutAt` calls `gf_SceneryS6Pods` on a cut into
  S6 on pass 0. It runs once per game (`gv_s6PodsDone`). Each pod: a free
  4x4 spot near its point (`gf_DropPodPoint`), the lane pod impact
  (`gf_PodImpactQueue`), `libVCMI_gf_CreateDropPod` with an empty group,
  owner: the Overmind's owner.
- **Wraith orbits: removed** (operator 2026-11-20, R-SCN-3 withdrawn).
  The code is deleted. The harness checks that no neutral `SCOBAWraith`
  exists; this check is not run yet. The text below is history.
- **Wraith orbits (history).** `gf_OrbitsPlace` at map init. Two `SCOBAWraith`, player
  0, invulnerable, not targetable, not selectable, speed 9.
  - Ellipse 0: half axes 16 and 10, long axis toward 225 from the Psi
    Destroyer, counter-clockwise. Ellipse 1: 13 and 8.5, toward 250,
    clockwise. The Psi Destroyer is at a focus.
  - Every 0.25 s each Wraith gets a move to the ellipse point 35 degrees of
    parametric angle ahead of its own (`gf_OrbitSteer`).

  - Height `c_ORBIT_HEIGHT` 14, not the air creep height 72, so they are in
    the frame of intro shot S9 (operator 2026-11-20: none was visible).
    [tested] `herodrop/20261120-213652` `scenery`: height 13..15. In the S9
    frame: operator check.
- **Changed 2026-11-20** (operator: closer to the camera): the S6 pods are
  54, 58 and 62 ahead, -3, +3 and 0 to the side. The eye is 33.6 above the
  ground; ground nearer than about 54 is under the frame.
- **Changed 2026-11-20, second round** (operator). This replaces the numbers
  above. [tested] `herodrop/20261120-220934` `scenery`, `failures: 0`.
  - Storm radius `c_STORM_RADIUS` 16 (was 32). Farthest storm 15.22;
    negative: none past 16.
  - S6 pods 46, 52 and 60 ahead, -6, +6 and 0 to the side. One game second
    between two pods (`c_S6_POD_GAP`). Pods made at 0.5 s steps: 1, 2, 2, 3,
    3, 3 (negative: not all at once). Smallest distance between two: 14.14.
    The nearest pod is at the lower edge of the frame on level ground.
  - Ellipses: half axes 26 and 12 (long diameter 52), and 24 and 11 (48).
    Height `c_ORBIT_HEIGHT` 22 (was 14) in that run; then 44 (operator
    2026-11-20: at least 2x). Farthest from the Psi Destroyer
    45.65 and 42.31; a full lap each, opposite directions; none out of the
    map. The Psi Destroyer is still at a focus, not at the centre: it is 6
    cells from the playable edge.
- **S7 camera pod** (R-SCN-4, operator 2026-11-20). `gf_SceneryS6Pods`
  also starts `gt_SceneryS7Pod` at the S6 cut. It waits the S6 length (6 s)
  less `c_POD_DELAY_ZERG` (2.383 s), game time, then drops one empty Zerg
  pod on `c_INTRO_S7_EYE_X/Y` (64.98, 64.98), the S7 eye at the cut (the
  row start) on the ground plane, generated by `s7_eye()`. Target, yaw
  and distance hold over S7; the pitch moves from -20 to -35, so the eye
  drifts about 1.1 toward the target after the cut. No spot search: the
  point is the camera's. Host: `test_s7_pod_lands_on_the_eye_at_the_cut`. In game:
  `scenery` keys `s7Made`, `s7LandMs`, `s7Off100`, `s7NearUnits`; not run
  yet. Limits: the landing time is the creation time plus the measured pod
  fall, not an impact event; the pod and the S7 camera start from the S6
  cut, so a seat that joins the loop later sees it at another time.

## 3. Facts from runs

| ID | Fact | Source |
| --- | --- | --- |
| F1 | An ellipse centred on the Psi Destroyer has room for a half axis of 4 only. | `herodrop/20261120-204148` |
| F2 | A Wraith at speed 9 circles a waypoint at about 4.5 and never comes within 4. Waypoints with a reach do not work. | `herodrop/20261120-204148` |

## 4. Tests

`scripts/playtest.sh herodrop scenery`. Harness
`scripts/testkit/galaxy/herodrop_scenery.galaxy`, checks
`scripts/testkit/profiles/herodrop_scenery.py`.

## 5. Known limits

- The storm doodad's look and its thunder sound are not tested.
- The S6 pods are tested by a direct call, not through a live intro pass.
- The S6 host test takes the ground as level.

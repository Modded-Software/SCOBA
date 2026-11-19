# SPEC-ROSTER: Player Roster and Multiplayer Seats

**Date:** 2026-11-18
**Requirements:** [REQ-ROSTER](../requirements/REQ-ROSTER.md)

## 1. Requirement state

States: `[planned]` = not built; `[built]` = code exists, no test passed;
`[tested]` = an in-game or build check passed in a named run;
`[operator]` = only a person can judge it.

| ID | State | Backed by |
| --- | --- | --- |
| R-ROSTER-1 | [build] | `player_slots.check_script`: `gf_RosterOwner` matches `player_slots.LANES` (validator, `test_player_slots`). Owner numbers outside the table and a non-zero default return fail the check (`test_script_owner_outside_table`) |
| R-ROSTER-2 | [tested] | `roster/20261118-201457` `rs_table`: players 9..14 type 2, race, status 1, lane, owner |
| R-ROSTER-3 | [build] [operator] | `player_slots.check` of MapInfo and Attributes in the validator; the lobby itself: AC-ROSTER-1 |
| R-ROSTER-4 | [tested] | `roster/20261118-201457` `rs_table`: `inBad` 0, `crossBad` 0 (passive and vision, both ways, 7 x 7 pairs) |
| R-ROSTER-5 | [tested] | `roster/20261118-201457` `rs_seats`: seat 1 hero and wallet; seats 2..6 no hero, no wallet, no pod; every lane's wave made and ordered. Base AI per owner: `baseai` |
| R-ROSTER-6 | [tested] | `herodrop/20261118-202228` `drop_seat2`: seat 2 death, pod, fresh return owned by 2; seat 1 hero same, alive, not held, yaw unchanged |
| R-ROSTER-7 | [built] | the touchdown facing is `c_DROP_YAW`, not the camera yaw. No build check yet |
| R-ROSTER-8 | [tested] | `herodrop/20261118-202228` `drop_leave`: `gf_RosterLeave(2)` mid-fall: pod gone, hold off, not pending, not played, no landing. The engine leave event: operator (AC-ROSTER-1) |

## 2. Facts

| ID | Fact | Source |
| --- | --- | --- |
| F1 | Source MapInfo: players 1 and 4 user; 2, 3, 5, 6, 7, 8 computer; 9 to 14 neutral; 15 hostile. The build makes 9 and 10 computer. | `slots_probe.py` 2026-11-18 |
| F2 | Source Attributes (controller 500): slots 0, 1, 7, 8 `Open`; slots 2 to 6 `Comp`, locked. | `Attributes` |
| F3 | Waves are made for the seat player (lane N: player N), not for the base owner. | `systems/spawns.galaxy` |
| F4 | The map places `Tosh` for player 1 and `Kerrigan` for player 4. | `Objects` |

## 3. Design

### 3.1 Table (`core/roster.galaxy`)

| Lane | Seat | Team | Base owner | Human seat | Seat hero |
| --- | --- | --- | --- | --- | --- |
| 1 | 1 | Terran | 9 | yes | `ToshSCOBA` |
| 2 | 2 | Terran | 11 | yes | `ToshSCOBA` |
| 3 | 3 | Terran | 12 | yes | `ToshSCOBA` |
| 4 | 4 | Zerg | 10 | no | none |
| 5 | 5 | Zerg | 13 | no | none |
| 6 | 6 | Zerg | 14 | no | none |

- `gf_RosterOwner(lane)`, `gf_RosterSeat(lane)`, `gf_RosterTerran(lane)`,
  `gf_RosterHumanSeat(lane)`, `gf_RosterHeroType(lane)`,
  `gf_RosterLaneOf(player)` (a seat or a base owner), `gf_RosterIsOwner(player)`.
- `gv_rosterPlayed[p]`: set at map init for a human seat with
  `PlayerType` user and `PlayerStatus` active. Tests set it with
  `gf_RosterPlay(p, on)`.
- `gv_rosterHero[p]`: the seat hero. The active hero stays
  `gv_tPSUNIT[p]`.
- The base AI, waves, wallet, hire, medic and alliances call the table.

### 3.2 Build (`scripts/mapgen/player_slots.py`)

- Base owners 9, 11, 12 Terran, 10, 13, 14 Zerg: computer, race set, lobby
  `Comp` locked.
- Seats 1 to 3: user, Terran, lobby `Open`. Seats 4 to 6: computer, Zerg,
  lobby `Comp` locked.
- The check fails the build on any other state.

### 3.3 Seat hero

- Seat 1: the placed `Tosh` is replaced by `ToshSCOBA` (as now). Seats 2
  and 3: `ToshSCOBA` created at the lane spawn when played.
- Player 1 keeps the developer bodies (Alt+2 Kerrigan, Alt+3 SCV, Alt+4
  Viking) and the switch keys; `gv_heroActive` is player 1's switch state.
- An unplayed seat: no hero, no pod, no wallet, no intro.

### 3.4 Per-seat modules

| Module | Job |
| --- | --- |
| `systems/hero_drop` | Per seat: one death trigger for all played seats (`gf_UnitIsHero`); the wave calls `gf_HeroDropStart(p, at)`; the pod, its clock and its camera shot. Fixed yaw `c_DROP_YAW`. |
| `systems/hero_return` | Touchdown: a fresh hero unit of the dead hero's type at the pod; current stat values (`c_unitPropCurrent`) and learned abilities carried; the dead unit removed; `gf_HeroBindPlayer(p, unit)`. No `UnitRevive`. |
| `core/input_hold`, `systems/intro_ui` | `gv_inputHeld[p]`. Every gated trigger checks `gf_InputHeld(player)` first; no trigger is disabled. |
| camera guards | No separate owner module. The writers read the seat's own state: `camera_refollow` (intro, pending, pod), `camera_dof` (intro, pod), `camera` clamp (pod), all `[p]`. |
| `systems/intro`, `intro_flow` | State, prompt, countdown, shot per seat; Space per seat (`EventPlayer()`). Scenery (seed units, prompt dialog) once for the game. |

### 3.5 Leave

`gt_RosterLeave` (player leaves): `gf_RosterLeave(p)` ends the drop,
releases the input, ends the intro, removes the pod.

## 4. Tests

| Profile | Scenario | Asserts | Negative case |
| --- | --- | --- | --- |
| `roster` | `table` | Owners 9..14 computer with race; alliances per team | No cross-team ally |
| `roster` | `seats` | Seat 1 hero valid; waves of seats 2, 3 created and ordered | Seats 2, 3: no hero, no pod, wallet 0 |
| `herodrop` | `drop_seat2` | Seat 2 played by the harness: death, wave, pod, return | Seat 1 input, camera owner, hero unchanged |
| `herodrop` | `drop_twice` | Three deaths by enemy damage, three fresh returns, type and life max kept | Old unit gone; no removal after a later death |
| `intro` | `seats` | Seat 2 intro: deploy, fall, touchdown, hold off | Seat 1 stays in LOOP, prompt, music, held, no pod |
| `herodrop` | `drop_leave` | `gf_RosterLeave(2)` mid-fall: pod gone, hold off | No return later |

Two clients and the lobby are operator checks (AC-ROSTER-1, 2).

## 5. Files

| File | Role |
| --- | --- |
| `scripts/app/core/roster.galaxy` | Table, played seats |
| `scripts/mapgen/player_slots.py` | Player records, lobby |
| `scripts/app/systems/hero_drop.galaxy`, `hero_return.galaxy` | Drop and fresh return |
| `scripts/app/core/input_hold.galaxy` | Per-seat hold |
| `scripts/app/systems/roster.galaxy` | Leave |
| `scripts/app/systems/intro.galaxy`, `intro_flow.galaxy` | Per-seat intro |

## 6. Known limits

- `gv_abilitiesButtons` (learned abilities) and the dialog ids are one table
  for all players: a second played seat shares them. Not per seat yet.
- Two seats run the intro on one client in the `intro` `seats` test only; real network sync is untested (operator).
- `gv_heroActive`, `gv_heroTosh`, `gv_heroKerrigan` are player 1's
  developer switch state.

## 7. Runs

- `roster/20261118-200814`: 7 failures. Empty seat 2 had a hero handle:
  `gf_HeroUnit(2)` returned `gv_heroKerrigan` (fixed: roster seat hero).
  Waves of lanes 3 and 6 missing after a fixed 14 s wait: the lanes drop
  one after the other (test fixed: polls until ordered, at most 60 s).
- `roster/20261118-201457`: 0 failures.
- `intro/20261118-201711` (per-player hold): 34 failures, the same set as
  `intro/20261118-191202` (DOF checks, seed group, S9 distance, countdown
  6750 ms, `tafter JumpPresses` 1). All hold checks pass: `InputHeld`,
  `InputHeld2` false, `TrigOn` = `TrigAll`.
- `herodrop/20261118-202228`: 0 failures (`drop_main`, `drop_twice`,
  `drop_seat2`, `drop_leave`). Raw: `dead1..3ByDamage` False: self-damage
  did not kill, the second path, `UnitKill`, did. Stat keep read the normal value
  (life max 300 normal, 350 current). Fixed: an enemy Zergling deals the
  damage and `ByDamage` is asserted; the keep reads `c_unitPropCurrent`.
- `herodrop/20261118-203207`: 0 failures. `dead1..3ByDamage` True,
  `back1..3LifeMax` 350, `deadByDamage2` True.
- `intro/20261118-202955` (group `seats`): seat checks pass. 4 failures in
  `boot` seed checks, the same as the earlier baseline: the test expected
  the seed groups at X at 1 s, but they start 50 back (fixed in the test).
- `intro/20261118-203746` (full): 27 failures, all `dof` (per-shot DOF
  checks of the other session); `seats` all pass.
- Regressions after the change: `roster/20261118-203952` 0 failures;
  `combat/20261118-204348` 0; `podbirth/20261118-204123` 5, the same 5 as
  `podbirth/20261118-191358` (pod camera checks older than the fixed-yaw
  drop camera); `baseai/20261118-204818` (`probe`) 1, see SPEC-BASE-AI 9.
  Host: 145 tests OK; galaxy lint 145 files OK.

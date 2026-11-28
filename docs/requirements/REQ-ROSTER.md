# REQ-ROSTER: Player Roster and Multiplayer Seats

**Date:** 2026-11-18
**Status:** Stated by the operator on 2026-11-18:

- up to six players, real multiplayer;
- each player has their own intro and their own deploy press;
- lane base owners 9, 11, 12, 10, 13, 14 for lanes 1 to 6;
- an empty seat keeps its waves and its base AI, and has no hero;
- humans play Terran only (operator 2026-11-18); Zerg heroes are to be decided;
  Kerrigan is a proof of concept and is not a seat hero;
- three Toshes (operator 2026-11-18).

The specification lists the state of each requirement.

## 1. Scope

In scope:

- one table of lanes, seats, teams, base owners and seat heroes;
- the lobby slots and the map's player records;
- a hero per human seat, its death, drop and return;
- each seat's intro, input hold and camera, apart from the other seats.

Out of scope:

- Zerg human seats and Zerg heroes (O-ROSTER-1);
- a hero pick screen (O-ROSTER-2);
- a bot hero on an empty seat;
- victory and defeat;
- the developer bodies of player 1 (Alt+2 Kerrigan, Alt+3 SCV, Alt+4
  Viking): they stay a player 1 debug tool.

## 2. Definitions

- **Lane**: one of the six lane spawns, 1 to 6 (`gv_sPAWNLOCATIONS`).
- **Seat**: the player that owns a lane's waves: player N for lane N.
- **Human seat**: a seat a person may take in the lobby: seats 1 to 3.
- **Played seat**: a human seat a person took (an active user player at
  map init).
- **Base owner**: the computer player that holds a lane's town hall and
  runs the stock AI.
- **Seat hero**: the unit a played seat controls.

## 3. Requirements

| ID | Requirement |
| --- | --- |
| R-ROSTER-1 | One table in the map script MUST hold, per lane: seat, team, base owner, human seat flag, seat hero type. No other script code MUST name a lane's base owner or seat by number. |
| R-ROSTER-2 | Base owners MUST be 9, 11, 12 (Terran) and 10, 13, 14 (Zerg) for lanes 1 to 6. The build MUST make them computer players with their race. |
| R-ROSTER-3 | Seats 1 to 3 MUST be open user slots, Terran, in the lobby and in the player records. Seats 4 to 6 MUST be locked computer slots, Zerg. |
| R-ROSTER-4 | Each team MUST be one alliance with shared vision: its seats, its base owners and its corner player. |
| R-ROSTER-5 | Each played seat MUST get its own seat hero (`ToshSCOBA`) at its lane spawn. A seat that is not played MUST get no hero, no pod and no wallet; its waves and its base AI MUST run as on a played seat. |
| R-ROSTER-6 | Hero state MUST be per seat: active hero, death, drop, return, input hold, camera owner, intro. One seat's state MUST NOT change another seat's. |
| R-ROSTER-7 | The death, drop, return and intro logic MUST NOT read the camera. (TPS movement reads it by design, O-ROSTER-3.) |
| R-ROSTER-8 | When a player leaves, their pending drop, held input and intro MUST end. |
| R-ROSTER-9 | A unit's side (Terran or Zerg) MUST come from the roster table, not from the owner's race. An empty seat has no race (`PlayerRace` is "", roster run 2026-11-18), yet its waves MUST go on to the enemy spawn at the X like a played seat's (operator 2026-11-19: "the ally lanes are retreating and clustering with the army of the macro AI"). |
| R-ROSTER-10 | The roster MUST name the middle lanes: lane 1 (Terran) and lane 4 (Zerg), the lanes that meet at the center X (REQ-INTRO). The base AI lane mode reads them (REQ-BASE-AI R-BASE-37). |

## 4. Acceptance

| ID | Check |
| --- | --- |
| AC-ROSTER-1 | Lobby: three Terran slots open, three Zerg computer slots locked. |
| AC-ROSTER-2 | Two clients: each person gets a Tosh, an intro and a deploy press of their own; one person's death and drop do not move the other's camera or block their input. |

## 5. Open points

| ID | Point |
| --- | --- |
| O-ROSTER-1 | Zerg heroes and Zerg human seats: to be decided. |
| O-ROSTER-2 | A hero choice per seat: the table has a hero type column for it. |
| O-ROSTER-3 | TPS movement reads each client's camera direction; network sync of that is not tested on one client. |

Implementation lives in [SPEC-ROSTER](../specifications/SPEC-ROSTER.md).

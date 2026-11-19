# REQ-BASE-AI: Bases, Resources and AI Assistance

**Date:** 2026-11-18
**Status:** Stated by the operator on 2026-11-18 as the new core gameplay
loop. Operator choices the same day:

- the AI is the full stock melee AI (economy, production, army);
- the timed reinforcement waves stay: they are the early counter to a hero
  rush;
- resources go to the lane spawns and to expansion sites;
- the Zerg jungle sites are made by the build, where the Lurkers are;
- the AI starts at map init.

Nothing is built yet. The specification lists the state of each requirement.

## 1. Scope

In scope:

- resource sites on the map;
- a starting base and workers for each lane player;
- the stock AI at the highest difficulty for each lane player;
- the lane player's ownership of, and orders to, the units the AI makes;
- the units the AI must leave alone.

Out of scope:

- victory and defeat conditions;
- a resource or supply display in the HUD;
- selecting and ordering more than one unit at a time (order mode orders
  one unit, see O-BASE-1);
- Protoss;
- changes to the reinforcement waves, the air creeps, the hero drop, the
  intro, the lane gates and order mode;
- balance of AI armies against heroes and waves.

Implementation lives in
[SPEC-BASE-AI](../specifications/SPEC-BASE-AI.md).

## 2. Definitions

- **Lane player**: the lane's base owner in
  [REQ-ROSTER](REQ-ROSTER.md): 9, 11, 12 (Terran, lanes 1 to 3) and 10,
  13, 14 (Zerg, lanes 4 to 6). Revised 2026-11-18 (operator): the seats 1
  to 6 own the lane waves and the heroes; the base owners own the town
  halls and run the AI. Each lane has one spawn region
  (`gv_sPAWNLOCATIONS`), where R-BASE-1 and R-BASE-9 apply.
- **Corner player**: players 7 (Terran) and 8 (Zerg). They hold the corner
  bases.
- **Site**: a place with 8 mineral fields and 2 vespene geysers around a
  free spot for a town hall.
- **Main site**: the site of a lane spawn.
- **Expansion site**: a site with no starting base.
- **Town hall**: a Command Center (Terran) or a Hatchery (Zerg).
- **AI unit**: the starting town hall, the starting workers, the starting
  Overlord, and every unit or structure made from them.
- **Script unit**: a unit of a lane player that is not an AI unit. The
  heroes, the hero pods, the companions, the Medics, the aim target
  dummies, the reinforcement wave units, the air creeps, the intro seed
  units and the units placed in the map source.
- **Reinforcement**: an expiry of the spawn timer `gv_sPAWNTIMER` (every
  40 s), when the lane spawns drop their pods.

## 3. Requirements

### 3.1 Resource sites

| ID | Requirement |
| --- | --- |
| R-BASE-1 | Each of the 6 lane spawns MUST have one main site. |
| R-BASE-2 | The map MUST have 12 expansion sites: two at each Terran jungle region (Left, Right), two at each of the two Zerg jungle places, and two at each guarded camp (Brakk, infested siege tank): one toward the map centre, one behind the camp (operator 2026-11-18). |
| R-BASE-3 | The build MUST compute the two Zerg jungle places from the Lurkers placed in the map source: one place per Lurker group. No coordinate of them is written by hand. |
| R-BASE-4 | Each site MUST have 8 mineral fields and 2 vespene geysers, with free ground for a town hall that workers can reach from every field and geyser. |
| R-BASE-5 | No part of a site MUST lie on unpathable ground or on another site. Sites are placed first; trees, placed units and flora are fitted around them (R-BASE-31). |
| R-BASE-6 | No site MUST block a lane. A unit MUST still walk each lane from spawn to enemy spawn through both gates. |
| R-BASE-7 | Flora and lane hazards MUST keep out of the sites. |
| R-BASE-8 | The build MUST place the sites. The same map source MUST give the same sites on every build. The build MUST fail when R-BASE-1 to R-BASE-7 do not hold. |

### 3.2 Starting bases

| ID | Requirement |
| --- | --- |
| R-BASE-9 | At map init each lane player MUST get one town hall on its main site: a Command Center for players 1 to 3, a Hatchery for players 4 to 6. |
| R-BASE-10 | At map init each lane player MUST get 12 workers at its town hall: SCVs for Terran, Drones for Zerg. Each Zerg lane player MUST also get one Overlord. |
| R-BASE-11 | At map init each lane player MUST have 50 minerals and 0 vespene. |
| R-BASE-12 | The corner players MUST NOT get a base, workers or resources from this feature. |

### 3.3 AI assistance

| ID | Requirement |
| --- | --- |
| R-BASE-13 | From map init the stock melee AI MUST run for each lane player at the highest stock difficulty (Cheater Insane). This includes the lane players a person plays. |
| R-BASE-14 | The AI MUST do the macro: gather, build structures, train units, expand to expansion sites. It MUST also run its army, as the stock AI does. |
| R-BASE-15 | The AI MUST run during the intro. |
| R-BASE-16 | The lane player MUST own every AI unit. No AI unit MUST belong to another player. |
| R-BASE-17 | A lane player MUST still be able to order its AI units. An order to an AI unit MUST be accepted and the unit MUST act on it. |
| R-BASE-18 | The AI MUST NOT change what a person controls: the hero, the control mode, the camera, the selection, the toggles. |
| R-BASE-19 | The corner players MUST NOT get an AI from this feature. |

### 3.4 Script units

| ID | Requirement |
| --- | --- |
| R-BASE-20 | The AI MUST NOT order a script unit and MUST NOT put it in an AI wave. |
| R-BASE-21 | A script unit MUST NOT use supply of its player. |
| R-BASE-22 | The reinforcement waves MUST drop as before and walk their lanes through the gates as before. |
| R-BASE-23 | The air creeps, the hero drop, the intro, the lane gates and order mode MUST behave as before. |

### 3.5 Melee map (operator 2026-11-18)

The stock melee AI must find its towns, expansions and enemies from map
data, as on a ladder map. No script may drive its expansion or attacks.

| ID | Requirement |
| --- | --- |
| R-BASE-24 | The map MUST have one start location per base owner (9, 11, 12, 10, 13, 14), at its main site. No start location for seats 1 to 6 or for players 7 and 8. |
| R-BASE-25 | `PlayerStartLocation(owner)` MUST return that start location. |
| R-BASE-26 | Every mineral field and geyser of every site MUST be a placed map object in the built map, with the amounts of `c_SITE_RES_MULT` (4x stock). No script makes resources. |
| R-BASE-27 | The AI MUST be started with the stock `AIMeleeStart(owner)`. |
| R-BASE-28 | No script MUST call `AIExpand` or set an attack state for an owner. |
| R-BASE-29 | The six Supply Depots placed in the map source MUST belong to the Terran base owners, two each: 9, 11, 12, one pair per base. Player 7 MUST own none. |
| R-BASE-30 | The Command Center family MUST NOT block pathing and MUST NOT need clear ground around it: units walk under it, and it may stand on a mineral field (operator 2026-11-19, after "Failed to expand there" by player 9). The Command Center model is scaled x1.2 over the earlier 3.0 so small units fit under it. A grounded hall MUST block the cells where its scaled model meets the ground (the legs, R-FP-10), and other buildings MUST NOT overlap them (operator 2026-11-19, after the AI built a Barracks against a hall). Its middle MUST stay open, so workers reach it to drop off cargo (a blocker in the middle stopped mining). Lifted, it blocks nothing; landed, it blocks again where it stands. |
| R-BASE-31 | Build order (operator 2026-11-18): the build MUST place the sites first. Then every source tree inside a site keep-out MUST move to the nearest free spot, and every placed unit inside one MUST move, each unit alone, to its nearest free cell. Then tree blockers and flora are made. |
| R-BASE-32 | Mineral fields and geysers MUST spread organically: varied radius, angle and depth per pile, seeded per site, so the same source gives the same layout. Optimal mining distance is not required. |

### 3.6 Live game (operator 2026-11-18)

"Make everything aggressive, fast and interesting." Losses are part of the
game.

| ID | Requirement |
| --- | --- |
| R-BASE-33 | Tests MUST count losses. An owner that loses units MUST react: supply made plus supply lost keeps growing, and lost units are replaced. |
| R-BASE-34 | The AI MUST play aggressively and fast: owners attack early and repeatedly, and expand while they fight. Only stock AI behaviour and map data drive it (R-BASE-28). |

## 4. Acceptance

Operator checks. A test cannot judge them.

| ID | Check |
| --- | --- |
| AC-BASE-1 | Each spawn shows a base with a mineral line and two geysers. Workers mine. |
| AC-BASE-2 | The bases and mineral lines look right next to the scaled trees and props. |
| AC-BASE-3 | Over a few minutes each base grows: more workers, new structures, an army. |
| AC-BASE-4 | In order mode, a lane player orders an AI unit and it obeys. |
| AC-BASE-5 | The hero plays as before in both control modes while the AI runs for player 1. |
| AC-BASE-6 | The frame rate holds with six AIs running. |
| AC-BASE-7 | A hero rush is still held by the early waves. |

## 5. Open points

| ID | Point |
| --- | --- |
| O-BASE-1 | Micro of several units at once. Order mode orders one unit. A group selection is not part of this feature. |
| O-BASE-2 | AI armies choose their own paths. They may leave the lanes and cross the jungle. |
| O-BASE-3 | How long a player order holds before the AI gives the unit a new order. The tests record it. No limit is set yet. |
| O-BASE-4 | The corner bases of players 7 and 8 get no resources. |
| O-BASE-5 | The Lurkers (player 8) and the Predators (player 7) stay where the jungle sites are. They attack enemy workers that expand there. |
| O-BASE-6 | Main sites hold 4x stock minerals. The stock depletion expansion (3000 to 40000 minerals left) fires late. Expansion is expected from the fast-expand and worker-saturation paths. Measured by `macro`. |
| O-BASE-7 | The 8x8 Command Center may not fit the stock expansion placement. `macro` records it. |

# REQ-SCENERY: permanent scenery

Operator 2026-11-20. Things that are in every game and take no part in it.

## 1. Requirements

| ID | Requirement |
| --- | --- |
| R-SCN-1 | At map init at least 5 thunder storm doodads MUST be created at random positions within 16 cells of the Overmind (operator 2026-11-20: was 32). They MUST stay for the whole game. |
| R-SCN-2 | On the first Overmind orbit shot of the intro (S6, first pass) 3 empty Zerg drop pods MUST fall in the near view of the shot, apart from each other in place and in time (operator 2026-11-20). Once per game. |
| R-SCN-3 | Withdrawn (operator 2026-11-20: "delete the orbiting wraiths"). No scenery Wraith MUST exist. Old text: Two Wraiths MUST circle the Psi Destroyer on elliptical paths for the whole game. The long diameter of each ellipse MUST be at least 48 cells (operator 2026-11-20). They MUST NOT take part in the game: no fight, no damage taken, not counted as air creeps. |

## 2. Acceptance

| ID | Check |
| --- | --- |
| AC-SCN-1 | Lightning and thunder show around the Overmind. |
| AC-SCN-2 | In the first S6 shot three Zerg pods fall in the foreground and hit the ground. |
| AC-SCN-3 | Withdrawn with R-SCN-3. |

## 3. Open points

| ID | Point |
| --- | --- |
| O-SCN-1 | The storm doodad is the stock `ThunderLightning`. `ZerusLightning` is the other candidate. |
| O-SCN-2 | Closed: the orbit Wraiths are removed. |
| O-SCN-3 | Closed: the orbit Wraiths are removed. |

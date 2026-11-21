# REQ-SCENERY: permanent scenery

Operator 2026-11-20. Things that are in every game and take no part in it.

## 1. Requirements

| ID | Requirement |
| --- | --- |
| R-SCN-1 | At map init at least 5 thunder storm doodads MUST be created at random positions within 16 cells of the Overmind (operator 2026-11-20: was 32). They MUST stay for the whole game. |
| R-SCN-2 | On the first Overmind orbit shot of the intro (S6, first pass) 3 empty Zerg drop pods MUST fall in the near view of the shot, apart from each other in place and in time (operator 2026-11-20). Once per game. |
| R-SCN-3 | Withdrawn (operator 2026-11-20: "delete the orbiting wraiths"). No scenery Wraith MUST exist. Old text: Two Wraiths MUST circle the Psi Destroyer on elliptical paths for the whole game. The long diameter of each ellipse MUST be at least 48 cells (operator 2026-11-20). They MUST NOT take part in the game: no fight, no damage taken, not counted as air creeps. |
| R-SCN-4 | One more empty Zerg drop pod MUST fall on the exact camera spot of intro shot S7 (the shot that looks up at the Overmind). It MUST hit the ground at the cut from S6 into S7, on the first pass. Once per game (operator 2026-11-20). |
| R-SCN-5 | Every tree doodad MUST play its animation at 0.25 of its normal speed, for the whole game (operator 2026-11-21). This holds for all `ZerusTree` doodads and their footprint clones, and for the two intro S2 trees (R-INTRO-17). The particles the trees emit (the rising vapour) MUST rise at 0.25 of their normal speed too (operator 2026-11-21). |

## 2. Acceptance

| ID | Check |
| --- | --- |
| AC-SCN-1 | Lightning and thunder show around the Overmind. |
| AC-SCN-2 | In the first S6 shot three Zerg pods fall in the foreground and hit the ground. |
| AC-SCN-3 | Withdrawn with R-SCN-3. |
| AC-SCN-4 | As the view cuts to the look-up Overmind shot, a pod hits the ground at the camera. |

## 3. Open points

| ID | Point |
| --- | --- |
| O-SCN-1 | The storm doodad is the stock `ThunderLightning`. `ZerusLightning` is the other candidate. |
| O-SCN-2 | Closed: the orbit Wraiths are removed. |
| O-SCN-3 | Closed: the orbit Wraiths are removed. |

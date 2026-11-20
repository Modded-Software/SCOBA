# REQ-RIM-FALLS: Procedural Waterfalls at the Inner Rim of the 256 Map

**Date:** 2026-11-20
**Status:** Requirements stated by the operator on 2026-11-20. Built. The
specification lists the state of each requirement and the run that backs it.

## 1. Scope

The map is a bowl with raised walls. The build places groups of waterfalls
at the inner rim of the built map (`out/SCOBA256.SC2Map`), at the foot of
that wall. Placement is procedural. `src/SCOBA.SC2Map` is not changed.

Operator, 2026-11-20: "adds rock and normal waterfalls at relatively empty
positions at the inner rim of the map (it is a bowl with raised walls)";
"they need to be scaled and layered randomly, rotated so they face the same
direction as the normal of the raised terrain behind them". Then: 12 to 24
groups; "basins allowed, include rocks on bottom"; "stay decorative leave
walkable"; "YES ROCK WATERFALLS RIM ONLY".

Out of scope: the water features at the psi decimator
([REQ-WATER-FEATURES](REQ-WATER-FEATURES.md)). They keep having no rock
waterfall (R-WF-05).

Implementation: [SPEC-RIM-FALLS](../specifications/SPEC-RIM-FALLS.md).

## 2. Requirements

| ID | Requirement |
|---|---|
| R-RF-01 | The build MUST place 12 to 24 groups of waterfalls at the inner rim: on the lower part of the wall that rises to the map edge, with raised terrain behind and flatter ground in front. Flat ground and ground that falls toward the edge MUST NOT get a group. |
| R-RF-02 | A group MUST stand at a relatively empty position: clear of every placed object (a tree counts with its canopy) and of every water rectangle. Two groups MUST NOT stand close together. |
| R-RF-03 | A group MUST have rock waterfalls and normal waterfalls, layered: the normal ones in front of a rock waterfall, not taller than it. |
| R-RF-04 | Counts, variations, sizes and offsets MUST be chosen by chance, so groups differ. |
| R-RF-05 | Every waterfall MUST face the downhill normal of the raised terrain behind it, with a small turn of chance. |
| R-RF-06 | A group MAY have a basin cut into the ground at its foot. A basin MUST have rocks on its bottom. The ground MUST only be lowered, by a bounded amount, and only at the group. A tree with an absolute height MUST follow the ground it stands on. |
| R-RF-07 | The groups are decorative. The step MUST NOT block ground the map leaves walkable: no pathing paint, no doodad footprint. |
| R-RF-08 | Rock waterfalls MUST be placed by this step only, at the rim. |
| R-RF-09 | The same input MUST give the same groups. A change at one place of the rim MUST NOT change groups far from it. |
| R-RF-10 | The build MUST fail, and write nothing, when a requirement above is measured as broken. |
| R-RF-11 | `SC2_NO_RIM_FALLS=1` MUST skip the step. |
| R-RF-12 | A rock waterfall MUST be embedded in the wall: the ground at its place MUST cover a share of its height (operator 2026-11-20, from the game: "these need to be embedded in the terrain, they are floating in front of it"). |
| R-RF-13 | A group MUST NOT stand near a geyser (operator 2026-11-20: "never place them near geysers"). |
| R-RF-14 | A group MUST stand close to the map edge: at most 20 from it (operator 2026-11-20: "they need to be closer to the rim"). |

## 3. Operator checks

The look: where the groups stand, their size against the wall, the
layering, the facing as drawn, the basins and their rocks. No test decides
these.

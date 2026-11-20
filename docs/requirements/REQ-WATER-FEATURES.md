# REQ-WATER-FEATURES: Procedural Water Features in the 256 Map

**Date:** 2026-11-20
**Status:** Requirements stated by the operator on 2026-11-20. Built. The
specification lists the state of each requirement and the run that backs it.

## 1. Scope

The build makes the water features of the built map
(`out/SCOBA256.SC2Map`): where water falls, where it lands, and the ground
around it. Placement is procedural. `src/SCOBA.SC2Map` is not changed.

In scope now: the two holes by the psi decimator (operator: "Decimator
holes first"). Both are painted with `Albion` water. The decimator's pipes
are the water source.

Out of scope: every other water area of the map. Placed water doodads
there stay as the operator placed them.

This replaces REQ-WATER-DOODADS. That step multiplied every placed water
doodad. It is removed.

Implementation: [SPEC-WATER-FEATURES](../specifications/SPEC-WATER-FEATURES.md).

## 2. Requirements

| ID | Requirement |
|---|---|
| R-WF-01 | The build MUST make one water feature at every site: a water rectangle of a site water type that a pipe mouth of a pipe unit reaches. |
| R-WF-02 | The pipes MUST be the source. Every pipe mouth of a site MUST have at least two falls. A fall's top MUST be just over the pipe lip, in the lower half of the opening, and its base MUST stand 0.2 over the water surface (operator 2026-11-20: "raise regular waterfalls by 0.2"; operator 2026-11-20: on the lip was too low; high in the opening was "from the top, not the bottom"). The falls of a mouth MUST together be at least as wide as its opening, and no two MUST be the same size (operator 2026-11-20: too thin; then "more variation in their scale"). The bigger pipe of a site MUST have the wider falls, and no fall MUST reach past the side of its pipe (operator 2026-11-20). Every fall MUST face the mean direction of all pipes, not the direction of its own pipe (operator 2026-11-20, from the game: one group ran "too much facing the east", the other "too much to the south, need a southwest facing"; the mean of the decimator's pipes is southwest). The falls of a site MUST stand 2.5 cells from the measured mouths toward its bigger pipe (operator 2026-11-20, from the game: both features stood 2 to 3 cells off their pipes). |
| R-WF-03 | Falling water MUST land in water: under every fall base the ground MUST be under the surface, inside the pool. |
| R-WF-04 | The ground MUST be shaped in the build: a pool under the falls, and a rim around it. The water MUST end on a shore, not on the straight edge of its rectangle. |
| R-WF-05 | A site MUST NOT have rock waterfalls (operator 2026-11-20: "remove rock waterfall features entirely"; before that the build placed them on the shore). Instead the sloped walls of the pools MUST be painted with the dirt texture the map uses for its lanes (operator 2026-11-20: first "an upscaled rock texture", then "switch to dirt, replace with the dirt texture we use"). Flat ground and ground away from the pools MUST NOT be painted. Dirt already painted MUST NOT be weakened. |
| R-WF-06 | Two falls of a site MUST NOT overlap by more than 80 % of the smaller one. Up to that they read as one stream. |
| R-WF-07 | Sizes, heights and landing points MUST come from the measured models, not from a hand table. |
| R-WF-08 | Placed water doodads at a site MUST be dropped from the built map: the feature replaces them. Placed water doodads elsewhere MUST stay, unchanged and not multiplied. |
| R-WF-09 | The ground change MUST be local and bounded. Ground away from the sites MUST NOT move. A tree with an absolute height MUST follow the ground it stands on. |
| R-WF-10 | Units MUST NOT walk into the pool or through a rock in it. |
| R-WF-11 | The same input MUST give the same features. |
| R-WF-12 | The build MUST fail, and write nothing, when a requirement above is measured as broken or when no site is found. |
| R-WF-13 | The features MUST look good in the game: falls read as flowing out of the pipes, the pool as natural, with dirt walls, rocks in it and plants round it. |
| R-WF-14 | Every pool MUST have rocks standing in it (operator 2026-11-20: "some rocks inside, find appropriate doodads from zerus"): Zerus rock doodads, in the water, standing in the pool floor, their tops over the surface, clear of where the falls land, apart from each other, no two of one variation in a pool. Their textures MUST be upscaled like those of every placed doodad. |
| R-WF-15 | Every pool MUST have vegetation round it (operator 2026-11-20: "the pools need vegetation around"): Zerus plants in a ring round the water, none in the water, none on the pool walls, clear of placed units. The plants MUST be flora plants: non-blocking, crushable, covered by the flora checks. |

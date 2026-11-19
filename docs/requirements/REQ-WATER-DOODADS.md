# REQ-WATER-DOODADS: Water Doodad Density in the 256 Map

**Date:** 2026-11-19
**Status:** Requirements stated by the operator on 2026-11-19. Built.
The specification lists the state of each requirement.

## 1. Scope

The build doubles the map from 128 to 256 cells and scales every placed
position by 2. Waterfall runs that were dense in the source are spread apart
and look sparse.

In scope: `Waterfall`, `RockWaterfall`, `ZerusWaterfall`.

Out of scope: the water mesh (`t3Water`), `FogMist`, `RainEmitterLarge`.

The source map (`src/SCOBA.SC2Map`) is not changed. The rules run on the
built map only.

Implementation: [SPEC-WATER-DOODADS](../specifications/SPEC-WATER-DOODADS.md).

## 2. Requirements

| ID | Requirement |
|---|---|
| R-WD-01 | The built map MUST hold 2x the placed count of each in-scope water doodad type. |
| R-WD-02 | Added doodads MUST fill the gaps the 2x spread made: between close neighbours, or beside a lone doodad along its cliff lip. |
| R-WD-03 | Added doodads MUST vary from their source: scale, a small rotation change that keeps the flow direction, and a different model variation where the model has more than one. |
| R-WD-04 | Other doodads and units MUST NOT be added or changed by this step. |
| R-WD-05 | The step MUST be deterministic: the same source gives the same map. |

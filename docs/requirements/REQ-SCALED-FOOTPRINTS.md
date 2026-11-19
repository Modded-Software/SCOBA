# REQ-SCALED-FOOTPRINTS: Pathing Blockers of Scaled Props

**Date:** 2026-11-15
**Status:** Requirements stated by the operator on 2026-11-15, revised the
same day (v2: trunk outline instead of round radius). Built. The
specification lists the state of each requirement and the run that backs it.

## 1. Scope

The map build scales placed props: Zerus trees go to 2x-8x
(`scripts/props_expand.py`), and spore cannons and spore crawlers go to 3x
(`scripts/mapgen/spore_scale.py`). A placed Scale only scales the mesh. The pathing
footprint stays at its stock size, so units walk into large trees and spores.

In scope: Zerus trees (`ZerusTree`), `SporeCannon`, `SporeCrawler`.

Out of scope: the psi destroyer. Its stock blocker is already large enough
(operator, 2026-11-15).

The v1 round blockers were rejected: asymmetric trees got offset blockers and
the largest trees blocked too much.

Implementation: [SPEC-SCALED-FOOTPRINTS](../specifications/SPEC-SCALED-FOOTPRINTS.md).

## 2. Requirements

| ID | Requirement |
|---|---|
| R-FP-01 | Every placed Zerus tree MUST block ground pathing inside the outline of its scaled trunk at feet height (world z 0.05-0.35), at its placed position and rotation. Small clipping is allowed. |
| R-FP-02 | Every placed spore cannon and spore crawler MUST block a round area of its solid core. |
| R-FP-03 | A blocker MUST follow the outline, including off-centre (leaning) trunks. |
| R-FP-04 | A blocker MUST NOT block ground pathing about one unit past its outline, where nothing else blocks it. |
| R-FP-05 | A hero walking across a blocked prop MUST NOT enter the outline (beyond its own radius) and MUST still reach the far side. |
| R-FP-06 | Blocker shapes MUST come from the measured model, placed scale, and rotation, not from a hand table. |
| R-FP-07 | The build MUST fail when a placed tree or spore has no generated blocker, or a tree blocker that covers too little of its trunk or blocks far more than it. |

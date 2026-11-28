# REQ-CINEMATIC: Cinematic Mode on F9

**Date:** 2026-11-27
**Status:** Stated by the operator on 2026-11-27. Built, not yet run in game.
The specification lists the state of each requirement and the run that
backs it.

## 1. Scope

In scope:

- F9 toggles cinematic mode: all UI hidden, play goes on;
- Shift+F9 toggles a horizontal letterbox to 16:9, only in cinematic mode.

Out of scope:

- reading the screen size: the bars are sized for 16:10 (operator
  2026-11-27). On 4:3 or 16:9 screens the picture is not exactly 16:9.

Implementation lives in [SPEC-CINEMATIC](../specifications/SPEC-CINEMATIC.md).

## 2. Requirements

| ID | Requirement |
| --- | --- |
| R-CINE-1 | F9 MUST toggle cinematic mode for the player who pressed it. |
| R-CINE-2 | In cinematic mode all UI MUST be hidden: the game console, the minimap, every map dialog, the TPS crosshair, the TPS shot texts and the world texts (damage numbers). |
| R-CINE-3 | Cinematic mode MUST NOT hold input: the hero moves, turns and shoots as without it. |
| R-CINE-4 | Leaving cinematic mode MUST bring back exactly the UI that was shown before it. |
| R-CINE-5 | Shift+F9 MUST toggle black bars at the top and the bottom that make the picture 16:9 on a 16:10 screen. |
| R-CINE-6 | Shift+F9 MUST do nothing while cinematic mode is off. |
| R-CINE-7 | Leaving cinematic mode MUST remove the bars. |
| R-CINE-8 | The intro and the hero drop MUST work as before with cinematic mode on or off; their end MUST NOT show the UI while cinematic mode is on. |
| R-CINE-9 | F9 no longer toggles the animation probe (operator 2026-11-27: the probe has no key). |
| R-CINE-10 | The bars MUST slide in from the screen edges and slide back out, not pop (operator 2026-11-27). |

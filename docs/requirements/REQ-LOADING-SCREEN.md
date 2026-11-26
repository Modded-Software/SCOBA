# REQ-LOADING-SCREEN: Loading Screen Text and Wait

**Date:** 2026-11-26
**Status:** Stated by the operator on 2026-11-26:

- "the map loading screen description is from the 2018 era, needs a
  complete overhaul";
- the map name: "SCOBA: StarCraft Online Battle Arena";
- the author field: `SCOBA` in both locales;
- the wording of section 4, shown before the build: "use it";
- the intro line "Two control modes. The Controls button switches them."
  dropped: the tip starts with the controls (operator 2026-11-26);
- "do not auto-enter the game on load, wait for user to press key".

The specification lists the state of each requirement.

## 1. Scope

In scope:

- the map name, author, short and long description and the loading
  screen tip, in all 13 locales ("translate for all locales now",
  operator 2026-11-26);
- the wait for a key at the end of loading.

Out of scope:

- every player name (operator 2026-11-26);
- the loading screen image and layout;
- the tooltips of the command-card buttons.

## 2. Definitions

- **Tip**: the string `LoadingScreen/Tip`, shown on the loading screen.
- **Fields**: `DocInfo/Name`, `DocInfo/Author`, `DocInfo/DescShort`,
  `DocInfo/DescLong` and the tip.
- **Built map**: the map the build makes (`$SC2_BUILT_MAP`).
- **Test map**: a copy of the built map with a test harness.

## 3. Requirements

| ID | Requirement |
| --- | --- |
| R-LOAD-1 | Every field MUST be set in every locale. The name MUST be `SCOBA: StarCraft Online Battle Arena`. The author MUST be `SCOBA`. |
| R-LOAD-2 | enUS and enGB MUST hold the same text in every field. Every other locale MUST hold a translation of the descriptions and the tip. A translated tip MUST keep the key names, button labels, numbers and line breaks of enUS: the map's buttons are English in every locale. |
| R-LOAD-7 | The game shows the copy of the fields in `DocumentHeader`. The build MUST write it from the GameStrings, and the check MUST compare the two. |
| R-LOAD-3 | No field MUST hold a word of the texts before 2026-11-26: the Outbreak name, FPS and RTS modes, PAGE UP and PAGE DOWN, the E, D, S, F and G, R, T, A keys, Ctrl to zoom, "auto-attack", "Destroy all enemy structures", the old author names. |
| R-LOAD-4 | The tip MUST name only controls and rules the map has. Each key, mouse button, button name and level rule it names MUST be the one the map script or the button data binds. A key that no check covers MUST fail the build. |
| R-LOAD-5 | The built map MUST NOT enter the game by itself when loading ends. It MUST wait on the loading screen until the player presses a key, then enter. |
| R-LOAD-6 | A test map MUST enter the game by itself: a test run has nobody to press a key. The one test of R-LOAD-5 keeps the wait. |

## 4. Text

Name: `SCOBA: StarCraft Online Battle Arena`

Short description: `Co-op hero arena for up to 3 players. Six lanes, two
control modes.`

Long description: `Up to three players fight as Terran heroes beside their
lane armies, Terran against Zerg, across six lanes. Gain XP, spend stat
points and learn abilities.`

Tip, one line per screen line:

```text
BOTH MODES
W, A, S, D - move
Shift (hold) - slow walk
Space - deploy at the start, then jump
Z (hold) - zoom
Mouse wheel - camera distance
Ctrl+E - order mode. Ctrl+C - leave it

WASD / POINT & CLICK
Left click - pick a target
Right click - attack. With Chase on Move, also move
Hold a mouse button and drag - turn the camera
Ctrl+C - cancel the attack
Attack button - Single or Auto. Chase button - Stand or Move

ACTIONS (TPS)
Mouse - turn the camera
Right hold - aim. Left click while aiming - shoot
Middle click - show or hide the cursor

HERO
3 stat points per level. A new ability at levels 3, 6, 9, 12 and 15. At level 20, one ultimate from a skill tree with 3 points in it.
```

The second mode is `ACTIONS (TPS)`: its button reads `Controls: Actions`.
The requirements call it `WASD / TPS` ([REQ-TPS](REQ-TPS.md)).

## 5. Acceptance

| ID | Check |
| --- | --- |
| AC-LOAD-1 | Load the map: the loading screen shows the name and the tip of section 4. Nothing of the old texts shows. Operator check. The build writes the text into `DocumentHeader`, the copy the game shows; the validator compares it with the GameStrings. |
| AC-LOAD-2 | Loading ends: the game does not start. Press a key: it starts. |
| AC-LOAD-3 | Each line of the tip does what it says in the game. Operator check; the bindings are checked by the build. |

## 6. Open points

| ID | Point |
| --- | --- |
| O-LOAD-1 | The tip names no goal. Victory and defeat are out of scope of [REQ-ROSTER](REQ-ROSTER.md). |
| O-LOAD-2 | The tooltip of `Controls: Actions` still says "Alt shows the cursor". R-TPS-34 took that from Alt. Not part of this change. |
| O-LOAD-3 | The player names keep their campaign texts (the Raynor names) in every locale. |
| O-LOAD-4 | The translations are the agent's. A native reader has not checked them. Key names stay English (`Ctrl`, not `Strg`). |

Implementation lives in
[SPEC-LOADING-SCREEN](../specifications/SPEC-LOADING-SCREEN.md).

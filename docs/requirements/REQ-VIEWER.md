# REQ-VIEWER: Asset Viewer

**Date:** 2026-11-24
**Status:** Stated by the operator on 2026-11-23 where the source column says
"operator". The rows marked "today" restate what the viewer already does, in
game-neutral words. The rows marked "derived" follow from the operator's goal
and are the author's wording. Awaiting operator review of this text. Partly
built: two games (sc2, ghost) and two formats (m3, nod) run through the
extension points. Open: R-VIEW-2 and 3 (shown only by a game or format
added without a core edit), R-VIEW-10, 11 and 14 (step 8). SPEC-VIEWER
section 12 lists the state of each requirement.

## 1. Scope

This contract binds the web viewer under `webviewer/`: a page that shows game
assets in a 3D view, and the server that feeds it.

In scope:

- reuse: one viewer for several games and several asset formats;
- the extension points a new game or a new format plugs into;
- the language and structure of the viewer's code;
- the game tabs and the panel handles;
- the features every game gets: gallery, scene, selection, camera, view
  tools, saved state, failure reports.

Out of scope:

- the rules of any one game. Each game has its own specification;
- how closely a renderer matches a game's own picture. That is tracked per
  format in the game specifications;
- tools that build catalogs from game data.

No game is named in this document. A game is named only in its own
specification.

Implementation lives in [SPEC-VIEWER](../specifications/SPEC-VIEWER.md).

## 2. Definitions

- **Game**: one product whose assets the viewer can show.
- **Dataset**: one set of a game's data and assets. A game has one or more.
- **Category**: one kind of thing a game lists in the gallery.
- **Record**: one entry of a category, with the data that decides its look.
- **Asset**: a file a record or a model names: a model, a texture, an
  animation.
- **Format**: a file layout the viewer can read and draw.
- **Instance**: one placed copy of a model in the scene.
- **Scene**: all instances, of all games, in one 3D view.
- **Gallery**: the panel that lists what can be added.
- **Instances panel**: the panel that lists what is in the scene.
- **Drawer**: a panel that slides out of the window and back.
- **Handle**: the button that opens and closes a drawer.
- **Game tab**: the button that makes one game the gallery's game.
- **Capability**: something only some instances can do, such as a colour
  choice or a second texture set.
- **Core**: the viewer code that knows no game and no format.
- **Game module**: the code for one game.
- **Format module**: the code for one format.
- **Feature**: one user-facing function of core, such as selection or copy
  and paste.

## 3. Requirements

### 3.1 Reuse and extension

| ID | Requirement | Source |
| --- | --- | --- |
| R-VIEW-1 | Core MUST NOT hold a name, a path, a data rule or a file format of any one game. | operator |
| R-VIEW-2 | Adding a game MUST take a game module for the page, a game module for the server, and one registration line for each. It MUST NOT take an edit to core or to another game. | operator |
| R-VIEW-3 | Adding a format MUST take a format module and its registration. It MUST NOT take an edit to core or to another format. | operator |
| R-VIEW-4 | Every extension point MUST be a written, typed interface. Core MUST reach games and formats through these interfaces only. | operator |
| R-VIEW-5 | Every feature MUST work on an instance of any game and any format, through one instance interface. | operator |
| R-VIEW-6 | A feature that needs a capability MUST ask the instance for it. For an instance without it, the feature's controls MUST be absent. They MUST NOT be shown and fail. | derived |
| R-VIEW-7 | Game modules MUST NOT depend on each other. Two games MAY share a format module. | derived |
| R-VIEW-8 | A game whose data is not on the machine MUST be reported with the reason. The other games MUST keep working. | derived |
| R-VIEW-9 | Game data MUST NOT be in the repository. Its place on the machine comes from machine settings. | today |

### 3.2 Code

| ID | Requirement | Source |
| --- | --- | --- |
| R-VIEW-10 | All viewer code that runs in the browser or in Node MUST be TypeScript, checked in strict mode: the page, the server, the Node tools and the tests. | operator |
| R-VIEW-11 | The page and the server MUST share one definition of every message they exchange. | derived |
| R-VIEW-12 | A module MUST state what it uses by import. No module may publish or read state through a shared untyped object. | operator |
| R-VIEW-13 | The type check MUST be part of the test run. A type error MUST fail the run. | derived |
| R-VIEW-14 | The page MUST offer one typed object for tests and debugging. Tests MUST NOT reach into module internals. | derived |

### 3.3 Games in the page

| ID | Requirement | Source |
| --- | --- | --- |
| R-VIEW-20 | The gallery MUST have one tab per registered game. The tabs MUST be vertical and sit at the top of the gallery's right edge. | operator |
| R-VIEW-21 | A game tab MUST make that game the gallery's game: its datasets, its categories, its lists. It MUST NOT change the scene, the camera or the selection. | operator |
| R-VIEW-22 | The chosen game MUST be kept over a reload. | derived |
| R-VIEW-23 | With the gallery closed, the game tabs MUST stay reachable at the window edge. A click on one MUST open the gallery on that game. | operator |
| R-VIEW-24 | The handle of the gallery and the handle of the instances panel MUST each sit at the bottom of its panel's right edge. | operator |
| R-VIEW-25 | The categories shown in the gallery MUST come from the chosen game. | operator |
| R-VIEW-26 | Instances of different games MUST stand in one scene, side by side. | operator |
| R-VIEW-27 | The tab of a game that is not available (R-VIEW-8) MUST be shown, MUST NOT open, and MUST state the reason. | derived |
| R-VIEW-28 | A closed drawer MUST NOT take the mouse or the keys. The view MUST use the space a closed drawer leaves: what stands there MUST be reachable by the mouse, and messages MUST centre on the free view. | today |

### 3.4 Datasets

| ID | Requirement | Source |
| --- | --- | --- |
| R-VIEW-30 | The gallery MUST list the datasets of its game and show the current one. The choice MUST be kept per game over a reload. | today |
| R-VIEW-31 | Each instance MUST keep the dataset it came from. Instances of different datasets MUST stand side by side. | today |
| R-VIEW-32 | An instance MUST be able to change dataset. Its place, angle, scale and id MUST stay. When the other dataset lacks its record, the instance MUST stay as it is and the reason MUST be shown. | today |
| R-VIEW-33 | Every asset a model names MUST be read from the instance's dataset. | today |
| R-VIEW-34 | When a dataset's files change on disk, the page MUST ask whether to reload the data. "Yes" MUST reload it. "No" MUST hide the question until the files change again. | today |

### 3.5 Gallery

| ID | Requirement | Source |
| --- | --- | --- |
| R-VIEW-40 | A category MUST offer a text search, the filters its game declares, a count, and a list that loads a page at a time. | today |
| R-VIEW-41 | A click on a record MUST show a preview of its data with an "add to scene" control. | today |
| R-VIEW-42 | A record MUST be draggable into the view. A preview MUST stand on the ground under the pointer. A drop MUST place it there as previewed. A drop off the ground MUST place nothing and say why. | today |
| R-VIEW-43 | "Add all" MUST ask first, with the count. It MUST add every listed record, lay the new instances out by size without overlap, put them next to those already there, and save the view as a named landmark. Records the game marks as not placeable MUST be left out and named in the question. | today |
| R-VIEW-44 | The game, not core, MUST decide how a record becomes an instance: which file, which scale, which height, which angle, which animation. | derived |
| R-VIEW-45 | A game MAY mark a record as a backdrop. Added or dropped, such a record MUST become the backdrop and MUST NOT be placed. | today |

### 3.6 Scene

| ID | Requirement | Source |
| --- | --- | --- |
| R-VIEW-50 | The instances panel MUST list every instance with its name, a remove control, its position, angle and scale, and its animation. It MUST show a further control only for a capability the instance has. | today |
| R-VIEW-51 | The instance search MUST hide the rows that do not match. It MUST NOT change the scene or the selection. | today |
| R-VIEW-52 | The mouse MUST find an instance by its drawn solid surface at the pixel. See-through parts MUST NOT count. | today |
| R-VIEW-53 | The instance under the mouse MUST be marked. A click MUST select it. Shift MUST add to or take from the selection. A dragged rectangle MUST select what is inside. A row click MUST select the same way. Every selected instance MUST be marked, in another way than the one under the mouse. | today |
| R-VIEW-54 | Selected instances MUST be movable, turnable and removable as a group. | today |
| R-VIEW-55 | The selection MUST be copyable, cuttable and pastable. A copy MUST keep everything that defines the instance. A paste MUST keep the shape of the group, put it under the pointer, or where it was copied from when the pointer is off the view, and select the copies. | today |
| R-VIEW-56 | An instance MUST offer a menu of its animations: play one once, or make it the looping one. After a play-once the instance MUST go back to its looping one. | today |
| R-VIEW-57 | "Clear" MUST ask before it removes every instance. | today |
| R-VIEW-58 | The instances panel MUST offer a way to point the camera at one instance. | today |
| R-VIEW-59 | A key command MUST NOT act on the scene while a text field has the keys. | today |

### 3.7 View

| ID | Requirement | Source |
| --- | --- | --- |
| R-VIEW-60 | The mouse MUST pan, orbit, turn and zoom the camera. The eye MUST NOT go under the ground. | today |
| R-VIEW-61 | A ground grid MUST be available and switchable. It MUST show at every zoom. It MUST mark the place under the pointer and the place of every instance. | today |
| R-VIEW-62 | A backdrop MUST be choosable from those the games offer. | today |
| R-VIEW-63 | Camera views MUST be savable as named landmarks, reachable again, and deletable after a question. | today |
| R-VIEW-64 | Every message and every failure MUST be shown to the user and kept in a message log the user can open. None may be dropped. | today |
| R-VIEW-65 | The view MUST follow the window size. | today |

### 3.8 Saved state

| ID | Requirement | Source |
| --- | --- | --- |
| R-VIEW-70 | A scene MUST be kept as a scene document in the browser's database. Each instance MUST name its game, its dataset and its record or file. A reload MUST show the same scene. | operator 2026-11-23 |
| R-VIEW-71 | A scene document MUST carry a version and be checked against one written type. A document of another version, or one that fails the check, MUST be refused with a message naming the fault. It MUST NOT be read in part. | operator 2026-11-23 |
| R-VIEW-72 | The camera, the open drawers, the grid, the backdrop, the landmarks, the chosen game, the chosen datasets and the open scene MUST be kept over a reload. | today, operator 2026-11-23 |
| R-VIEW-73 | A stored value that is not valid MUST be refused, reported and replaced. | today |
| R-VIEW-74 | The page address MUST NOT hold the scene or any part of it. An address that holds a scene in an older form MUST be refused with a message and cleared. | operator 2026-11-23 |
| R-VIEW-75 | There MUST be several named scenes. The user MUST be able to make a new one, rename one, open one and delete one. A delete MUST ask first. The scene open last MUST open after a reload. | operator 2026-11-23 |
| R-VIEW-76 | A scene MUST be exportable as a file and importable from one. An import MUST pass the check of R-VIEW-71. A refused import MUST change nothing. | operator 2026-11-23 |
| R-VIEW-77 | A scene that fails its check MUST NOT stop the other scenes from opening. | derived |

### 3.9 Failures

| ID | Requirement | Source |
| --- | --- | --- |
| R-VIEW-80 | An asset that cannot be read MUST be reported and MUST NOT be added. | today |
| R-VIEW-81 | A model with parts the renderer cannot draw MUST be added, and the parts MUST be named. | today |
| R-VIEW-82 | A format module MUST refuse, with a message, a file version or a record layout it does not read. It MUST NOT draw data it guessed. | derived |

### 3.10 Proof

| ID | Requirement | Source |
| --- | --- | --- |
| R-VIEW-90 | Every requirement MUST have a test a program decides, with at least one negative case. | today |
| R-VIEW-91 | Every extension interface MUST have at least two implementations under test. One implementation does not prove an interface. | operator |
| R-VIEW-92 | Every format MUST have a survey tool that reads every file of that format in a dataset and reports each file it cannot read. | today |
| R-VIEW-93 | What only a person can judge MUST be listed as an operator check and MUST NOT be reported as verified. | today |

## 4. Operator checks

Only a person can judge these:

- whether the game tabs and the handles look right and are easy to hit;
- whether the scene list looks right and is easy to use;
- whether a model looks as it does in its game;
- animation, effects and colours as a picture.

## 5. Open points

| ID | Point |
| --- | --- |
| O-VIEW-1 | The rows marked "today" were written from the current code and its test titles. The operator has not reviewed them as requirements. |
| O-VIEW-2 | R-VIEW-10 names the tests. They are converted last, so that they keep proving behaviour while the code under them moves. |
| O-VIEW-3 | Closed (operator 2026-11-23): the renderer library is viewer code. This repository patches it and builds from its own clone. R-VIEW-10 and R-VIEW-13 bind it: it is TypeScript in strict mode, and its type check is part of the test run. |
| O-VIEW-4 | The review of 2026-11-23 added R-VIEW-28, 45, 58, 59 and 65 and widened R-VIEW-53, 55, 56, 60, 61, 63 and 64. All restate what the current page does. The numbers and the inputs are in section 16 of the specification, not here. |
| O-VIEW-5 | Closed (operator 2026-11-23): the scene leaves the page address. Scenes are documents in IndexedDB, several and named, with export and import. The camera, the grid, the backdrop and the landmarks stay global, not per scene. Scenes of the old address form are not carried over. Scenes are per browser; the export file is the way to move one. |

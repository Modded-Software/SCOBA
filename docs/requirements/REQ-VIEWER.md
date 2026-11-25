# REQ-VIEWER: Asset Viewer

**Date:** 2026-11-24
**Status:** Stated by the operator on 2026-11-23 where the source column says
"operator". The rows marked "today" restate what the viewer already does, in
game-neutral words. The rows marked "derived" follow from the operator's goal
and are the author's wording. Awaiting operator review of this text. Partly
built: two games (sc2, ghost) and two formats (m3, nod) run through the
extension points. Open: R-VIEW-2 and 3 (shown only by a game or format
added without a core edit), R-VIEW-10, 11 and 14 (step 8), and section
3.11 (textures, operator 2026-11-24, not built). SPEC-VIEWER section 12
lists the state of each requirement.

## 1. Scope

This contract binds the web viewer under `webviewer/`: a page that shows game
assets in a 3D view, and the server that feeds it.

In scope:

- reuse: one viewer for several games and several asset formats;
- the extension points a new game or a new format plugs into;
- the language and structure of the viewer's code;
- the game tabs and the panel handles;
- the features every game gets: gallery, scene, selection, camera, view
  tools, saved state, failure reports;
- showing a game's textures and their upscaled results, and choosing what
  is packaged.

Out of scope:

- the rules of any one game. Each game has its own specification;
- how closely a renderer matches a game's own picture. That is tracked per
  format in the game specifications;
- tools that build catalogs from game data;
- how a texture is upscaled, kept and packaged. That is
  [REQ-HD-TEXTURES](REQ-HD-TEXTURES.md). Its words result, chain, pick,
  selection, package and blocked are used here as defined there.

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
- **Texture service**: what a game's server module offers so that the page
  can show texture states, start upscales and set picks.
- **Texture window**: the window that shows the textures of one thing.
- **Ground texture**: a texture that tiles, drawn on the ground of the view.

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
| R-VIEW-66 | Ctrl+/ MUST switch the triangle edges of the selected instances on or off, all the same way. The edges MUST be drawn as thin green lines over the model, follow its pose, and show only where nothing is in front of them. An instance far from the eye MUST show no edges. The choice MUST NOT be kept over a reload or in a copy. | operator 2026-11-24 |

### 3.8 Saved state

| ID | Requirement | Source |
| --- | --- | --- |
| R-VIEW-70 | A scene MUST be kept as a scene document in the browser's database. Each instance MUST name its game, its dataset and its record or file. A reload MUST show the same scene. | operator 2026-11-23 |
| R-VIEW-71 | A scene document MUST carry a version and be checked against one written type. A document of another version, or one that fails the check, MUST be refused with a message naming the fault. It MUST NOT be read in part. | operator 2026-11-23 |
| R-VIEW-72 | The camera, the open drawers, the grid, the ground texture, the backdrop, the landmarks, the chosen game, the chosen datasets and the open scene MUST be kept over a reload. | today, operator 2026-11-23, 2026-11-24 |
| R-VIEW-73 | A stored value that is not valid MUST be refused and reported. It MUST NOT be replaced by a default or by another value: the page MUST NOT start. It MUST list each refused key with its stored value and the reason, and offer to clear exactly those keys. A stored game, dataset or scene the server or the scene store does not have MUST be refused the same way. A value that is not stored MUST read its declared default. | today; changed 2026-11-25 by the operator (no fallbacks) |
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

### 3.11 Textures

Every row holds for any game that offers a texture service. Words as in
[REQ-HD-TEXTURES](REQ-HD-TEXTURES.md) section 2: variant, skin, owner,
bake, problem, preview.

Operator statement (2026-11-24): "each individual texture can have
variants"; "a button 'UPSCALE' opens a dialog to select the input texture
variant, the upscaling algorithm / model and the output dimensions"; "the
result is added to the variants and a dropdown with available variants
replaces the simple HD checkbox". On skins: "slick and minimal skin config
UI where each texture and its variants are previewed and clicking on a
variant highlights it and selects it in the config". On the button: "in
both places; upscale on a whole instance creates a new skin with all its
textures queued for upscale". On models: show the real ones, block
`seedvr2` on problem texture types. On sizes: "a list". On quality: show
the numbers, colour-coded, with an info text when a number is a problem.
On the ground and skybox choosers: keep them, show texture previews. On
baking: a viewer control next to the skin choice, "Bake Skin"; a preview
on an instance and a bake into the map are separate.

Operator statement (2026-11-25): "BUTTON NAMES SHOULD BE VERBS"; "add a
badge with a bread emoji if baked"; "you need a edit icon next to each
skin and also a Add new... item last instead of Edit"; "all dialogs need
button capitalisation"; the name box and Copy of the skin editor: "who
requested them?"; "make the Upscale button inside the Texture and Skin
viewers a card / tile button - as large as the texture preview tiles";
"what does default represent? ... replace this with original then any
additional configuration that uses textures other than original needs to
be under another skin - if changes made (non-original textures selected)
then create temp skin named New Skin with a save icon next to it in the
list instead of the edit icon; ask user explicitly to name the skin on
save, otherwise keep making all changes under this temp skin". Answers of
the same day: Original shows the game's textures only; "currently baked
user texture automatically fall under unsaved New Skins"; the editor's
first tile is the currently picked variant, still selectable, and a pick
goes to New Skin; New Skin is kept by the server; Rename and Delete are
editor buttons with a dialog. Later the same day: "ensure selecting a
different texture variant from the texture viewer automatically create as
New Skin if missing, present a notification dialog to the user with a desc
of what is about to happen".

Operator review (2026-11-25, later): "there is a horrible misalignment
between the texture and skin viewer windows"; the texture window lacks the
blue outline of the current texture, and its Use button is replaced by a
click on the tile; "used by" scrolls at a fixed height; the "what it shows
now" label goes; no question-mark cursor, the info mark explains orange and
red on hover; the skin choice gets an icon and an arrow; "delete buttons
should be red everywhere, buttons should be more descriptive e.g. Rename -
Rename Skin"; every skin in the list but Original has edit and a trash icon
that asks first, New Skin too, and no save icon. Answers of the same day: a
click on a tile "just loads it for preview; we need to design a separate
explicit save mechanic on a skin-level", in both windows; the outline marks
the texture presented now; the game knows units, actors, models and
textures, not skins, so the first tile shows what the game holds and names
no skin.

Source "operator" is that statement. "agent" marks the agent's own rows.

| ID | Requirement | Source |
| --- | --- | --- |
| R-VIEW-100 | A game MAY offer a texture service. For a game without one, every control of this section MUST be absent. They MUST NOT be shown and fail. | agent |
| R-VIEW-113 | An instance whose owner has textures MUST offer a skin choice: **Original**, each saved skin of its owner in its dataset, and **New Skin** when the owner has one. It replaces the HD checkbox. The choice MUST change that instance only. It MUST be kept with the scene and in a copy. | operator, revised 2026-11-25 |
| R-VIEW-114 | Next to the skin choice there MUST be an **Upscale Skin** button, a **Bake Skin** button, and a badge with 🍞 and the name of the baked skin while the owner has a bake. Without a bake the badge MUST be absent. | operator, revised 2026-11-25 |
| R-VIEW-126 | Each saved skin and New Skin in the choice MUST have an edit icon that opens the skin editor on it, and a trash icon that asks first, then deletes it (New Skin: discards it). The trash of the baked skin MUST be disabled and say why. Original MUST have neither. There MUST be no save icon. The last entry MUST be **Add New Skin…**, which opens the editor on New Skin. | operator, revised 2026-11-25 |
| R-VIEW-131 | The first tile of a texture, in the skin editor and in the texture window, MUST be **In game**: the file the game shows for that texture after a build (the owner's bake, else the bake below, else the original). It MUST name no skin. When the package does not hold that file, the tile MUST say so in amber. | operator 2026-11-25 |
| R-VIEW-132 | The skin editor and the texture window MUST show a texture's choices as the same tiles: In game, Original, each variant, the open requests, Upscale. The tiles shown now MUST have the blue outline. | operator 2026-11-25 |
| R-VIEW-133 | A click on a tile MUST only preview it and mark it picked. It MUST change no skin, no bake and no instance. The picks of a window MUST be kept per texture until saved or reverted. **Save to Skin…** MUST ask first in one dialog: the target skin (New Skin or a saved skin), each change from and to, whether New Skin is made, and which instance shows the target. Only then MUST it set each pick in the target. **Revert Changes** MUST drop the picks. Cancel MUST change nothing. | operator 2026-11-25 |
| R-VIEW-134 | "used by" MUST have a fixed height and scroll inside. | operator 2026-11-25 |
| R-VIEW-135 | The info mark of a tile MUST NOT change the cursor. On hover it MUST show a tooltip that says amber is near a limit, red misses a limit, and which numbers miss. | operator 2026-11-25 |
| R-VIEW-136 | A button or icon that deletes or discards MUST be red, in every window and dialog. | operator 2026-11-25 |
| R-VIEW-137 | The skin choice MUST start with a skin icon and end with a down arrow, so it reads as a drop-down. | operator 2026-11-25 |
| R-VIEW-127 | Original MUST show the game's textures only. A change to Original MUST go to New Skin, made on the first change. Save MUST ask for a name and keep New Skin under it. Until saved, every change MUST go to New Skin. New Skin MUST NOT be baked. | operator 2026-11-25 |
| R-VIEW-128 | A button name MUST be a verb and the thing it acts on (**Rename Skin**, **Delete Skin**, **Upscale Texture**). Every dialog title and button MUST start with a capital letter. A question MUST say what will happen in plain words. | operator, revised 2026-11-25 |
| R-VIEW-129 | **Upscale** in the skin editor and in the texture window MUST be a tile as large as a texture preview tile. | operator 2026-11-25 |
| R-VIEW-115 | **Upscale** MUST open a dialog with three choices: the input variant, the model (`pbrify`, `fast`, `seedvr2`) and the output size from a list (1024, 2048, 4096). | operator |
| R-VIEW-116 | The dialog MUST NOT let `seedvr2` be chosen for a data texture, and MUST say why. On an instance, `seedvr2` MUST be choosable; the dialog MUST say that its data textures get `fast`. A size the input cannot reach (R-HD-123) MUST NOT be choosable. | operator, R-HD-122 |
| R-VIEW-117 | **Upscale** on an instance MUST make New Skin of its owner, from the skin the instance shows, and queue a variant of each of its textures. The input of each is its variant in that skin. The instance MUST show New Skin. While the owner has an unsaved New Skin it MUST be refused with the reason. | operator, revised 2026-11-25 |
| R-VIEW-118 | The skin editor MUST show each texture of the owner with a preview, and for the selected texture a preview of each of its variants. Its tiles MUST follow R-VIEW-131 to 133; a save from Original MUST go to New Skin. Every instance that shows the target skin MUST show the saved change without a page reload. The editor MUST have no name box and no Copy. A saved skin MUST have **Rename Skin** and **Delete Skin**, each with a dialog; New Skin MUST have **Save New Skin As…** and **Discard New Skin**. | operator, revised 2026-11-25 |
| R-VIEW-119 | The skin editor MUST have an **Upscale Texture** tile per texture. It MUST open the dialog of R-VIEW-115 for that one texture. The variant it makes MUST appear in the texture's list. | operator |
| R-VIEW-120 | Each variant MUST show its input, model, size and quality numbers. A number that is a problem MUST show red, a number near its limit amber, others green. A problem MUST carry an info text that names the limit and what it means. | operator |
| R-VIEW-121 | A variant that is queued or being made MUST show as such, with its state, until it is done or has failed. A failure MUST show its reason. A request MUST go on when the editor or the page is closed. | agent |
| R-VIEW-122 | **Bake Skin** MUST bake the skin the instance shows for its owner in its dataset, after a confirmation. With Original chosen the button MUST be **Unbake Skin**. The badge of R-VIEW-114 MUST show which skin is baked now. A preview MUST NOT bake. A bake MUST NOT change the skin choice of any instance. | operator, revised 2026-11-25 |
| R-VIEW-123 | A refused bake MUST change nothing and say why. | agent |
| R-VIEW-107 | A game MAY mark a category as ground textures. Its records MUST be listed in the ground button's dialog only, with no gallery tab (operator 2026-11-25). Such a record, added, MUST become the ground and MUST NOT be placed. | agent, revised by operator |
| R-VIEW-108 | The ground MUST show the chosen ground texture tiled. "No ground texture" MUST be choosable. The grid of R-VIEW-61 MUST be drawn over it and stay switchable on its own. | agent |
| R-VIEW-124 | The ground texture chooser and the skybox model chooser MUST show a preview of each entry. | operator |
| R-VIEW-125 | A ground texture MUST offer a variant choice, **Upscale** and **Bake** per texture (R-HD-145). | operator |
| R-VIEW-110 | Adding an instance MUST NOT wait on a texture state. An instance MUST be added, drawn and usable while the texture service is slow, failing or absent. Its skin choice MAY appear later. | operator 2026-11-24, first statement |
| R-VIEW-111 | The viewer MUST get a texture state by reading what the texture store holds. It MUST NOT run the texture tooling to show a state. A read of the states of one model's textures MUST answer within 250 ms, on a store read for the first time too. | operator 2026-11-24, first statement; 250 ms agent (O-VIEW-6) |
| R-VIEW-112 | The viewer MUST take the original of a texture from the file the texture tooling names for it. The viewer and the tooling MUST NOT each decide which stored file an asset is. | operator 2026-11-24, first statement |
| R-VIEW-101 | The texture window MUST open on a record, on an instance, or on a model file. It MUST list every texture that thing names, the original beside each of its variants, for comparison. It MUST NOT set a pick or a default. It MUST change a skin only as R-VIEW-130 says. | agent, revised 2026-11-25 |
| R-VIEW-130 | In the texture window, a click on a tile MUST show it beside the original; Ctrl+click MUST add or remove a tile to compare. For a thing with a texture owner, the picks MUST be saved only by **Save to Skin…** (R-VIEW-133); the dialog MUST also say that bakes and Original stay as they are. Without an owner there MUST be no Save to Skin. | operator, revised 2026-11-25 |

Withdrawn on 2026-11-24 with picks: R-VIEW-102 to 106 and 109 (by
R-VIEW-113 to 123). R-VIEW-105, a dataset default in the texture window,
was the agent's and was wrongly marked "operator". The ids are not reused.

## 4. Operator checks

Only a person can judge these:

- whether a variant looks better than its original, in the texture window,
  in the skin editor, on a model and on the ground;
- whether the skin editor is slick and minimal, and whether the skin
  choice, its icons, the bake badge, the Upscale dialog and tiles, the
  Bake Skin control, the dialogs, the tile outline and the info tooltip,
  the red of delete buttons, the skin choice's icon and arrow, the ground chooser and the skybox
  chooser read well and are easy to use;
- whether the previews and the quality colours read well;
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
| O-VIEW-7 | The amber band of R-VIEW-120 ("near its limit") is the agent's. The operator named no band. The specification gives the number. |
| O-VIEW-6 | The 250 ms of R-VIEW-111 is the agent's number. The operator asked for a bound and named none. Measured before: 2.0 s for a state not read yet. |
| O-VIEW-5 | Closed (operator 2026-11-23): the scene leaves the page address. Scenes are documents in IndexedDB, several and named, with export and import. The camera, the grid, the backdrop and the landmarks stay global, not per scene. Scenes of the old address form are not carried over. Scenes are per browser; the export file is the way to move one. |

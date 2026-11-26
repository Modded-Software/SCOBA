# REQ-HD-TEXTURES: Upscaled Textures

**Date:** 2026-11-24
**Status:** Variants, skins and bake (3.2, 3.5, 3.7, 3.8) are stated by the
operator on 2026-11-24, second statement. They replace steps, kinds, chains,
selections and picks (section 6). Rows marked [agent] are the agent's, not
the operator's. Awaiting operator review of this text. Not built: the
specification lists the state of each requirement.

Operator statement (2026-11-24): "each individual texture can have
variants; introduce concept of skins - configurable presets for each of
the actor's models (or propagated up to unit level in the case of sc2 as we
do not expose the actors currently); a skin has default values those of the
based model for each texture and can select on a per-texture level".
"if skin is on a unit level - clone actors / models so other units are
unaffected; if skin on an actor level - clone models; if on a model-level
then just the textures are modified / added; in each case all layers
upstream get the change". "FAST IS ALWAYS THE DEFAULT FOR SEEDVR2". "BAKE
FOR TERRAIN IS PER-TEXTURE". "DELETE" (the results upscaled from the wrong
file). "DO NOT LOSE ANY WORK AND DO NOT REGRESS".

## 1. Scope

This contract binds the tooling that upscales a game's textures, keeps the
variants, and bakes the chosen ones into a game's data.

In scope:

- finding the textures of a game and of a dataset;
- reading the originals;
- upscaling them with the `upscale-on-arc` tool, on demand;
- keeping every variant in a texture store;
- skins: presets that name a variant per texture of a unit, actor or
  model;
- baking a skin into the game's data;
- checks that a variant is sound and that the map still loads;
- the interfaces a second game plugs into.

Out of scope:

- how the viewer shows and edits all this. That is
  [REQ-VIEWER](REQ-VIEWER.md), section 3.11;
- textures of the user interface;
- baking and packaging for StarCraft: Ghost (operator 2026-11-25: "add
  full support for texture upscaling to SC:G, only without BAKING for
  NOW"). Ghost has variants, skins and requests; its bake is refused
  (3.11);
- any game but StarCraft II and StarCraft: Ghost.

Implementation lives in
[SPEC-HD-TEXTURES](../specifications/SPEC-HD-TEXTURES.md).

## 2. Definitions

- **Game**: one product whose textures the tooling handles. The same word
  as in REQ-VIEWER.
- **Dataset**: one set of a game's data and assets. The same word as in
  REQ-VIEWER.
- **Texture**: one texture file of a dataset, named by its asset path.
- **Original**: the file as the dataset holds it.
- **Model** (upscaler): one model of the `upscale-on-arc` tool:
  `pbrify`, `fast`, `seedvr2`. Each enlarges four times per side.
- **Data texture**: a texture that holds amounts, not light: a normal map,
  a mask, a specular map. A colour texture may hold a data plane too (a
  mask in alpha).
- **Variant**: one version of one texture: the original, what a model
  made of an input variant, at an output size, or what a person's edit
  made of an input variant (an edited variant, REQ-PHOTOCRAFT). A
  texture can have many.
- **Owner**: what a skin belongs to: a unit, an actor or a model. SC2's
  viewer shows units and doodads; it has no actor list.
- **Skin**: a named preset of one owner in one dataset. It names one
  variant for each texture of the owner's models.
- **Layer**: unit above actor above model. A unit shows its actors, an
  actor shows its models.
- **Original skin** (`original`): names no variant. Each texture shows its
  original. It always exists and cannot be changed. It replaces the
  default skin (operator 2026-11-25).
- **New Skin N** (`New Skin 1`, `New Skin 2`, …): the name a skin gets
  when it is made without one. It is stored and baked as any skin, and can
  be renamed.
- **Bake**: making a skin the one the dataset's package holds for its
  owner. A terrain texture is baked on its own, as one variant.
- **Package**: the files the baked skins and terrain variants put into the
  game's data.
- **Problem**: a quality limit a variant misses, with the number.
- **Built map**: `out/SCOBA256.SC2Map`, the package target of the dataset
  `scoba`.
- **Preview**: what the viewer shows on one instance. A preview changes
  no bake.

## 3. Requirements

### 3.1 Tooling

| ID | Requirement |
| --- | --- |
| R-HD-1 | The tooling MUST be persistent and live under `scripts/`. A map build MUST package on its own. `out/` MUST NOT be edited by hand. |
| R-HD-2 | The map source `src/SCOBA.SC2Map` MUST NOT hold upscaled files or their catalog entries. |
| R-HD-3 | The tooling MUST find the textures from the game's data and the dataset's files. No list of textures, units or models MUST be typed in by hand. |
| R-HD-4 | The tooling MUST read the originals from the dataset: its own files first, then the installed game. |
| R-HD-112 | Where the installed game holds an asset in more than one form, the original MUST be the form the game shows by default. A form for an age rating MUST NOT be the original while a default form exists. Without a default form, the form of the installed language MUST be the original. The answer MUST NOT depend on the order the game's storage lists its files in. |
| R-HD-5 | Upscaling MUST use the `upscale-on-arc` tool. |
| R-HD-6 | A second run MUST redo only what changed. Upscaling takes up to minutes per texture. |

### 3.2 Variants

| ID | Requirement |
| --- | --- |
| R-HD-120 | Each texture MUST be able to have any number of variants. The original MUST be one of them. |
| R-HD-121 | A variant MUST be made on request from three choices: an input variant of the same texture, a model of the `upscale-on-arc` tool, and a factor: 2x or 4x of the input's longest side. An edited variant is made another way: by the transfer of an edit of an input variant, at the input's size (R-PC-51). [agent, O-PC-14] |
| R-HD-122 | `seedvr2` MUST NOT be chosen for a data texture. On a colour texture with a data plane, `seedvr2` MUST make the colour and `fast` MUST make the data plane. Where `seedvr2` is chosen for many textures at once, every data texture among them MUST get `fast`. [agent, O-HD-10: with `pbrify` too, data planes get `fast`, as today] |
| R-HD-123 | The size of a variant MUST be the factor times the input's longest side, at most the largest side. The largest side MUST be a setting of the viewer, `TEXTURE_MAX_SIDE`: 1024, 2048 or 4096; unset, 4096. A factor that gives no side above the input's MUST be refused with the reason, and so MUST a size above the largest side. The model's output MUST be shrunk to that size. An input with a side above 2048 MUST be shrunk until no side is above 2048, before the model. [operator 2026-11-26] |
| R-HD-124 | Two requests with the same input, model and resulting size MUST give one variant. A variant MUST record its input, its model per plane, its size and its quality numbers. An edited variant MUST also record the planes that changed and the hash of the rendered planes; two transfers with the same input and the same rendered planes MUST give one variant (R-PC-54, R-PC-55). [agent, O-PC-14] |
| R-HD-146 | A variant MUST be removable on request. A skin of the dataset the removal is asked in MUST NOT refuse it; that skin MUST name the original for the texture after. The removal MUST be refused, with the reason, while a bake of any dataset or a skin of another dataset names it, while another variant is made from it, while a request of its recipe is open, or while an edit session is open on it. The original MUST NOT be removable. [operator 2026-11-25: "add a trash icon for all textures with confirmation dialog; make currently selected, skin-selected and baked texture non-deletable"; operator 2026-11-26: a skin does not keep it, "only the one that is currently selected"; the other refusals are the agent's] |
| R-HD-10 | A variant MUST keep the layout of its original: the same compression format, a full mip chain, the same channel meaning, and the bytes the game stores after the last mip. |
| R-HD-11 | A variant a model made MUST show the same picture as its original. Brightness, colour, and surface tilt seen from far away MUST match the original. A variant a model made from an edited variant MUST match the nearest edited variant among its inputs instead (R-PC-83). An edited variant is not bound by this (R-PC-80). |
| R-HD-12 | A variant of a texture that tiles MUST tile as well as its original does. |
| R-HD-52 | A variant MUST keep the compression format of its original. |
| R-HD-53 | A texture the tooling cannot upscale soundly MUST be left as it is. A request for it MUST fail with the reason. |
| R-HD-56 | A flip book whose cells are known MUST be upscaled so that no cell takes pixels from another cell. Where model files read one flip book with different cells, the cells most model files use MUST hold, and a model file that reads it another way MUST keep the original. A flip book whose cells are not known, or that as many model files read one way as another, MUST be refused. |

### 3.3 Quality

| ID | Requirement |
| --- | --- |
| R-HD-13 | The tooling MUST measure R-HD-10 to R-HD-12 on every variant and keep the numbers with it. |
| R-HD-90 | A variant that misses a limit MUST be kept, with the limit and the number: a problem. A bake whose skin names a variant with a problem MUST be refused with the problem. A variant marked accepted MUST show its problems, which MUST NOT refuse a bake. No command MUST set the mark. [agent: whether a problem refuses a bake is not stated by the operator; see O-HD-9] The limits bind a variant a model made. An edited variant MUST NOT have a problem, and its numbers MUST NOT refuse a bake (R-PC-80, R-PC-81). |
| R-HD-161 | Only a person sets the accepted mark. A program MUST NOT write an entry that holds it; such a write MUST be refused and MUST keep nothing (operator 2026-11-26, "GO" to the four guards; wording [agent]). |
| R-HD-91 | The seam limit of R-HD-12 MUST apply only to a texture that tiles. A texture that does not tile MUST NOT be upscaled or joined with its edges matched across its border; a variant made by the other rule MUST still be shown, and a request of it MUST make a new variant beside it (R-HD-158, operator 2026-11-26). |

### 3.4 Texture store

| ID | Requirement |
| --- | --- |
| R-HD-85 | One texture store MUST hold the variants, the skins, the bakes and the edit sessions (REQ-PHOTOCRAFT) of every game and every dataset, in one layout. It MUST be outside git. One machine setting MUST name its place. |
| R-HD-86 | Variants MUST exist side by side. Making one MUST NOT change another. |
| R-HD-87 | Datasets that hold the same original MUST share its variants. |
| R-HD-158 | A kept variant MUST NOT be changed or overwritten by a request. A request that would make a kept variant again MUST make a new variant with a new id beside it. A skin or bake that names the old one MUST keep naming it, with its files and its marks as they were (operator 2026-11-26, after the remake of O-HDS-18). The new id MUST be the old one with a revision on its last step: `pbrify~2@512` beside `pbrify@512`. A request MUST NOT make a further revision while a kept one can serve it; its reply MUST name the variant that serves it. [agent: the last two sentences] |
| R-HD-159 | A request of several steps MUST take a kept variant as the input of a step where one holds that step's result, and MUST NOT make it again (operator 2026-11-26). That holds for an input kept without its planes and for one whose edges were made for the other rule (R-HD-91). A stale input (R-HD-88) MUST refuse the request with the reason. [agent: the stale rule] |
| R-HD-88 | A variant whose original has changed since MUST NOT be used. It MUST be reported as stale. |
| R-HD-113 | The texture store MUST hold one index of state: for each texture of each dataset its original, its variants and its requests; each skin; each bake. The tooling MUST write the index whenever one of them changes. A reader MUST get a state by reading the index, without running the tooling. |
| R-HD-156 | The state of a texture MUST name each owner of its dataset whose bake or skin names a variant of it other than the original: the owner, the skin, the variant, and whether it is the bake. A skin change or a bake MUST write the states of the textures it changes again. [agent, for R-VIEW-160 to 162] |
| R-HD-114 | The index MUST be rebuildable from the files of the store and of the dataset by one command. Where the index and the files differ, the files hold. One command MUST bring the index up to date after the dataset's files or the installed game changed. |

### 3.5 Skins

History: until 2026-11-25 an owner had one unsaved New Skin, stored as
`new`, saved by a name and never baked. Since 2026-11-26 a skin made
without a name is New Skin N (R-HD-137); a stored `new` is an ordinary
skin of that name.

| ID | Requirement |
| --- | --- |
| R-HD-130 | A skin MUST belong to one owner in one dataset: a unit, an actor or a model. In SC2 a unit's skin MUST cover the models of its actors; a doodad's skin MUST cover the models of its actor. |
| R-HD-131 | A skin MUST be able to name one variant for each texture of its owner's models. A texture it does not name MUST show its original, previewed and baked (operator 2026-11-25: Original is the game's textures only). |
| R-HD-132 | Every owner MUST have the Original skin. It MUST NOT be changed, renamed, deleted, baked or used as a name. |
| R-HD-133 | A skin MUST be made, renamed, changed per texture, and deleted. A skin MUST be made as a copy of another. |
| R-HD-134 | One request MUST make a skin of an owner and queue a variant of each of its textures, with one model and one factor. Without a name the skin MUST be the next New Skin N (R-HD-137). A request that would queue no variant MUST be refused with each texture's reason, and MUST store no skin. The input of each MUST be its variant in the skin the request names as its source. A skin MUST NOT name or keep a link to another skin. Each texture of the skin MUST name its variant once it is made, unless R-HD-162 puts its input back. |
| R-HD-162 | A skin upscale MUST NOT leave its skin naming a variant that misses a limit without the accepted mark. Where such a variant is already made, the skin MUST keep the texture's input, with the reason. Where the request makes one, the skin MUST name the texture's input again, and the reply MUST say so with the reason. The variant MUST stay kept (R-HD-90). A skin that names another variant by then MUST NOT be changed. A request that fails makes no variant and MUST keep the name, so it can be asked again (operator 2026-11-26, "GO" to the four guards; wording and the last two sentences [agent]). |
| R-HD-137 | A skin made without a name (a copy, an upscale) MUST be stored at once as `New Skin N`, N one above the highest N of the owner's skins named so (from 1); a deleted number below it MUST NOT be taken again. An owner MAY have any number of them. Each MUST be renamed, baked and deleted as any skin. No change MUST ask to save or discard another skin first. No skin MUST be offered that was not made. A skin name MUST be 1 to 40 letters, digits, `-` or `_`, one space between words; `original` (ignoring case) MUST be refused. A stored skin MUST be read under the name it is stored with; reading MUST NOT rename or write it. The owner's state MUST name the next New Skin N, so a reader shows the name the pipeline gives. (Operator 2026-11-26: "some of the old logic for saving new skins before creating new ones remains; this should be removed, subsequent New Skin 1, New Skin 2, etc. created instead"; nothing may stand in for a skin, the operator's rule in capitals.) |
| R-HD-135 | A skin MUST NOT name a variant of another texture. |
| R-HD-136 | A bake MUST name the skin it was made from. Changing a skin MUST NOT change a bake's textures until the skin is baked again. Renaming a baked skin MUST rename it in the bake. Deleting a baked skin MUST be refused (operator 2026-11-25). |
| R-HD-138 | The skin names of an owner MUST be unique, ignoring case. A change or a skin file that would give two skins one name MUST be refused. `original` MUST NOT be used in another case (operator 2026-11-25). |

### 3.6 On demand

| ID | Requirement |
| --- | --- |
| R-HD-97 | A variant MUST be made on request only. Nothing MUST be upscaled that was not asked for. |
| R-HD-98 | Requests MUST be queued. The GPU work MUST run on GPU 1, one plane at a time (operator 2026-11-24: "move it to GPU1"). GPU 0 drives the desktop and MUST NOT be used. |
| R-HD-99 | A request MUST report its state: queued, upscaling, encoding, done, or failed with the reason. The state MUST outlive the program that asked. |
| R-HD-100 | A failed request MUST NOT leave a variant. |

### 3.7 Bake and package

| ID | Requirement |
| --- | --- |
| R-HD-140 | An owner MUST have at most one baked skin per dataset. Baking a skin MUST replace the one baked before. Unbaking MUST give the owner its original again. |
| R-HD-141 | A skin baked on a unit MUST change that unit only: the package MUST hold copies of its actors and their models, changed to name the skin's variants, and the unit MUST name the copied actors. |
| R-HD-142 | A skin baked on an actor MUST change that actor only: the package MUST hold copies of its models, changed to name the skin's variants, and the actor MUST name the copies. |
| R-HD-143 | A skin baked on a model MUST change the model: every unit and actor that shows it MUST show the skin. |
| R-HD-144 | Whatever names the owner MUST get the change: a unit's placed instances, its death, placement and portrait models where the unit names them. [agent reading of "all layers upstream get the change"] |
| R-HD-145 | A terrain texture MUST be baked on its own, as one variant per texture. |
| R-HD-101 | The map build MUST package the bakes of the dataset `scoba` into the built map, under paths of their own, with what makes the game load them. |
| R-HD-54 | The bakes MUST cover every model the dataset shows. A map shows the models of what it places and of what its own catalogs name; the game's own data shows every model. |
| R-HD-102 | A build MUST fail when a bake names a variant that is missing or stale, or that has a problem and is not accepted. The message MUST name the texture and the command that fixes it. |
| R-HD-160 | A bake MUST hold the hash of each variant file it names, as the file was when baked. A package MUST fail where a baked variant's file has another hash, and MUST name each such bake. It MUST NOT package the original in its place. Baking again MUST take the file as it is then (operator 2026-11-26, "GO" to the four guards; wording [agent]). |
| R-HD-157 | Where several owners bake a variant that fails R-HD-102, the message MUST name each of them, with the command that unbakes each, and their number. [agent; the build of 2026-11-26 named 1 of 18] |
| R-HD-103 | A bake for an owner that nothing in the dataset uses MUST be kept and listed by the build as unused. It MUST NOT fail the build. |
| R-HD-22 | A build with no bake MUST succeed, keep the built-in textures, and say so. |
| R-HD-104 | A package that holds a variant for one terrain texture the map paints with MUST hold one for every terrain texture the map paints with, colour and normal map. A build that would mix them MUST fail, before a file is written, and name what is missing. A terrain texture the map does not paint with MAY be packaged alone. |
| R-HD-105 | Each package MUST leave a record in the texture store: every packaged texture with its owner, skin, variant and the hash of the packaged file. |
| R-HD-106 | A dataset that no build packages MUST be packageable by one command into a folder shaped like a map layer. |
| R-HD-21 | The built map MUST load with no script error, no load failure, and no texture warning in the game logs. |
| R-HD-24 | A package that does not fit its target MUST fail the build with a message that names the fix. |
| R-HD-55 | R-HD-21 and R-HD-24 hold for model textures. |

### 3.8 Games

| ID | Requirement |
| --- | --- |
| R-HD-107 | The store, the variants, the skins, the bakes, the queue and the limits MUST NOT hold a name, a path, a data rule or a file format of any one game. |
| R-HD-108 | A game MUST plug in through one written interface: list the textures of a dataset, read an original, name where every texture file of a dataset lies, say how a texture is split into planes and whether it tiles, name its users, list the owners and the textures of each, package the bakes, check a package. |
| R-HD-109 | A texture file format MUST plug in through one written interface: read, decode, encode. |
| R-HD-110 | Adding a game or a format MUST NOT take an edit to the core or to another game. |
| R-HD-111 | StarCraft II is the first game, StarCraft: Ghost the second (3.11, operator 2026-11-25). Each interface MUST have a second implementation under test. |
| R-HD-115 | A game MUST be able to say that it bakes nothing, with the reason. Then a bake, an unbake and a package of its datasets MUST be refused with that reason and MUST change no file. Every reader of a state MUST be able to read the reason. [agent: "without BAKING for NOW"] |

### 3.11 StarCraft: Ghost

Operator 2026-11-25: "plan how to add full support for texture upscaling
to SC:G, only without BAKING for NOW; meaning db, pipeline, viewers,
menus, the entire shebang, just don't enable baking yet". The choices of
the plan were the operator's the same day: the material lookup of
NODExport, owners actor and model, the original's format kept, the bake
control disabled with the reason.

| ID | Requirement |
| --- | --- |
| R-HD-150 | Ghost MUST be a game of the tooling, with one dataset: the extracted game build that `GHOST_PATH` names. The tooling MUST NOT write into the build. |
| R-HD-151 | Its textures MUST be the texture files the materials of its model files name, found by the material lookup the viewer uses (NODExport). No second copy of the lookup rules MUST exist. |
| R-HD-152 | Its owners MUST be a model file (`model:`) and an actor, a template of `Global.not` with a model (`actor:`). An actor MUST show its model file. |
| R-HD-153 | A variant MUST keep its original's compression format: DXT1, DXT3, DXT5, or 32-bit ARGB without compression. Any other file MUST be refused with the reason: DXT2, a cube map, a volume, DXT1 with transparent pixels, a side under 32 pixels. |
| R-HD-154 | Ghost MUST bake nothing (R-HD-115). The reason MUST be "baking is not enabled for StarCraft: Ghost". |
| R-HD-155 | Requests, the queue, the limits, skins, New Skin N, removal and edits MUST hold for Ghost as for StarCraft II. |

### 3.9 Classic skins

Operator 2026-11-20: "replace all terran and zerg units that have remastered
versions with the remastered ones".

| ID | Requirement |
| --- | --- |
| R-HD-60 | The Marine, SCV, Battlecruiser, Hydralisk, Ultralisk, Drone, Hatchery, Lair, and Hive MUST show the models of their classic ("Remastered") collection skin, for every player, whether or not the player owns the skin. Their death, placement, and portrait models MUST be those of the skin, as the skin lists them. |
| R-HD-61 | The swap MUST keep the map's own changes to those model entries (scale, animation speed). |
| R-HD-62 | The Command Center, with its Orbital Command and Planetary Fortress forms, MUST show the classic model too. Its leg footprint (REQ-SCALED-FOOTPRINTS R-FP-10) MUST be measured on the classic model (operator 2026-11-20: "the legs are a tiny bit off need to recalculate footprint"). |
| R-HD-65 | The SCV MUST be drawn at 200% of its stock size (operator 2026-11-20; 150% first). |

### 3.10 Back faces

Operator 2026-11-20, on the psi destroyer: "find all culled / missing faces
... insides of pipes, under surfaces, etc. paint them solid dark gray".
Then, the same day: "texture from front of face mirrored on back instead of
solid color". The second replaces the gray.

| ID | Requirement |
| --- | --- |
| R-HD-70 | Where the eye meets the back of a solid surface of the psi destroyer model, it MUST see the texture of the front of that surface, mirrored, not through the model. This holds for every solid, one-sided surface: the inside of pipes, the underside of plates, the inside of the hull. |
| R-HD-71 | The front of every surface, and the glass and energy parts of the model, MUST look as before. |
| R-HD-72 | The tooling MUST report how many pieces of the model are open and how many open edges they have. |

## 4. Operator Checks

Only a person can judge these. The tooling does not claim them.

| ID | Check |
| --- | --- |
| O-HD-1 | The ground in the game looks sharper than before and keeps its look. |
| O-HD-2 | No seams, grain, or invented patterns show on the ground. |
| O-HD-3 | Lighting on the ground looks as before: no flat or inverted bumps, no new shine. |
| O-HD-4 | The game runs as smoothly as before. |
| O-HD-5 | Models with baked skins look sharper and keep their look: edges of leaves, team colour, glow, and shine. |
| O-HD-6 | The classic units look and animate right in the game: stand, walk, attack, death, portrait; the Hive at its scale of the map. |
| O-HD-7 | The psi destroyer shows no see-through holes from any side or from below. What was a hole shows the texture of the surface, with no flicker, and its lighting fits the model. |
| O-HD-8 | Whether a variant is good enough to bake. The limits of 3.3 only flag what is measurably wrong. |

## 5. Open

| ID | Question |
| --- | --- |
| O-HD-9 | R-HD-90 keeps today's rule: a problem refuses a bake unless the variant is accepted. The operator asked to show the numbers; he did not say whether a problem may still be baked. [agent] |
| O-HD-10 | Today `pbrify` gets colour planes only; data planes get `fast`, because `pbrify` draws a crosshatch into masks and normal maps. The operator named only `seedvr2` as blocked. The design keeps today's rule for `pbrify`. [agent] |

## 6. Withdrawn

Withdrawn on 2026-11-24 with the variant design of 2026-11-15: R-HD-14, 15,
20, 23, 30 to 35, 40, 50, 51, 63 and 64.

Withdrawn on 2026-11-24 with steps, chains and picks: R-HD-80 to 84 (by
R-HD-120 to 124), R-HD-92 to 96 (by R-HD-130 to 136 and 140). The ids are not
reused.

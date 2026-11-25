# REQ-PHOTOCRAFT: Texture Editing in PhotoCraft

**Date:** 2026-11-25
**Status:** Draft. Written from the operator's statement and answers of
2026-11-25. Rows marked "operator" restate them. Rows marked "agent" are
the agent's and need the operator's word. Awaiting operator review of this
text. Not built: the specification lists the state of each requirement.

Operator statement (2026-11-25): "research how to integrate PhotoCraft in a
dialog the same way as we have the teture viewer, need to clone the repo,
automate the provisioining for a wasm build, run server in the bg, etc. incl
managed sessions". "the goal is to be able to click a small edit button in
the bottom left of the texture card thumbnail and open a png scratch copy of
the texture in photocraft embedded, with automation to detect edits to the
scratch file and offer the user to transfer them to the actual texture via a
dialog".

Operator answers (2026-11-25, later), to the first draft's questions. Where
the button goes: "yes, in the window, not the list". One plane as a PNG, or
the whole file: "properly integrate everything as photoshop layers inside
photocraft; make it professional". Whether a transfer also offers Save to
Skin: "no, just creates the new variant". The quality limits on an edit: "it
should be able to bake arbitrary things if user-made; the rule only applies
to uto-generated content". The Rust toolchain: "own".

Operator answers (2026-11-25, third), to the second draft's questions.
Whether a model's variant made from an edit is compared with the edit:
"yes". A mask as a plane group or as an alpha channel: "separate alpha layer
better than alpha channel". A layer outside the plane groups: "leave it out
and say so".

The second answer replaces "a png scratch copy": the scratch is one layered
document that holds every plane of the texture.

## 1. Scope

This contract binds the editing of a texture in PhotoCraft, an open-source
image editor, run inside the viewer page.

In scope:

- building PhotoCraft from its source, on this machine: the editor for the
  browser, and the tool that renders a document without a window;
- serving the editor in the background;
- the editor window in the viewer page;
- edit sessions: the layered scratch document of a texture, kept and
  managed;
- detecting an edit of the scratch;
- transferring an edit to the texture, as a new variant.

Out of scope:

- what PhotoCraft can do as an editor. That is its own project;
- upscaling, skins, bakes and the package. That is
  [REQ-HD-TEXTURES](REQ-HD-TEXTURES.md);
- the texture window itself. That is [REQ-VIEWER](REQ-VIEWER.md), section
  3.11;
- editing a texture of a game that offers no texture service.

Implementation lives in
[SPEC-PHOTOCRAFT](../specifications/SPEC-PHOTOCRAFT.md).

## 2. Definitions

Words of REQ-HD-TEXTURES and REQ-VIEWER keep their meaning: texture,
original, variant, plane, skin, bake, texture store, texture window, tile.

- **PhotoCraft**: the image editor of the project `storytold/photocraft`.
- **Editor site**: PhotoCraft built for the browser: a folder of static
  files.
- **Renderer**: PhotoCraft's own tool that opens a document, runs commands
  and writes pictures, with no window.
- **Editor window**: the window of the viewer page that shows the editor
  site in a frame.
- **Bridge**: our change to PhotoCraft that lets the viewer hand it a
  document and take its saves.
- **Edit session**: the kept state of one edit: what was opened, the
  scratch, and what was transferred.
- **Base**: the planes a session was opened with. They never change.
- **Scratch**: the layered document of a session that the person edits, in
  Photoshop's format (PSD).
- **Plane group**: a named group of layers in the scratch. It holds one
  plane of the texture.
- **Rendered plane**: the picture the renderer makes of one plane group.
- **Edited**: a scratch with a rendered plane whose pixels differ from its
  base.
- **Transfer**: making an edited scratch a variant of its texture.
- **Edited variant**: a variant made by a transfer. It is user-made.
  Every other variant but the original is made by a model.

## 3. Requirements

Source "operator" is the statement and the answers above. "agent" marks the
agent's own rows.

### 3.1 Provisioning

| ID | Requirement | Source |
| --- | --- | --- |
| R-PC-1 | The editor site MUST be built on this machine from PhotoCraft's source, to WebAssembly. The renderer MUST be built from the same source. The source MUST be a clone at one pinned tag and commit. | operator; the renderer is the agent's |
| R-PC-2 | One command MUST do the whole provisioning: the build tools, the clone, our patches, both builds, the install, and a check of the result. | operator |
| R-PC-3 | A second run with nothing changed MUST do no work and say so. A run after a pin or a patch changed MUST rebuild. | agent |
| R-PC-4 | Every pin MUST be written in one place in the repository: the source commit, the toolchain, the build tool. The install MUST record the pins and the hash of each patch it was built from. | agent |
| R-PC-5 | Our changes to PhotoCraft MUST be patch files in the repository. The clone, the build output and every cache of the build MUST be outside git and off the repository disk. | agent, SPEC-PATHS |
| R-PC-6 | The build MUST bring its own Rust toolchain. It MUST NOT change a toolchain other projects on the machine use. | operator ("own") |
| R-PC-7 | A failed step MUST stop the command, name the step and name its log. Nothing MUST be installed from a failed build. | agent |
| R-PC-8 | The installed site MUST hold PhotoCraft's licence, notice and attribution files. | agent |
| R-PC-9 | The dependency check MUST report whether the site and the renderer are installed and whether they match the pins. It MUST install nothing. | agent |

### 3.2 Serving

| ID | Requirement | Source |
| --- | --- | --- |
| R-PC-10 | The editor site MUST be served in the background by a managed service. No one MUST have to start a server by hand to edit. | operator |
| R-PC-11 | The service MUST be installed, started, stopped and checked by the same means as the viewer's. | agent |
| R-PC-12 | The editor MUST load and work with no network past this machine. | agent |
| R-PC-13 | While PhotoCraft is not installed, the viewer MUST start and work. Every control of this contract MUST be absent, and the health answer MUST say what is missing. | agent |

### 3.3 Editor window

| ID | Requirement | Source |
| --- | --- | --- |
| R-PC-20 | In the texture window, each tile that shows a variant MUST have a small **Edit Texture** button at the bottom left of its preview. The list rows MUST NOT have one. | operator |
| R-PC-21 | A click on the button MUST open PhotoCraft in a window of the viewer page, as the texture window is: floating, movable, inside the page. It MUST NOT open a browser tab. | operator |
| R-PC-22 | The editor MUST open with the scratch of that tile's variant loaded. The person MUST NOT have to choose a file. | operator |
| R-PC-23 | A click on the button MUST NOT pick the tile. It MUST change no variant, no skin and no bake. | agent |
| R-PC-24 | While the editor has the keyboard, every key MUST go to the editor. Escape MUST NOT close the editor window. | agent |
| R-PC-25 | **File > Save** in the editor MUST write the session's scratch. It MUST NOT start a browser download. The editor MUST say whether the save was kept. | agent |
| R-PC-26 | Closing the editor window while the editor holds work it has not saved MUST ask first. | agent |
| R-PC-27 | An editor that does not start, or a scratch that does not load, MUST be reported in the window with the reason. | agent |
| R-PC-28 | For a game without a texture service the button MUST be absent (R-VIEW-100). | agent |
| R-PC-29 | A texture the tooling cannot split into planes (R-HD-53) MUST NOT be editable. Its button MUST be disabled and say why. | agent |

### 3.4 The scratch

| ID | Requirement | Source |
| --- | --- | --- |
| R-PC-70 | The scratch MUST be one layered document in Photoshop's format. It MUST hold every plane of the texture, each as a plane group named after the plane. | operator ("everything as photoshop layers") |
| R-PC-71 | The document MUST have the variant's width and height. Each plane group MUST start with one layer that holds the plane as it was opened. | agent |
| R-PC-72 | What the person adds MUST be kept by a save and be there when the session is resumed: layers, masks, adjustment layers, layer styles, blend modes. | operator ("make it professional"); the list is the agent's |
| R-PC-73 | A plane MUST be read from the scratch by PhotoCraft's own renderer. What the editor shows for a plane group alone MUST be what is transferred. | agent |
| R-PC-74 | The scratch MUST be a file another program that reads and writes Photoshop's format can edit in place. | agent, R-PC-41 |
| R-PC-75 | A scratch that cannot give every plane MUST be reported with the reason when it is detected: a file that cannot be read, another width or height, a plane group that is missing, a plane that renders with a see-through pixel. | agent |
| R-PC-76 | A layer outside the plane groups MUST be left out of every plane. It MUST NOT refuse the scratch. The viewer MUST say so, naming each such layer: on the session and in the transfer dialog. | operator ("leave it out and say so") |

### 3.5 Edit sessions

| ID | Requirement | Source |
| --- | --- | --- |
| R-PC-30 | Opening the editor on a tile MUST make an edit session, or resume the one there is. There MUST be at most one session per texture and input variant. The tiles of each plane of that texture and variant MUST open the same session. | operator ("managed sessions") |
| R-PC-31 | A session MUST hold its base, its scratch, and a record of what it was opened from. The base MUST NOT change. | operator |
| R-PC-32 | Sessions MUST live in the texture store. They MUST outlive the page, the server and a restart of the machine. No step MUST delete a scratch unless the person discards it. | agent, REQ-HD-TEXTURES "DO NOT LOSE ANY WORK" |
| R-PC-33 | The viewer MUST list the sessions of a dataset with their states. Each MUST be resumable. Each MUST be discardable, after a question; the discard button MUST be red (R-VIEW-136). | operator ("managed sessions") |
| R-PC-34 | A session MUST have one of four states: unchanged, edited, transferred, stale. The state MUST be worked out from the session's files. | agent |
| R-PC-35 | A session whose input variant is gone, or has another file than when it was opened, MUST be stale. A stale session MUST keep its scratch and MUST refuse a transfer with the reason. | agent, R-HD-88 |
| R-PC-37 | A texture with a session MUST show it in the texture window: on its list row and on the tiles it was opened from. | agent |

### 3.6 Detecting an edit

| ID | Requirement | Source |
| --- | --- | --- |
| R-PC-40 | The viewer MUST detect a changed scratch with no action of the person in the viewer. | operator |
| R-PC-41 | It MUST detect a change made by a save in the editor window, and a change made by any other program that writes the scratch file. | operator ("detect edits to the scratch file") |
| R-PC-42 | A scratch MUST count as edited by the pixels of its rendered planes, not by its time or its bytes. A scratch saved again with rendered planes equal to its base MUST be unchanged. | agent |
| R-PC-43 | On an edit the viewer MUST offer the transfer in a dialog. It MUST NOT transfer without the person's confirmation. | operator |
| R-PC-44 | The offer MUST open once per changed scratch content. An offer that was put off MUST leave a mark and a **Transfer Edit…** control on the session; it MUST NOT open again by itself until the scratch changes again. | agent |

### 3.7 Transfer

| ID | Requirement | Source |
| --- | --- | --- |
| R-PC-50 | The transfer dialog MUST show the texture, the input variant, each plane that changed with its base and its rendered plane as pictures, the planes that did not change by name, and what will happen in plain words. Its buttons MUST be **Transfer Edit**, **Keep Editing** and **Discard Edit**. Discard MUST be red and MUST ask again. | operator ("via a dialog"); the content is the agent's |
| R-PC-51 | A transfer MUST make a new variant of the texture: an edited variant. It MUST do nothing else. The original, the input variant and every other variant MUST NOT change (R-HD-86). | operator ("just creates the new variant") |
| R-PC-52 | An edited variant MUST keep the layout of its original (R-HD-10). Each plane comes from the scratch's rendered plane. A plane that did not change MUST be the input variant's, bit for bit. | agent |
| R-PC-53 | A scratch of R-PC-75 MUST be refused with the reason. A refused transfer MUST change nothing. | agent |
| R-PC-54 | Two transfers with the same input variant and the same rendered planes MUST give one variant (R-HD-124). | agent |
| R-PC-55 | An edited variant MUST record its input variant, the planes that changed, the hash of the rendered planes, and its numbers (R-HD-13). | agent |
| R-PC-56 | A transfer MUST change no skin and no bake, and MUST NOT offer to. The edited variant MUST appear in the tiles of its texture and MUST be picked and saved to a skin as any variant is (R-VIEW-133). | operator |
| R-PC-57 | A transfer MUST report its state as a request does (R-HD-99) and MUST leave no variant when it fails (R-HD-100). It MUST go on when the page is closed. | agent |
| R-PC-58 | After a transfer the session MUST stay. A later edit of its scratch MUST be offered again. | agent |
| R-PC-59 | Rendering a scratch and making an edited variant MUST NOT use a GPU (R-HD-98 keeps GPU 0 for the desktop and GPU 1 for the queue). | agent |

### 3.8 Limits

| ID | Requirement | Source |
| --- | --- | --- |
| R-PC-80 | The quality limits of REQ-HD-TEXTURES 3.3 MUST apply only to a variant a model made. They MUST NOT make a problem on an edited variant. | operator ("the rule only applies to uto-generated content") |
| R-PC-81 | A bake MUST NOT be refused for the numbers of an edited variant. | operator ("it should be able to bake arbitrary things if user-made") |
| R-PC-82 | The numbers of an edited variant MUST still be measured and shown, with no colour band. | agent |
| R-PC-83 | A variant a model made from an edited variant MUST be held to the limits against that edited variant, not against the original. Through several model steps, it is the nearest edited variant among its inputs. | operator ("yes"); the second sentence is the agent's |

### 3.9 Proof

| ID | Requirement | Source |
| --- | --- | --- |
| R-PC-60 | Every requirement MUST have a test a program decides, with at least one negative case (R-VIEW-90). | agent |
| R-PC-61 | What only a person can judge MUST be listed as an operator check and MUST NOT be reported as verified (R-VIEW-93). | agent |

## 4. Operator Checks

Only a person can judge these. The tooling does not claim them.

| ID | Check |
| --- | --- |
| O-PC-1 | PhotoCraft in the editor window looks right and is usable: its panels, tools, menus and shortcuts. |
| O-PC-2 | Painting is quick enough to work with at the sizes of our textures. |
| O-PC-3 | The **Edit Texture** button reads well on a tile and is easy to hit. |
| O-PC-4 | The transfer dialog and the session list read well and say what will happen. |
| O-PC-5 | An edited variant looks right in the texture window, on a model and in the game. |
| O-PC-6 | The scratch reads as a professional layered document: the plane groups, their names and their order make sense to someone who edits textures. |

## 5. Open

| ID | Question |
| --- | --- |
| O-PC-10 | Closed (operator 2026-11-25): the button is on the tiles of the texture window, not on the list rows. |
| O-PC-11 | Closed (operator 2026-11-25): not one plane as a PNG. Every plane, as layers of one document (3.4). |
| O-PC-12 | Closed (operator 2026-11-25): a transfer makes the new variant and nothing else. |
| O-PC-13 | Closed (operator 2026-11-25): the limits apply to variants a model made. A user-made variant is baked whatever its numbers (3.8). |
| O-PC-14 | R-HD-121 says a variant is made from an input, a model and a size. An edited variant is made from an input and a scratch. R-HD-121, R-HD-124, R-HD-11 and R-HD-90 now have a sentence for it, in the agent's words. The operator has not read them. [agent] |
| O-PC-15 | Closed (operator 2026-11-25): the build brings its own toolchain. |
| O-PC-16 | Datasets that hold the same original share its variants (R-HD-87). The design shares its edit sessions the same way. [agent] |
| O-PC-17 | Closed (operator 2026-11-25): yes. A variant a model makes from an edited variant is compared with its edited input (R-PC-83). |
| O-PC-18 | Closed (operator 2026-11-25): "separate alpha layer better than alpha channel". The alpha plane is a plane group, not a channel of the document (R-PC-70). |
| O-PC-19 | Closed (operator 2026-11-25): "leave it out and say so". A layer outside the plane groups is left out and named (R-PC-76). |

## 6. Withdrawn

Withdrawn on 2026-11-25 with the operator's second answer: R-PC-36 (a
working document beside a PNG scratch; the scratch is the layered document
now, R-PC-70 and R-PC-72) and R-PC-45 (the rules of a PNG scratch; by
R-PC-75). The ids are not reused.

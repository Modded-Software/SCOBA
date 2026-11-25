# SPEC-VIEWER: Asset Viewer, Core and Interfaces

**Date:** 2026-11-24
**Status:** Built through step 7: two games (sc2, ghost) and two formats
(m3, nod) run through the extension points. Not built: step 8 (tests in
TypeScript, the typed test object) and section 17 (textures). Section 12
gives the state of each requirement.
**Requirements:** [REQ-VIEWER](../requirements/REQ-VIEWER.md)

Game specifications: [SPEC-VIEWER-SC2](SPEC-VIEWER-SC2.md),
[SPEC-VIEWER-GHOST](SPEC-VIEWER-GHOST.md).

This document names no game rule. Names and types of every interface are
in the code files each section names. This document states duties and
rules.

## 1. Principle

- Core knows games and formats only as interfaces (R-VIEW-1, R-VIEW-4).
- A game is two modules, page and server, each registered in one line
  (R-VIEW-2).
- A format is one module. A game lists the formats it uses (R-VIEW-3).
- The server describes a game's gallery as data. The page builds the
  gallery from it (R-VIEW-25).
- The game's page module holds only what data cannot say: how a record
  becomes an instance (R-VIEW-44).
- Features see instances through one interface and ask for capabilities
  (R-VIEW-5, R-VIEW-6).

## 2. Labels

- **[verified]**: a Playwright test passed in a run named in section 12.
- **[today]**: the code does it and the named test files passed in a full
  run of section 13. No one has checked that they assert every clause.
- **[plan]**: not in the code.
- **[operator]**: only a person can judge it.

## 3. Layers

All under `webviewer/src/`.

| Layer | Side | Holds |
| --- | --- | --- |
| `shared` | both | ids and messages |
| `page/core` | page | render host, scene, camera, events, store, status, registries |
| `page/features` | page | one folder per feature |
| `page/ui` | page | components, drawers, game tabs, gallery, instances panel |
| `formats/<id>` | page | one format |
| `games/<id>` | both | one game: `page`, `server`, `shared` |
| `server/core` | server | HTTP, routes, static files, game registry |
| `tools` | Node | surveys, fixtures, the build |

Import rule, checked in every test run (section 9):

- `shared` imports nothing of the viewer. `core` imports `shared`.
- `features` and `ui` import `core` and `shared`. `features` may import
  `ui`, never the reverse.
- `formats/<id>` imports `core` and `shared`.
- `games/<id>` imports `core`, `shared` and the formats it lists, never
  another game (R-VIEW-7).
- `core`, `features` and `ui` never import a game or a format.
- Only `page/main.ts` and `server/main.ts` import games.
- Page code and server code never import each other. Neither do a game's
  `page` and `server`; both may import its `shared`.
- `tools` may import `shared`, formats, a game's `shared` and `server`,
  `server/core` and the renderer library, never page code.
- The renderer library is imported only by `page/core`, formats and
  `tools`.
- An import that leaves `src/` is refused, except the renderer library and
  the packages of `package.json`.

## 4. Source layout

Besides `src/`, under `webviewer/`:

| Path | Holds |
| --- | --- |
| `public/` | the HTML, style sheets, shaders, and the page bundle |
| `tests/` | Playwright tests |
| `scripts/` | shell entry points |
| `ref/`, `patches/` | the renderer library's repo and its commits as files (section 9) |
| `build/` | bundles; not in git |

Adding a game adds `src/games/<id>/` and one line in each `main.ts`.

## 5. Shared types

`src/shared/`. Both sides compile against them (R-VIEW-11).

| Type | Holds |
| --- | --- |
| ids | game, dataset, category, format: the id rule of section 8 |
| game info | id, label, tab text, available, the reason when not, whether it has a texture service. |
| dataset info | id, label, built-in, the signature loaded, the signature of its sources now, whether they differ |
| category info | id, tab label, noun, filters, whether "add all" is offered. The page's game plugin says whether its records are ground textures. |
| filter info | query parameter, label, buttons or select, values with labels |
| page | total and items |
| record summary | id, name, the grey line under it, icon, placeable, the word for it when not |
| record detail | the summary, game, dataset, category, servable model files (one per variant), picture, the game's own data. A ground record: its colour file and its normal map, as the texture service names them. |
| backdrop | id, name, game, dataset, file |
| asset kind | model, texture, animation, material |
| error | the error text and context fields |

## 6. Page interfaces

`src/page/core/plugin.ts` and `context.ts`.

### 6.1 Model and instance

Every format's model and instance offer these. Features use nothing else.

| Of | Offers |
| --- | --- |
| model | its format; culling sphere; rest-pose box; whether it has geometry; the parts not drawn (R-VIEW-81); the texture references it names; a new instance |
| instance | its model; its sequences with lengths; place, turn, scale; a sequence to play, looped or held at its end, and a time scale; the playhead and whether it passed the end; show and hide; attach to and detach from a scene; whether the last frame drew it; mouse-over brightness; solid parts only; a draw alone for the outline; a draw in one flat colour for the pick |

- Sequences are on the instance. Two items may share a model file and
  differ in animations, when a game keeps animations outside it (6.4).
- m3: an adapter closes the gaps to the library's classes. The library is
  not changed for them. The adapter keeps the library object as `m3`.

### 6.2 Capabilities

Optional. A missing one means the instance cannot do it (R-VIEW-6).

| Capability | Does | m3 | nod |
| --- | --- | --- | --- |
| `teamColor` | a count; set by index | 14 colours | no |
| `tint` | set a colour or none | the vertex colour | no |
| `textureOverride` | lists slots, each with its in-model path and its own texture's longest side; puts another texture into a slot or takes it out; counts the slots that hold another | one slot per active layer that names a texture file | no |
| `edges` | draws the triangle edges as lines in one flat colour; returns the lines drawn | yes (patch 0056) | yes |

- An item without `teamColor` has no team control.
- `edges` draws each edge once, with the format's own vertex shader, so
  the lines follow the pose. The caller sets depth and blend state.
- A new capability is a new optional member and the feature that uses it.
  Existing formats are not edited.

### 6.3 Format module

| Member | Duty |
| --- | --- |
| id, extensions | |
| handlers | the renderer library's model and texture readers |
| `adopt` | the library's loaded resource as this format's model, or nothing |
| `parse`, optional | the bytes of a model file as the object its handler takes |
| `attachClips`, optional | give an instance animations kept outside its model file; returns the clips left out, each with its reason |
| `capabilities` | those of an instance |
| `postPasses`, optional | draws after the scene, each with an id and a switch |
| `inspect`, optional | what only the format knows, for `state()` |
| `probes`, optional | inspection for tests |

- The library picks a handler by a file's bytes, never by its name. A
  format without a magic number gives `parse`: core picks the format by
  the file's extension, parses, and hands the result to the library.
- Core loads every model through one call and keeps one model per game,
  dataset signature and file.
- Core asks each format to adopt a loaded file. The first that does owns
  it. None: the load fails.
- A format refuses what it cannot read, naming the file, the record and
  the version (R-VIEW-82). The load fails with that message. A failed
  fetch gives "cannot load <file>".
- Clips for a format without `attachClips` are a failure, reported. A
  clip that fails is left out and named; the others are kept. The rest
  animation waits for the clips.
- Core sums what the post passes drew per frame. A test turns a pass off
  by its id.
- Probes are reached as `sc2viewer.probe(format, name, ...)`. An unknown
  format or name is an error that names it.

### 6.4 Game plugin

| Member | Duty |
| --- | --- |
| id, formats | |
| categories | each category's route name and noun. The noun names the row's data attribute, the drag type and the item's key in `state()`. |
| `checkRecord` | checks what the server sent, field by field |
| `describe` | the lines of the preview card |
| `place` | how a record becomes an instance |
| `placeFile` | how a bare file becomes one |
| `playRate` | the speed of one animation of an item |
| `restSequence` | the animation an instance starts with, or none |
| backdrop word | what a backdrop record is called |

A placement holds: the model file; the variant and how many there are;
scale; height; angle; tint; pick, which chooses inside data ranges;
whether it becomes the backdrop; clips; radius, for the grid glow and the
room in a row; hit radius; whether the team control shows; icon.

- Core applies a placement. It does not read a record's data.
- No variant wished: a random one, the map editor's rule. A wished variant
  the record lacks is refused, on an add, a dataset swap and the variant
  select: "<id> has no variation N (it has M)".
- An instance's sequences are those of its model file, then the clips.
- The server resolves asset paths. The page has no resolver.

### 6.5 Scene item

`core/types.ts`. An item holds: id; game; dataset; its source, a category
and record or a bare file; placement; model; instance; capabilities;
place, angle, scale; sequence; one-shot; team; skin; the largest
texture side it shows; options.

- Options are checked by the game. An unknown key refuses the item, with
  its name; the item is not added. Neither game has options of its own.
- `team` and the skin are item fields, not game options: the team
  colour is a format capability, the skin core's (17.4). The scene
  document keeps the skin as the option `skin`. A `team` that is not a
  whole number, or a skin that is not a name, refuses the item.
- A team or an animation the model does not have refuses the item, with
  the number; neither is replaced.
- A scene document keeps them all in the item's options.

### 6.6 Features

A feature has an id and an install that takes the context. The context
gives: games, render host, scene, selection, camera, status, store,
events, the API client, UI, the texture window, the skins, and the
test API builder.

- A feature takes what it needs from the context. There is no page object
  and no shared untyped state (R-VIEW-12).
- Features talk through events and services. A feature never imports
  another feature.
- Row controls and menu entries are added through the UI service, each
  with a test of the item. A capability control tests for the capability.
- `main.ts` builds the services in order. Then each game installs and
  gives its parts. Then each feature installs.
- Features: `dataset-reload`, `controls`, `landmarks`, `add-all`, `drag`,
  `sky`, `pick`, `select`, `clipboard`, `inspect`, `scenes`, `edges`.
- A game's parts: its glow class, its facts, its options check, the
  texture service's name of a texture an instance names (absent: no
  service), and what a double-click on an item or a record opens.
- A game or feature adds test members through the test API builder. They
  make `window.sc2viewer` and `window.SC2App`. A member given twice
  throws.

Events (`core/bus.ts`): item added, removed, swapped, changed; scene
edited; selection, game, dataset, view, landmarks, camera changed; frame;
scene drawn, after which a listener may draw over the scene with its
depth; startup and flush, which collect work. A listener that throws is
reported. The others still run.

## 7. Server interface

`src/server/core/backend.ts`. A backend answers in values and throws for a
reply that is not a success. It never sees a request, except in its
extensions.

| Member | Duty |
| --- | --- |
| id, label, tab text, default dataset | |
| datasets | list them with their problems; say whether one exists; reload one |
| categories, summary | of a dataset. The summary is the game's own counts. |
| list, record | one page of a category; one record. Either may answer later (a promise). |
| file, asset, icon | a file on disk or nothing: a raw file by its servable path, a reference a model uses, an icon |
| backdrops | one page |
| extensions | routes below `/api/<game>/x/` |
| textures | the texture service (section 17). Absent: the game has none. |

- A game whose data is not on the machine is listed as not available,
  with the reason. The server starts without it (R-VIEW-8).
- Only the icon names a dataset's index lists are served.
- Core's own settings: `PORT` (4517; tests use 4518) and `HOST`
  (`127.0.0.1`). Every other setting is a game's.

## 8. Protocol

Replies are JSON unless a file is served.

| Method and route | Reply |
| --- | --- |
| `GET /api/health` | each game's id and whether it is available |
| `GET /api/games` | the default game and every game's info |
| `GET /api/<game>/datasets` | default, datasets, problems |
| `POST /api/<game>/datasets/<id>/reload` | the dataset's info |
| `GET /api/<game>/categories?dataset=` | category infos |
| `GET /api/<game>/summary?dataset=` | the game's counts |
| `GET /api/<game>/records/<category>?dataset=&q=&offset=&limit=&<filter>=` | a page of record summaries |
| `GET /api/<game>/record/<category>?dataset=&id=` | a record detail |
| `GET /api/<game>/file?dataset=&path=&v=` | the file |
| `GET /api/<game>/asset?dataset=&kind=&ref=&v=` | the file, or JSON for a material |
| `GET /api/<game>/icon/<name>?dataset=` | the image |
| `GET /api/<game>/backdrops?q=&offset=&limit=` | a page of backdrops |
| `any /api/<game>/x/<name>` | the game's own |
| `GET /api/<game>/textures?dataset=&asset=` | texture states (17.2) |
| `POST /api/<game>/textures/judge?dataset=` | has the named assets judged; their states (17.2) |
| `POST /api/<game>/textures/request?dataset=` | queues an asset, an input, a model and a size; the request's state |
| `GET /api/<game>/textures/owner?dataset=&owner=` | an owner's state (17.2); null when the index holds no such owner with textures |
| `POST /api/<game>/textures/skin?dataset=` | a skin change of 4.8 of SPEC-HD-TEXTURES; the owner's state |
| `POST /api/<game>/textures/bake?dataset=` | bakes an owner's skin, or a terrain texture's variant; the state |
| `POST /api/<game>/textures/unbake?dataset=` | removes a bake; the state |
| `GET /api/<game>/textures/file?dataset=&asset=&variant=&v=` | a variant's file |
| `GET /texture-viewer.html`, `/vendor/texview.js` | the texture window's page and its script |

- `dataset` is required wherever it appears.
- `limit` is 1 to 500, 60 when absent. `offset` is 0 when absent.
- `v` is the dataset's signature. It only makes the URL change on a
  reload.
- An extension gets the rest of the path and answers 404 for what it does
  not have.
- Errors: 400 a missing or bad parameter; 404 an unknown game, dataset,
  category, record, file or asset kind the game lacks; 405 a wrong method;
  503 a game that is not available; 500 anything else.
- The route is matched on the raw URL, so an encoded `..` reaches no
  route.
- The id rule: `^[a-z0-9][a-z0-9_-]{0,39}$`.

## 9. Build and code rules

- TypeScript in strict mode, with `noUncheckedIndexedAccess` and
  `noImplicitOverride` (R-VIEW-10). Node 24.11.1, compiler 7.0.2.
- No `any`. No cast that hides a type error. No file over the line limit.
- `src/tools/build.ts` bundles the page into `public/vendor/renderer.js`
  and the server into `build/server.js`, with esbuild.
- When the page bundle does not load, a few lines in `index.html` show the
  failure and name the file.
- `scripts/tool.sh <name>` bundles and runs `src/tools/<name>.ts`.
- `scripts/typecheck.sh` runs the compiler on three settings files (Node
  code, page code, the library) and then the import rule of section 3. It
  runs first in `scripts/test.sh`. An error ends the run (R-VIEW-13).
- Python and shell tools stay as they are.

The renderer library, `mdx-m3-viewer`, is viewer code (operator
2026-11-23):

- It is bundled from its source in `ref/`. There is no global renderer
  object.
- A change to it is a commit in the ref repo and a file in `patches/`, 56
  today. The build refuses a ref repo with uncommitted changes and writes
  the patches from the commits. The commit hooks do not see the ref repo.
- Only the code we bundle is type-checked, under the library's own flags.
  It does not pass `noUncheckedIndexedAccess` (O-VSPEC-1).
- Our code reads the library's declaration files. `core/events.d.ts`
  declares the part of the `events` package the page uses. A file named
  `events.ts` would hide it, so the bus is `bus.ts`.

## 10. Page layout and saved state

### 10.1 Panels

- `#side` is the left column: `#gallery` on top, `#instances` below, each
  half the window height.
- `#game-tabs`: one button per game, stacked, vertical text, at the top of
  the gallery's right edge (R-VIEW-20). The chosen tab is bold.
- `#gallery-handle` and `#instances-handle` sit at the bottom of each
  panel's right edge (R-VIEW-24).
- With the gallery closed, its tabs and handle stay clickable at the
  window edge. A tab click opens the gallery on that game (R-VIEW-23).
- The tab of a game that is not available is disabled. Its title is the
  reason (R-VIEW-27).
- Inside the gallery: the dataset select, the category tabs, and one pane
  per category built from its filters.

### 10.2 Scene documents

`src/shared/scene.ts` holds the document type and its check. The page and
an exported file use the same ones (R-VIEW-70).

| Field | Rule |
| --- | --- |
| format, version | `viewer-scene`, 1 |
| id | `s-` then 1 to 40 of a-z and 0-9; unique in the database |
| name | 1 to 80 characters, trimmed |
| created, modified | ISO 8601 UTC |
| items | at most 20000 |

| Item field | Rule |
| --- | --- |
| game, dataset | ids |
| source | a category, a record and a variant or none; or a file |
| x, y, rot | finite; rot in degrees |
| scale | finite, above 0 |
| sequence | an integer, -1 or more |
| pick | 0 to 1 |
| options | the game's own item values |

- The check returns the document or names the first fault by its path. A
  document that fails is not read in part. An unknown field is a fault
  (R-VIEW-71).
- A later version adds a migration from the one before.
- An item whose game, category or record the server lacks is reported and
  not added. The others are added (R-VIEW-80).
- Store: IndexedDB database `viewer`, object store `scenes`, one record
  per scene.
- At startup every record is checked. One that fails is listed as refused,
  with its reason, and can only be deleted (R-VIEW-77).
- The scene to open is the stored id. A stored id that names no scene, or
  a refused one, stops the start with the refused-settings panel (10.3,
  R-VIEW-73). Nothing stored: the newest good scene opens. With none, an
  empty "scene 1" is made.
- Every change writes the document. Writes run one after another. While a
  scene's items are being added, one write follows at the end.
- The scene list is in the view tools: open, rename, delete after a
  question, new, export, import (R-VIEW-75). Export downloads the document
  as stored. An import is checked, given a new id and a free name, stored
  and opened. A refused import changes nothing and says why (R-VIEW-76).
- The page never writes a scene into its address. An address with a `#`
  part is refused with a message and cleared (R-VIEW-74).

### 10.3 Settings

`core/settings.ts` holds every key, its parser and its default. Keys, all
under `viewer.`:

| Key | Holds | Nothing stored |
| --- | --- | --- |
| `camera` | yaw, pitch, distance, target | the origin from the south: yaw -pi/2, pitch 0.5, distance 9, target (0, 0, 0.8) |
| `drawers` | which drawers are open | both open |
| `game` | the chosen game (R-VIEW-22) | the server's default game |
| `dataset.<game>` | the chosen dataset of a game | the game's default dataset |
| `view` | the grid switch, the backdrop and the ground texture (17.7) | grid on, no backdrop, no ground texture |
| `landmarks` | the landmarks and the chosen one | none but the origin, none chosen |
| `scene` | the id of the open scene | the newest scene, else a new one |

- Each key has one parser. An object must have exactly its keys: a
  missing or an unknown key is refused. A backdrop and a ground texture
  name their game and dataset. The chosen landmark is the origin (0) or
  one of the list.
- Before the page starts, `main.ts` checks every stored `viewer.*` key
  (`refusedSettings`). A key the page does not know, text that is not
  JSON, and a value its parser refuses are refused.
- At start the game, dataset and scene choices are checked against what
  exists: a game the server cannot open, a dataset the game does not
  list, a scene that is missing or fails its check. These are refused
  the same way (`SettingsRefused`).
- A refusal stops the start (R-VIEW-73). Nothing is put in place of the
  refused value, and `ready` stays unset. The panel `#settings-refused`
  (`core/refusals.ts`) lists one row per key: the key, the stored text
  and the reason. "Clear refused settings"
  (`#settings-refused-clear`) removes exactly those keys and reloads.
  Every other key is kept.
- A read gives the stored value, or the declared default when nothing
  is stored. The camera and the landmarks tell which (`cameraStart`,
  `landmarkState().start`: `stored` or `default`).
- A write is checked by the same parser first. A module cannot store
  what it could not read back.
- The server's default game that cannot open is an error, not a
  refusal: it names no stored key.
- Only a choice is stored as the game. The startup pick is not.
- The camera, the grid, the backdrop and the landmarks are global, not per
  scene.

## 11. Tests

- Runner: Playwright, through `scripts/test.sh`. A program decides pass or
  fail. A picture never does.
- **A full run needs the operator's permission** (operator 2026-11-23).
  Since 2026-11-24: targeted spec files only.
- Two projects (`playwright.config.mjs`):
  - `unit` (`tests/unit/`, `make viewer-test`): no browser. The tools'
    own checks; page and game logic bundled for Node by esbuild
    (`tests/unit/source.mjs`); the server's routes asked directly.
  - `e2e` (`tests/e2e/`, `make viewer-test-e2e`): the page in a browser.
  - `ARGS=<filter>` runs only the spec files that match.
  - `@slow` tests run only with `make viewer-test-all`.
- Where a test goes: logic that needs no DOM, storage or WebGL when it is
  called is a unit test. A rule (a setting's check, the scene document
  check, the zoom, the add-all layout, the list names) is tested there, every
  case. An e2e test shows only that the page wires the rule in: one case,
  and the negative.
- One test per stored thing and reload: the scene store
  (`scenes.spec`, every field and item kind), the view settings
  (`landmarks-store.spec`). No other test reloads to check what was
  kept.
- Every problem fails the test unless the test names it (`tests/fixtures.mjs`, the `page` fixture).
  Every e2e test fails on any of these, unless the test names it with
  `allowErrors(pattern)`:
  - an uncaught page error;
  - a console error, or any `viewer:` / `sc2viewer:` report;
  - a reply of 400 or more, or a request with no reply (not an abort);
  - an error line in the worker server's log.
  An allowance that matches nothing fails the test too.
  `clean-load.spec` loads real units (among them the ones that failed on
  the dev service on 2026-11-25) and a doodad with no allowance. Its
  negative case answers textures with 500 and requires the fixture to
  record it.
- The texture pipeline flows have one e2e test each (operator
  2026-11-25): Save to Skin (`skin-editor`), the owner Upscale
  (`texture-variants`), Bake (`texture-bake`), the texture window
  (`texture-window`), the ground picker (`ground-texture`). Their rules
  are unit tests (`texture-service-api`, `skin-choices`).
- The e2e browser renders WebGL on the GPU (`playwright.config.mjs`;
  `gpu.spec` fails on a software renderer). The workers' browsers start
  one at a time, and each must link a WebGL program before its tests run
  (`tests/fixtures.mjs`, the `browser` fixture). Four starting at once
  sometimes gave one page a lost context (runs e2e17, e2e18, e2e21,
  e2e23).
- Isolation (11.1): each worker has its own server, texture store and
  datasets folder (`tests/fixtures.mjs`). Global setup
  (`tests/global-setup.mjs`) makes the base store's state index once;
  each worker copies it. A server refuses a port that already answers: a
  killed run can leave one there.
- No fixed sleep and no wall-clock bound: a test waits for frames, idle or
  a state. A time a test measures depends on the load of the run, so a
  time bound (the 250 ms of R-VIEW-111) is not tested.
- Tests use the page's test object and the DOM (R-VIEW-14).
- Contract tests run once per available game: every route of section 8
  answers in its shape, and a record is previewed, added, selected, moved,
  copied, pasted, stored and removed (`contract.spec`).
- Two implementations (R-VIEW-91): the contract tests pass for two games,
  the instance tests for two formats.
- Mixed scene: instances of two games are selected, moved and copied
  together (`ghost-mix.spec`).
- Game not available: its tab is disabled with the reason and the other
  game still passes (`ghost-unavailable.spec`).
- Known to fail under machine load: `pick-pixel.spec` `@slow` (timeout),
  `particle-motion.spec`. `fresnel.spec` compares two frames with a small
  tolerance (operator 2026-11-23).
- Each game specification lists its own tests.

## 12. Requirement state

Nothing is [verified]. [today] rows passed in run `full102` or an earlier
full run of section 13.

| R-VIEW | State | Where |
| --- | --- | --- |
| 1 | [today] | `core-names.spec`: core code holds no game id and no game file extension. Comments and the test object's names still do. |
| 2, 3 | [plan] | Not shown: the second game and format came with core edits. |
| 4, 7 | [today] | the import rule; `import-rule.spec` |
| 5, 26 | [today] | `contract.spec`, `ghost-mix.spec` |
| 6, 21 | [today] | `ghost-mix.spec` |
| 8, 27 | [today] | `ghost-unavailable.spec`, `game-tabs.spec` |
| 9 | [today] | `local.env`, `.gitignore` |
| 10, 11 | [plan] | The page, the server and `src/tools` are TypeScript. The surveys under `tools/` and the tests are not. |
| 12 | [today] | Typed services, no page object. No test asserts the clause. |
| 13 | [today] | `typecheck.spec` |
| 14 | [plan] | Tests still read item internals. |
| 20, 22 to 24 | [today] | `game-tabs.spec`, `side.spec` |
| 25 | [today] | `units-ui.spec`, `doodads-ui.spec`, `datasets-ui.spec` |
| 28, 51, 64 | [today] | `side.spec` |
| 30 to 33 | [today] | `datasets-ui.spec`, `datasets-api.spec` |
| 34 | [today] | `datasets-change.spec` (unit: the server sees the change and reloads). The page's question, Yes and No: not tested (removed 2026-11-25) |
| 40, 41 | [today] | `units-ui.spec`, `doodads-ui.spec`, `paged-list.spec` |
| 42 | [today] | `drag-preview.spec`, `units-ui.spec`, `doodads-ui.spec` |
| 43 | [today] | `add-all.spec` (unit and e2e), `add-all-view.spec`, `landmarks.spec`, `skybox-units.spec` |
| 44 | [today] | `units-ui.spec`, `ghost-gallery.spec` |
| 45 | [today] | `skybox-units.spec` |
| 50 | [today] | `viewer.spec`, `instances.spec` |
| 52 | [today] | `pick-pixel.spec`, `cutout.spec` |
| 53 | [today] | `pick.spec`, `multi-select.spec`, `instances.spec` |
| 54 | [today] | `move.spec`, `clipboard.spec`, `pick.spec`, `multi-select.spec` |
| 55 | [today] | `clipboard.spec` |
| 56 | [today] | `pick.spec` |
| 57, 65, 80 | [today] | `viewer.spec` |
| 58 | [today] | `scene-focus.spec` |
| 59 | [today] | `clipboard.spec`, `multi-select.spec`, `texture-skins.spec` (Ctrl+L) |
| 60 | [today] | `camera.spec`, `zoom.spec` (unit and e2e), `viewer.spec` |
| 61 | [today] | `ground-sky.spec`, `grid-levels.spec` |
| 62 | [today] | `ground-sky.spec`, `skyboxes.spec` |
| 63 | [today] | `landmarks.spec`, `landmarks-store.spec` |
| 66 | [plan] | Implemented, not verified. `edges.spec`: 8 of 9 passed in one run; the ninth passed alone after a test fix. |
| 70 | [today] | `scenes.spec` |
| 71, 74 to 77 | [today] | `scenes.spec`, `scene-document.spec` (unit) |
| 72, 73 | [today] | `settings.spec` (unit), `landmarks-store.spec`, `side.spec`, `scenes.spec`, `game-tabs.spec` |
| 81 | [today] | `displacement.spec`, `particles.spec` |
| 82 | [today] | nod: `ghost-look.spec`, `ghost-anim.spec`. m3: not asserted. |
| 90 | [today] | for the [today] rows only |
| 91 | [today] | `contract.spec`. The capability part is `ghost-mix.spec`. |
| 92 | [today] | the game specifications |
| 93 | [today] | `AGENTS.md` |
| 100, 107, 108, 110 to 112 | [plan] | 17.1, 17.2, 17.7; built, the specs of 17.8 passed before skins (runs v4 to v10 of 2026-11-24) |
| 101, 113 to 137 | [plan] | 17.3 to 17.7; implemented, not verified: the specs of 17.8 have not passed; 126 to 137 and the revisions of 2026-11-25 are being built |

## 13. Migration and runs

Steps 1 to 7 are done: tooling, typed page modules, the server core and
one backend, the protocol, scene documents, the interfaces, the generic
gallery and game tabs, the second game and format. Step 8 is open: tests
in TypeScript and the typed test object.

Full runs, every test, `@slow` too:

| Run | Day | Closes | Result |
| --- | --- | --- | --- |
| `full85` | 2026-11-23 | the baseline | 273 passed |
| `full86` | 2026-11-23 | step 2 | 273 passed |
| `full88` | 2026-11-23 | step 3 | 297 passed |
| `full91` | 2026-11-23 | step 4a | 297 passed |
| `full93` | 2026-11-23 | steps 4b, 4c | 314 passed |
| `full94` | 2026-11-23 | step 5 | 314 passed |
| `full96` | 2026-11-23 | step 6 | 321 passed |
| `full99` | 2026-11-24 | step 7 | 349 passed |
| `full102` | 2026-11-24 | selected instances stay lit | 350 passed |

Since `full102` only targeted runs: the shared texture window, the edges,
section 17. The last targeted runs, 2026-11-24, covered 37 of the 71 spec
files. Three checks there still named the shapes from before section 17
(`server`, `ghost-api`, `pick`). The other spec files were not run since.
Run logs are not kept in the repository. The step-by-step record is in
this file's git history.

## 14. Operator checks

- The look and the feel of the game tabs, the handles and the scene list.
- Whether the gallery of a game reads well.
- The edges of Ctrl+/: thin, green, no flicker on the surface they lie on,
  and whether 40 is a good range.
- Section 17: whether a variant looks better than its original; the look
  of the texture window, the skin choice, the Upscale dialog, the skin
  editor, the quality colours, the ground and skybox previews.

## 15. Open points

| ID | Point |
| --- | --- |
| O-VSPEC-1 | The library is checked without `noUncheckedIndexedAccess`. That is the author's reading; the operator ruled only that it is viewer code. The library code we do not bundle is not checked. |
| O-VSPEC-2 | The commit hooks have not been seen on `.ts` files here. |
| O-VSPEC-3 | A capability for a format's own effects (particles, lights) is left to probes and post passes until a second format needs it. |
| O-VSPEC-6 | Section 16 was written from the page code and the test titles. What no test asserts there is read from the code. |

## 16. Feature behaviour

What the page does. A number here is a constant of the code.

### 16.1 Status messages

- A message shows as a toast at the top centre of the free view (16.2).
- It stays 5 s, a failure 9 s. Messages in a row replace each other; each
  shows at least 0.1 s.
- A click on the toast opens the message log. The log holds every message
  in order, with its time and a failure mark (R-VIEW-64).

### 16.2 Drawers

- The gallery and the instances panel are drawers. A handle slides its
  drawer out and back. The choice is stored.
- A closed drawer takes no mouse and no keys (R-VIEW-28).
- The free view is the window without the open drawers. The toast and the
  camera framing centre on it.
- An instance behind an open drawer is not under the mouse.

### 16.3 Mouse

| Input | Does |
| --- | --- |
| Left drag | holds the ground point under the pointer and pulls the map |
| Ctrl + left, held, with a selection | turns the selected instances to face the pointer |
| Alt + left drag on an instance | moves it, and the whole selection when it is selected |
| Alt + left drag off an instance | draws the select rectangle |
| Middle drag | orbits around the ground point under the pointer, 0.004 rad per pixel; from the sky, around the camera target |
| Ctrl + middle drag | turns the view around the eye |
| Right drag | pans, 0.0006 x the camera distance per pixel |
| Wheel | zooms, gliding over a few frames; less per notch near the ground; a quarter with Ctrl; distance at most 2000 |
| Left click | selects. A press that moves more than 4 pixels is a drag. |
| Right click on an instance | opens its animation menu |
| Double-click on a record or an instance | the game's own |

The eye never goes under the ground.

### 16.4 Pick and selection

- The instance under the mouse is the one whose solid surface is drawn at
  that pixel (R-VIEW-52).
- Under the mouse it is drawn brighter, with a feathered green glow around
  its outline.
- A click selects it. A click on the ground clears. Shift + click adds or
  takes out. A drag does not select.
- Every selected instance gets a ring and stays brighter, without the
  glow.
- A click on a row name selects the same way. Ctrl + click also points the
  camera at the instance.
- The rectangle selects every instance whose foot, middle or top is
  inside. With shift it adds. An empty one clears. Under 4 pixels it is a
  click.
- The selection survives a new instance. A removed instance leaves it.

### 16.5 Animation menu

- A right click on an instance opens a menu of its animations. It stays
  open until Escape or a click elsewhere.
- Choosing one plays it once. Then the instance goes back to its looping
  one.
- With the menu's "loop" box checked, the chosen one becomes the looping
  one.
- Capability controls and a game's own entries stand in the same menu.

### 16.6 Keys

| Key | Does |
| --- | --- |
| Delete | removes the selected instances |
| Ctrl+C, Ctrl+X, Ctrl+V | copy, cut, paste |
| Ctrl+L | switches the menu's "loop" choice, with a selection |
| Ctrl+/ | switches the edges of the selected instances (16.13) |
| Escape | closes the open menu, dialog or floating window |

- No key acts on the scene while a text field has the keys (R-VIEW-59).
- A Ctrl key the viewer owns never reaches the browser, wherever the keys
  are.
- A game adds its own keys through the UI service.

### 16.7 Clipboard

- The clipboard is kept in the page. It is not the system clipboard.
- A copy keeps what defines the item: game, dataset, record or file,
  variant, scale, angle, animation, pick, options.
- A paste keeps the shape of the group. Its centre goes under the pointer,
  or where it was copied from when the pointer is off the view. The copies
  become the selection.

### 16.8 Gallery

- A list loads a page at a time as it is scrolled. A new search starts at
  the first page. The total is shown. A hidden list loads its first page
  only, and the next once it is shown and scrolled.
- A click on a row shows the preview with "add to scene". A double-click
  adds nothing.
- A drag shows the record's model on the ground under the pointer. Above
  the horizon there is no ground: no preview, and a drop places nothing
  and says why.
- A drop places what the preview showed: the same variant and angle.
- A backdrop record has no preview. Added or dropped, it becomes the
  backdrop.
- "Add all" asks first, with the count, and names what it leaves out.
  Declined, it changes nothing.
- It reads the list 500 at a time and loads 6 models at once.
- It lays the new instances out by size, without overlap, next to those
  already there. Then the camera frames them and a landmark is saved,
  named after the filters.

### 16.9 View tools

- Landmarks: "origin" is always there and cannot be deleted. The pin asks
  for a name and saves the view. The trash asks, then deletes.
- Grid: hexagonal, on at first. Its cell size follows the zoom, so it
  shows at every distance. It glows under the pointer and around every
  instance. A game may give an item another glow class. It needs the GL
  extension `OES_standard_derivatives`.
- Backdrop: chosen in a dialog, drawn behind everything.
- Ground texture: 17.7.
- The canvas follows the window size.

### 16.10 Datasets in the page

- The page asks for the datasets every 3 s.
- A dataset that changed raises a question. Yes reloads the data and the
  page. No hides it until the files change again (R-VIEW-34).
- Every asset URL carries the dataset's signature.
- An instance row has a dataset select (R-VIEW-32).

### 16.11 Frame

Order: clear; the backdrop and its post passes; depth clear; the grid; the
scene; the post passes; the edges; the outline of the instance under the
mouse. One step of animation time is at most 100 ms.

### 16.12 Components

Paged list, dialog, picker dialog, confirm dialog, toast, drop-down,
floating window: `page/ui/components/`.

### 16.13 Edges

`features/edges` (R-VIEW-66).

- Ctrl+/ switches the edges of the selected instances that have the
  `edges` capability. All go the same way: off when the one selected last
  shows them.
- The status line names the count, or says why nothing happened.
- The lines are 1 pixel, colour (0.2, 1.0, 0.3), drawn after the post
  passes with the depth test on and depth write off. The depth range is
  pulled to `[0, 1 - 5e-5]`, so a line wins over the surface it lies on.
  What is hidden is not drawn.
- An instance farther than 40 from the eye draws no edges. It keeps the
  choice.
- The choice is not in the scene document and not in a copy.
- Tests read `sc2viewer.state().edges` and `sc2viewer.edgePixels()`.

## 17. Textures

R-VIEW-100, 101, 107, 108, 110 to 125; their state is in section 12. How a
variant is made, kept, put in a skin and baked is
[SPEC-HD-TEXTURES](SPEC-HD-TEXTURES.md). Its words are used here. Status:
17.1 and 17.2 reading are built and were tested. Skins, the dialog, the
editor, bake and previews are built, and their specs (17.8) have not
passed yet.

### 17.1 Parts

| Part | Where | Holds |
| --- | --- | --- |
| Shared types | `src/shared/textures.ts` | 17.2, the routes as the page builds them |
| Routes | `server/core/textureroutes.ts` | the texture routes of section 8, over a game's texture service |
| Service over the pipeline | `server/core/textures.ts` | runs `scripts/hd_textures.py` only to change something (below). A game registers it in one line. |
| Index reader | `server/core/textureindex.ts` | reads the pipeline's state index (below) |
| Owner of a record | the game's server module | which owner a record or an instance is (SPEC-VIEWER-SC2 8.2) |
| Owner of an instance | the game's page part `textureOwner` | the owner id of an item, or none |
| Texture window | `page/core/texturewindow.ts`, the page `texture-viewer.html` with `page/texview` | 17.3; compare, pick, Save to Skin… |
| Skins of an instance | `page/core/skins.ts`, the instance menu in `features/pick/menu.ts` | 17.4 |
| Upscale dialog | `features/skins/upscale.ts`, its choices in `features/skins/choices.ts` | 17.5 |
| Skin editor | `features/skins/editor.ts`, its dialogs in `features/skins/actions.ts` | 17.6, 17.6.2 |
| Tiles of a texture | `page/core/tiles.ts`, their look in `public/theme.css` | 17.6.1, both windows |
| Icons | `page/ui/icons.ts` | the pencil, trash and skin icons |
| Previews | `page/core/previews.ts` | a small picture decoded in the page from a file |
| Ground and skybox | `page/core/render/ground.ts`, `page/core/sky.ts`, `features/sky`, its ground row in `features/sky/groundrow.ts` | 17.7 |

- A game without a texture service gets no control of this section, and
  its texture routes answer 404 (R-VIEW-100).
- A state, a listing, an owner, a variant's file and an original's place
  are read from the state index in the texture store (SPEC-HD-TEXTURES
  4.9), with the statements of `sql/texture-index/`, read once when the
  service starts. The file is opened read-only for each read, with a busy wait of
  200 ms. A read that cannot be made in that time fails and says so. The
  service keeps nothing between reads and runs no pipeline code to answer
  one (R-VIEW-111).
- Built only when missing (operator 2026-11-25). At start the server
  indexes a dataset the state index does not hold yet, and nothing else.
  A dataset it holds is not synced at start; a reload of the dataset
  syncs it. The game storage's file list is kept in
  `$WEBVIEWER_CACHE/storage-listing.txt`, made when missing; delete it
  after a game update. The tests' base store is kept between runs; delete
  `$TEXTURE_STORE` (the test one) to build it again.
- The reader is Node's own `node:sqlite`. Node 24.11.1 marks it
  experimental and says so once in the log at start.
- A change made past the viewer (the CLI, a map build) shows on the next
  read.
- The service applies one rule of its own, the reader's rule of
  SPEC-HD-TEXTURES 4.9: a request whose process is gone shows as failed,
  and its variant may be asked for again.
- The service runs these pipeline commands, each as a process:

| Command | When |
| --- | --- |
| `index` | the server starts; a dataset is reloaded. One at a time per dataset. |
| `index --asset` | the judge route; a request for a texture not judged yet |
| `upscaler` | before a request. It names the worker's command; the service starts the worker when none runs. |
| `request` | the request route. It outlives the server (R-VIEW-121). |
| `skin` | the skin route. `skin upscale --defer` writes the skin and starts no request; the service then starts one `request` per texture it names, side by side, each outliving the server, and answers once the index shows each. |
| `bake`, `unbake` | their routes |

- At start, a dataset the index never held is indexed before the server
  listens. A dataset it holds is indexed while the server serves.
- A failed `index` is logged. The states stay as the index holds them.
- A request, and each request of a skin upscale, answers once the index shows it or its variant, at most 30 s
  after its process started. What the index held of that variant before,
  an attempt that failed or a stale variant, does not count.
- An index of another schema is an error on every read. The pipeline
  rebuilds it on its next write.

### 17.2 States

What the server says of one texture:

| Field | Meaning |
| --- | --- |
| asset, kind, users | from the pipeline's description |
| judged | the pipeline has read its role and size. Not judged: `reason` and `models` are empty. |
| reason | why it cannot be upscaled, or none |
| colour | whether it has a colour plane |
| variants | per variant: id, input, models per plane, size, file hash, numbers each with bound, band (`ok`, `near`, `problem`) and info text; stale; accepted |
| models | per model: whether a request may ask for it, else why |
| sizes | per size: whether it can be reached, else why |
| requests | those not done: variant id, state, step and plane counts, error |
| bake | for a terrain texture: the baked variant, and whether the package holds its file |

What the server says of one owner:

| Field | Meaning |
| --- | --- |
| owner, title, layer | from the index |
| below | the owners below it, each with its bake |
| textures | its textures' assets; their states come by the textures route |
| skins | per skin: name, the variant per asset, and whether it is stored. `new` is New Skin; an offered one is not stored (SPEC-HD-TEXTURES 4.6) |
| shows | per asset, what the owner shows now: its bake, else the nearest bake below, else the original. The In game tile of both windows reads it (17.6.1) |
| bake | the baked skin's name and map, or none; whether the package holds it |

- With the states come the sizes, the models and the limits with their
  bands and info texts.
- "Held by the package" is decided by the file: the package record names
  it, and the file at the recorded place has the recorded hash.
- A refused request, skin change or bake is a 400 with the pipeline's
  reason. Nothing changes (R-VIEW-123).
- The pipeline judges a texture when it has a variant or is asked for by
  name. The judge route asks for a list of textures by name and answers
  with their states. A name that is no texture of the dataset is refused.
- A read of the states of one model's textures answers within 250 ms, on
  a store read for the first time too (R-VIEW-111).
- An original is served by the asset route. For a texture it is the file
  the index's origin table names for the asset in that dataset
  (R-VIEW-112, R-VIEW-33). An asset the table does not hold is found by
  the game's own listing.

### 17.3 Texture window

One window for every game, a floating window with the texture page in its
frame. The page is viewer code. It compares; it changes a skin only by
**Save to Skin…** (R-VIEW-101, R-VIEW-130, R-VIEW-133).

- It opens on a record, an instance or a model file, by a double-click.
  Without a rule of the game's own, the textures are those the model
  names.
- The list has one entry per texture and plane: a small picture, the size,
  and state badges. Chips filter by kind and plane; a search by name.
- Below the view: the details of the chosen texture (format, kind,
  "used by", why it cannot be upscaled, its bake, the game's facts), then
  its tiles, the same tiles as the skin editor (17.6.1, R-VIEW-132).
  "used by" lists one user per line in a box 72 px high (about 4.5 lines)
  that scrolls (R-VIEW-134).
- The view shows the original and, beside it, the tiles shown now, parted
  by lines that can be dragged. Zoom, pan, 1:1, tile and fit. At first the
  In game tile is shown.
- A click on a tile shows it alone beside the original and picks it.
  Ctrl+click adds it to the view or takes it out; the pick stays. The
  tiles shown have the blue outline. Picking the In game variant drops
  the texture's pick (R-VIEW-130).
- **Upscale Texture** is the last tile (R-VIEW-129). It sends the page
  event `texture-upscale` with the game, dataset and asset; the viewer
  opens 17.5 on it.
- When the thing has a texture owner (SC2: a unit, a doodad's actor, a
  bare model file; a ground texture has none), a bar above the tiles says
  "<n> textures picked" with **Save to Skin…** and **Revert Changes**,
  while there is a pick. A list row with a pick has the badge PICKED.
  **Save to Skin…** sends the page event `texture-save` with the game,
  dataset, owner, the picks and the instance the window was opened on, if
  any; the viewer asks in the dialog of 17.6.2. Saved, the picks are
  dropped. **Revert Changes** drops them; nothing else changes. Without an
  owner there is no bar.
- When a texture changes for its game and dataset (`textures-changed`),
  the window reads the states again.
- Every picture is decoded in the page from the file itself.
- It has no key of its own. Ctrl+L stays the viewer's inside it.
- On opening, it shows the states at once, then calls the judge route
  for the textures not judged and does not wait.
- While a shown texture has an open request, the states are asked for
  once a second.

### 17.4 Skins of an instance

The skin choice of an instance (R-VIEW-113).

- The instance's owner comes from the game. An instance without an owner
  with textures has no skin controls.
- The item's choice is a skin name. Absent means `original`. It is kept
  in the scene document as the option `skin`, and in a copy. It changes
  no other instance.
- Choosing a skin the owner does not have is refused: the instance keeps
  the skin it had. An item read with such a skin is reported as a
  failure and shows its model's own textures.
- A rename or a delete in this page first sets every instance of the
  owner on that skin to the new name or to Original, then changes the
  skin; a refused change sets them back.
- The menu row: the skin list, **Upscale Skin**, **Bake Skin**, and a
  badge (R-VIEW-114, 126). The list is a button: a skin icon, the chosen
  skin's label, and a down arrow (R-VIEW-137). A click opens its rows:
  - **Original** first, with no icon;
  - each saved skin, with an edit icon and a red trash icon;
  - **New Skin**, when the owner has one, with the same two icons;
  - **Add New Skin…** last.
- A click on a row's label chooses the skin for the instance. The edit
  icon opens 17.6 on that skin. The trash icon of a saved skin asks
  "Delete Skin", of New Skin "Discard New Skin" (17.6); answered, the
  instances on it show Original. The trash of the baked skin is disabled;
  its title says "baked: unbake it or bake another skin first". **Add New
  Skin…** opens 17.6 on New Skin.
- The bake button says **Bake Skin**, or **Unbake Skin** while Original
  is chosen. Unbake Skin is disabled while the owner has no bake. Bake
  Skin is disabled on New Skin, with the reason in its title (R-VIEW-127).
- The badge shows 🍞 and the baked skin's name. It is absent while the
  owner has no bake.
- **Bake Skin** asks to confirm, naming the owner, the skin and the
  dataset, then calls the bake route (R-VIEW-122). **Unbake Skin** asks
  "Remove the bake of <title> in <dataset>? It will show its original
  textures." A refusal shows its reason; nothing changes (R-VIEW-123).
- Dialog titles and buttons start with a capital letter and name what
  they act on: **Bake Skin**, **Unbake Skin**, **Save Skin**, **Delete
  Skin**, **Discard New Skin**, **Rename Skin**, **Save to Skin**,
  **Cancel** (R-VIEW-128). A button that deletes or discards is red
  (R-VIEW-136).
- An instance shows its own textures at once. Adding it makes no call of
  the texture service and waits for none (R-VIEW-110). Its skin follows
  when the owner is in; `idle()` waits for it.
- A slot shows the variant the skin names, at its size. A texture the
  skin does not name shows its original. Original names nothing: every
  slot shows the original, whatever is baked (R-VIEW-127).
- A named variant with an open request: the slot shows the model's own
  texture until it is made (below). A named variant that is stale, has a
  problem not accepted, is not made with no request, or cannot be
  loaded: the skin is reported as a failure, naming the texture and why.
- When a skin or a variant changes for its game and dataset, the skin is
  applied again to every instance that shows it.
- While an instance's skin names a variant with an open request, the
  states of those textures are read again once a second, and the skin
  applied again, until the variant is made or its request failed.
- What is baked shows on an instance only through a skin: the baked
  skin, or the offered New Skin that names what the owner shows now
  (R-HD-137).

### 17.5 Upscale dialog

One dialog, opened from an instance (whole owner) or a texture (one
texture) (R-VIEW-115 to 117, 119).

| Choice | One texture | Whole owner |
| --- | --- | --- |
| Input | a select of its variants, `original` first | the skin shown now; each texture's input is its variant there |
| Model | `pbrify`, `fast`, `seedvr2`; those the state refuses are disabled, with the reason | all three; with `seedvr2` or `pbrify`, a line says how many data textures get `fast` |
| Size | 1024, 2048, 4096; those the input cannot reach are disabled | all three; a line says how many textures cannot reach it and keep their variant |

- The button is **Upscale Texture** on one texture, **Upscale Skin** on
  an owner. Submit on one texture calls the request
  route. Submit on an owner calls the skin route with `upscale` and the
  name `new`; the instance then shows New Skin. While the owner has a
  stored New Skin, the server refuses it: save or discard it first.
- The dialog closes when the call answers. A refusal keeps it open with
  the reason.

### 17.6 Skin editor

A floating window on one owner and one skin (R-VIEW-118 to 121).

- Left: one row per texture of the owner, with a preview and its name.
- Right: the selected texture's tiles (17.6.1). The picked tile has the
  blue outline: the texture's pick, else the variant the skin names, else
  the original; In game too when it is the same variant.
- A click picks the tile. It changes no skin and no instance
  (R-VIEW-133). A texture row with a pick that differs from the skin has
  the mark ●. While there is such a pick, a bar says "<n> changes" with
  **Save to Skin…** and **Revert Changes**.
- **Save to Skin…** opens 17.6.2 with the skin open as the target; on
  Original, New Skin (R-VIEW-127). Saved, the editor shows the target
  skin, and the instance shows it. **Revert Changes** drops the picks.
- A saved skin the owner no longer has is reported as a failure; the
  editor does not switch to another skin.
- A queued or running variant shows as a tile with its state; a failed
  one with its reason.
- The header has no name box and no Copy. A saved skin has **Rename
  Skin** (a dialog asks the name; a bake of it follows the new name) and
  **Delete Skin** (a dialog asks to confirm). Delete Skin of the baked
  skin is disabled, its title says "baked: unbake it or bake another skin
  first", and the service refuses it too (R-HD-136). A name another
  skin holds, ignoring case, is refused (R-HD-138). New Skin has **Save
  New Skin As…** (a dialog asks the name) and **Discard New Skin** (a
  dialog asks to confirm). Original has none. Delete Skin and Discard
  New Skin are red (R-VIEW-136).

#### 17.6.1 Tiles of a texture

The skin editor and the texture window show the same tiles, in this
order (R-VIEW-131, R-VIEW-132):

- **In game**: the variant the owner shows now (`shows`: its bake, else
  the bake below, else the original). Without an owner (a ground
  texture), the texture's own bake, else the original. The second line is
  the size and "baked" or "not baked". It names no skin. When a bake is
  there and the package does not hold it as it is (owner `held` false, or
  texture `packaged.held` false), an amber line says "not in the package
  yet: build the map".
- **Original**, then each variant: a preview, the id, the size, and the
  numbers, each coloured by band (R-VIEW-120). A stale or blocked variant
  has an amber title.
- A tile with a number off the ok band has an info mark "i". It keeps the
  arrow cursor. On hover a tooltip says "Amber: near a limit. Red: misses
  a limit." and names each such limit, its number, its bound and what a
  miss looks like (R-VIEW-135).
- Each open request: its state and step, or its failure reason. It cannot
  be clicked.
- Last, **Upscale Texture**, as large as a preview tile (R-VIEW-129).

#### 17.6.2 Save to Skin dialog

One dialog for both windows (R-VIEW-133).

- A select of the target: New Skin (with "made now" when it is not
  stored) and each saved skin.
- One line per pick: the texture, the variant the target names now, and
  the pick. A pick the target names already says "no change".
- "<title> (<owner>) in <dataset>. Bakes, Original and the other skins do
  not change." "New Skin will be made from what <title> shows now." when
  the target is New Skin and it is not stored. "This instance will show
  <target>." for an instance; else "No instance changes its skin."
- **Save to Skin** is disabled while no line is a change. It calls the
  skin route `set` once per change, in order, then sets the instance's
  skin to the target. A refusal stops there and shows its reason in the
  window. **Cancel** changes nothing.

### 17.7 Ground texture and skybox

- A ground category lists ground textures, each row with a preview and a
  state badge (R-VIEW-107, R-VIEW-124). Its records are not placeable.
- It has no gallery tab: the ground button below is the one place to
  choose a ground texture (operator 2026-11-25).
- Such a record, added, becomes the ground.
- The ground is held with the grid and the backdrop: stored and global.
- The view tools get a ground button beside the grid button. Its dialog
  lists the ground records of the gallery's game and dataset, "none"
  first, each with a preview. The chosen one has a variant select,
  **Upscale**, **Bake** and a badge (R-VIEW-125). The button says
  **Unbake** while the select shows the bake. The badge shows 🍞 and the
  baked variant. It is hidden when the texture has no bake.
- The texture is drawn on the ground, repeated by world position, under
  the grid. One repeat is 8 world units, for every game (SPEC-VIEWER-SC2
  O-SC2-4). It fades out to the ground's rim and is drawn with the grid
  off too. The grid switch is unchanged (R-VIEW-108).
- It is the chosen variant of the record's colour file; none chosen, its
  terrain bake; no bake, its original. A chosen or baked variant that
  cannot be shown is reported as a failure and no ground is drawn.
- Only the colour is drawn. The ground is not lit.
- The skybox chooser shows a preview of each model: its colour texture,
  else a rendered picture of the model.
- The buttons are there only for a gallery game with a texture service
  and a ground category.

### 17.8 Tests

Each with a negative case. The base test store is built only when
missing and kept between runs: its state index and the game's index of
its model files (17.1). No test writes to it; each worker copies it.
The runner enlarges by pixel repeat (`HDTEX_RUNNER=repeat`): no test
enlarges on a GPU.

| Area | Proves | Negative | Spec |
| --- | --- | --- | --- |
| Routes | the page and its script are served | the pick, default and chain routes: 404 | `texture-service-api` (unit) |
| Start | the server lists every dataset in a state index that was not there | a name that is no texture is unknown | `texture-service-api` (unit) |
| State read | the states of one model's textures are read from the index, the same each time (the 250 ms bound is not tested, section 11) | no read fails beside eight writers | `texture-service`, `texture-service-api` (unit) |
| Judge | the route has a texture judged | an unknown name: 400 | `texture-service-api` (unit) |
| Instance add | the instance is added and usable while states stall or fail | no skin controls until the owner is in | `texture-service` |
| Gone request | a killed request shows as failed and may be asked again | while it runs it is not failed | `texture-service-api` (unit) |
| Request | input, model and size give the variant; it is listed | `seedvr2` on a data texture: 400, nothing queued; a size the input cannot reach: 400 | `texture-service-api` (unit) |
| Dialog | the disabled models and sizes match the state; submit queues | `pbrify` and `seedvr2` on a data texture cannot be chosen | `skin-choices` (unit); the owner dialog in `texture-variants`. The texture card's dialog in the page: not tested (removed 2026-11-25) |
| Owner upscale | New Skin names a variant of every texture; each is made; the instance shows each one on a slot of its model without a reload | data textures with `pbrify`: `fast`; no other skin and no bake; refused while New Skin is stored | `texture-variants` |
| Skin choice | the list has Original, the saved skins and New Skin with edit and trash, Add New Skin… last; the button has its icon and arrow; a choice changes the overrides of that instance; kept in the scene | Original has no icon; Original holds no override; an unknown item option, a bad team, animation or skin type refuses the item | `texture-skins`, `texture-bake`, `scenes`. Not tested (removed 2026-11-25): the trash dialog, a skin showing its variant, a skin of one dataset on another, the 2048 glow |
| Editor | a click picks and outlines a tile; Save to Skin… sets the picks in the skin open; every instance on the skin changes without a reload; Rename Skin, Delete Skin by dialog; In game tile | a click changes no stored skin and no instance; the baked skin cannot be deleted; a name another skin holds: refused | `skin-editor`. Not tested (removed 2026-11-25): New Skin (Add New Skin…, Save New Skin As…, Discard New Skin), Revert Changes, a cancelled save, no name box and no Copy, the refused names in the editor |
| Dialogs | each dialog's title and buttons start with a capital letter and name what they act on; delete and discard buttons are red | no dialog button in lower case; a button that keeps is not red | `skin-editor`, `texture-bake`, `scenes` |
| Window tiles | In game is first; "used by" has a fixed height and scrolls; the info mark's tooltip names amber and red | no Use button and no checkbox; a click on In game changes no skin; a cursor of help | `texture-window`. Not tested (removed 2026-11-25): a click shows the tile beside the original, Ctrl+click |
| Save to Skin | the picks of the window go to the chosen target in one dialog; the instance shows it | Cancel changes nothing; Revert Changes drops the picks; the bake is unchanged; no bar without an owner | `texture-window` (no bar without an owner). The rest: not tested (removed 2026-11-25) |
| Quality | each number has a band; a problem has its info text | a variant that misses no limit has no number in the problem band | `skin-editor` (the ok band, no info mark). A problem band: not tested (removed 2026-11-25) |
| Bake | the bake route writes the bake; the badge shows it; Unbake on Original unbakes | choosing a skin writes no bake; Original shows no bake; a cancelled or refused bake changes nothing; another dataset unchanged | `texture-bake`, `texture-service-api` (unit). Not tested (removed 2026-11-25): an actor's bake offered to its unit as New Skin; New Skin cannot be baked |
| Ground | a ground record becomes the ground | "none" gives the bare ground; Ghost has no button | `ground-texture`, `ghost-textures`. Not tested (removed 2026-11-25): a blocked variant cannot be baked or chosen |
| Previews | the ground rows carry a preview image of the entry's file | "none" shows no picture and no broken image | Not tested (removed 2026-11-25) |
| Doodad owner | a doodad's owner is its actor | | `skin-editor` |

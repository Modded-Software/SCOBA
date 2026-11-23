# SPEC-VIEWER: Asset Viewer, Core and Interfaces

**Date:** 2026-11-23
**Status:** Design. Not built. The viewer that exists today is one game's
viewer in plain JavaScript; section 13 maps it to this design. Section 12
gives the state of each requirement. Section 16 records what the features
do today. One run backs the [today] rows: the baseline of section 13.
**Requirements:** [REQ-VIEWER](../requirements/REQ-VIEWER.md)

Game specifications:

- [SPEC-VIEWER-SC2](SPEC-VIEWER-SC2.md)
- [SPEC-VIEWER-GHOST](SPEC-VIEWER-GHOST.md)

This document names no game rule. It names games only as links and in the
state and migration tables.

## 1. Principle

- Core knows games and formats only as interfaces (R-VIEW-1, R-VIEW-4).
- A game is two modules: one for the page, one for the server. Each is
  registered in one line (R-VIEW-2).
- A format is one module. A game lists the formats it uses (R-VIEW-3).
- The server describes a game's gallery as data. The page builds the gallery
  from that data. A game needs no gallery code of its own (R-VIEW-25).
- The game's page module holds only what data cannot say: how a record
  becomes an instance (R-VIEW-44).
- Features see instances through one interface, and ask for capabilities
  (R-VIEW-5, R-VIEW-6).

## 2. Labels

State of a requirement:

- **[verified]**: a Playwright test passed in a run named in section 12.
- **[today]**: the current code does it, in its one-game form. The test
  files named cover it and passed in the baseline run (section 13). It is
  not [verified]: no one has checked that the tests assert every clause of
  the requirement.
- **[plan]**: not in the code.
- **[operator]**: only a person can judge it.

## 3. Layers

```
page                                    server
----                                    ------
ui         components, drawers,         core      http, router, static files,
           game tabs, gallery,                    game registry
           instances panel                 |
features   pick, select, move,             v
           clipboard, drag, add all,    GameBackend  (one per game)
           landmarks, backdrop, grid
core       render host, scene, camera,
           events, store, status,
           registries
   |                |
   v                v
GamePlugin      FormatModule
(one per game)  (one per format)

shared     ids and messages, used by both sides
```

Dependency rule, checked by the build (section 9):

- `shared` imports nothing of the viewer.
- `core` imports `shared`.
- `features` and `ui` import `core` and `shared`.
- `formats/<id>` imports `core` and `shared`.
- `games/<id>` imports `core`, `shared` and the formats it lists.
- `games/<a>` never imports `games/<b>` (R-VIEW-7).
- `core`, `features` and `ui` never import `games/` or `formats/`.
- Only the two composition roots import games: `src/page/main.ts` and
  `src/server/main.ts`.
- `features` may import `ui`. `ui` never imports `features`.
- Page code (`src/page/`) and server code (`src/server/`) never import
  each other. `shared` is all they have in common.
- `games/<id>/page` never imports `games/<id>/server`, and the reverse.
  Both may import `games/<id>/shared`.
- `src/tools/` runs in Node. It may import `shared`, `formats/`,
  `games/<id>/shared`, `games/<id>/server`, `server/core` and the
  renderer library. It never imports `src/page/`.
- The renderer library is imported only by `page/core`, `formats/<id>`
  and `src/tools/`.
- An import that leaves `src/` is refused, except the renderer library
  and the packages in `package.json`.

The last six rules were proposed by the author and accepted by the
operator (2026-11-23, O-VSPEC-7).

## 4. Source layout

```
webviewer/
  src/
    shared/            ids, protocol messages, scene address format
    page/
      core/            render host, scene, camera, events, store, status
      ui/              components, drawers, game tabs, gallery, instances
      features/        one folder per feature
      main.ts          registers the games, installs the features
    formats/<id>/      one folder per format
    games/<id>/
      page/            GamePlugin
      server/          GameBackend
      shared/          the game's record types
    server/
      core/            http, router, static files, registry
      main.ts          registers the game backends
    tools/             Node tools (surveys, fixtures)
  tests/               Playwright tests
  scripts/             shell entry points
```

Adding a game adds `src/games/<id>/` and two lines, one in each `main.ts`.

## 5. Shared types

`src/shared/`. Both sides compile against these (R-VIEW-11).

```ts
type GameId = string;      // all four: the id rule of section 8
type DatasetId = string;
type CategoryId = string;
type FormatId = string;

interface GameInfo {
  id: GameId;
  label: string;           // full name
  tab: string;             // short text of the game tab
  available: boolean;
  reason: string | null;   // why not, when not available
}

interface DatasetInfo {
  id: DatasetId;
  label: string;
  builtin: boolean;
  signature: string | null;  // what is loaded
  current: string;           // its sources now
  changed: boolean;          // they differ
}

interface FilterInfo {
  id: string;                // the query parameter
  label: string;
  kind: 'buttons' | 'select';
  values: { value: string; label: string }[];
}

interface CategoryInfo {
  id: CategoryId;
  label: string;             // tab text
  noun: string;              // "unit": for counts and questions
  filters: FilterInfo[];
  addAll: boolean;
}

interface Page<T> { total: number; items: T[] }

interface RecordSummary {
  id: string;
  name: string;
  sub: string;                 // the grey line under the name
  icon: string | null;
  placeable: boolean;
  notPlaceableAs: string | null;  // the word for it, when not placeable
}

interface RecordDetail<D> extends RecordSummary {
  game: GameId;
  dataset: DatasetId;
  category: CategoryId;
  files: string[];             // servable model files, one per variant
  picture: string | null;
  data: D;                     // the game's own record type
}

interface Backdrop { id: string; name: string; game: GameId; dataset: DatasetId; file: string }

type AssetKind = 'model' | 'texture' | 'animation' | 'material';

interface ApiError { error: string }  // plus context fields
```

## 6. Page interfaces

### 6.1 Model and instance

Every format's model and instance satisfy these. Features use nothing else.

```ts
interface ViewerModel {
  readonly format: FormatId;
  readonly bounds: { readonly r: number };      // culling sphere
  readonly vertexMin: Vec3;                     // rest pose box
  readonly vertexMax: Vec3;
  readonly undrawn: readonly string[];          // parts not drawn (R-VIEW-81)
  readonly textures: readonly string[];         // references it names
  addInstance(): ViewerInstance;
}

interface ViewerInstance {
  readonly model: ViewerModel;
  readonly sequences: readonly { readonly name: string }[];
  setLocation(at: Vec3): void;
  setRotation(turn: Quat): void;
  setScale(by: Vec3): void;
  setSequence(index: number): void;             // -1: none
  setLoop(loop: boolean): void;                 // true: repeat. false: play to the end and hold
  timeScale: number;
  readonly sequenceEnded: boolean;              // the playhead passed the end in the last step
  show(): void;
  hide(): void;
  detach(): void;
  highlight: number;                            // mouse-over brightness
  solidOnly: boolean;                           // draw solid parts only
  renderOpaque(): void;                         // alone, for the outline mask
  renderPick(r: number, g: number, b: number): void;  // flat colour, solid parts
}
```

`sequences` is on the instance, not on the model. The renderer library
keeps one model per file. Two items may share a model file and have
different animations, when a game keeps animations outside the model file
(6.4, `clips`).

Where the library's M3 classes stand against these, read from their code
and from the page's use of them:

| Member | M3 classes today |
| --- | --- |
| `bounds`, `vertexMin`, `vertexMax`, `addInstance` | the same |
| `setLocation`, `setRotation`, `setScale`, `setSequence`, `timeScale`, `sequenceEnded`, `show`, `hide`, `detach`, `highlight`, `solidOnly`, `renderOpaque`, `renderPick` | the same |
| `format` | absent |
| `sequences` | on the model |
| `undrawn` | `undrawnBatches` |
| `textures` | read out of `materials` by the page |
| `setLoop(loop)` | `setSequenceLoopMode(2)` and `(1)`. Mode 0, "as the file says", is not used by the page. |

The format module `m3` closes these gaps with an adapter. The library is
not changed for them.

### 6.2 Capabilities

Optional. A missing member means the instance cannot do it (R-VIEW-6).

```ts
interface Capabilities {
  teamColor?: { readonly count: number; set(index: number): void };
  tint?: { set(color: Rgb | null): void };
  textureOverride?: {
    slots(): readonly TextureSlot[];
    set(slot: TextureSlot, texture: Texture | null): void;
  };
}
```

A new capability is a new optional member plus the feature that uses it.
Existing formats are not edited.

### 6.3 Format module

```ts
interface FormatModule {
  readonly id: FormatId;
  readonly extensions: readonly string[];        // ".ext", lower case
  readonly handlers: readonly RendererHandler[]; // model and texture readers
  /** The bytes of a model file, as the object its handler takes. */
  parse?(bytes: Uint8Array, name: string): unknown;
  /** Give an instance animations kept outside its model file. */
  attachClips?(instance: ViewerInstance, clips: readonly Clip[], resolver: AssetResolver): Promise<void>;
  capabilities(instance: ViewerInstance): Capabilities;
  readonly postPasses?: readonly PostPass[];     // draws after the scene
  readonly probes?: Readonly<Record<string, Probe>>;  // inspection for tests
}

interface PostPass {
  readonly id: string;
  enabled: boolean;
  draw(scene: RenderScene, width: number, height: number): number;
}
```

- The render host is the renderer library's viewer. A format's handlers are
  that library's handler objects: `load`, `isValidSource`, `resource`.
- The library picks a handler by the bytes of a file (`isValidSource`),
  never by its name. That works for a file with a magic number. A format
  without one gives `parse`: core fetches the file, picks the format by
  the extension of the file's path, calls `parse`, and hands the result to
  the library. The format's `isValidSource` then accepts only that parsed
  object.
- Core loads every model through one call and keeps one model per game,
  dataset signature and file. The library's own store is keyed by URL and
  does not hold a model that came through `parse`.
- A format without `attachClips` cannot take `clips`. A placement with
  clips for such a format is a failure, reported.
- A format refuses what it cannot read (R-VIEW-82): its parser throws with
  the file, the record and the version.
- `probes` replace format-only members of the test object. They are reached
  as `viewer.probe(format, name, ...)`.

### 6.4 Game plugin

```ts
interface GamePlugin<D> {
  readonly id: GameId;
  readonly formats: readonly FormatModule[];
  /** URLs for what a model of this game names, per dataset. */
  resolver(dataset: DatasetId, version: string): AssetResolver;
  /** The lines of the preview card. */
  describe(record: RecordDetail<D>): PreviewCard;
  /** How a record becomes an instance. */
  place(record: RecordDetail<D>, wish: PlacementWish): Placement;
  /** How a bare file becomes an instance. */
  placeFile(file: string, wish: PlacementWish): Placement;
  /** Speed of one animation of an item. */
  playRate(item: SceneItem<D>, sequence: number): number;
  /** The animation an instance starts with, out of its names; -1 for none. */
  restSequence(names: readonly string[]): number;
  /** Game-owned settings of an item: checked, and written to the address. */
  readonly itemOptions: OptionsCodec;
  /** Game-only features, such as a second texture set. */
  install?(context: FeatureContext): void;
}

interface AssetResolver {
  url(reference: string, kind: AssetKind): string;
}

interface PlacementWish {
  x?: number; y?: number; rot?: number; scale?: number;
  sequence?: number; pick?: number; variant?: number;
  options?: JsonObject;
}

interface Placement {
  file: string;              // servable model file
  variant: number | null;    // which of record.files
  variants: number;          // how many the user may choose from
  scale: Vec3;               // from the record's data
  height: number;            // over the ground
  rot: number;               // degrees
  tint: Rgb | null;
  pick: number;              // 0..1, chooses inside data ranges
  asBackdrop: boolean;       // becomes the backdrop, is not placed
  clips: readonly Clip[];    // animations kept outside the model file
}

interface Clip { name: string; reference: string }  // read as kind "animation"
```

Core applies a `Placement`. It does not read `record.data`.

An instance's `sequences` are those of its model file, then the
placement's `clips`, in that order. A format whose files hold their own
animations gets an empty `clips`. Core hands the clips to the format
(`attachClips`) before it asks the game for the rest animation.

### 6.5 Scene item

```ts
interface SceneItem<D> {
  readonly id: number;
  game: GameId;
  dataset: DatasetId;
  source: { category: CategoryId; record: string } | { file: string };
  record: RecordDetail<D> | null;
  placement: Placement;
  model: ViewerModel;
  instance: ViewerInstance;
  capabilities: Capabilities;
  x: number; y: number; rot: number; scale: number;
  sequence: number;
  oneShot: number | null;
  options: JsonObject;       // read and written through the game's itemOptions
}
```

### 6.6 Features

```ts
interface Feature {
  readonly id: string;
  install(context: FeatureContext): void;
}

interface FeatureContext {
  readonly games: GameRegistry;
  readonly render: RenderHost;
  readonly scene: SceneService;       // add, remove, swap, items
  readonly selection: SelectionService;
  readonly camera: CameraService;
  readonly status: StatusService;
  readonly store: Store;              // typed local storage
  readonly events: EventBus<ViewerEvents>;
  readonly api: ApiClient;            // typed calls of section 8
  readonly ui: UiService;             // rows, menus, dialogs, tools
  readonly testApi: TestApiBuilder;
}
```

- A feature states what it needs by taking it from the context. Nothing is
  published on a shared object (R-VIEW-12).
- Features talk to each other through `events` and the services. A feature
  never imports another feature.
- Row controls and menu entries are added through `ui`, each with a test:
  `when(item) => boolean`. A capability control uses
  `when: (item) => item.capabilities.x !== undefined`.
- The grid glows around each instance. A game may register a rule that
  gives an item one of the grid's glow classes. Without a rule the item
  gets the standard one.
- A game's `install` uses the same `ui` calls for what only it has: a key,
  a menu entry, what a double-click on a record or an instance opens.
- What each feature does, with its numbers, is in section 16.

Events: `item-added`, `item-removed`, `item-changed`, `selection-changed`,
`game-changed`, `dataset-changed`, `camera-changed`, `frame`.

## 7. Server interface

```ts
interface GameBackend {
  readonly id: GameId;
  readonly label: string;
  readonly tab: string;
  /** Index the data. Throws GameUnavailable with the reason (R-VIEW-8). */
  start(settings: Settings): Promise<void>;
  datasets(): Promise<{ default: DatasetId; datasets: DatasetInfo[]; problems: DatasetProblem[] }>;
  reload(dataset: DatasetId): Promise<DatasetInfo>;
  categories(dataset: DatasetId): Promise<CategoryInfo[]>;
  /** The game's own counts: what is indexed, and what was left out and why. */
  summary(dataset: DatasetId): Promise<JsonObject>;
  list(dataset: DatasetId, category: CategoryId, query: ListQuery): Promise<Page<RecordSummary>>;
  record(dataset: DatasetId, category: CategoryId, id: string): Promise<RecordDetail<unknown> | null>;
  /** A raw file by its servable path. */
  file(dataset: DatasetId, path: string): Promise<FileRef | null>;
  /** A reference a model uses, resolved for the dataset. */
  asset(dataset: DatasetId, kind: AssetKind, reference: string): Promise<AssetReply | null>;
  icon(dataset: DatasetId, name: string): Promise<FileRef | null>;
  backdrops(query: ListQuery): Promise<Page<Backdrop>>;
  /** Routes below /api/<game>/x/, for game-only features. */
  readonly extensions?: Readonly<Record<string, RouteHandler>>;
}

interface ListQuery { q: string; offset: number; limit: number; filters: Record<string, string> }
type AssetReply = FileRef | { json: JsonObject };
```

- Server core owns the HTTP side: parsing, paging limits, error replies,
  file streaming, cache headers. A backend never sees a request object,
  except in `extensions`.
- A backend that throws `GameUnavailable` in `start` is listed with
  `available: false`. The server starts without it.
- `icon` serves only the names the dataset's index lists. No name can
  reach a file outside the icon folder [today].
- Server core has two settings of its own: `PORT` (4517; the tests use
  4518) and `HOST` (`127.0.0.1`) [today]. Every other setting belongs to
  a game and is named in its specification.

## 8. Protocol

All replies are JSON unless a file is served. Lists are `Page`.

| Method and route | Reply |
| --- | --- |
| `GET /api/health` | `{ games: { id, available }[] }` |
| `GET /api/games` | `{ default, games: GameInfo[] }` |
| `GET /api/<game>/datasets` | `{ default, datasets: DatasetInfo[], problems }` |
| `POST /api/<game>/datasets/<id>/reload` | `DatasetInfo` |
| `GET /api/<game>/categories?dataset=` | `CategoryInfo[]` |
| `GET /api/<game>/summary?dataset=` | the game's counts, a JSON object |
| `GET /api/<game>/records/<category>?dataset=&q=&offset=&limit=&<filter>=` | `Page<RecordSummary>` |
| `GET /api/<game>/record/<category>?dataset=&id=` | `RecordDetail` |
| `GET /api/<game>/file?dataset=&path=&v=` | the file |
| `GET /api/<game>/asset?dataset=&kind=&ref=&v=` | the file, or JSON for `kind=material` |
| `GET /api/<game>/icon/<name>?dataset=` | the image |
| `GET /api/<game>/backdrops?q=&offset=&limit=` | `Page<Backdrop>` |
| `any /api/<game>/x/<name>` | the game's own |

Rules:

- `dataset` is required on every route that has it. There is no implied
  dataset.
- `limit` is 1 to 500; 60 when absent. `offset` is 0 or more; 0 when
  absent. This holds for every list route, `backdrops` too (before step
  4b it gave every skybox when `limit` was absent).
- `/api/health` holds no counts. The counts are in the game's `summary`.
  The start scripts and the test runner wait on `/api/health`.
- An extension (`x/<name>`) gets the rest of the path: empty for the name
  alone, `/...` below it. It answers 404 for a path it does not have.
- A `kind` outside `model`, `texture`, `animation`, `material` is `400`.
  A kind the game has no assets of is `404`.
- `v` is the dataset's signature. It only makes the URL change when the
  dataset is reloaded.
- Errors: `400` a missing or bad parameter; `404` an unknown game, dataset,
  category, record or file; `405` a wrong method; `503` a game that is not
  available; `500` anything else. The body is `ApiError`.
- The route is matched on the raw URL, so an encoded `..` never reaches a
  real route.
- The id rule: a game id, a dataset id, a category id and a format id
  match `^[a-z0-9][a-z0-9_-]{0,39}$`: 1 to 40 letters. This is today's
  rule for a dataset id.

## 9. Build and code rules

- TypeScript in strict mode, with `noUncheckedIndexedAccess` and
  `noImplicitOverride` (R-VIEW-10). One `tsconfig.json` for page, server,
  tools and tests. The renderer library has its own (below).
- esbuild bundles the page (`src/page/main.ts`), the server
  (`src/server/main.ts`) and each Node tool into `build/`. `build/` is not
  in git. The test runner starts `build/server.js`.
- The page is one bundle (step 3, done). `src/tools/build.ts` bundles
  `src/page/main.ts` into `public/vendor/renderer.js` and the server
  (`src/server/main.ts`) into `build/server.js` (step 4a). The page
  bundle stays under `public/vendor/`, its route since before step 3.
  `public/js` is gone. The HTML, the
  style sheets and the shader files stay static files.
- When the bundle does not load, a few lines of script on its tag in
  `index.html` show `#load-failure` and log the file name (`side.spec`).
- The renderer library is bundled from its source in the ref repo, in the
  page bundle and in the tool bundles that parse models. There is no
  global renderer object, and no separate parser bundle.
- The renderer library is viewer code (operator 2026-11-23): we patch it
  and build from our clone. R-VIEW-10 and R-VIEW-13 bind it.
  - It is TypeScript in strict mode (`strict`, `noImplicitOverride`). Its
    own `tsconfig.json` was written for compiler 4.3. Compiler 7.0.2
    refuses it: `suppressImplicitAnyIndexErrors` and
    `moduleResolution=node10` no longer exist.
  - `webviewer/tsconfig.lib.json` restates the library's flags without
    those two. `scripts/typecheck.sh` checks it in every test run. A type
    error in it ends the run.
  - Only the code we bundle is checked (operator 2026-11-23): the viewer,
    the `m3`, `dds` and `tga` handlers, the `m3` and `dds` parsers, and
    what they import. The rest of the library is never bundled and is
    not checked. Measured with `gl-matrix` 3.3.0: 68 errors in the whole
    library, 27 in the bundled part.
  - `gl-matrix` is 3.4.4, named in `package.json`. The declaration file
    of 3.3.0 does not pass compiler 7.0.2.
  - The 18 errors left in the bundled part are fixed in two library
    commits (patches 0052 and 0053). 0052 changes declarations only.
    0053 changes four places of code. Every test passed with both
    (run `full86`, section 13).
  - Step 3 added two commits that change types only, for our callers:
    0054 (`M3ModelInstance.model` is an `M3Model`) and 0055
    (`setVertexColor` takes any list of numbers). Run `full88` passed
    with them.
  - The page settings (`tsconfig.page.json`) have no Node globals. The
    library's `ModelViewer` extends `EventEmitter` of the npm package
    `events`, which ships no types. `src/page/core/events.d.ts` declares
    the part the page uses.
  - It does not pass `noUncheckedIndexedAccess`. Read from its code:
    `handlers/m3/handler.ts` reads `teamColors[i]` and then indexes the
    result. No compiler run backs this.
  - So there are two settings files: ours with that flag, the library's
    without. Making the library pass the flag is a series of changes over
    all its M3 code. That is not in this change (O-VSPEC-1).
  - A change to it stays a commit in the ref repo and a file in
    `webviewer/patches/`. The ref repo is outside git, so the commit
    hooks and the line limit do not see its files.
- `src/tools/build.ts` (before step 2: `tools/build-renderer.mjs`) keeps
  two duties: it refuses a ref repo with uncommitted changes, and it
  writes `webviewer/patches/` from the commits.
- `scripts/tool.sh <name>` bundles `src/tools/<name>.ts` into
  `build/tools/<name>.js` and runs it. `scripts/build.sh` starts the build
  tool this way.
- Python and shell tools stay as they are.
- `scripts/typecheck.sh` runs the compiler without output, on three
  settings files: the library's (`tsconfig.lib.json`), Node code
  (`tsconfig.json`) and page code (`tsconfig.page.json`). `scripts/test.sh`
  runs it first; a type error ends the run (R-VIEW-13).
- `scripts/typecheck.sh` also checks the import rule of section 3 with a
  Node tool that reads the import lines (`src/tools/import-rule.ts`). A
  forbidden import ends the run. Tests: `import-rule.spec`,
  `typecheck.spec`. The operator accepted the rule (O-VSPEC-7).
- No file over the repository's line limit. No `any`. No cast that hides a
  type error.

## 10. Page layout and saved state

### 10.1 Panels

- `#side`: the column at the left. `#gallery` on top, `#instances` below,
  each half the window height.
- `#game-tabs`: one `button[data-game]` per game, stacked, text turned
  vertical, on the gallery's right edge from its top (R-VIEW-20).
- `#gallery-handle`, `#instances-handle`: at the bottom of each panel's
  right edge (R-VIEW-24).
- Gallery closed: the game tabs and the gallery handle slide to the window
  edge with it and stay clickable. A tab click opens the gallery on that
  game (R-VIEW-23).
- A tab of a game that is not available is `disabled`. Its `title` is the
  reason (R-VIEW-27).
- Inside the gallery: the dataset select, then the category tabs built from
  `CategoryInfo[]`, then one pane per category built from its filters.

### 10.2 Scene documents

A scene is a document (R-VIEW-70). The type and its check are in
`src/shared/scene.ts`; the page and an exported file use the same ones.

```ts
interface SceneDocument {
  format: 'viewer-scene';
  version: 1;
  id: string;          // "s-" then 1 to 40 of a-z, 0-9; unique in the database
  name: string;        // 1 to 80 characters, trimmed
  created: string;     // ISO 8601 UTC
  modified: string;    // ISO 8601 UTC
  items: SceneItemDocument[];   // at most 20000
}

interface SceneItemDocument {
  game: GameId;
  dataset: DatasetId;
  source: { category: CategoryId; record: string; variant: number | null }
        | { file: string };
  x: number; y: number;  // finite
  rot: number;           // degrees, finite
  scale: number;         // finite, above 0
  sequence: number;      // integer, -1 or more
  pick: number;          // 0 to 1
  options: JsonObject;   // the game's own item values
}
```

- `parseSceneDocument(unknown)` returns the document or throws a
  `SceneError` that names the first fault by path, such as
  `items[3].scale: not above 0`. A document that fails is not read in
  part (R-VIEW-71). Unknown fields are a fault.
- `version` other than 1 is a fault. A later version adds a migration
  from the one before; the check runs on the result.
- SC2 `options`: `team` (integer 0 to 13, the 14 team colours) and `hd`
  (boolean). Step 5 moves
  them behind the game's `itemOptions`.
- An item whose game, category or record the server does not have is
  reported and not added. The other items are added (R-VIEW-80).

Store (`src/page/core/store/scenes-db.ts`): IndexedDB database `viewer`,
version 1, object store `scenes`, key path `id`. One record per scene.

- At startup every record is checked. A record that fails is listed as
  refused, with its reason, and can only be deleted. The others open
  (R-VIEW-77).
- The scene to open is the id in the setting `viewer.scene`. When it is
  missing or refused, the newest good scene opens. With none, an empty
  scene "scene 1" is made.
- Every change to the scene writes the document. Writes run one after
  another. `sc2viewer.scenes.flush()` waits for the last one.
- While a scene's items are being added, no write is made; one write
  follows.

Scene list (`features/scenes`, in `#view-tools`, before the landmarks):

- `#scenes-button` shows the open scene's name. `#scenes-list` lists the
  scenes by name: a click opens one; each has rename and delete; delete
  asks first (R-VIEW-75).
- At the end: new, export, import. New asks a name. Export downloads
  `<name>.scene.json`, the document as it is stored. Import reads a file,
  checks it, gives it a new id and a free name, stores it and opens it. A
  refused import changes nothing and says why (R-VIEW-76).

The page address (R-VIEW-74): the page never writes a scene into it. At
startup an address with a `#` part is refused with a failure message
("the scene is no longer kept in the address") and cleared. Old scenes
are not carried over (O-VIEW-5).

### 10.3 Settings

`src/page/core/settings.ts` holds every key, its parser and its default.
A module reads and writes only through it. Keys, all under `viewer.`:

| Key | Holds | Module |
| --- | --- | --- |
| `camera` | yaw, pitch, distance, target | `core/camera.ts` |
| `drawers` | which drawers are open | `ui/drawers.ts` |
| `dataset.<game>` | the chosen dataset of a game | `core/datasets.ts` |
| `view` | the grid toggle and the backdrop | `features/sky` |
| `landmarks` | the landmarks and the chosen one | `features/landmarks` |
| `scene` | the id of the open scene | `features/scenes` |

- `game` (the chosen game) comes with the game tabs, step 6.
- Each read returns the value and how it went: `none`, `restored`, or
  `refused: <why>`. A refused value is reported and not used; the next
  write replaces it (R-VIEW-73).
- The keys used before this design (`sc2viewer.*`) are not read.
- The camera, the grid, the backdrop and the landmarks are global, not per
  scene (O-VIEW-5).

## 11. Tests

- Runner: Playwright, through `scripts/test.sh`. A program decides pass or
  fail. A picture never does.
- The page offers `window.viewer`, typed `TestApi`, built from what the
  features register (R-VIEW-14). Tests use it and the DOM.
- **Contract tests** run once per available game, from `/api/games`:
  - protocol: every route of section 8 answers in its shape; paging walks a
    list without repeats; unknown ids give `404`;
  - page: the tab shows the game's categories; a record is previewed,
    added, selected, moved, copied, pasted, saved in the address and back
    after a reload, removed;
  - capabilities: a control shows only on an instance that has the
    capability. Negative: it is absent on one that has not.
- **Two implementations** (R-VIEW-91): the contract tests must pass for two
  games, and the instance tests for two formats.
- **Mixed scene**: instances of two games side by side; selection, group
  move and copy and paste work across them (R-VIEW-26).
- **Game not available**: the server is started with one game's data path
  unset. Its tab is disabled with the reason; the other game passes its
  contract tests (R-VIEW-8, R-VIEW-27).
- **Import rule**: a host test feeds the import checker a forbidden import
  and expects a failure.
- Each game specification lists its own tests.

## 12. Requirement state

Run: `full85`, the baseline of section 13. Every test file named below
passed in it. Nothing here is [verified]: see section 2.

| Requirement | State | Where |
| --- | --- | --- |
| R-VIEW-1 to 8 | [plan] | |
| R-VIEW-9 | [today] | `local.env`, `.gitignore` |
| R-VIEW-10 to 12 | [plan] | TypeScript today: the page (`src/page`, `src/formats/m3`, `src/shared`), the server (`src/server`, `src/games/sc2/server`) and `src/tools`. The survey tools under `tools/` and the tests are still JavaScript (step 8). |
| R-VIEW-13 | [today] | `scripts/typecheck.sh`, first in `scripts/test.sh`; it passed in run `full88` (section 13). `typecheck.spec` asserts that a type error ends the check. |
| R-VIEW-14 | [plan] | Today: `window.sc2viewer` plus direct reads of the shared object in 19 test files. |
| R-VIEW-20 to 23 | [plan] | |
| R-VIEW-24 | [plan] | Today the handles are at the top: `side.spec`. |
| R-VIEW-25 to 27 | [plan] | |
| R-VIEW-28 | [today] | `side.spec` |
| R-VIEW-30 to 33 | [today] | `datasets-ui.spec`, `datasets-api.spec` |
| R-VIEW-34 | [today] | `datasets-toast.spec` |
| R-VIEW-40 | [today] | `units-ui.spec`, `doodads-ui.spec`, `paged-list.spec` |
| R-VIEW-41 | [today] | `units-ui.spec`, `doodads-ui.spec` |
| R-VIEW-42 | [today] | `drag-preview.spec`, `units-ui.spec`, `doodads-ui.spec` |
| R-VIEW-43 | [today] | `add-all.spec`, `add-all-view.spec`, `landmarks.spec`, `skybox-units.spec` |
| R-VIEW-44 | [plan] | Today the rules sit in core: `page/core/rules.ts`, `page/core/scene.ts`. |
| R-VIEW-45 | [today] | `skybox-units.spec` |
| R-VIEW-50 | [today] | `viewer.spec`, `instances.spec` |
| R-VIEW-51 | [today] | `side.spec` |
| R-VIEW-52 | [today] | `pick-pixel.spec`, `cutout.spec` |
| R-VIEW-53 | [today] | `pick.spec`, `multi-select.spec`, `instances.spec` |
| R-VIEW-54 | [today] | `move.spec`, `clipboard.spec`, `pick.spec`, `multi-select.spec` |
| R-VIEW-55 | [today] | `clipboard.spec` |
| R-VIEW-56 | [today] | `pick.spec` |
| R-VIEW-57 | [today] | `viewer.spec` |
| R-VIEW-58 | [today] | `scene-focus.spec` |
| R-VIEW-59 | [today] | `clipboard.spec`, `multi-select.spec`, `hd-textures.spec` |
| R-VIEW-60 | [today] | `camera.spec`, `zoom.spec`, `viewer.spec` |
| R-VIEW-61 | [today] | `ground-sky.spec`, `grid-levels.spec` |
| R-VIEW-62 | [today] | `ground-sky.spec`, `skyboxes.spec` |
| R-VIEW-63 | [today] | `landmarks.spec`, `landmarks-store.spec` |
| R-VIEW-64 | [today] | `side.spec` |
| R-VIEW-65 | [today] | `viewer.spec` |
| R-VIEW-70 | [today] | `scenes.spec`, `viewer.spec`, `units-ui.spec`, `doodads-ui.spec`, `datasets-ui.spec`, `hd-textures.spec` (step 4c, run `t-4c`) |
| R-VIEW-71 | [today] | `scenes.spec`: ten faulty files, each refused with its path |
| R-VIEW-72, 73 | [today] | `camera-persist.spec`, `landmarks-store.spec`, `side.spec`, `scenes.spec` (the open scene). The chosen game is [plan] (step 6). |
| R-VIEW-74 to 77 | [today] | `scenes.spec` |
| R-VIEW-80 | [today] | `viewer.spec` |
| R-VIEW-81 | [today] | `displacement.spec`, `particles.spec` |
| R-VIEW-82 | [plan] | |
| R-VIEW-90 | [today] | For the [today] rows only. |
| R-VIEW-91 | [plan] | |
| R-VIEW-92 | [today] | One format only: see the game specification. |
| R-VIEW-93 | [today] | `AGENTS.md` |

## 13. Migration from the current code

| Today | Becomes |
| --- | --- |
| `public/js/core.js` | `page/core/` (render host, camera, status); its data rules go to the game |
| `public/js/scene.js` | `page/core/scene`, `page/ui/instances`, `features/focus` |
| `public/js/panels.js`, `doodads.js` | `page/ui/gallery`, built from `CategoryInfo` |
| `public/js/datasets.js` | `page/core/datasets`, `features/dataset-reload` |
| `public/js/side.js` | `page/ui/drawers`, `page/ui/game-tabs` |
| `public/js/controls.js`, `pick.js`, `select.js`, `clipboard.js`, `drag.js`, `landmarks.js`, `addall.js`, `sky.js` | one folder each under `page/features/` |
| `public/js/inspect.js` | `features/inspect` and format `probes` |
| `public/js/hd.js`, `textures.js`, `particles.js`, `billboards.js` | the game or its format |
| `public/components.js` | `page/ui/components/` |
| `public/ground.js`, `outline.js`, `pickbuffer.js`, `displacement.js` | `page/core/render/`; displacement becomes a format `PostPass` |
| `public/js/main.js` | `page/main.ts`, `page/core/frame`, `shared/address` |
| `public/index.html`, `style.css`, `theme.css`, `public/shaders/` | stay static files; the HTML loads one bundle and holds no game name |
| `public/vendor/renderer.js`, `src/renderer-entry.cjs`, `src/parser-entry.cjs` | gone: the library is imported where it is used |
| `server.mjs` | `server/core/` and the game's backend |
| `server-*.mjs` | the game's backend |
| `tools/*.mjs` | `src/tools/` |
| `tools/*.py`, `scripts/*.sh` | stay; the scripts start the bundles |
| `playwright.config.mjs` | `playwright.config.ts`; it starts `build/server.js` |
| `tests/*.spec.mjs` | `tests/*.spec.ts`, last |

Two tests of today prove how the page is served, not what it does. They
cannot pass unchanged, and are rewritten in step 3:

| Test | Today | After |
| --- | --- | --- |
| `server.spec`: "every page module in public/js is served, read at request time; nothing else under /js/" | 20 files under `/js/` | the bundle is served; nothing else under its folder |
| `side.spec`: "a page module that does not load is reported as a failure, naming the file" | one of 20 scripts fails to load | the bundle fails to load: a few lines of script in the HTML itself show the failure and name the file |

Numbers of today, counted in the files, not from a run: 51 test files with
254 `test(` calls (some stand in a loop and make several tests), 20 page
scripts, 51 library patches (53 after step 2, 55 after step 3).

Baseline (step 1, done 2026-11-23). Every test, the `@slow` ones too
(`WEBVIEWER_TEST_ALL=1 bash webviewer/scripts/test.sh`):

| Run | Start (UTC) | Result |
| --- | --- | --- |
| `full84` | 12:11:40 | 273 tests: 266 passed, 1 failed, 6 did not run. Exit 1, 179 s. |
| `full85` | 12:18:04 | 273 tests: 273 passed. Exit 0, 333 s. |

- Repository HEAD `3a640a05`, library HEAD `bce6a587`. The working tree
  held uncommitted changes; under `webviewer/` only `scripts/setup.sh` and
  `scripts/ref-docs-setup.sh`.
- `full84` failed in `datasets-api.spec`: "the datasets are listed, the
  built-in ones first; none has changed". Cause: the catalog of one dataset
  was older than two data files of the map. It was rebuilt
  (`catalog.sh --if-stale`), nothing else changed, and `full85` passed.
- The logs are `/tmp/opencode/full84.log` and `full85.log`. They are not
  kept in the repository.

Step 2 (done 2026-11-23), the same command:

| Run | Start (UTC) | Result |
| --- | --- | --- |
| `full86` | 12:44:19 | 273 tests: 273 passed. Exit 0, 335 s. |

- Repository HEAD `3a640a05` with the step 2 changes uncommitted. Library
  HEAD `1989c174`, 53 patches. Node 24.11.1, compiler 7.0.2.
- Both type checks passed at the start of the run.
- Built: the compiler, the two settings files, `scripts/typecheck.sh`,
  `scripts/tool.sh`, and the build tool in TypeScript.
- Not built in step 2: the page bundle and `build/server.js` (they come
  with the code they bundle, steps 3 and 4), and the import-rule check
  (O-VSPEC-7).
- With `gl-matrix` 3.3.0 the build tool gave the same two files, byte for
  byte, as `tools/build-renderer.mjs` did.

Step 3 (done 2026-11-23), the same command:

| Run | Start (UTC) | Result |
| --- | --- | --- |
| `full87` | 13:56:27 | 297 tests: 290 passed, 1 failed, 6 did not run. Exit 1, 198 s. |
| `full88` | 14:00:34 | 297 tests: 297 passed. Exit 0, 365 s. |

- Repository HEAD `3a640a05` with the step 2 and 3 changes uncommitted.
  Library HEAD `7ac1103a`, 55 patches.
- `full87` failed in `fresnel.spec`: "negative: a model with no fresnel
  layer draws the same frame with the term on and off". The two frames
  differed in the colour sums by one level of one pixel. The test passed
  20 of 20 times alone (`--repeat-each=10`) and in `full88`, unchanged.
  It was not seen to fail before step 3. It now has a small tolerance
  (O-VSPEC-8).
- Built: every file of `public/js`, `public/components.js` and the four
  render files is a typed module under `src/page` or `src/formats/m3`.
  `index.html` loads one script. The server's `/js/` route is gone.
- Changed tests: the two of the table above, and `skyboxes.spec`, which
  read the library's global `ModelViewer` (now `sc2viewer.DdsImage`).
- The page is still one shared object (`page/core/app.ts`), put together
  in `page/main.ts` in the old script order. Step 5 replaces it.

Step 4a (done 2026-11-23), the same command: the server in TypeScript,
with today's routes.

| Run | Start (UTC) | Result |
| --- | --- | --- |
| `full89` | 14:25:38 | 297 tests: 290 passed, 1 failed, 6 did not run. Exit 1, 183 s. |
| `full90` | 14:29:23 | 297 tests: 295 passed, 1 failed, 1 did not run. Exit 1, 347 s. |
| `full91` | 14:39:31 | 297 tests: 297 passed. Exit 0, 345 s. |

- Library HEAD `7ac1103a`, 55 patches, as in step 3.
- `full89` failed in `datasets-api.spec` ("none has changed"): the map's
  `UnitData.xml` and `BehaviorData.xml` were written at 14:25:42, four
  seconds into the run, by work outside the viewer. The scoba catalog
  was rebuilt at the start of `full90`.
- `full90` failed in `pick-pixel.spec` "CommandCenter (stock) @slow": the
  60 s test timeout. The machine's load average was 36 (other jobs). The
  test took 30 to 33 s in `full85` to `full88`, and 8.8 s when run again
  at once.
- Built: `src/server/core` (HTTP, static files, settings),
  `src/games/sc2/server` (storage, datasets, catalogs, skyboxes, HD
  textures, today's routes) and `src/server/main.ts`.
  `src/tools/build.ts` bundles it into `build/server.js`; the scripts and
  the test runner start that. `tools/datasets.mjs` is
  `src/tools/datasets.ts`, run with `scripts/tool.sh datasets`.
  `server.mjs` and `server-*.mjs` are gone.
- No test changed. The protocol of section 8 is step 4b.

Step 4b (2026-11-23): the protocol of section 8. The old routes are gone
(operator choice SWITCH).

| Run | Start (UTC) | Result |
| --- | --- | --- |
| `full92` | 15:07:18 | 302 tests: 300 passed, 1 failed, 1 did not run. Exit 1, 298 s. |
| `t-sky` | after 15:12 | 297 tests: 297 passed. Exit 0, 252 s. Not a planned full run (below). |

- Library HEAD `7ac1103a`, 55 patches, as in step 3.
- `full92` failed in `skyboxes.spec` "every skybox loads ... @slow": it
  read `backdrops` with no `limit`, so it surveyed 60 of 66 skyboxes. The
  test now asks `limit=500` and asserts that it got all of them.
- `t-sky` was meant to run that one test. With `WEBVIEWER_TEST_ALL=1` the
  `slow` project depends on `main`, so the whole `main` project ran too. A
  single `@slow` test is run with `--project slow --no-deps`. In it the
  survey passed with all 66 skyboxes. From here
  on, a full run needs the operator's permission (operator 2026-11-23).
- Built: `src/shared/protocol.ts` (ids, types, the route builder),
  `src/server/core/backend.ts` (`GameBackend`), `src/server/core/protocol.ts`
  (the routes over the games). `src/games/sc2/server/index.ts` is the SC2
  `GameBackend`. The page builds every URL with `routes`.
- Changed tests: every test that named an old route uses `tests/api.mjs`.
  New in `server.spec`: health and games, the categories, a dataset is
  required, unknown games, categories, kinds and methods, and the old
  routes answer 404. `ground-sky.spec` asserts the default page of 60.

Step 4c (2026-11-23): scene documents and settings (section 10). Targeted
runs while building; one full run, `full93`, with the operator's leave.

| Run | Result |
| --- | --- |
| `t-set` | the settings: 5 files, 35 tests, 35 passed |
| `t-scenes`, `t-scenes2` | `scenes.spec`: 1 failed each, both faults of the test (below) |
| `t-scenes3` | `scenes.spec`, `--repeat-each=3`: 33 passed |
| `t-4c` | 16 changed files named. 309 tests ran, 309 passed (below). |
| `t-scenes4` | `scenes.spec` after a types-only move: 11 passed |
| `full93` | Start 15:52:52 UTC. Every test, `@slow` too (operator allowed). 314 tests: 314 passed. Exit 0, 327 s. It closes steps 4b and 4c. |
| `t-swallow` | After full93, four promise errors that were dropped are now reported (dataset reload, scene open queue, paged list, picker search; the commit hook found them). `datasets-toast`, `paged-list`, `scenes`, `ground-sky`, `typecheck`: 30 passed. |
| `live1` to `live3` | The real server (`scripts/start.sh`, port 4600, real `scoba` and `stock` data) in a real browser: page on the new routes only, a gallery Marine drawn and back after a reload, two named scenes, export and import, an old address scene refused, a bad import refused, settings back under `viewer.*`. `live1`: 4 passed, 1 failed (the test hid the gallery before using its dataset select; test fixed). `live2` and `live3` (after the error fix): 5 passed. |

- Library HEAD `7ac1103a`, 55 patches.
- `t-scenes`: the test read a doodad's name from `unit`; it is in
  `doodad`. `t-scenes2`: the test read the open scene before "new" had
  opened it; it now polls. Neither was a fault of the page.
- `t-4c` was meant to run 16 files. `datasets-toast.spec` is in the
  `shared` project, which depends on `main`, so the whole `main` project
  ran: a run of the default suite, not asked for. `t-4b` ran the same way.
  A `shared` spec is run with `--no-deps` from now on.
- Built: `src/shared/scene.ts` (the document, its check, ids, names),
  `src/page/core/settings.ts` (every `viewer.*` key), `core/store/scenes-db.ts`
  (IndexedDB), `features/scenes` (the scenes and their list),
  `core/scenes-api.ts` (types). The camera, drawers, dataset, view and
  landmark modules read and write through `settings.ts`. `frame.ts` keeps
  no scene; `saveHash` is `saveScene`.
- Changed tests: the 10 files that read `location.hash` read the stored
  scene (`tests/scene.mjs`). `camera-persist.spec` and
  `landmarks-store.spec` use the new keys; a new negative proves the old
  key is not read. New: `scenes.spec`, 11 tests.
- Operator check: the look of the scene list and its dialogs.

Order of work:

1. Baseline: one full run of the current tests, recorded. Done, above.
2. Tooling: compiler, bundles, type check in the test run. Done, above.
3. Page to typed modules, behaviour unchanged. Done, above.
4. Server to core and one backend (4a, done, above), new routes (4b,
   above). Then 4c: scene documents and stored settings (section 10),
   in IndexedDB, named, with export and import; the URL holds no scene
   (operator 2026-11-23).
5. Interfaces of sections 5 to 7; the existing game becomes a plugin.
6. Game tabs and handles.
7. The second game and the second format.
8. Tests to TypeScript. Documents to the final state.

Each step ends with a full run, once the operator allows it. Until then
the step's own test files are run.

## 14. Operator checks

- The look and the feel of the game tabs and the handles.
- Whether the gallery of a game reads well.

## 15. Open points

| ID | Point |
| --- | --- |
| O-VSPEC-1 | The renderer library is viewer code and is type-checked in the test run (section 9). (a) Open: the operator ruled that it is viewer code, not which flags bind it. Checking it without `noUncheckedIndexedAccess` is the author's reading. (b) Closed (operator 2026-11-23): one compiler, and only the bundled code is checked. It passes in run `full86`. (c) Open: how our code imports it under two settings files. Step 3 shows it: our code reads the library's declaration files (`build/lib-types`, path `@renderer/*`) under our flags; the library's source is checked under its own. The page needs `src/page/core/events.d.ts` (section 9). (d) Open: the library code we do not bundle is not checked. |
| O-VSPEC-2 | The commit hooks have not been seen on `.ts` files in this repository. |
| O-VSPEC-3 | `Capabilities` lists what today's features need. A capability for a format's own effects (particles, lights) is left to the format's `probes` and `postPasses` until a second format needs the same. |
| O-VSPEC-4 | Closed (operator 2026-11-23): accepted. `sequences` on the instance, `parse` with the choice of format by extension, and core's own model store. |
| O-VSPEC-5 | Closed (step 2): Node 24.11.1, compiler `typescript` 7.0.2, `@types/node` 24.19.2. `scripts/typecheck.sh` prints the first two at the start of every run. |
| O-VSPEC-6 | Section 16 was written from the page code and the test titles. The baseline run `full85` (section 13) passed every test of today. It proves what those tests assert, not every sentence and constant of section 16: what no test asserts there stays read from the code. |
| O-VSPEC-7 | The import-rule check of section 9 was written first in step 3, with its tests (`src/tools/import-rule.ts`, `import-rule.spec`). Closed (operator 2026-11-23): the last six rules of section 3 are accepted: what `src/tools/` may import, `features` over `ui`, page and server apart, a game's `page` and `server` apart, where the library is imported, and imports from outside `src/`. |
| O-VSPEC-8 | `fresnel.spec` "negative: ... the same frame with the term on and off" asserts two frames equal to the last colour level. It failed once in `full87` by one level of one pixel and passed alone 20 of 20 times. Two renders of one still scene are known to differ a little (`changedSinceMark` ignores steps up to 40). Closed (operator 2026-11-23): a small tolerance. The test now allows 5 pixels of coverage and 0.05 levels of mean colour per channel; the real term moves the mean brightness by over 20. |

## 16. Feature behaviour

All [today]: what the current page does, read from its code and its test
titles. Core keeps it unchanged through the migration. A number here is a
constant of the code. Nothing here names a game.

### 16.1 Status messages

- A message shows as a toast at the top centre of the free view (16.2),
  not inside a panel.
- It stays 5 s. A failure stays 9 s.
- Messages in a row replace each other. Each shows at least 0.1 s.
- A click on the toast opens the message log and takes the toast down.
- The log holds every message in order, with its clock time and a failure
  mark. It grows while open.

### 16.2 Drawers

- The gallery and the instances panel are drawers. A handle slides its
  drawer out to the left and back. It shows a single angle mark that
  points left when open and right when closed, and carries
  `aria-expanded`. The choice is stored.
- A closed drawer is `inert`: it takes no mouse and no keys.
- The free view is the window without the open drawers. The toast and the
  camera framing centre on it.
- An instance behind an open drawer is not under the mouse. With the
  drawer closed it is.
- Each panel is half the window high, whatever it holds.

### 16.3 Mouse

| Input | Does |
| --- | --- |
| Left drag | holds the ground point under the pointer and pulls the map |
| Ctrl + left, held, with a selection | turns the selected instances to face the pointer. With no selection it is a left drag. |
| Alt + left drag on an instance | moves it. If it is selected, the whole selection moves by the same step. The point pressed stays under the pointer. |
| Alt + left drag off an instance | draws the select rectangle |
| Middle drag | orbits around the ground point under the pointer, 0.004 rad per pixel. Started on the sky, it orbits around the camera target. |
| Ctrl + middle drag | turns the view around the eye |
| Right drag | pans, 0.0006 x the camera distance per pixel |
| Wheel | zooms. The step glides over a few frames. A notch moves less the closer the eye is to the ground. Ctrl makes a notch a quarter. The eye never goes under the ground. The distance is at most 2000. Setting the view stops a glide. |
| Left click | selects (16.4). A press that moves more than 4 pixels is a drag. |
| Right click on an instance | opens its animation menu (16.5) |
| Double-click on a record or an instance | the game's own (6.6) |

### 16.4 Pick and selection

- The instance under the mouse is the one whose solid surface is drawn at
  that pixel. An instance in front takes the pixel from one behind.
- Under the mouse: it is drawn brighter, with a feathered green glow
  around its outline, only while it is there.
- A click selects it. Another instance takes the selection. A click on the
  ground clears it. A drag does not select.
- Shift + click adds an instance to the selection or takes it out.
- Every selected instance gets a ring.
- A click on a row name selects the same way, with shift too. Ctrl + click
  on a row name also points the camera at the instance.
- The rectangle selects every instance whose foot, middle or top is inside
  it. A new rectangle replaces the selection. With shift it adds. An empty
  one clears. A rectangle under 4 pixels is a click.
- The selection survives a new instance. A removed instance leaves it.

### 16.5 Animation menu

- A right click on an instance opens a menu of all its animations. A right
  drag does not. A right click on the ground does not.
- The menu stays open until Escape or a click elsewhere.
- Choosing one plays it once; then the instance goes back to its looping
  one.
- With the menu's "loop" box checked, the chosen one becomes the
  instance's looping animation.
- Capability controls and a game's own entries stand in the same menu.

### 16.6 Keys

| Key | Does |
| --- | --- |
| Delete | removes the selected instances |
| Ctrl+C, Ctrl+X, Ctrl+V | copy, cut, paste (16.7) |
| Ctrl+L | switches the menu's "loop" choice, when an instance is selected |
| Escape | closes the menu, the dialog or the floating window that is open |

- No key acts on the scene while a text field has the keys. The field
  keeps them: copy and paste work on its text.
- Ctrl+L never reaches the browser, wherever the keys are: not with a
  selection, not without, not from a text field, not from a floating
  window. The same holds for a Ctrl key a game adds.
- A game adds its own keys through `ui`.

### 16.7 Clipboard

- The clipboard is kept in the page. It is not the system clipboard.
- A copy keeps what defines the item: dataset, record or file, variant,
  scale, angle, animation, pick, item options. The game is added to this
  list [plan].
- A paste keeps the shape of the group. Its centre goes under the pointer.
  With the pointer off the view, the copies go where they were copied
  from.
- The copies become the selection.
- With no selection nothing is copied. An empty clipboard pastes nothing.

### 16.8 Gallery

- A list loads one page, then the next when scrolled to its end. A new
  search starts at the first page. The total is shown.
- A click on a row shows the preview: picture, data, "add to scene". A
  double-click on a row adds nothing.
- A drag shows the record's model on the ground point under the pointer.
  Off the view the preview hides. Above the horizon there is no ground:
  no preview, and a drop places nothing and says why.
- A drop places what the preview showed: the same variant and angle.
- A record that is a backdrop has no preview. Added or dropped, it becomes
  the backdrop.
- "Add all" asks first, with the count, and names what it leaves out. A
  question that is declined adds nothing, no landmark, and leaves the
  camera.
- "Add all" reads the list 500 at a time and loads 6 models at once.
- It lays the new instances out by size: clusters of small, medium and
  large ones, outliers alone. Nothing overlaps. The block goes next to the
  instances already there; none of those moves.
- Then the camera frames the block, and a landmark is saved, named after
  the filters, with a number when the name is taken.

### 16.9 View tools

- Landmarks: "origin" is always there, takes the camera to 0, 0, 0, and
  cannot be deleted. The pin asks for a name and saves the view. The trash
  asks, then deletes that one. The list and the chosen one are stored.
- Grid: hexagonal, on at first. Lines are about one pixel and solid, also
  at a flat angle. Its cell size follows the zoom, so it shows at every
  distance. It glows under the pointer and around every instance. The
  switch is stored. It needs the GL extension `OES_standard_derivatives`.
- Backdrop: chosen in a dialog, drawn behind everything. Escape closes the
  dialog without a change. The choice is stored.
- The camera is stored. A stored camera that is not valid is refused,
  reported and replaced by the default view.
- The canvas follows the window size.

### 16.10 Datasets in the page

- The page asks for the datasets every 3 s.
- A dataset that changed raises a question at the bottom: yes or no. Yes
  reloads the data and the page. No hides it until the files change again.
- Every asset URL carries the dataset's signature.
- An instance row has a dataset select (R-VIEW-32).

### 16.11 Frame

Order of one frame: clear; the backdrop and its post passes; depth clear;
the grid; the scene; the post passes; the outline of the instance under
the mouse. One step of animation time is at most 100 ms.

### 16.12 Components

`PagedList`, `Dialog`, the picker dialog, `ConfirmDialog`, `Toast`, the
drop-down, `FloatingWindow`. They move to `page/ui/components/` as typed
classes with the same behaviour.

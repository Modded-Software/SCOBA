// The services the page is made of, and what a feature or a game gets
// (SPEC-VIEWER 6.6). main.ts builds the services in core and ui, then
// installs each feature with one FeatureContext. A feature takes what it
// needs from the context; it publishes nothing on a shared object
// (R-VIEW-12). Features talk to each other through `events` and the
// services; a feature never imports another feature.

import type ModelViewer from '@renderer/viewer/viewer';
import type Scene from '@renderer/viewer/scene';
import type { AssetKind, CategoryInfo, GameInfo } from '../../shared/protocol';
import type { DatasetInfo } from '../../shared/records';
import type {
  AddOptions,
  CameraState,
  GroundBox,
  GroundChoice,
  Hit,
  Item,
  Ray,
  Rect,
  SelectBox,
  Sky,
  SkyChoice,
  StatusOptions,
  Vec2,
  Vec3,
} from './types';
import type { EventBus, ViewerEvents } from './bus';
import type { FormatModule, GameCategory, GameRecord, PageGame, PostPass, ViewerModel } from './plugin';
import type { Landmarks } from './landmarks';
import type { Ground } from './render/ground';
import type { Outline } from './render/outline';
import type { PickBuffer } from './render/pickbuffer';
import type { DefaultedSetting, Setting } from './settings';
import type { Skins } from './skins';
import type { TextureWindow } from './texturewindow';

/** The games: what main.ts registered, the server lists, and the gallery shows (core/games.ts, core/datasets.ts). */
export interface GameRegistry {
  readonly games: readonly PageGame[];
  /** The plugin of the gallery's game. */
  plugin(): PageGame;
  /** The gallery's game id. */
  game(): string;
  pluginOf(game: string): PageGame;
  /** What a registered game adds to the page; an error before it installed. */
  partsOf(game: string): GameParts;
  addParts(game: string, parts: GameParts): void;
  /** The games as the server lists them, in its order. */
  gamesInfo(): GameInfo[];
  /** Why a game cannot be the gallery's, or null. */
  gameRefusal(id: string): string | null;
  /** Make a game the gallery's (R-VIEW-21); an error when it is refused. */
  setGame(id: string): Promise<void>;
  /** Read a game's datasets, once. */
  loadGame(id: string): Promise<void>;
  /** The category of a noun ("unit") in the gallery's game, or an error. */
  categoryOf(noun: string): GameCategory;
  /** The noun of an item's category, or null for a bare model file. */
  nounOf(item: Item): string | null;
}

/**
 * The typed calls of SPEC-VIEWER 8 (core/datasets.ts). Each takes a game
 * id last; absent: the gallery's. A dataset absent or null: that game's
 * current one.
 */
export interface ApiClient {
  getJson<T>(url: string): Promise<T>;
  record(category: string, id: string, dataset?: string | null, game?: string): Promise<GameRecord>;
  records(category: string, params?: Record<string, string>, dataset?: string | null, game?: string): string;
  categories(dataset?: string | null, game?: string): Promise<CategoryInfo[]>;
  extensionUrl(name: string, game?: string): string;
  modelUrl(path: string, dataset?: string | null, game?: string): string;
  pathSolver(dataset?: string | null, game?: string): (src: unknown) => unknown;
  /** The route of a reference a model uses, of one kind, resolved for the dataset. */
  assetUrl(kind: AssetKind, reference: string, dataset?: string | null, game?: string): string;
  iconUrl(name: string, dataset?: string | null, game?: string): string;
  /** The gallery game's current dataset. */
  dataset(): string | null;
  currentDataset(game?: string): string | null;
  defaultDataset(game?: string): string | null;
  datasets(game?: string): DatasetInfo[];
  setDataset(id: string): void;
  requireDataset(id: string | null, game?: string): string;
  hasDataset(id: string, game?: string): boolean;
  datasetLabel(id: string, game?: string): string;
  /** Take a fresh dataset list of the gallery's game: the changed state of the known ones. */
  updateDatasets(list: readonly DatasetInfo[]): void;
}

/** The renderer and the frame (core/host.ts, core/frame.ts). */
export interface RenderHost {
  readonly viewer: ModelViewer;
  readonly scene: Scene;
  readonly skyScene: Scene;
  readonly ground: Ground;
  readonly outline: Outline;
  readonly pickBuffer: PickBuffer;
  readonly formats: readonly FormatModule[];
  readonly postPasses: readonly PostPass[];
  readonly canvas: HTMLCanvasElement;
  readonly BACKGROUND: Vec3;
  /** Load a model file through the formats; null when no format reads it. */
  loadModel(url: string, solver: (src: unknown) => unknown): Promise<ViewerModel | null>;
  formatOf(model: ViewerModel): FormatModule;
  reportUndrawn(name: string, model: ViewerModel): void;
  resize(): void;
  /** The part of the canvas no open panel covers, in page pixels. */
  visibleRect(): Rect;
  /** Draw one frame now. */
  draw(dt: number): void;
  /** Run one post pass or not. */
  setPostPass(id: string, on: boolean): void;
  /** Parts the post passes drew in the last frame. */
  displacedBatches(): number;
}

/** The scene: its items, the sky and the grid (core/scene.ts, core/sky.ts). */
export interface SceneService {
  /** In the order they were added. */
  readonly items: Item[];
  add(path: string, options?: AddOptions): Promise<number>;
  /** A backdrop record becomes the sky; then null. */
  addRecord(category: string, id: string, options?: AddOptions): Promise<number | null>;
  setVariation(item: Item, variant: number): Promise<void>;
  setItemDataset(item: Item, dataset: string): Promise<void>;
  remove(id: number): void;
  removeMany(ids: readonly number[]): number;
  clear(): void;
  restart(): void;
  playOnce(item: Item, sequence: number): void;
  loopSequence(item: Item, sequence: number): void;
  endOneShots(): void;
  setRotation(item: Item, rot: number): void;
  setPosition(item: Item, x: number, y: number): void;
  applyTransform(item: Item): void;
  applySequence(item: Item): void;
  applyLook(item: Item): void;
  /** The skybox shown, or null. */
  sky(): Sky | null;
  setSky(choice: SkyChoice | null): Promise<void>;
  setGrid(on: boolean): void;
  grid(): boolean;
  /** The ground texture's record, or null: none (SPEC-VIEWER 17.5). */
  ground(): GroundChoice | null;
  setGround(choice: GroundChoice | null): Promise<void>;
}

/** The selection, what is under the mouse, and the hit tests (core/selection.ts). */
export interface SelectionService {
  select(id: number | null): void;
  setSelection(ids: Iterable<number>): void;
  toggleSelected(id: number): void;
  /** The one selected last, or null. */
  selectedId(): number | null;
  selectedIds(): number[];
  hasSelection(): boolean;
  /** The item under the mouse, as the pick feature last found it. */
  hovered(): Item | null;
  setHovered(id: number | null): void;
  /** The select rectangle while it is dragged, in page pixels. */
  rect(): SelectBox | null;
  setRect(box: SelectBox | null): void;
  itemAt(clientX: number, clientY: number): Item | null;
  hitAt(clientX: number, clientY: number): Hit | null;
  planeAt(clientX: number, clientY: number, z: number): Vec2 | null;
  itemPixel(id: number): Vec2 | null;
  /** The page pixel of an item's column at height share `k` (0 base, 1 top). */
  itemScreen(id: number, k?: number): Vec2 | null;
  /** Is a key for a text field (the key is not the viewer's then)? */
  editingText(target: EventTarget | null): boolean;
}

/** The camera (core/camera.ts, core/view.ts) and its landmarks (core/landmarks.ts). */
export interface CameraService extends Landmarks {
  readonly camera: CameraState;
  /** Where the camera's start came from: the stored setting, or its declared default. */
  readonly cameraStart: 'stored' | 'default';
  /** The ground point under the mouse, or null off the ground. */
  pointer(): Vec2 | null;
  /** Set it where no mouse move says (a drag over the view: features/drag). */
  setPointer(point: Vec2 | null): void;
  eye(): Vec3;
  applyCamera(): void;
  groundAt(px: number, py: number): Vec2 | null;
  eventGround(e: MouseEvent): Vec2 | null;
  rayAt(px: number, py: number): Ray;
  screenOf(point: Vec3): Vec2 | null;
  /** Set any of yaw, pitch, distance, target. Stops a zoom glide. */
  view(next: Partial<CameraState>): void;
  /** The zoom goal while the camera glides to it, or null. */
  zoomGoal(): number | null;
  /** What one wheel notch would move now, as a share of the distance. */
  notchShare(ctrl?: boolean): number;
  wheel(e: WheelEvent): void;
  stopGlide(): void;
  /** The camera that shows a ground box whole in the visible part of the view. */
  frameBox(box: GroundBox): CameraState;
  /** Move the camera to show these items (features/focus). */
  focusItem(item: Item): void;
}

export interface StatusService {
  setStatus(text: string, options?: StatusOptions): void;
  /** End of the line for a failed user action: logged and shown. */
  reportFailure(error: unknown): void;
  /** Loads in flight; the tests wait for 0. */
  pending: number;
  /** Run a load with the pending count up. */
  busy<T>(work: () => Promise<T>): Promise<T>;
  placeStatus(): void;
  statusState(): { text: string | null; up: boolean; failure: boolean };
  statusLog(): { shown: string[]; waiting: number; lastUpMs: number | null };
}

/** The typed local storage (core/settings.ts). */
export interface Store {
  /** The stored value, or the setting's declared default when nothing is stored. */
  read<T>(setting: DefaultedSetting<T>): T;
  /** The stored value; null: nothing is stored, and the caller's own rule decides. */
  find<T>(setting: Setting<T>): T | null;
  write<T>(setting: Setting<T>, value: T): void;
  clear<T>(setting: Setting<T>): void;
}

export interface WindowPlace {
  left: number;
  top: number;
  width: number;
  height: number;
}

/** A movable window over the view (ui/components/floatingwindow). */
export interface FloatingWindowHandle {
  readonly title: HTMLElement;
  readonly body: HTMLElement;
  readonly isOpen: boolean;
  open(place: WindowPlace): void;
  close(): void;
}

/** A button of a gallery pane's tool row ("add all"); its id is `<tool id>-<category id>`, its class the tool id. */
export interface GalleryTool {
  readonly id: string;
  readonly label: string;
  title(category: CategoryInfo): string;
  /** Whether the pane of this category has the button. */
  when(category: CategoryInfo): boolean;
  run(category: CategoryInfo): Promise<void>;
}

/** What a feature does when a gallery row is dragged. */
export interface RowDrag {
  start(e: DragEvent, record: { id: string; name: string }, noun: string): void;
  end(): void;
}

/** The panels and the building blocks (ui/). */
export interface UiService {
  setDrawer(id: string, to?: boolean): void;
  drawerState(): Record<'gallery' | 'instances', boolean>;
  /** A category list's query as shown: `q` and each filter that is set. */
  galleryQuery(category: string): Record<string, string>;
  /** A tool button on every gallery pane of records. */
  addGalleryTool(tool: GalleryTool): void;
  /** What a drag of a gallery row does; one feature sets it. */
  setRowDrag(drag: RowDrag): void;
  /** A record icon from a dataset of a game, or an empty box. */
  iconNode(name: string | null, dataset?: string, game?: string): HTMLElement;
  /** `escape` false: Escape does not close it. `closing`: called for its close button in place of the close. */
  floatingWindow(spec: { id: string; title: string; escape?: boolean; closing?: () => void }): FloatingWindowHandle;
}

/** What a feature adds to the test API: `app` members go on window.SCOBAEdit, `viewer` on window.scobaeditor. */
export interface TestApiBuilder {
  app(members: Readonly<Record<string, unknown>>): void;
  viewer(members: Readonly<Record<string, unknown>>): void;
  /** A key of scobaeditor.state() that a feature knows (pick, dragPreview). */
  statePart(name: string, read: () => unknown): void;
  /** Every state part, read now (features/inspect). */
  stateParts(): Record<string, unknown>;
}

export interface FeatureContext {
  readonly games: GameRegistry;
  readonly render: RenderHost;
  readonly scene: SceneService;
  readonly selection: SelectionService;
  readonly camera: CameraService;
  readonly status: StatusService;
  readonly store: Store;
  readonly events: EventBus<ViewerEvents>;
  readonly api: ApiClient;
  readonly ui: UiService;
  /** The one texture window; a game opens it on its textures (core/texturewindow.ts). */
  readonly textureWindow: TextureWindow;
  /** The skins of the instances (core/skins.ts). */
  readonly skins: Skins;
  readonly testApi: TestApiBuilder;
}

export interface Feature {
  readonly id: string;
  install(context: FeatureContext): void;
}

/** What a game gets at install: the same context as a feature. */
export type GameContext = FeatureContext;

/** What a game adds to the page: hooks core and the features call. */
/** The itemOptions of a game without item options: any key is refused. */
export function noItemOptions(raw: Readonly<Record<string, unknown>>): Record<string, unknown> {
  const [key] = Object.keys(raw);
  if (key !== undefined) throw new Error(`unknown item option "${key}"`);
  return {};
}

export interface GameParts {
  /** The grid glow class of an item: 0 the standard one, 1 the game's second. */
  glowOf(item: Item): number;
  /** The game's facts of an item, for scobaeditor.state(). */
  itemFacts(item: Item): Record<string, unknown>;
  /** The game's settings of an item, checked; an unknown key is refused (thrown). */
  itemOptions(raw: Readonly<Record<string, unknown>>): Record<string, unknown>;
  /** The texture service's name of a texture an instance names (SPEC-VIEWER 17); absent: the game has none. */
  readonly textureAsset?: (source: string) => string;
  /** The texture owner of an item (SPEC-HD-TEXTURES 5.1); null or absent: it has none, and no skin controls. */
  readonly textureOwner?: (item: Item) => string | null;
  /** What a double-click on an instance or its list row opens. */
  openItem(item: Item): Promise<void>;
  /** What a double-click on a gallery row opens. */
  openRecord(category: string, id: string): Promise<void>;
}

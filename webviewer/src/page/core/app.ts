// The page's shared object (window.SC2App) and its parts, as types.
//
// Step 3 of SPEC-VIEWER section 13 ports the page as it is: one object
// that every module adds its part to, and reads the others' parts from.
// Each part's type is here, in core, because a feature may not import
// another feature (section 3). Step 5 replaces the object with the
// services of section 6.6.
//
// main.ts puts the parts together in the order the old scripts loaded and
// hands the whole to setApp. A module reads the whole through app(), at
// call time; at install time it gets only the parts installed before it.

import type ModelViewer from '@renderer/viewer/viewer';
import type Scene from '@renderer/viewer/scene';
import type M3Model from '@renderer/viewer/handlers/m3/model';
import type M3ModelInstance from '@renderer/viewer/handlers/m3/modelinstance';
import type { CategoryInfo } from '../../shared/protocol';
import type { ScenesApi } from './scenes-api';
import type { DatasetInfo, DoodadRecord, Facets, PlacedRecord, UnitRecord, Vec3 } from '../../shared/records';
import type { Ground } from './render/ground';
import type { Outline } from './render/outline';
import type { PickBuffer } from './render/pickbuffer';
import type { viewerLib } from './library';
import type { make } from './dom';

export type { Vec3 };
export type Vec2 = [number, number];

/** A placed unit, doodad or bare model file. */
export interface Item {
  readonly id: number;
  path: string;
  /** Where its record and textures come from. */
  dataset: string;
  /** A unit's or a doodad's record; null for a bare model file. */
  unit: PlacedRecord | null;
  model: M3Model;
  instance: M3ModelInstance;
  x: number;
  y: number;
  /** Degrees. */
  rot: number;
  scale: number;
  sequence: number;
  team: number;
  /** 0 to 1: chooses inside the data's scale ranges. */
  pick: number;
  /** Which of a doodad's model variations this is; null for a unit or a bare model. */
  variation: number | null;
  dataScale: Vec3;
  /** The animation played once from the menu, or null. */
  oneShot: number | null;
  /** The HD texture set, where the model has one; hdLayers: how many layers have both. */
  hd: boolean;
  hdLayers: number;
  largestTexture: number;
}

/** How an item is added: every field optional. */
export interface AddOptions {
  dataset?: string;
  unit?: PlacedRecord | null;
  pick?: number;
  x?: number;
  y?: number;
  rot?: number;
  scale?: number;
  sequence?: number;
  team?: number;
  variation?: number | null;
  hd?: boolean;
}

export interface CameraState {
  yaw: number;
  pitch: number;
  distance: number;
  target: Vec3;
}

/** A page rectangle. */
export interface Rect {
  left: number;
  right: number;
  top: number;
  bottom: number;
}

export interface Ray {
  from: Vec3;
  dir: Vec3;
}

/** What playRate needs of an item. */
export interface Playing {
  unit: PlacedRecord | null;
  model: M3Model;
  sequence: number;
}

export interface StatusOptions {
  failure?: boolean;
}

/** core/host.ts: the renderer, the camera, shared state and helpers. */
export interface CoreApi {
  lib: typeof viewerLib;
  viewer: ModelViewer;
  scene: Scene;
  skyScene: Scene;
  ground: Ground;
  outline: Outline;
  pickBuffer: PickBuffer;
  displacement: { enabled: boolean; draw(scene: Scene, w: number, h: number): number };
  canvas: HTMLCanvasElement;
  BACKGROUND: Vec3;
  /** Team colours the renderer knows. */
  TEAMS: number;
  camera: CameraState;
  /** 'none', 'restored', or 'refused: <why>'. */
  cameraRestore: string;
  /** Items in the scene, in the order they were added. */
  items: Item[];
  /** Model and unit loads in flight. */
  pending: number;
  /** The ground point under the mouse, or null when it is off the ground. */
  pointer: Vec2 | null;
  $: (id: string) => HTMLElement;
  visibleRect(): Rect;
  reportFailure(error: unknown): void;
  reportUndrawn(name: string, model: M3Model): void;
  getJson<T>(url: string): Promise<T>;
  el: typeof make;
  iconNode(name: string | null, dataset?: string): HTMLElement;
  shown(value: number): string;
  eye(): Vec3;
  applyCamera(): void;
  resize(): void;
  groundAt(px: number, py: number): Vec2 | null;
  eventGround(e: MouseEvent): Vec2 | null;
  rayAt(px: number, py: number): Ray;
  screenOf(point: Vec3): Vec2 | null;
  dataScale(unit: PlacedRecord | null, pick: number): Vec3;
  baseHeight(unit: PlacedRecord | null): number;
  playRate(item: Playing): number;
  defaultSequence(model: M3Model): number;
}

/** The status toast and its message log. */
export interface StatusApi {
  setStatus(text: string, options?: StatusOptions): void;
  statusState(): { text: string | null; up: boolean; failure: boolean };
  statusLog(): { shown: string[]; waiting: number; lastUpMs: number | null };
  placeStatus(): void;
}

export interface DrawersApi {
  setDrawer(id: string, to?: boolean): void;
  drawerState(): Record<'panel' | 'instances', boolean>;
}

export interface DatasetsApi {
  setupDatasets(): Promise<void>;
  setDataset(id: string): void;
  requireDataset(id: string | null): string;
  record(kind: 'unit', id: string, dataset?: string | null): Promise<UnitRecord>;
  record(kind: 'doodad', id: string, dataset?: string | null): Promise<DoodadRecord>;
  record(kind: 'unit' | 'doodad', id: string, dataset?: string | null): Promise<PlacedRecord>;
  /** The URL of one page of a category (units, doodads, models) of a dataset; default: the current one. */
  records(category: string, params?: Record<string, string>, dataset?: string | null): string;
  categories(dataset?: string | null): Promise<CategoryInfo[]>;
  /** The gallery filters' values, out of the categories. */
  facets(dataset?: string | null): Promise<Facets>;
  /** The game the page shows (/api/games default). */
  game(): string;
  /** The URL of a game-only route, below /api/<game>/x/. */
  extensionUrl(name: string): string;
  dataset(): string | null;
  defaultDataset(): string | null;
  datasets(): DatasetInfo[];
  onDatasetChange(listener: (id: string) => void): number;
  /** Take a fresh /api/<game>/datasets list: the changed state of the known ones. */
  updateDatasets(list: readonly DatasetInfo[]): void;
  hasDataset(id: string): boolean;
  datasetLabel(id: string): string;
  modelUrl(path: string, dataset?: string | null): string;
  pathSolver(dataset?: string | null): (src: unknown) => unknown;
  iconUrl(name: string, dataset?: string | null): string;
}

export interface DatasetReloadApi {
  checkDatasets(): Promise<void>;
  datasetToast(): { up: boolean; dataset: string | null; text: string | null };
  startDatasetPolling(): void;
}

export interface ControlsApi {
  zoomGoal(): number | null;
  notchShare(ctrl?: boolean): number;
  view(next: Partial<CameraState>): void;
}

export interface DoodadPlacement {
  variation: number;
  rot: number;
}

export interface SceneApi {
  add(path: string, options?: AddOptions): Promise<number>;
  addUnit(id: string, options?: AddOptions): Promise<number | null>;
  addDoodad(id: string, options?: AddOptions): Promise<number>;
  doodadPlacement(doodad: DoodadRecord, options?: AddOptions): DoodadPlacement;
  setVariation(item: Item, variation: number): Promise<void>;
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
}

export interface FocusApi {
  focus(id: number): void;
  focusItem(item: Item): void;
}

/** The instances panel: the scene list. */
export interface InstancesApi {
  renderList(): void;
  markSelected(ids: ReadonlySet<number>, last: number | null): void;
  /** Show an item's field in its list row: the animation, the angle, the place. */
  showItemField(item: Item, field: 'sequence' | 'rot' | 'x' | 'y'): void;
}

export interface UnitQuery {
  q: string;
  race: string;
  kind: string;
  family?: string;
}

export interface DoodadQuery {
  q: string;
  type: string;
  tileset: string;
}

export interface GalleryApi {
  setupUnits(): Promise<void>;
  unitQuery(): UnitQuery;
  setupDoodads(): Promise<void>;
  doodadQuery(): DoodadQuery;
}

export interface Landmark extends CameraState {
  id: number;
  name: string;
}

export interface GroundBox {
  x0: number;
  x1: number;
  y0: number;
  y1: number;
  z?: number;
}

export interface LandmarksApi {
  addLandmark(view: Omit<Landmark, 'id'>): number;
  goToLandmark(id: number): void;
  removeLandmark(id: number): void;
  landmarkState(): { list: Landmark[]; selected: number | null; restore: string };
  frameBox(box: GroundBox): CameraState;
  filterName(query: UnitQuery): string;
  landmarks(): Landmark[];
}

export interface LayoutEntry {
  id: number;
  size: number;
  x: number;
  y: number;
  cluster: number;
  cell: number;
}

export interface AddAllRun {
  asked: number;
  added: number;
  failed: string[];
  running: boolean;
  layout: LayoutEntry[];
  landmark: number | null;
  skipped: string[];
}

export interface AddAllApi {
  addAll(kind?: string): Promise<void>;
  arrangeBySize(list: readonly Item[], others?: readonly Item[]): LayoutEntry[];
  addAllState(): AddAllRun & { dialogOpen: boolean; question: string | null };
}

export interface GhostState {
  kind: string;
  unit: string;
  variation: number | null;
  rot: number;
  loaded: boolean;
  shown: boolean;
  location: number[] | null;
}

export interface DragApi {
  startDrag(e: DragEvent, record: { id: string; name: string }, kind?: 'unit' | 'doodad'): void;
  endGhost(): void;
  ghostState(): GhostState | null;
}

export interface SkyChoice {
  id: string;
  name: string;
  file: string;
}

export interface Sky extends SkyChoice {
  model: M3Model | null;
  instance: M3ModelInstance | null;
}

export interface SkyApi {
  /** The skybox shown, or null. */
  sky: Sky | null;
  setGrid(on: boolean): void;
  setSky(choice: SkyChoice | null): Promise<void>;
  restoreView(): Promise<void>;
}

export interface Hit {
  item: Item;
  point: Vec3;
}

export interface MenuState {
  item: number;
  entries: (string | null)[];
  playing: (string | null)[];
  loop: boolean;
  hd: boolean | undefined;
}

export interface PickState {
  hovered: number | null;
  selected: number | null;
  selection: number[];
  rect: SelectBox | null;
  menu: MenuState | null;
  loop: boolean;
}

export interface PickApi {
  updatePick(): void;
  faceSelected(e: MouseEvent): void;
  forget(id: number | null): void;
  pickState(): PickState;
  select(id: number | null): void;
  setSelection(ids: Iterable<number>): void;
  toggleSelected(id: number): void;
  toggleLoop(): boolean;
  refreshMenu(): void;
  selectedId(): number | null;
  selectedIds(): number[];
  hasSelection(): boolean;
  itemAt(clientX: number, clientY: number): Item | null;
  hitAt(clientX: number, clientY: number): Hit | null;
  planeAt(clientX: number, clientY: number, z: number): Vec2 | null;
  hoveredItem(): Item | null;
  itemPixel(id: number): Vec2 | null;
  itemScreen(id: number, k?: number): Vec2 | null;
}

export interface SelectBox {
  left: number;
  top: number;
  width: number;
  height: number;
}

export interface SelectApi {
  startSelectRect(e: MouseEvent): void;
  moveSelectRect(e: MouseEvent): void;
  endSelectRect(e: MouseEvent): void;
  editingText(target: EventTarget | null): boolean;
  selectRect(): SelectBox | null;
}

export interface ClipboardApi {
  copySelected(): number;
  cutSelected(): number;
  pasteCopied(at?: Vec2 | null): Promise<number[]>;
  copiedCount(): number;
}

export interface TexturesApi {
  openTexturesFor(kind: 'unit' | 'doodad', id: string): Promise<void>;
  openTexturesOf(item: Item): Promise<void>;
  textureWindow(): { open: boolean; user: string | null; file: string | null; dataset: string | null; originals: string };
}

export interface HdApi {
  setupHd(): Promise<void>;
  applyHd(item: Item): Promise<void>;
  setHd(item: Item, on: boolean): Promise<boolean>;
  isHd(item: Item): boolean;
  toggleSelectedHd(): Promise<void>;
  hdAssets(): string[];
}

/** core/frame.ts: drawing and the frame loop. */
export interface FrameApi {
  /** Displacement batches the last frame drew, sky and units (for the tests). */
  displacedBatches: number;
  draw(dt: number): void;
  setDisplacement(on: boolean): void;
}

export type { RefusedScene, ScenesApi, ScenesState } from './scenes-api';

/**
 * The whole object. The inspection for the tests (features/inspect,
 * formats/m3 particles and billboards) is not part of it: main.ts adds it
 * to window.SC2App only.
 */
export type App = CoreApi &
  StatusApi &
  DrawersApi &
  DatasetsApi &
  DatasetReloadApi &
  ControlsApi &
  SceneApi &
  FocusApi &
  InstancesApi &
  GalleryApi &
  LandmarksApi &
  AddAllApi &
  DragApi &
  SkyApi &
  PickApi &
  SelectApi &
  ClipboardApi &
  TexturesApi &
  HdApi &
  ScenesApi &
  FrameApi;

let whole: App | null = null;

/** The whole object. Throws before main.ts has put it together. */
export function app(): App {
  if (whole === null) throw new Error('page: a module used the app before main.ts put it together');
  return whole;
}

export function setApp(value: App): void {
  whole = value;
}

/** Two parts as one object: `a`, with the members of `b` added. */
export function merge<A extends object, B extends object>(a: A, b: B): A & B {
  return Object.assign(a, b);
}

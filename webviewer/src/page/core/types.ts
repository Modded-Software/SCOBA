// The page's data types: items, the camera, and what the tests read. The
// services that hold and change them are in core/context.ts.

import type { Capabilities, GameRecord, Placement, ViewerInstance, ViewerModel } from './plugin';
import type { Vec3 } from '../../shared/records';

export type { Vec3 };
export type Vec2 = [number, number];
export type { RefusedScene, ScenesState } from './scenes-api';

/** Where an item comes from: a record of one of the game's categories. */
export interface ItemSource {
  /** The category's route name: "units". */
  category: string;
  record: GameRecord;
}

/** A placed record or bare model file. */
export interface Item {
  readonly id: number;
  /** Its game: the plugin that placed it, the routes its files come by (R-VIEW-26). */
  readonly game: string;
  /** The model file shown: the placement's. */
  path: string;
  /** Where its record and textures come from (a dataset of its game). */
  dataset: string;
  /** Its record; null for a bare model file. */
  source: ItemSource | null;
  /** How the game placed it (SPEC-VIEWER 6.4). */
  placement: Placement;
  model: ViewerModel;
  instance: ViewerInstance;
  /** What the instance can do (SPEC-VIEWER 6.2), from its format. */
  capabilities: Capabilities;
  x: number;
  y: number;
  /** Degrees. */
  rot: number;
  scale: number;
  sequence: number;
  /** The team colour, where the format has them and the placement shows them. */
  team: number;
  /** The animation played once from the menu, or null. */
  oneShot: number | null;
  /** The skin of its owner it shows (SPEC-VIEWER 17.4): "original", "new" or a saved skin's name. */
  skin: string;
  /** The longest side of any texture it shows, once they are in; 0 before. */
  largestTexture: number;
  /** The game's settings of the item (SPEC-VIEWER 6.5), as its itemOptions checked them. */
  options: Record<string, unknown>;
}

/** How an item is added: every field optional. */
export interface AddOptions {
  /** The item's game; absent: the gallery's. */
  game?: string;
  /** A dataset of that game; absent: its current one. */
  dataset?: string;
  pick?: number;
  x?: number;
  y?: number;
  rot?: number;
  scale?: number;
  sequence?: number;
  team?: number;
  /** The skin; absent: "original". */
  skin?: string;
  /** Which of the record's model files; null or absent: the game chooses. */
  variant?: number | null;
  /** The game's settings, checked by its itemOptions. */
  options?: Readonly<Record<string, unknown>>;
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

export interface StatusOptions {
  failure?: boolean;
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

/** The record being dragged into the view (features/drag): scobaeditor.state().dragPreview. */
export interface DragPreviewState {
  kind: string;
  unit: string;
  variation: number | null;
  rot: number;
  loaded: boolean;
  shown: boolean;
  location: number[] | null;
}

export interface SkyChoice {
  id: string;
  name: string;
  file: string;
  /** Whose backdrop, from which dataset. */
  game: string;
  dataset: string;
}

export interface Sky extends SkyChoice {
  model: ViewerModel | null;
  instance: ViewerInstance | null;
}

/** A record of a ground category (SPEC-VIEWER 17.5), and the texture it shows: its `file`, as the texture service names it. */
export interface GroundChoice {
  game: string;
  dataset: string;
  category: string;
  id: string;
  name: string;
  texture: string;
  /** The variant the ground shows; absent: the terrain bake, else the original. */
  variant?: string;
}

export interface Hit {
  item: Item;
  point: Vec3;
}

/** The open instance menu. */
export interface MenuState {
  item: number;
  entries: (string | null)[];
  playing: (string | null)[];
  loop: boolean;
  /**
   * The skin row (SPEC-VIEWER 17.4): the chosen skin and its label, whether the choice has its icon
   * and arrow (R-VIEW-137), the choices, the rows of the list with their icons ("Add New Skin…"
   * last, name ""), the bake button's verb and whether it is disabled, the shown bake badge (null:
   * hidden); null: the menu has none.
   */
  skins: { value: string; label: string; dropdown: boolean; choices: string[]; rows: { name: string; label: string; icons: ('edit' | 'trash')[] }[]; bake: string; bakeDisabled: boolean; badge: string | null } | null;
}

export interface PickState {
  hovered: number | null;
  selected: number | null;
  selection: number[];
  rect: SelectBox | null;
  menu: MenuState | null;
  loop: boolean;
}

export interface SelectBox {
  left: number;
  top: number;
  width: number;
  height: number;
}

// The page side of a model format (SPEC-VIEWER section 6.1 to 6.3).
// Core and the features name a model and an instance only through these
// types. A format module (src/formats/<id>) gives the classes behind them.

import type ModelViewer from '@renderer/viewer/viewer';
import type Scene from '@renderer/viewer/scene';
import type Texture from '@renderer/viewer/texture';
import type { Vec3 } from '../../shared/records';
import type { Rgb } from './render/gl';
import type { FeatureContext } from './context';

export type FormatId = string;
export type Quat = [number, number, number, number];
/** A scene of the renderer library: the units' one, or the sky's. */
export type RenderScene = Scene;
/** One model or texture reader of the renderer library. */
export type RendererHandler = Parameters<ModelViewer['addHandler']>[0];

/** One animation of an instance. `length` in ms. */
export interface SequenceInfo {
  readonly name: string;
  readonly length: number;
}

export interface ViewerModel {
  readonly format: FormatId;
  /** Culling sphere. */
  readonly bounds: { readonly r: number };
  /** Rest pose box, model space. */
  readonly vertexMin: ArrayLike<number>;
  readonly vertexMax: ArrayLike<number>;
  /** The model has geometry to draw. */
  readonly loaded: boolean;
  /** Parts the renderer does not draw (R-VIEW-81). */
  readonly undrawn: readonly string[];
  /** The texture references the model names. */
  readonly textures: readonly string[];
  addInstance(): ViewerInstance;
}

export interface ViewerInstance {
  readonly model: ViewerModel;
  readonly sequences: readonly SequenceInfo[];
  setLocation(at: Vec3): void;
  setRotation(turn: Quat): void;
  setScale(by: Vec3): void;
  /** -1: none. */
  setSequence(index: number): void;
  /** true: repeat. false: play to the end and hold. */
  setLoop(loop: boolean): void;
  timeScale: number;
  /** The playhead passed the end in the last step. */
  readonly sequenceEnded: boolean;
  /** The animation set, -1 for none, and its playhead in ms. */
  readonly sequence: number;
  readonly frame: number;
  /** What the renderer holds: place, turn and scale. */
  readonly location: ArrayLike<number>;
  readonly rotation: ArrayLike<number>;
  readonly scaling: ArrayLike<number>;
  show(): void;
  hide(): void;
  /** Not hidden. */
  readonly shown: boolean;
  attach(scene: RenderScene): void;
  detach(): void;
  /** In a scene. */
  readonly attached: boolean;
  /** Drawn in the last frame: in a scene, shown and not culled. */
  readonly drawn: boolean;
  /** Mouse-over brightness. */
  highlight: number;
  /** Draw solid parts only. */
  solidOnly: boolean;
  /** Draw alone, for the outline mask. */
  renderOpaque(): void;
  /** Flat colour, solid parts. */
  renderPick(r: number, g: number, b: number): void;
}

/** One texture of an instance that may be swapped (section 6.2). */
export interface TextureSlot {
  /** The in-model path of the texture. */
  readonly source: string;
  /** The longest side of the model's own texture, once loaded; 0 before. */
  ownSize(): number;
}

/** Optional. A missing member means the instance cannot do it (R-VIEW-6). */
export interface Capabilities {
  teamColor?: { readonly count: number; set(index: number): void };
  tint?: { set(color: Rgb | null): void };
  textureOverride?: {
    slots(): readonly TextureSlot[];
    set(slot: TextureSlot, texture: Texture | null): void;
    /** How many slots hold another texture now. */
    applied(): number;
  };
  /**
   * The triangle edges of the drawn parts as lines in one flat colour,
   * posed like the triangles. The caller sets the depth and blend state.
   * Returns how many lines it drew.
   */
  edges?: { draw(r: number, g: number, b: number): number };
}

/** A draw after the scene. Returns how many parts it drew. */
export interface PostPass {
  readonly id: string;
  enabled: boolean;
  draw(scene: RenderScene, width: number, height: number): number;
}

export type GameId = string;

/** What core reads of any record. A game's records hold more; only the game reads it. */
export interface GameRecord {
  readonly id: string;
  readonly name: string;
  /** The servable model file. */
  readonly file: string;
  /** The dataset the record was read from. */
  readonly dataset: string;
}

/** One record category of a game, as core names it. */
export interface GameCategory {
  /** The route name: "units". */
  readonly id: string;
  /** One of them, in lower case: "unit". The list row's data attribute, the drag type, the state key. */
  readonly noun: string;
}

/** What the user or a document asks of a new instance (SPEC-VIEWER 6.4). */
export interface PlacementWish {
  /** 0 to 1: chooses inside the data's ranges. */
  pick: number;
  /** Degrees. */
  rot?: number;
  /** Which of the record's model files; null or absent: the game chooses. */
  variant?: number | null;
  /** A variant the record does not have: the game chooses one (default), takes the first, or refuses. */
  otherwise?: 'random' | 'first' | 'refuse';
}

/** An animation kept outside the model file (SPEC-VIEWER 6.4); fetched as asset kind "animation". */
export interface Clip {
  readonly name: string;
  readonly reference: string;
}

/** How a record becomes an instance. Core applies it; core does not read the record's data. */
export interface Placement {
  /** Animations kept outside the model file; the instance's sequences are the file's, then these. */
  clips: readonly Clip[];
  /** Servable model file. */
  file: string;
  /** Which of the record's files; null when it has one. */
  variant: number | null;
  /** How many the user may choose from. */
  variants: number;
  /** From the record's data. */
  scale: Vec3;
  /** Over the ground. */
  height: number;
  /** Degrees. */
  rot: number;
  tint: Rgb | null;
  pick: number;
  /** Becomes the backdrop and is not placed. */
  asBackdrop: boolean;
  /** Footprint on the ground: the grid glow and the room in a row; null: a default. */
  radius: number | null;
  /** The radius a pick ray must pass within; null: from the model's bounds. */
  hitRadius: number | null;
  /** Takes a team colour, when the format can show one. */
  team: boolean;
  /** The list row's icon: null, no icon; `name` null, an empty icon box. */
  icon: { readonly name: string | null } | null;
}

/** The gallery's preview card of a record. `picture`: an icon name, or null. */
export interface PreviewCard {
  readonly name: string;
  readonly picture: string | null;
  readonly facts: readonly string[];
}

/** The page side of a game (SPEC-VIEWER 6.4). */
export interface PageGame {
  /** The preview card of a record. */
  describe(category: string, record: GameRecord): PreviewCard;
  readonly id: GameId;
  readonly categories: readonly GameCategory[];
  /** What a backdrop record is called in this game's messages: "skybox". */
  readonly backdrop: string;
  /** A record as the server sent it, checked; an error when it is not one of the category. */
  checkRecord(category: string, body: unknown): GameRecord;
  /** How a record becomes an instance. An error when the wish cannot be met (a variant it has not). */
  place(category: string, record: GameRecord, wish: PlacementWish): Placement;
  /** How a bare file becomes an instance. */
  placeFile(file: string, wish: PlacementWish): Placement;
  /** Speed of one animation of a record's instance; null record: a bare file. */
  playRate(record: GameRecord | null, sequence: SequenceInfo | undefined): number;
  /** The animation an instance starts with; -1 for none. */
  restSequence(sequences: readonly SequenceInfo[]): number;
  /** A list's name, read like a phrase, from its query (the search `q` and the filters): an "add all" landmark. */
  listName(category: string, query: Readonly<Record<string, string>>): string;
}

export interface FormatModule {
  readonly id: FormatId;
  /** ".ext", lower case. */
  readonly extensions: readonly string[];
  /** Model and texture readers. */
  readonly handlers: readonly RendererHandler[];
  /** The library's loaded resource as this format's model; null when it is not one. */
  adopt(resource: unknown): ViewerModel | null;
  /**
   * Give an instance animations kept outside its model file. `url` gives a
   * clip's route. A clip the format cannot read is left out; the result
   * names each one with the reason, and core reports them (R-VIEW-82). A
   * format without it cannot take clips: a placement with clips for it is
   * a failure (SPEC-VIEWER 6.3).
   */
  attachClips?(instance: ViewerInstance, clips: readonly Clip[], url: (reference: string) => string): Promise<readonly string[]>;
  capabilities(instance: ViewerInstance): Capabilities;
  /** Draws after the scene, made once per viewer. */
  postPasses?(viewer: ModelViewer): readonly PostPass[];
  /** What the format alone knows of an instance, for the tests. */
  inspect?(instance: ViewerInstance): Record<string, unknown>;
  /**
   * The format's own test members, made once with the page's services.
   * The tests reach them as `sc2viewer.probe(format, name, ...args)`.
   */
  probes?(context: ProbeContext): Readonly<Record<string, unknown>>;
}

/** What a format's probes may use (a part of the FeatureContext, SPEC-VIEWER 6.6). */
export type ProbeContext = Pick<FeatureContext, 'render' | 'scene'>;

// The texture service of SPEC-VIEWER section 17: what the server says of a
// texture and of an owner, and what the page asks of it. The words variant,
// recipe, skin, owner and bake are those of SPEC-HD-TEXTURES. The pipeline
// writes these shapes (scripts/hdtex/core/view.py); the server passes them on.

import type { DatasetId, GameId } from './protocol';

/** The variant id of the original: no step. */
export const ORIGINAL = 'original';
/** The Original skin: names nothing, every texture shows its original (R-HD-132). */
export const ORIGINAL_SKIN = 'original';
/** New Skin: the one unsaved skin of an owner (R-HD-137). */
export const NEW_SKIN = 'new';
/** What a list shows for a skin name. */
export const skinLabel = (name: string): string => (name === ORIGINAL_SKIN ? 'Original' : name === NEW_SKIN ? 'New Skin' : name);
/** Joins the steps of a recipe; `@` parts a step's model from its size. */
const JOIN = '+';
const AT = '@';

/** A model of the pipeline (SPEC-HD-TEXTURES 4.3). */
export interface TextureModel {
  id: string;
  title: string;
  /** What it does, in one line. */
  note: string;
}

/** How a number stands against its bound (R-VIEW-120). */
export type Band = 'ok' | 'near' | 'problem';

/** One number of a variant against its bound. A value of null has no finite number. */
export interface TextureNumber {
  limit: string;
  value: number | null;
  bound: number;
  band: Band;
}

/** One variant of a texture: one recipe at one size. */
export interface TextureVariant {
  id: string;
  /** The variant it was made from: `original`, or an id. */
  input: string;
  title: string;
  recipe: string;
  /** By plane: the model its last step ran, or null for a plane it kept. */
  models: Record<string, string | null>;
  size: number;
  /** The recipe's own size: the largest it was made at. */
  own: number;
  /** Its original changed since it was made. */
  stale: boolean;
  numbers: TextureNumber[];
  /** The limits it misses, each with its number and bound. */
  problems: { limit: string; value: number | null; bound: number }[];
  /** Why the limits it misses do not block it; empty: they do (O-HD-9). */
  accepted: string;
  /** The hash of its file: the `v` of its URL. */
  sha256: string;
}

/** What a request may ask for from one input: per model, why it is refused (empty: it is not), and per size why it cannot be reached. */
export interface TextureAsk {
  input: string;
  models: Record<string, { reason: string; sizes: Record<string, string> }>;
}

/** A request that is not done, by its recipe. */
export interface TextureRequest {
  state: 'queued' | 'upscaling' | 'encoding' | 'failed';
  /** Why it failed; empty otherwise. */
  reason: string;
  step: number;
  steps: number;
  planes: number;
}

/** What the server says of one texture (17.2). */
export interface TextureState {
  asset: string;
  kind: string;
  users: string[];
  tiles: boolean;
  /** The pipeline has read its role and size. False: `reason` and `asks` are empty; the judge route reads them. */
  judged: boolean;
  /** Why it cannot be upscaled; empty: it can. */
  reason: string;
  /** It has a colour plane: without one, every model is `fast` (R-HD-122). */
  colour: boolean;
  /** Largest first within each recipe. */
  variants: TextureVariant[];
  asks: TextureAsk[];
  /** By recipe: the requests that are not done. */
  requests: Record<string, TextureRequest>;
  /** A texture baked on its own (terrain): its variant id; null: none. */
  bake: string | null;
  /** Why that bake would be refused; empty: it would not. */
  bakeProblem: string;
  /** What the package holds of that bake, and whether it is the file the bake names. Null: nothing. */
  packaged: { variant: string | null; held: boolean } | null;
}

/** One skin of an owner. */
export interface TextureSkin {
  name: string;
  /** Asset to variant id; an asset it does not name shows its original. */
  textures: Record<string, string>;
  /** False: New Skin offered from what the owner shows, not stored yet (R-HD-137). */
  stored: boolean;
}

/** What the server says of one owner (17.2). */
export interface OwnerState {
  owner: string;
  title: string;
  layer: 'unit' | 'actor' | 'model';
  textures: string[];
  /** The owners below it, nearest first, each with its baked skin. */
  below: { owner: string; bake: string | null }[];
  skins: TextureSkin[];
  /** Per asset: what the owner shows now: its bake, else the nearest bake below, else the original. */
  shows: Record<string, string>;
  bake: { skin: string; textures: Record<string, string> } | null;
  /** The package holds the bake as it is. */
  held: boolean;
}

/** What holds for every texture of a dataset. */
export interface TexturesHead {
  sizes: number[];
  models: TextureModel[];
  limits: { limit: string; info: string }[];
}

/** GET /api/<game>/textures. */
export interface TexturesBody extends TexturesHead {
  textures: TextureState[];
  /** The assets asked for that are no texture of the dataset. */
  unknown: string[];
}

/** What a skin change or a bake answers: the owner's state. */
export interface OwnerBody extends TexturesHead {
  owner: OwnerState;
}

/** GET /api/<game>/textures/owner. Null: the index holds no such owner with textures. That is an answer, not an error. */
export interface OwnerLookup extends TexturesHead {
  owner: OwnerState | null;
}

/** POST /api/<game>/textures/judge: the textures whose role and size the pipeline is to read. */
export interface TextureJudgeAsk {
  assets: string[];
}

/** POST /api/<game>/textures/request: one variant, from an input, by a model, at a size. */
export interface TextureRequestAsk {
  asset: string;
  input: string;
  model: string;
  size: number;
}

/** POST /api/<game>/textures/skin: one change of SPEC-HD-TEXTURES 4.8. */
export type SkinAsk =
  | { owner: string; action: 'copy'; name: string; from: string }
  | { owner: string; action: 'rename'; name: string; new: string }
  | { owner: string; action: 'delete'; name: string }
  | { owner: string; action: 'set'; name: string; asset: string; variant: string | null }
  | { owner: string; action: 'upscale'; name: string; from: string; model: string; size: number };

/** What a skin upscale did: the variants it requested, and the textures that keep what the source shows, with why. */
export interface SkinUpscaled {
  requests: Record<string, string>;
  kept: Record<string, string>;
  /** The requests that did not start. */
  failed: { asset: string; variant: string; error: string }[];
}

/** POST /api/<game>/textures/skin: the owner, and for an upscale what it did. */
export interface SkinBody extends OwnerBody {
  upscaled: SkinUpscaled | null;
}

/** POST /api/<game>/textures/bake: an owner's skin, or a texture's variant. */
export type BakeAsk = { owner: string; skin: string } | { asset: string; variant: string };

/** POST /api/<game>/textures/unbake. */
export type UnbakeAsk = { owner: string } | { asset: string };

/** The reply of bake and unbake: the owner's state, or the texture's. */
export type BakeBody = OwnerBody | TexturesBody;

/** A variant id: the input's steps, then the model at the size. */
export const variantId = (input: string, model: string, size: number): string => `${input === ORIGINAL ? '' : input + JOIN}${model}${AT}${size}`;

/** The recipe of a variant: the id without its last size. */
export function recipeOf(variant: string): string {
  const at = variant.lastIndexOf(AT);
  return at < 0 ? variant : variant.slice(0, at);
}

/** A variant that may be shown or baked (R-HD-90, R-HD-102). */
export const isUsable = (variant: TextureVariant): boolean => !variant.stale && (variant.problems.length === 0 || Boolean(variant.accepted));

/** The worst band of a variant's numbers. */
export function bandOf(variant: TextureVariant): Band {
  if (variant.numbers.some((number) => number.band === 'problem')) return 'problem';
  return variant.numbers.some((number) => number.band === 'near') ? 'near' : 'ok';
}

/** The models a request from `input` may use, and the sizes each reaches. Empty: none (not judged, or no such input). */
export const asksFrom = (state: TextureState, input: string): TextureAsk['models'] => state.asks.find((ask) => ask.input === input)?.models ?? {};

/** The routes of the texture service, as the page builds them. */
export const textureRoutes = {
  states: (game: GameId, dataset: DatasetId, assets: readonly string[]): string => {
    const query = new URLSearchParams({ dataset });
    for (const asset of assets) query.append('asset', asset);
    return `/api/${game}/textures?${query}`;
  },
  owner: (game: GameId, dataset: DatasetId, owner: string): string => `/api/${game}/textures/owner?${new URLSearchParams({ dataset, owner })}`,
  judge: (game: GameId, dataset: DatasetId): string => `/api/${game}/textures/judge?${new URLSearchParams({ dataset })}`,
  request: (game: GameId, dataset: DatasetId): string => `/api/${game}/textures/request?${new URLSearchParams({ dataset })}`,
  skin: (game: GameId, dataset: DatasetId): string => `/api/${game}/textures/skin?${new URLSearchParams({ dataset })}`,
  bake: (game: GameId, dataset: DatasetId): string => `/api/${game}/textures/bake?${new URLSearchParams({ dataset })}`,
  unbake: (game: GameId, dataset: DatasetId): string => `/api/${game}/textures/unbake?${new URLSearchParams({ dataset })}`,
  file: (game: GameId, dataset: DatasetId, asset: string, variant: string, version: string): string => `/api/${game}/textures/file?${new URLSearchParams({ dataset, asset, variant, v: version })}`,
};

// The texture service of SPEC-VIEWER section 17: what the server says of a
// texture and of an owner, and what the page asks of it. The words variant,
// recipe, skin, owner and bake are those of SPEC-HD-TEXTURES. The pipeline
// writes these shapes (scripts/hdtex/core/view.py); the server passes them on.

import type { DatasetId, GameId } from './protocol';

/** The variant id of the original: no step. */
export const ORIGINAL = 'original';
/** The Original skin: names nothing, every texture shows its original (R-HD-132). */
export const ORIGINAL_SKIN = 'original';
/** What a list shows for a skin name. */
export const skinLabel = (name: string): string => (name === ORIGINAL_SKIN ? 'Original' : name);
/** A skin name (scripts/hdtex/core/skins.py check_name; both are tested against hdtex.core's skin_names.json). */
const SKIN_NAME = /^(?=.{1,40}$)[A-Za-z0-9_-]+(?: [A-Za-z0-9_-]+)*$/;
/** Why `name` is no skin name; empty: it is one. */
export function skinNameRefusal(name: string): string {
  if (!SKIN_NAME.test(name)) return 'a name is 1 to 40 letters, digits, - or _, with one space between words';
  if (name.toLowerCase() === ORIGINAL_SKIN) return 'Original is the skin that names nothing';
  return '';
}
/** Whether an owner has a skin: Original always. */
export const hasSkin = (owner: { skins: readonly { name: string }[] }, skin: string): boolean => skin === ORIGINAL_SKIN || owner.skins.some((one) => one.name === skin);
/** What a skin of an owner names for a texture now; a texture it does not name shows its original (R-HD-131). The skin must exist (`hasSkin`). */
export function namedIn(owner: { owner: string; skins: readonly { name: string; textures: Record<string, string> }[] }, skin: string, asset: string): string {
  if (skin === ORIGINAL_SKIN) return ORIGINAL;
  const found = owner.skins.find((one) => one.name === skin);
  if (!found) throw new Error(`${owner.owner} has no skin "${skin}"`);
  return found.textures[asset] ?? ORIGINAL;
}
/** Where Save to Skin… sets the picks (R-VIEW-133): a skin made by the save (its name comes from the pipeline), or a skin the owner has. */
export type SaveInto = { kind: 'new' } | { kind: 'existing'; skin: string };
/** The target Save to Skin… offers first: the skin the instance shows when the owner has it and it is not Original; else a new skin. */
export const firstSaveInto = (owner: { skins: readonly { name: string }[] }, shown: string | null): SaveInto =>
  shown !== null && shown !== ORIGINAL_SKIN && hasSkin(owner, shown) ? { kind: 'existing', skin: shown } : { kind: 'new' };
/** What a save target names for a texture before the save. A new skin is made from Original, so it names the original. */
export const namedInto = (owner: { owner: string; skins: readonly { name: string; textures: Record<string, string> }[] }, into: SaveInto, asset: string): string =>
  into.kind === 'new' ? ORIGINAL : namedIn(owner, into.skin, asset);
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

/** How a number stands against its bound (R-VIEW-120). `none`: no limit binds it: the variant is user-made (R-PC-80). */
export type Band = 'ok' | 'near' | 'problem' | 'none';

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
  /** It must be made again: its original changed since. */
  stale: boolean;
  /** Why it is stale, in words; empty: it is not. */
  staleWhy: string;
  /** Its edges were made for the other rule (tiles or not). It is shown; a request makes it again. */
  edgesOff: boolean;
  numbers: TextureNumber[];
  /** The limits it misses, each with its number and bound. */
  problems: { limit: string; value: number | null; bound: number }[];
  /** Why the limits it misses do not block it; empty: they do (O-HD-9). */
  accepted: string;
  /** A person made it, by the transfer of an edit: its numbers have the band `none` and make no problem (R-PC-80). */
  edited: boolean;
  /** The variant its numbers compare with: the nearest user-made one among its inputs; empty: the original (R-PC-83). */
  reference: string;
  /** The hash of its file: the `v` of its URL. */
  sha256: string;
}

/** What one factor of the input's side gives: the side, at most the head's maxSide, and why it cannot be asked for (empty: it can). */
export interface FactorAsk {
  size: number;
  reason: string;
}

/** What a request may ask for from one input: per model, why it is refused (empty: it is not), and per factor what it gives. */
export interface TextureAsk {
  input: string;
  models: Record<string, { reason: string; factors: Record<string, FactorAsk> }>;
}

/** A request that is not done, by its recipe. */
export interface TextureRequest {
  state: 'queued' | 'upscaling' | 'encoding' | 'failed';
  /** Why it failed; empty otherwise. */
  reason: string;
  step: number;
  steps: number;
  planes: number;
  /** The planes of this step whose job is done. */
  done: number;
  /** The id it was asked as: what Ask Again asks for (R-VIEW-146). Empty: the transfer of an edit, which no request makes again. */
  variant: string;
  /** Its start, in seconds since 1970; null: not known. */
  since: number | null;
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
  /** The name the pipeline gives the next skin made without one (scripts/hdtex/core/skins.py `next_new`). */
  next: string;
  /** Per asset: what the owner shows now: its bake, else the nearest bake below, else the original. */
  shows: Record<string, string>;
  bake: { skin: string; textures: Record<string, string> } | null;
  /** The package holds the bake as it is. */
  held: boolean;
}

/** What holds for every texture of a dataset. */
export interface TexturesHead {
  /** How many times its input's side a request may ask for (R-HD-123). */
  factors: number[];
  /** The largest side a request may ask for: the setting TEXTURE_MAX_SIDE. */
  maxSide: number;
  models: TextureModel[];
  limits: { limit: string; info: string }[];
  /** Why the game bakes nothing (R-VIEW-151); empty: it bakes. */
  bake: string;
  /** The hash of the code that wrote its states (scripts/hdtex/core/view.py `code`). At its start the server indexes a head of other code again. */
  code: string;
}

/** A head before the first answer: nothing offered, nothing refused. */
export const EMPTY_HEAD: TexturesHead = { factors: [], maxSide: 0, models: [], limits: [], bake: '', code: '' };

/** The head of an answer, without its body. */
export const headPart = (body: TexturesHead): TexturesHead => ({ factors: body.factors, maxSide: body.maxSide, models: body.models, limits: body.limits, bake: body.bake, code: body.code });

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

/** POST /api/<game>/textures/request: one variant, from an input, by a model, at a factor of the input's side; or at the size of a known variant id (Ask Again). One of the two. */
export interface TextureRequestAsk {
  asset: string;
  input: string;
  model: string;
  factor?: number;
  size?: number;
}

/** POST /api/<game>/textures/remove: one variant of an asset (R-HD-146). */
export interface TextureRemoveAsk {
  asset: string;
  variant: string;
}

/** POST /api/<game>/textures/skin: one change of SPEC-HD-TEXTURES 4.8. */
export type SkinAsk =
  /** `name` null: the next New Skin N (R-HD-137). */
  | { owner: string; action: 'copy'; name: string | null; from: string }
  | { owner: string; action: 'rename'; name: string; new: string }
  | { owner: string; action: 'delete'; name: string }
  | { owner: string; action: 'set'; name: string; asset: string; variant: string | null }
  /** `name` null: the next New Skin N. */
  | { owner: string; action: 'upscale'; name: string | null; from: string; model: string; factor: number };

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
  /** The skin a copy or an upscale made; null for the other changes. */
  made: string | null;
}

/** POST /api/<game>/textures/bake: an owner's skin, or a texture's variant. */
export type BakeAsk = { owner: string; skin: string } | { asset: string; variant: string };

/** POST /api/<game>/textures/unbake. */
export type UnbakeAsk = { owner: string } | { asset: string };

/** The reply of bake and unbake: the owner's state, or the texture's. */
export type BakeBody = OwnerBody | TexturesBody;

/** A variant id: the input's steps, then the model at the size. */
export const variantId = (input: string, model: string, size: number): string => `${input === ORIGINAL ? '' : input + JOIN}${model}${AT}${size}`;

/** The input, model and size a variant id was asked as; null: its last step is no model and size (an edit). */
export function askOf(asset: string, variant: string): TextureRequestAsk | null {
  const at = variant.lastIndexOf(AT);
  const join = variant.lastIndexOf(JOIN);
  const size = Number(variant.slice(at + 1));
  if (at < 0 || at < join || !Number.isInteger(size) || size <= 0) return null;
  return { asset, input: join < 0 ? ORIGINAL : variant.slice(0, join), model: variant.slice(join + 1, at), size };
}

/** The recipe of a variant: the id without its last size. */
export function recipeOf(variant: string): string {
  const at = variant.lastIndexOf(AT);
  return at < 0 ? variant : variant.slice(0, at);
}

/** The order the page shows variants in: by recipe name, then by size, smallest first (SPEC-VIEWER 17.6.1). */
export function shownOrder<T extends Pick<TextureVariant, 'recipe' | 'size'>>(variants: readonly T[]): T[] {
  return [...variants].sort((a, b) => a.recipe.localeCompare(b.recipe) || a.size - b.size);
}

/** A variant that may be shown or baked (R-HD-90, R-HD-102). */
export const isUsable = (variant: TextureVariant): boolean => !variant.stale && (variant.problems.length === 0 || Boolean(variant.accepted));

/** The worst band of a variant's numbers. A user-made variant has none. */
export function bandOf(variant: TextureVariant): Band {
  if (variant.edited) return 'none';
  if (variant.numbers.some((number) => number.band === 'problem')) return 'problem';
  return variant.numbers.some((number) => number.band === 'near') ? 'near' : 'ok';
}

/** The models a request from `input` may use, and what each factor gives. Empty: none (not judged, or no such input). */
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
  remove: (game: GameId, dataset: DatasetId): string => `/api/${game}/textures/remove?${new URLSearchParams({ dataset })}`,
  log: (game: GameId, dataset: DatasetId, asset: string, recipe: string): string => `/api/${game}/textures/log?${new URLSearchParams({ dataset, asset, recipe })}`,
  skin: (game: GameId, dataset: DatasetId): string => `/api/${game}/textures/skin?${new URLSearchParams({ dataset })}`,
  bake: (game: GameId, dataset: DatasetId): string => `/api/${game}/textures/bake?${new URLSearchParams({ dataset })}`,
  unbake: (game: GameId, dataset: DatasetId): string => `/api/${game}/textures/unbake?${new URLSearchParams({ dataset })}`,
  file: (game: GameId, dataset: DatasetId, asset: string, variant: string, version: string): string => `/api/${game}/textures/file?${new URLSearchParams({ dataset, asset, variant, v: version })}`,
};

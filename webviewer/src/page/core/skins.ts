// The skins of the instances (SPEC-VIEWER 17.4), over a game's texture
// service. The scene applies an item's skin when it adds or swaps the
// instance; the instance menu (features/pick) offers the choice; the skin
// editor and the upscale dialog (features/skins) change skins through here.
//
// States and owners are asked once per dataset and kept until textures
// change for that dataset (event "textures-changed", R-VIEW-109): then every
// item of it is applied again. A change made here emits that event.
// While Ctrl+. is held, the items held show Original (`peek`, R-VIEW-148).

import { EMPTY_HEAD, hasSkin, headPart, isUsable, namedIn, ORIGINAL, ORIGINAL_SKIN, recipeOf, skinLabel, textureRoutes, type OwnerLookup, type OwnerState, type TexturesBody, type TextureState } from '../../shared/textures';
import type { EventBus, ViewerEvents } from './bus';
import type { GameRegistry, StatusService } from './context';
import type { Host } from './host';
import { Texture } from './library';
import type { TextureSlot } from './plugin';
import type { Item } from './types';

/** What features/skins adds: the windows that change a skin. */
export interface SkinTools {
  /** Show this skin on the item, then open the texture window on it. */
  edit(item: Item, skin: string): void;
  /** Make the next New Skin N from the item's skin, show it, then open the texture window on it (R-HD-137). */
  create(item: Item): void;
  /** Open the upscale dialog on the item's whole owner. */
  upscale(item: Item): void;
  /** Ask, then delete a skin of the item's owner (R-VIEW-126). False: cancelled. */
  remove(item: Item, skin: string): Promise<boolean>;
}

export interface Skins {
  /** Whether a game offers a texture service (R-VIEW-100). */
  offered(game: string): boolean;
  /** The states of these textures in a dataset of a game. */
  states(game: string, dataset: string, assets: readonly string[]): Promise<TexturesBody>;
  /** Have the pipeline read what a request of these textures needs (17.2); their states. */
  judge(game: string, dataset: string, assets: readonly string[]): Promise<TexturesBody>;
  /** The texture owner of an item, as its game names it; null: none. */
  ownerOf(item: Item): string | null;
  /** The item's owner as last read; null: it has none with textures, or it is not read yet. */
  owner(item: Item): OwnerState | null;
  /** Read an owner; null when the service holds no such owner. */
  readOwner(game: string, dataset: string, owner: string): Promise<OwnerState | null>;
  /** The skin names an item may choose: `original`, then the owner's skins; empty: it has no skin controls. */
  choices(item: Item): string[];
  /** Show an item's skin on its instance, and measure what it shows. */
  apply(item: Item): Promise<void>;
  /** Set an item's skin, and apply it. Another instance of the owner does not change. */
  set(item: Item, skin: string): Promise<void>;
  /** Show Original on these items while `on`, their own skin again after; their skin choice stays (R-VIEW-148). */
  peek(items: readonly Item[], on: boolean): Promise<void>;
  /** The skin an item shows now: Original while peeked, else its own. */
  shownSkin(item: Item): string;
  /** Bake the item's skin for its owner; `original` unbakes (R-VIEW-122). A refusal is thrown with its reason. */
  bake(item: Item): Promise<void>;
  /** Why the item's game bakes nothing (R-VIEW-151); empty: it bakes, or its owner is not read yet. */
  bakeRefusal(item: Item): string;
  /** POST a change to a texture route; the textures of that dataset are read again. A refusal is thrown with its reason. */
  change<T>(game: string, dataset: string, route: string, body: unknown): Promise<T>;
  /** Whether the item's skin waits on variants still being made: their states are read again each second. */
  following(item: Item): boolean;
  /** The URL of a variant's file, when it is made, not stale and not blocked; null otherwise. */
  variantUrl(game: string, dataset: string, state: TextureState | undefined, variant: string): string | null;
  tools(): SkinTools | null;
  setTools(tools: SkinTools): void;
}

export interface SkinDeps {
  readonly host: Pick<Host, 'viewer'>;
  readonly games: GameRegistry;
  readonly status: StatusService;
  readonly events: EventBus<ViewerEvents>;
  /** The scene's items (the scene is made after this service). */
  readonly items: () => readonly Item[];
}

const keyOf = (game: string, dataset: string): string => `${game}\n${dataset}`;
/** How often the states of variants still being made are read again (as the texture window, 17.3). */
const REQUEST_POLL_MS = 1000;

async function answer<T>(response: Response, what: string): Promise<T> {
  const found: unknown = await response.json();
  if (!response.ok) throw new Error(`${what}: ${String(Reflect.get(Object(found), 'error') ?? response.status)}`);
  return found as T;
}

/** What a failed quality check means for the eye, by limit (SPEC-HD-TEXTURES limits). */
const CHECK_MEANS: Record<string, string> = {
  seam: 'its edges would show as lines where it repeats',
  encode_psnr: 'it would look blocky after compression',
  correlation: 'it does not match the original picture',
  coarse_rmse: 'from far away its brightness or colour would be wrong',
};

/** Why a named variant cannot be shown now, in plain words: stale, a failed check not accepted, or never made. */
function unshowable(state: TextureState | undefined, variant: string): string {
  const found = state?.variants.find((one) => one.id === variant);
  if (!state) return 'the texture service does not know this texture';
  if (!found) return 'its upscaled version was never made';
  if (found.stale) return `its upscaled version is out of date: ${found.staleWhy || 'the original changed'}; upscale it again`;
  const checks = found.problems.map((one) => `${one.limit} check (${one.value === null ? 'no number' : Number(one.value.toFixed(2))}, limit ${Number(one.bound.toFixed(2))})`).join(', ');
  const means = found.problems.map((one) => CHECK_MEANS[one.limit]).filter(Boolean).join('; ');
  return `its upscale failed the ${checks}${means ? `: ${means}` : ''}`;
}

/** The file name of an asset path, for a message. */
const fileOf = (asset: string): string => asset.split(/[\\/]/).at(-1) ?? asset;

export function createSkins({ host, games, status, events, items }: SkinDeps): Skins {
  /** By game and dataset: the states asked so far, by asset (null: no texture), and the owners (null: none). */
  const known = new Map<string, { head: Omit<TexturesBody, 'textures' | 'unknown'>; states: Map<string, TextureState | null>; owners: Map<string, OwnerState | null> }>();
  const ownerOfItem = new WeakMap<Item, OwnerState | null>();
  const polling = new WeakMap<Item, ReturnType<typeof setTimeout>>();
  /** The items that show Original while Ctrl+. is held (R-VIEW-148). */
  const peeking = new WeakSet<Item>();
  const shownSkin = (item: Item): string => (peeking.has(item) ? ORIGINAL_SKIN : item.skin);
  let tools: SkinTools | null = null;

  const entryOf = (game: string, dataset: string) => {
    const key = keyOf(game, dataset);
    const found = known.get(key) ?? { head: EMPTY_HEAD, states: new Map(), owners: new Map() };
    known.set(key, found);
    return found;
  };

  const offered = (game: string): boolean => games.gamesInfo().some((info) => info.id === game && info.textures) && games.partsOf(game).textureAsset !== undefined;
  const ownerOf = (item: Item): string | null => games.partsOf(item.game).textureOwner?.(item) ?? null;

  async function states(game: string, dataset: string, assets: readonly string[]): Promise<TexturesBody> {
    const entry = entryOf(game, dataset);
    const missing = [...new Set(assets)].filter((asset) => !entry.states.has(asset));
    if (missing.length) {
      const body = await answer<TexturesBody>(await fetch(textureRoutes.states(game, dataset, missing)), `the texture states of ${dataset}`);
      entry.head = headPart(body);
      for (const asset of missing) entry.states.set(asset, null);
      for (const state of body.textures) entry.states.set(state.asset, state);
    }
    const textures = assets.map((asset) => entry.states.get(asset)).filter((state): state is TextureState => Boolean(state));
    return { ...entry.head, textures, unknown: assets.filter((asset) => !entry.states.get(asset)) };
  }

  async function judge(game: string, dataset: string, assets: readonly string[]): Promise<TexturesBody> {
    const entry = entryOf(game, dataset);
    // Read them again first: the texture window or another page may have had them judged. A judge runs the pipeline over the dataset.
    for (const asset of assets) entry.states.delete(asset);
    await states(game, dataset, assets);
    // An asset the dataset does not list stays unknown: the judge route would refuse it.
    const unread = [...new Set(assets)].filter((asset) => entry.states.get(asset)?.judged === false);
    if (unread.length) {
      const response = await fetch(textureRoutes.judge(game, dataset), { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ assets: unread }) });
      const body = await answer<TexturesBody>(response, `what can be made of the textures of ${dataset}`);
      for (const state of body.textures) entry.states.set(state.asset, state);
    }
    return states(game, dataset, assets);
  }

  async function readOwner(game: string, dataset: string, owner: string): Promise<OwnerState | null> {
    const entry = entryOf(game, dataset);
    if (!entry.owners.has(owner)) {
      const response = await fetch(textureRoutes.owner(game, dataset, owner));
      const body = await answer<OwnerLookup>(response, `the owner ${owner} in ${dataset}`);
      entry.head = headPart(body);
      entry.owners.set(owner, body.owner);
    }
    return entry.owners.get(owner) ?? null;
  }

  function variantUrl(game: string, dataset: string, state: TextureState | undefined, variant: string): string | null {
    if (!state || variant === ORIGINAL) return null;
    const found = state.variants.find((one) => one.id === variant);
    return found && isUsable(found) ? textureRoutes.file(game, dataset, state.asset, found.id, found.sha256) : null;
  }

  /** Whether a variant is asked for and not done: its recipe has a request that has not failed. */
  const isOpen = (state: TextureState, variant: string): boolean => variant !== ORIGINAL && !state.variants.some((one) => one.id === variant) && (state.requests[recipeOf(variant)]?.state ?? 'failed') !== 'failed';

  /** While an item's skin names variants still being made, their states are read again each second and the skin applied again (17.4, as the window does, 17.3). */
  function follow(item: Item, assets: readonly string[]): void {
    if (polling.has(item)) return;
    polling.set(
      item,
      setTimeout(() => {
        polling.delete(item);
        if (!items().includes(item)) return;
        const entry = entryOf(item.game, item.dataset);
        for (const asset of assets) entry.states.delete(asset);
        apply(item).catch(status.reportFailure);
      }, REQUEST_POLL_MS),
    );
  }

  /** The pending count is up for all of it: the view is idle once every skin is shown. A failure goes to the caller. */
  async function apply(item: Item): Promise<void> {
    status.pending++;
    try {
      await applyNow(item);
    } finally {
      status.pending--;
    }
  }

  async function applyNow(item: Item): Promise<void> {
    const { instance } = item;
    const override = item.capabilities.textureOverride;
    if (!override) {
      item.largestTexture = 0;
      item.unshown = [];
      item.missingSkin = false;
      ownerOfItem.delete(item);
      return;
    }
    const slots = override.slots();
    const assetOf = games.partsOf(item.game).textureAsset;
    const name = ownerOf(item);
    const urls = new Map<TextureSlot, string>();
    /** The named variants that cannot be shown: their slots keep the model's own texture; the others show theirs. */
    const unshown: { key: string; asset: string; why: string }[] = [];
    let owner: OwnerState | null = null;
    /** The item names a skin its owner does not have: no slot is overridden, and it is said (SPEC-VIEWER 17.4). */
    let missing = false;
    if (assetOf && name && offered(item.game) && slots.length) {
      owner = await readOwner(item.game, item.dataset, name);
      missing = owner !== null && !hasSkin(owner, shownSkin(item));
      if (owner && !missing) {
        const body = await states(item.game, item.dataset, slots.map((slot) => assetOf(slot.source)));
        const byAsset = new Map(body.textures.map((state) => [state.asset, state]));
        const waiting = new Set<string>();
        for (const slot of slots) {
          const asset = assetOf(slot.source);
          const state = byAsset.get(asset);
          const named = namedIn(owner, shownSkin(item), asset);
          if (named === ORIGINAL) continue;
          const own = variantUrl(item.game, item.dataset, state, named);
          if (own !== null) urls.set(slot, own);
          // Still being made: the model's own texture until it is, read again each second (17.4).
          else if (state && isOpen(state, named)) waiting.add(asset);
          else if (!unshown.some((one) => one.asset === asset)) {
            const why = unshowable(state, named);
            unshown.push({ key: `${asset}: ${named}: ${why}`, asset, why });
          }
        }
        if (waiting.size) follow(item, [...waiting]);
      }
    }
    // Swapped while the states came: leave the new instance alone.
    if (item.instance !== instance) return;
    ownerOfItem.set(item, owner);
    // Said once, when it becomes so; it stays in item.missingSkin while it is.
    if (missing && !item.missingSkin && owner) status.setStatus(`${owner.title}: skin "${item.skin}" does not exist in ${item.dataset}; it shows its own textures until another skin is chosen.`, { failure: true });
    item.missingSkin = missing;
    // Each texture that cannot be shown is said once, when it becomes so; it stays in item.unshown while it is.
    const said = new Set(item.unshown);
    item.unshown = [...unshown].map((one) => one.key);
    for (const one of unshown) {
      if (!said.has(one.key)) status.setStatus(`${owner?.title ?? ''}, ${skinLabel(item.skin)}: ${fileOf(one.asset)} keeps its original texture. ${one.why[0]?.toUpperCase() ?? ''}${one.why.slice(1)}.`, { failure: true });
    }
    let largest = 0;
    for (const slot of slots) {
      const url = urls.get(slot);
      let shown: Texture | null = null;
      if (url !== undefined) {
        const texture = await host.viewer.load(slot.source, () => url);
        if (!(texture instanceof Texture)) throw new Error(`cannot load the texture of skin "${item.skin}" for ${slot.source}: ${url}`);
        shown = texture;
      }
      if (item.instance !== instance) return;
      override.set(slot, shown);
      if (shown) largest = Math.max(largest, shown.width, shown.height);
    }
    // The model's own textures, once they are in.
    await host.viewer.whenAllLoaded();
    for (const slot of slots) if (!urls.has(slot)) largest = Math.max(largest, slot.ownSize());
    if (item.instance === instance) item.largestTexture = largest;
  }

  function choices(item: Item): string[] {
    const owner = ownerOfItem.get(item);
    if (!owner) return [];
    // Original, then the skins the owner holds, as the pipeline sorts them.
    return [ORIGINAL_SKIN, ...owner.skins.map((skin) => skin.name)];
  }

  /**
   * A skin the owner does not have is refused before anything changes. A named variant that cannot be shown is no
   * refusal: its slot shows the model's own texture (item.unshown). A file that does not load is thrown after the
   * choice is made: the item is on the chosen skin and the failure is said.
   */
  async function set(item: Item, skin: string): Promise<void> {
    const id = ownerOf(item);
    const owner = id ? await readOwner(item.game, item.dataset, id) : null;
    if (!owner) throw new Error('this instance has no texture owner');
    if (!hasSkin(owner, skin)) throw new Error(`${owner.owner} has no skin "${skin}"`);
    item.skin = skin;
    events.emit('scene-edited', { what: 'skin' });
    events.emit('skin-set', { item });
    await apply(item);
  }

  /** No scene-edited event: the hold changes no choice. Items without skins are left alone. */
  async function peek(chosen: readonly Item[], on: boolean): Promise<void> {
    // On: those that show another skin. Off: every one held, whatever its skin is now.
    const changed = chosen.filter((item) => (on ? !peeking.has(item) && item.skin !== ORIGINAL_SKIN && Boolean(ownerOfItem.get(item)) : peeking.has(item)));
    for (const item of changed) {
      if (on) peeking.add(item);
      else peeking.delete(item);
    }
    await Promise.all(changed.map((item) => apply(item)));
  }

  async function change<T>(game: string, dataset: string, route: string, body: unknown): Promise<T> {
    const response = await fetch(route, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
    const found = await answer<T>(response, 'the texture service refused');
    events.emit('textures-changed', { game, dataset });
    return found;
  }

  /** Why the item's game bakes nothing, as its dataset's head said with its owner (R-VIEW-151); empty: it bakes. */
  const bakeRefusal = (item: Item): string => known.get(keyOf(item.game, item.dataset))?.head.bake ?? '';

  async function bake(item: Item): Promise<void> {
    const owner = ownerOf(item);
    if (!owner) throw new Error('this instance has no texture owner');
    const refused = bakeRefusal(item);
    if (refused) throw new Error(refused);
    if (item.skin === ORIGINAL_SKIN) await change(item.game, item.dataset, textureRoutes.unbake(item.game, item.dataset), { owner });
    else await change(item.game, item.dataset, textureRoutes.bake(item.game, item.dataset), { owner, skin: item.skin });
  }

  events.on('textures-changed', ({ game, dataset }) => {
    known.delete(keyOf(game, dataset));
    for (const item of items()) if (item.game === game && item.dataset === dataset) apply(item).catch(status.reportFailure);
  });

  return { offered, states, judge, ownerOf, owner: (item) => ownerOfItem.get(item) ?? null, readOwner, choices, apply, set, peek, shownSkin, bake, bakeRefusal, change, following: (item) => polling.has(item), variantUrl, tools: () => tools, setTools: (made) => (tools = made) };
}

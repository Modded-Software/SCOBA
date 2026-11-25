// The page of the texture window (SPEC-VIEWER 17.3), in its frame. The
// window hands it the textures of one thing, decoded (window.hdtex.show).
// For a game with a texture service it reads their states and shows the
// tiles of the chosen texture, the same as the skin editor's (core/tiles.ts,
// R-VIEW-132). A click on a tile shows it beside the original and picks it;
// Ctrl+click adds a tile to compare (R-VIEW-130). The picks are kept per
// texture; Save to Skin… hands them to the main page, which asks first
// (R-VIEW-133). Its Upscale Texture tile asks the window to open the dialog
// of the main page. src/tools/build.ts bundles it into public/vendor/texview.js.

import { decodeDdsBytes, fetchTexture, type DecodedTexture } from '../core/ddsdecode';
import { inGameOf, textureTiles, type TileState } from '../core/tiles';
import type { PageOwner } from '../core/texturewindow';
import { ORIGINAL, textureRoutes, type TextureJudgeAsk, type TexturesBody, type TexturesHead, type TextureState, type TextureVariant } from '../../shared/textures';
import { detailsOf } from './cards';
import { createImageView, type Side } from './imageview';
import { draftBar } from './draft';
import { ALL, chips, passes, type Filter, type FilterPage } from './filter';

/** One texture the window hands over. `asset`: the pipeline's name of it; null for a game without a texture service. */
export type HandedTexture = DecodedTexture & { asset: string | null; facts?: [string, string][] };

/** One pick: a variant for a texture. */
interface TexturePick {
  asset: string;
  variant: string;
}

export interface ShowRequest {
  user: string;
  game: string;
  dataset: string;
  /** The game offers a texture service. */
  service: boolean;
  /** The texture owner of the thing; null: none (a ground texture, a game without the service). */
  owner: PageOwner | null;
  textures: HandedTexture[];
  failed: string[];
  /** Called when a texture's variants or bake changed: the view applies the skins again (R-VIEW-109). */
  changed(): void;
  /** Open the upscale dialog on one texture (17.5); absent: the window offers none. */
  upscale?(asset: string): void;
  /** Save the picks to a skin of the owner; the main page asks first (R-VIEW-133). The target, or null: not saved. Absent: no owner. */
  save?(picks: TexturePick[]): Promise<string | null>;
}

interface Entry {
  id: string;
  asset: string | null;
  texture: string;
  plane: 'color' | 'alpha';
  format: string;
  size: [number, number];
  image: string;
  facts: [string, string][];
}

const POLL_MS = 1000;
const $ = (id: string): HTMLElement => {
  const found = document.getElementById(id);
  if (!found) throw new Error(`the texture viewer page has no #${id}`);
  return found;
};
const element = <K extends keyof HTMLElementTagNameMap>(tag: K, className = '', text?: string): HTMLElementTagNameMap[K] => {
  const made = document.createElement(tag);
  if (className) made.className = className;
  if (text !== undefined) made.textContent = text;
  return made;
};
const embed = new URLSearchParams(location.search).get('embed') === '1';
document.body.classList.toggle('embed', embed);
const image = createImageView($('view'), $('before'), $('tag-before'), $('status'));
const list = $('list');
const search = $('search') as HTMLInputElement;

let asked: ShowRequest | null = null;
let entries: Entry[] = [];
let problems: string[] = [];
let visible: number[] = [];
let index = -1;
const filter: Filter = { category: ALL, plane: ALL, text: '' };
/** Whose textures the page holds: the thing the window was opened on. */
let user = '';
/** The owner as the window read it last; null: none. */
let owner: PageOwner | null = null;
/** The states by asset, and what holds for all of them, from the service. */
const states = new Map<string, TextureState>();
let head: TexturesHead = { sizes: [], models: [], limits: [] };
/** The tiles shown beside the original, by asset; absent: the pick, else In game. */
const compared = new Map<string, Set<string>>();
/** The picks, by asset: only those that differ from In game (R-VIEW-133). */
const picks = new Map<string, string>();
/** Decoded variant files: `${asset}|${variant}|${sha256}` -> the decoded texture. */
const decoded = new Map<string, Promise<DecodedTexture>>();
const urls: string[] = [];
let poll: number | null = null;
/** The judge call of the textures shown is out. */
let judging = false;
/** A save to a skin is out: the bar waits for it. */
let saving = false;
let message = '';
let shownTiles: TileState[] = [];

const entry = (): Entry | undefined => entries[index];
const stateOf = (item: Entry): TextureState | undefined => (item.asset === null ? undefined : states.get(item.asset));
/** An entry's category chip when no state names its kind: a game without the texture service, a bare file, or states not read. */
const NO_KIND = 'kind not known';
/** The category chip of an entry: the kind its state names, else NO_KIND. */
function categoryOf(item: Entry): string {
  const state = stateOf(item);
  return state === undefined ? NO_KIND : state.kind;
}
/** What the game shows for an entry (R-VIEW-131). */
const inGame = (item: Entry): ReturnType<typeof inGameOf> => inGameOf(item.asset ?? '', stateOf(item), owner);
/** The tiles an entry shows beside its original. */
function shownOf(item: Entry): Set<string> {
  if (item.asset === null) return new Set([ORIGINAL]);
  return compared.get(item.asset) ?? new Set([picks.get(item.asset) ?? inGame(item).variant]);
}

function say(text: string): void {
  message = text;
  const line = $('message');
  line.textContent = text;
  line.classList.toggle('failure', Boolean(text));
}

async function call(url: string, body: unknown): Promise<TexturesBody> {
  const response = await fetch(url, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
  const answer: unknown = await response.json();
  if (!response.ok) throw new Error(typeof answer === 'object' && answer !== null && typeof Reflect.get(answer, 'error') === 'string' ? String(Reflect.get(answer, 'error')) : `${response.status}`);
  return answer as TexturesBody;
}

const variantsKey = (state: TextureState): string => state.variants.map((variant) => `${variant.id}:${variant.sha256}`).join() + `|${state.bake ?? ''}`;

/** Take a reply of the service; true when a texture shown before has other variants or another bake. */
function take(body: TexturesBody): boolean {
  let changed = false;
  head = { sizes: body.sizes, models: body.models, limits: body.limits };
  for (const state of body.textures) {
    const before = states.get(state.asset);
    if (before && variantsKey(before) !== variantsKey(state)) changed = true;
    states.set(state.asset, state);
  }
  return changed;
}

const assets = (): string[] => [...new Set(entries.map((item) => item.asset).filter((asset): asset is string => asset !== null))];
const busy = (): boolean => [...states.values()].some((state) => Object.values(state.requests).some((request) => request.state !== 'failed'));

/** Ask the states again; while a request runs, once a second. */
async function refreshStates(): Promise<void> {
  if (!asked?.service || !assets().length) return;
  const mine = asked;
  const body = await fetch(textureRoutes.states(mine.game, mine.dataset, assets())).then(async (response) => {
    const answer: unknown = await response.json();
    if (!response.ok) throw new Error(String(Reflect.get(Object(answer), 'error') ?? response.status));
    return answer as TexturesBody;
  });
  if (asked !== mine) return;
  if (take(body)) mine.changed();
  render();
}

/**
 * Have the pipeline read what a request needs of the textures nobody asked for by name yet (17.2).
 * The window shows them meanwhile; the steps they may ask for show once it has.
 */
async function judge(): Promise<void> {
  const mine = asked;
  const unread = [...states.values()].filter((state) => !state.judged).map((state) => state.asset);
  if (!mine?.service || !unread.length) return;
  judging = true;
  try {
    const body = await call(textureRoutes.judge(mine.game, mine.dataset), { assets: unread } satisfies TextureJudgeAsk);
    if (asked !== mine) return;
    take(body);
  } finally {
    if (asked === mine) judging = false;
  }
  render();
}

function schedule(): void {
  if (poll !== null) window.clearTimeout(poll);
  poll = busy() ? window.setTimeout(() => refreshStates().then(schedule, (error: unknown) => say(String(error))), POLL_MS) : null;
}

/** A variant's file, decoded once. */
function decodedOf(asset: string, variant: TextureVariant): Promise<DecodedTexture> {
  const key = `${asset}|${variant.id}|${variant.sha256}`;
  let texture = decoded.get(key);
  if (!texture && asked) {
    const url = textureRoutes.file(asked.game, asked.dataset, asset, variant.id, variant.sha256);
    texture = fetchTexture(url).then(async (response) => decodeDdsBytes(await response.arrayBuffer(), variant.id, urls));
    decoded.set(key, texture);
  }
  return texture ?? Promise.reject(new Error('no texture service'));
}

/** The tiles of an entry shown beside the original, decoded in the entry's plane. */
async function sides(item: Entry): Promise<Side[]> {
  const state = stateOf(item);
  if (!state || !asked || item.asset === null) return [];
  const shown = shownOf(item);
  const found: Side[] = [];
  for (const variant of state.variants) {
    if (!shown.has(variant.id)) continue;
    const made = await decodedOf(state.asset, variant);
    const plane = made.planes.find((one) => one.plane === item.plane);
    if (plane) found.push({ label: `${variant.title} · ${variant.size}`, image: plane.image, width: made.size[0] });
  }
  return found;
}

/** The picture of a tile, in the entry's plane. */
function preview(item: Entry, variant: string): HTMLElement {
  const box = element('span', 'tex-preview');
  const img = (src: string): HTMLImageElement => Object.assign(element('img'), { src, alt: '', draggable: false });
  if (variant === ORIGINAL) {
    box.append(img(item.image));
    return box;
  }
  const found = stateOf(item)?.variants.find((one) => one.id === variant);
  if (!found || item.asset === null) {
    box.classList.add('none');
    return box;
  }
  box.classList.add('loading');
  decodedOf(item.asset, found).then(
    (made) => {
      const plane = made.planes.find((one) => one.plane === item.plane) ?? made.planes[0];
      box.classList.remove('loading');
      if (plane) box.append(img(plane.image));
    },
    (error: unknown) => {
      box.className = 'tex-preview failed';
      box.title = `no picture: ${error instanceof Error ? error.message : String(error)}`;
      box.textContent = '?';
    },
  );
  return box;
}

/** A click on a tile: alone beside the original, and picked; Ctrl+click adds or takes out one to compare (R-VIEW-130). */
function clicked(item: Entry, variant: string, event: MouseEvent): void {
  const asset = item.asset;
  if (asset === null) return;
  if (event.ctrlKey || event.metaKey) {
    const set = new Set(shownOf(item));
    if (set.has(variant) && set.size > 1) set.delete(variant);
    else set.add(variant);
    compared.set(asset, set);
  } else {
    compared.set(asset, new Set([variant]));
    // Only a thing with an owner has picks to save (R-VIEW-133).
    if (asked?.save) {
      if (variant === inGame(item).variant) picks.delete(asset);
      else picks.set(asset, variant);
    }
  }
  render();
  show(index, true);
}

/** The bar of the picks: a count, Revert Changes, Save to Skin… (draft.ts, R-VIEW-133). */
const pickBar = (): HTMLElement =>
  draftBar({
    save: asked?.save?.bind(asked),
    picks,
    compared,
    saving: () => saving,
    setSaving: (on) => {
      saving = on;
    },
    redraw: () => {
      render();
      show(index, true);
    },
    render,
    say,
    element,
  });

function describe(item: Entry): void {
  const title = $('title');
  title.textContent = item.texture;
  title.append(element('small', '', [item.plane, categoryOf(item), item.format].join(' · ')));
  const state = stateOf(item);
  const cards = $('cards');
  const tiles = element('div', 'skin-tiles');
  shownTiles = [];
  if (state && asked) {
    const shown = shownOf(item);
    const upscale = asked.upscale;
    const made = textureTiles({
      asset: state.asset,
      state,
      head,
      inGame: inGame(item),
      originalSize: item.size.join('x'),
      preview: (variant) => preview(item, variant),
      highlighted: (variant) => shown.has(variant),
      click: (variant, event) => clicked(item, variant, event),
      upscale: upscale && state.judged && !state.reason ? () => upscale(state.asset) : null,
    });
    shownTiles = made.tiles;
    tiles.append(...made.nodes);
  }
  const area = element('div', 'tiles-area');
  area.append(pickBar(), tiles);
  cards.replaceChildren(detailsOf(item.size, item.format, item.facts, state ?? null), area);
}

let showing = 0;
function show(at: number, keepView: boolean): void {
  const item = entries[at];
  if (!item) return;
  list.querySelector('.row.current')?.classList.remove('current');
  index = at;
  const row = list.querySelector(`.row[data-index="${at}"]`);
  row?.classList.add('current');
  row?.scrollIntoView({ block: 'nearest' });
  describe(item);
  const original: Side = { label: 'Original', image: item.image, width: item.size[0] };
  image.show({ original, height: item.size[1], results: [] }, keepView);
  const mine = ++showing;
  sides(item).then(
    (results) => {
      if (mine === showing && results.length) image.show({ original, height: item.size[1], results }, true);
    },
    (error: unknown) => say(`a result cannot be shown: ${error instanceof Error ? error.message : String(error)}`),
  );
}

/** The list filter over the entries (filter.ts). */
const listed: FilterPage<Entry> = {
  filter,
  entries: () => entries,
  categoryOf,
  usersOf: (item) => stateOf(item)?.users ?? [],
  render,
  element,
};

function render(): void {
  chips(listed, $('categories'), 'category', categoryOf);
  chips(listed, $('planes'), 'plane', (item) => item.plane);
  visible = [];
  list.replaceChildren();
  entries.forEach((item, at) => {
    if (!passes(listed, item)) return;
    visible.push(at);
    const row = element('div', `row${at === index ? ' current' : ''}`);
    row.dataset['index'] = String(at);
    const thumb = element('img');
    thumb.decoding = 'async';
    thumb.alt = '';
    thumb.src = item.image;
    const meta = element('div', 'meta');
    const state = stateOf(item);
    const made = state ? state.variants.map((variant) => variant.id) : [];
    if (item.asset !== null && picks.has(item.asset)) {
      const badge = element('span', 'badge picked', 'PICKED');
      badge.title = `picked: ${picks.get(item.asset) ?? ''}, not saved`;
      meta.append(badge);
    }
    if (made.length) {
      const badge = element('span', 'badge hd', 'HD');
      badge.title = made.join(', ');
      meta.append(badge);
    }
    if (state?.packaged?.held) meta.append(element('span', 'badge packaged', 'PKG'));
    if (state && Object.values(state.requests).some((request) => request.state === 'failed')) meta.append(element('span', 'badge failed', 'FAILED'));
    else if (state && Object.keys(state.requests).length) meta.append(element('span', 'badge running', 'QUEUED'));
    meta.append(`${item.plane} · ${item.size.join('x')} · ${item.format}`);
    const text = element('div', 'text');
    text.append(element('div', 'name', item.texture), meta);
    row.append(thumb, text);
    row.title = state?.users.join(', ') ?? '';
    row.addEventListener('click', () => show(at, true));
    list.append(row);
  });
  if (!visible.length) {
    const none = element('div', '', entries.length ? 'No texture passes the filters.' : `${user || 'This'} names no texture.`);
    none.id = 'empty';
    list.append(none);
    index = -1;
    image.clear();
    $('title').textContent = '';
    $('cards').replaceChildren();
  }
  if (problems.length) {
    const shown = element('div', '', `Not shown: ${problems.join('; ')}`);
    shown.id = 'problems';
    list.append(shown);
  }
  $('count').textContent = `${visible.length} of ${entries.length} entries`;
  if (visible.length && !visible.includes(index)) show(visible[0] ?? 0, false);
  else if (index >= 0) {
    const item = entry();
    if (item) describe(item);
  }
}

async function showTextures(request: ShowRequest): Promise<void> {
  for (const url of urls.splice(0)) URL.revokeObjectURL(url);
  decoded.clear();
  states.clear();
  compared.clear();
  picks.clear();
  judging = false;
  saving = false;
  asked = request;
  owner = request.owner;
  user = request.user;
  index = -1;
  problems = request.failed;
  entries = request.textures.flatMap((texture) =>
    texture.planes.map((plane) => ({ id: `${texture.texture.toLowerCase().replace(/\.[^.]+$/, '')}.${plane.plane}`, asset: texture.asset, texture: texture.texture, plane: plane.plane, format: texture.format, size: texture.size, image: plane.image, facts: texture.facts ?? [] })),
  );
  say('');
  if (request.service) await refreshStates().catch((error: unknown) => say(`the texture states cannot be read: ${error instanceof Error ? error.message : String(error)}`));
  render();
  schedule();
  // Not waited for: the window is usable while the pipeline reads.
  judge().catch((error: unknown) => say(`what can be made of these textures cannot be read: ${error instanceof Error ? error.message : String(error)}`));
}

/** The main page changed textures (a request, a bake, a save): take the owner, read the states again, and poll while one runs. */
async function refresh(next: PageOwner | null = owner): Promise<void> {
  owner = next;
  // A pick In game now shows is no change any more.
  for (const item of entries) if (item.asset !== null && picks.get(item.asset) === inGame(item).variant) picks.delete(item.asset);
  await refreshStates();
  render();
  schedule();
}

search.addEventListener('input', () => {
  filter.text = search.value.trim().toLowerCase();
  render();
});
const step = (by: number): void => {
  if (!visible.length) return;
  const place = visible.indexOf(index);
  show(visible[place < 0 ? 0 : (place + by + visible.length) % visible.length] ?? 0, true);
};
$('previous').addEventListener('click', () => step(-1));
$('next').addEventListener('click', () => step(1));
$('fit').addEventListener('click', image.fit);
$('actual').addEventListener('click', image.actual);
for (const name of ['tile', 'smooth'] as const) $(name).addEventListener('click', () => $(name).classList.toggle('on', image.toggle(name)));
window.addEventListener('keydown', (event) => {
  if (event.target === search) {
    if (event.key === 'Escape') search.blur();
    if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return;
  }
  if (event.target instanceof HTMLSelectElement || event.ctrlKey || event.metaKey || event.altKey) return;
  if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
    event.preventDefault();
    step(-1);
  }
  if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
    event.preventDefault();
    step(1);
  }
  if (event.key === 'f') image.fit();
  if (event.key === '1') image.actual();
  if (event.key === 't') $('tile').classList.toggle('on', image.toggle('tile'));
  if (event.key === 's') $('smooth').classList.toggle('on', image.toggle('smooth'));
  if (event.key === '/') {
    event.preventDefault();
    search.focus();
    search.select();
  }
});

// For the window and its tests.
Reflect.set(window, 'hdtex', {
  show: showTextures,
  refresh,
  problems: () => [...problems],
  message: () => message,
  textures: () => [...states.values()],
  entries: () => visible.map((at) => {
    const item = entries[at];
    const state = item ? stateOf(item) : undefined;
    return item && { id: item.id, asset: item.asset, texture: item.texture, plane: item.plane, category: categoryOf(item), size: item.size, variants: state ? state.variants.map((variant) => variant.id) : [], image: item.image, facts: item.facts };
  }),
  state: () => {
    const item = entry();
    const draft = document.getElementById('draft');
    return {
      user,
      embed,
      total: entries.length,
      visible: visible.length,
      size: image.size(),
      polling: poll !== null,
      judging,
      current: item ? { id: item.id, texture: item.texture, asset: item.asset } : null,
      // What the view shows beside the original, the tiles, the picks and their bar (R-VIEW-130, 133).
      shown: item ? [...shownOf(item)] : [],
      tiles: [...shownTiles],
      picks: Object.fromEntries(picks),
      draft: { shown: draft !== null && !draft.hidden, text: draft?.querySelector('.draft-count')?.textContent ?? '' },
      owner: owner?.owner ?? null,
    };
  },
});

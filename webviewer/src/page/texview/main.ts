// The page of the texture window (SPEC-VIEWER 17.3), in its frame. The
// window hands it the textures of one thing, decoded (window.hdtex.show).
// For a game with a texture service it reads their states and shows the
// tiles of the chosen texture (core/tiles.ts, R-VIEW-132). A click on a tile
// picks it. Each tile's "Include in preview" box puts it in the picture
// beside the original; any number can be in it (R-VIEW-130). The picks are kept per
// texture; Save to Skin… hands them to the main page, which asks first
// (R-VIEW-133). Its Upscale Texture tile asks the window to open the dialog
// of the main page. A failed request's Ask Again calls the request route
// here; a variant's trash asks the main page first (R-VIEW-146, 147).
// This file owns what is shown: the entries, the picks, the picture's
// choice, and the order of a read and a draw. Its parts: states.ts (the
// service's calls and answers), pictures.ts (the decoded variant files),
// tileactions.ts (Ask Again, the trash), rows.ts (a list row), filter.ts,
// draft.ts, cards.ts, controls.ts, edits.ts, imageview.ts.
// src/tools/build.ts bundles it into public/vendor/texview.js.

import type { DecodedTexture } from '../core/ddsdecode';
import { inGameOf, textureTiles, tickElapsed, type TileState } from '../core/tiles';
import type { PageOwner } from '../core/texturewindow';
import { firstSaveInto, hasSkin, namedByLines, namedInto, ORIGINAL, ORIGINAL_SKIN, skinLabel, textureRoutes, usersBadge, type TextureJudgeAsk, type TextureState } from '../../shared/textures';
import { detailsOf } from './cards';
import { bindControls } from './controls';
import { createImageView, type Side } from './imageview';
import { draftBar } from './draft';
import { editsState, editsTaker, resetEdits, tileEdits, type EditTools } from './edits';
import { ALL, chips, passes, type Filter, type FilterPage } from './filter';
import { clearPictures, preview, sides } from './pictures';
import { listRow } from './rows';
import { busy, call, headOf, readStates, states, take } from './states';
import { clearRetries, removalTools, requestTools, type TilePage } from './tileactions';

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
  /** A variant tile's trash: the main page asks, then removes it (R-VIEW-147). False: cancelled; a refusal rejects. Absent: no trash. */
  remove?(asset: string, variant: string): Promise<boolean>;
  /** Save the picks to a skin of the owner; the main page asks first (R-VIEW-133). The target, or null: not saved. Absent: no owner. */
  save?(picks: TexturePick[]): Promise<string | null>;
  /** The edit sessions (edits.ts); absent: no edit control. */
  edit?: EditTools;
  /** The skin the instance shows; null or absent: the window is on no instance. */
  skin?: string | null;
  /** Rename the skin the instance shows; the main page asks the name (R-VIEW-156). The new name, or null: cancelled. Absent: no instance with an owner. */
  rename?(): Promise<string | null>;
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
/** The skin the instance shows, as the window said last; null: the window is on no instance. */
let skin: string | null = null;
/** The variants in the picture beside the original, by asset; absent: the pick, else In game. May be empty. */
const compared = new Map<string, Set<string>>();
/** The picks, by asset: only those that differ from In game (R-VIEW-133). */
const picks = new Map<string, string>();
let poll: number | null = null;
/** The judge call of the textures shown is out. */
let judging = false;
/** A save to a skin is out: the bar waits for it. */
let saving = false;
/** A rename of the skin is out: its button waits for it. */
let renaming = false;
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
/**
 * What a pick is a change against (R-VIEW-133): with an owner, what the target Save to Skin… offers first names
 * (`firstSaveInto`), so the bar and the dialog count the same picks. Without an owner there is nothing to save: In game.
 */
function baseOf(item: Entry): string {
  if (item.asset === null) return ORIGINAL;
  return owner && asked?.save ? namedInto(owner, firstSaveInto(owner, skin), item.asset) : inGame(item).variant;
}
/** The tiles an entry shows beside its original. */
function shownOf(item: Entry): Set<string> {
  if (item.asset === null) return new Set([ORIGINAL]);
  return compared.get(item.asset) ?? new Set([picks.get(item.asset) ?? baseOf(item)]);
}

function say(text: string): void {
  message = text;
  const line = $('message');
  line.textContent = text;
  line.classList.toggle('failure', Boolean(text));
}

const assets = (): string[] => [...new Set(entries.map((item) => item.asset).filter((asset): asset is string => asset !== null))];

/** Ask the states again; while a request runs, once a second. */
async function refreshStates(): Promise<void> {
  if (!asked?.service || !assets().length) return;
  const mine = asked;
  const body = await readStates(mine.game, mine.dataset, assets());
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

/** The variant picked for an entry: the pick, else what the game shows (R-VIEW-133). */
const pickedOf = (item: Entry): string => (item.asset === null ? ORIGINAL : (picks.get(item.asset) ?? baseOf(item)));

/**
 * A click on a tile picks it (R-VIEW-133). It also goes in the picture, beside
 * the ones there; its box takes it out again (R-VIEW-130).
 */
function clicked(item: Entry, variant: string): void {
  const asset = item.asset;
  if (asset === null) return;
  const set = new Set(shownOf(item));
  set.add(variant);
  compared.set(asset, set);
  // Only a thing with an owner has picks to save.
  if (asked?.save) {
    if (variant === baseOf(item)) picks.delete(asset);
    else picks.set(asset, variant);
  }
  render();
  show(index, true);
}

/** The "Include in preview" box of a tile: the variant goes in the picture or out of it; nothing is picked (R-VIEW-130). */
function included(item: Entry, variant: string, on: boolean): void {
  const asset = item.asset;
  if (asset === null) return;
  const set = new Set(shownOf(item));
  if (on) set.add(variant);
  else set.delete(variant);
  compared.set(asset, set);
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

/** A removed variant leaves the picture of its texture. */
function unpicture(asset: string, variant: string): void {
  compared.get(asset)?.delete(variant);
}

/** What the tiles' actions read and call of the page, for one show request (tileactions.ts). */
const tilePage = (mine: ShowRequest): TilePage => ({
  game: mine.game,
  dataset: mine.dataset,
  current: () => asked === mine,
  render,
  say,
  schedule,
  reread: () => {
    refreshStates().then(schedule, (error: unknown) => say(String(error)));
  },
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
    const mine = asked;
    const page = tilePage(mine);
    const shown = shownOf(item);
    const { upscale, remove } = mine;
    const made = textureTiles({
      asset: state.asset,
      state,
      head: headOf(),
      inGame: inGame(item),
      originalSize: item.size.join('x'),
      preview: (variant) => preview(mine, item, state, variant),
      highlighted: (variant) => variant === pickedOf(item),
      click: (variant) => clicked(item, variant),
      compare: { included: (variant) => shown.has(variant), include: (variant, on) => included(item, variant, on) },
      upscale: upscale && state.judged && !state.reason ? () => upscale(state.asset) : null,
      edit: tileEdits(state),
      // Ask Again and Open Log: a game with the service. The trash: a window that offers the removal.
      requests: mine.service ? requestTools(page, state) : undefined,
      removal: remove ? removalTools(page, { remove, owner, picked: pickedOf(item), removed: (variant) => unpicture(state.asset, variant) }, state) : undefined,
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
  sides(asked, item, stateOf(item), shownOf(item)).then(
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

/** Why Rename Skin… cannot be used now; empty: it can (R-VIEW-156). */
function renameBlock(): string {
  if (!asked?.rename || skin === null) return 'this window is on no instance with skins';
  if (skin === ORIGINAL_SKIN) return 'Original names nothing; pick or make a skin first';
  if (missing()) return `${owner?.owner ?? 'the owner'} has no skin "${skin}"; choose another skin`;
  if (renaming) return 'a rename is under way';
  return '';
}

/** The instance is on a skin its owner does not have (SPEC-VIEWER 17.4). */
const missing = (): boolean => owner !== null && skin !== null && !hasSkin(owner, skin);

/** The skin line: the skin the instance shows, and Rename Skin…. */
function skinLine(): void {
  const line = $('skin-line');
  line.hidden = !asked?.rename || skin === null;
  $('skin-name').textContent = skin === null ? '' : `Skin: ${skinLabel(skin)}${missing() ? ' (missing)' : ''}`;
  $('skin-name').classList.toggle('missing', missing());
  const button = $('skin-rename') as HTMLButtonElement;
  const block = renameBlock();
  button.disabled = block !== '';
  button.title = block || `Give skin "${skin ?? ''}" another name; every instance on it and its bake follow`;
}

$('skin-rename').addEventListener('click', () => {
  const rename = asked?.rename;
  if (!rename || renameBlock()) return;
  renaming = true;
  skinLine();
  rename.call(asked).then(
    () => {
      renaming = false;
      skinLine();
    },
    (error: unknown) => {
      renaming = false;
      say(`the skin was not renamed: ${error instanceof Error ? error.message : String(error)}`);
      skinLine();
    },
  );
});

function render(): void {
  skinLine();
  chips(listed, $('categories'), 'category', categoryOf);
  chips(listed, $('planes'), 'plane', (item) => item.plane);
  visible = [];
  list.replaceChildren();
  entries.forEach((item, at) => {
    if (!passes(listed, item)) return;
    visible.push(at);
    const picked = item.asset === null ? null : (picks.get(item.asset) ?? null);
    const row = listRow(item, { index: at, current: at === index, state: stateOf(item), picked, owner: owner?.owner ?? null });
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
  clearPictures();
  states.clear();
  compared.clear();
  picks.clear();
  judging = false;
  saving = false;
  renaming = false;
  clearRetries();
  resetEdits(request.edit ?? null);
  asked = request;
  owner = request.owner;
  skin = request.skin ?? null;
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

/**
 * The main page changed textures (a request, a bake, a save) or the instance's skin: take the owner and the skin,
 * read the states again, and poll while one runs. `shown` absent: the skin stays.
 */
async function refresh(next: PageOwner | null = owner, shown: string | null = skin): Promise<void> {
  owner = next;
  skin = shown;
  // A pick the target skin names now is no change any more.
  for (const item of entries) if (item.asset !== null && picks.get(item.asset) === baseOf(item)) picks.delete(item.asset);
  await refreshStates();
  render();
  schedule();
}

bindControls({
  $,
  search,
  image,
  searched: (text) => {
    filter.text = text;
    render();
  },
  step: (by) => {
    if (!visible.length) return;
    const place = visible.indexOf(index);
    show(visible[place < 0 ? 0 : (place + by + visible.length) % visible.length] ?? 0, true);
  },
});

// The time on each request tile counts each second, between the reads of the states (R-VIEW-145).
window.setInterval(() => tickElapsed([$('cards')], Date.now() / 1000), 1000);

// For the window and its tests.
Reflect.set(window, 'hdtex', {
  show: showTextures,
  refresh,
  /** The dataset's edit sessions, as the main page read them now. */
  edits: editsTaker(render),
  problems: () => [...problems],
  message: () => message,
  textures: () => [...states.values()],
  entries: () => visible.map((at) => {
    const item = entries[at];
    const state = item ? stateOf(item) : undefined;
    return item && { id: item.id, asset: item.asset, texture: item.texture, plane: item.plane, category: categoryOf(item), size: item.size, variants: state ? state.variants.map((variant) => variant.id) : [], image: item.image, facts: item.facts, usersBadge: state ? usersBadge(state, owner?.owner ?? null) : null };
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
      // The lines of "named by" of the current texture (R-VIEW-161).
      namedBy: item ? namedByLines({ namedBy: stateOf(item)?.namedBy ?? [] }) : [],
      // What the view shows beside the original, the tiles, the picks and their bar (R-VIEW-130, 133).
      shown: item ? [...shownOf(item)] : [],
      tiles: [...shownTiles],
      picks: Object.fromEntries(picks),
      draft: { shown: draft !== null && !draft.hidden, text: draft?.querySelector('.draft-count')?.textContent ?? '' },
      owner: owner?.owner ?? null,
      skin,
      // The skin line and Rename Skin… (R-VIEW-156).
      skinLine: { shown: !$('skin-line').hidden, text: $('skin-name').textContent, renameDisabled: ($('skin-rename') as HTMLButtonElement).disabled, renameTitle: $('skin-rename').title },
      edits: editsState(),
    };
  },
});

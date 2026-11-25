// The texture window (SPEC-VIEWER 17.3): the texture viewer page
// (public/texture-viewer.html, src/page/texview) in a movable window over
// the view, one for every game. A game hands it the textures of one thing,
// decoded (ddsdecode.ts). For a game with a texture service the page reads
// their states and compares the variants (R-VIEW-101). Its Upscale Texture
// tile is the event "texture-upscale", its Save to Skin… the event
// "texture-save" (R-VIEW-133), a variant's trash the event "texture-remove"
// (R-VIEW-147); a change made in the main page
// ("textures-changed") makes it read the states and the owner again. The
// owner tells the page what the game shows (In game, R-VIEW-131).

import type { EditSession } from '../../shared/edits';
import type { HealthBody } from '../../shared/protocol';
import { skinLabel, textureRoutes, type OwnerLookup, type OwnerState } from '../../shared/textures';
import type { EventBus, ViewerEvents } from './bus';
import type { RenderHost, UiService, WindowPlace } from './context';
import type { DecodedTexture } from './ddsdecode';
import { make, messageOf } from './dom';

/** What the page needs of the owner: what it shows, its bakes, whether the package holds them. */
export type PageOwner = Pick<OwnerState, 'owner' | 'shows' | 'held' | 'bake' | 'below' | 'skins'>;

const MARGIN = 16;
const TOP = 48; // below the view tools
// The first size; a smaller page gives a smaller window (SPEC-VIEWER 17.3).
const SIZE = [1100, 760] as const;

/** The page of the window, served by the server's core. */
export const TEXTURE_PAGE = '/texture-viewer.html';

/** One texture for the page: decoded, with the pipeline's name of it (null: none) and facts for its card ([name, value]). */
export type ShownTexture = DecodedTexture & { asset: string | null; facts?: [string, string][] };

/** What a game hands the window to show. */
export interface TextureRequest {
  /** Whose textures: the page lists them under this name. */
  user: string;
  /** The window's title. */
  name: string;
  /** The model file, its dataset and its game: with `user`, what makes two requests the same. */
  file: string;
  dataset: string;
  game: string;
  /** The game offers a texture service (R-VIEW-100). */
  service: boolean;
  /** The texture owner of the thing (R-VIEW-130); null: none, so the window offers no Save to Skin. */
  owner?: string | null;
  /** The instance the window is opened on; null or absent: a record or a file. */
  item?: number | null;
  /** The skin the instance shows, named in the title; null or absent: no instance, or no skins. */
  skin?: string | null;
  /** Read the textures; object URLs go in `urls` (the window revokes them). */
  read(urls: string[]): Promise<{ textures: ShownTexture[]; failed: string[] }>;
}

export interface TextureWindow {
  open(request: TextureRequest): Promise<void>;
  /** The open window's game and dataset, when its page has the edit controls; null: closed, not read yet, or none. */
  editing(): { game: string; dataset: string } | null;
  /** Hand the edit sessions of a game's dataset to the page, when it shows that dataset (SPEC-PHOTOCRAFT 9.3). */
  edits(game: string, dataset: string, sessions: readonly EditSession[]): void;
  /** For the tests (scobaeditor.textureWindow): whether the window is open, whose textures, how the read went. */
  state(): { open: boolean; user: string | null; file: string | null; dataset: string | null; originals: string };
}

/** The edit controls of the page: open a session, list the sessions. */
interface PageEdits {
  open(asset: string, variant: string): void;
  manage(): void;
}

/** What the texture viewer page offers the window. */
interface TexturePage {
  show(request: { user: string; game: string; dataset: string; service: boolean; owner: PageOwner | null; textures: ShownTexture[]; failed: string[]; changed(): void; upscale?(asset: string): void; remove?(asset: string, variant: string): Promise<boolean>; save?(picks: { asset: string; variant: string }[]): Promise<string | null>; edit?: PageEdits }): Promise<void>;
  /** Read the states again: the main page changed textures; `owner` as it is now. */
  refresh(owner: PageOwner | null): Promise<void>;
  /** The dataset's edit sessions, as the main page read them now. */
  edits(sessions: readonly EditSession[]): void;
}

/** Whether PhotoCraft is installed, as the health answer says. Read once (SPEC-PHOTOCRAFT 7); a read that failed is made again. */
let installed: Promise<boolean> | null = null;
function photocraftInstalled(): Promise<boolean> {
  installed ??= fetch('/api/health')
    .then(async (response) => {
      if (!response.ok) throw new Error(`the health answer: ${response.status}`);
      return ((await response.json()) as HealthBody).photocraft.installed;
    })
    .catch((error: unknown) => {
      installed = null;
      throw error;
    });
  return installed;
}

/** The owner as the server has it now; null: none, or no service. */
async function readOwner(game: string, dataset: string, owner: string | null): Promise<PageOwner | null> {
  if (owner === null) return null;
  const response = await fetch(textureRoutes.owner(game, dataset, owner));
  const body: unknown = await response.json();
  if (!response.ok) throw new Error(`the owner ${owner} in ${dataset}: ${String(Reflect.get(Object(body), 'error') ?? response.status)}`);
  return (body as OwnerLookup).owner;
}

function pageOf(frame: HTMLIFrameElement): TexturePage {
  const hdtex: unknown = frame.contentWindow ? Reflect.get(frame.contentWindow, 'hdtex') : undefined;
  const member = (name: string): unknown => (typeof hdtex === 'object' && hdtex !== null ? Reflect.get(hdtex, name) : undefined);
  const show = member('show');
  const refresh = member('refresh');
  const edits = member('edits');
  if (typeof show !== 'function' || typeof refresh !== 'function' || typeof edits !== 'function') throw new Error('the texture viewer page has no hdtex.show, hdtex.refresh or hdtex.edits');
  return {
    show: (request) => Promise.resolve(Reflect.apply(show, hdtex, [request])),
    refresh: (owner) => Promise.resolve(Reflect.apply(refresh, hdtex, [owner])),
    // The page's edits() answers nothing: it takes the sessions and draws.
    edits: (sessions) => {
      Reflect.apply(edits, hdtex, [sessions]);
    },
  };
}

/**
 * The one texture window of the page. `viewerKeys`: Ctrl+<key> that belong
 * to the viewer, kept from the browser inside the frame too.
 */
export function createTextureWindow(ui: Pick<UiService, 'floatingWindow'>, render: Pick<RenderHost, 'visibleRect'>, events: EventBus<ViewerEvents>, viewerKeys: readonly string[]): TextureWindow {
  const frame = make('iframe', { id: 'texture-frame', title: 'textures' });
  const win = ui.floatingWindow({ id: 'texture-window', title: 'textures' });
  win.body.append(frame);
  // Keys go to the frame once it was clicked: Escape there closes the window
  // too. In the page's search box and its selects Escape only leaves them.
  frame.addEventListener('load', () => {
    frame.contentWindow?.addEventListener('keydown', (e) => {
      const target = e.target;
      if (e.key === 'Escape' && !(target instanceof Element && target.matches('input, select'))) win.close();
      if (e.ctrlKey && !e.altKey && !e.metaKey && !e.shiftKey && viewerKeys.includes(e.key.toLowerCase())) e.preventDefault();
    });
  });
  /** `edit`: its page has the edit controls. */
  let shown: { user: string; file: string; dataset: string; game: string; item: number | null; owner: string | null; edit: boolean } | null = null;
  /** Counts the opens, so a slow read for an earlier one is dropped. */
  let turn = 0;
  let urls: string[] = [];
  /** 'none', 'loading', 'done', or 'failed: <why>'. */
  let originals = 'none';

  /** Where the window opens first: right of the open panels, as large as fits. */
  function firstPlace(): WindowPlace {
    const left = render.visibleRect().left + MARGIN;
    return { left, top: TOP, width: Math.min(SIZE[0], innerWidth - left - MARGIN), height: Math.min(SIZE[1], innerHeight - TOP - MARGIN) };
  }

  const frameLoaded = (): Promise<void> =>
    new Promise((resolve) => {
      frame.addEventListener('load', () => resolve(), { once: true });
    });

  async function open(request: TextureRequest): Promise<void> {
    const skin = request.skin ?? null;
    win.title.textContent = `textures · ${request.name}${skin === null ? '' : ` · ${skinLabel(skin)}`}`;
    win.open(firstPlace());
    // The same textures again: the window shows them already, or is reading them.
    if (shown && shown.user === request.user && shown.file === request.file && shown.dataset === request.dataset && shown.item === (request.item ?? null) && !originals.startsWith('failed')) return;
    const owner = request.service ? (request.owner ?? null) : null;
    const now = { user: request.user, file: request.file, dataset: request.dataset, game: request.game, item: request.item ?? null, owner, edit: false };
    shown = now;
    const mine = ++turn;
    for (const url of urls) URL.revokeObjectURL(url);
    urls = [];
    originals = 'loading';
    // A fresh page for every thing: nothing of the one before stays in it.
    const loaded = frameLoaded();
    frame.src = `${TEXTURE_PAGE}?embed=1`;
    try {
      // The edit controls: for a game with the service, while PhotoCraft is installed (R-PC-13, R-PC-28).
      const [found, ownerState, editable] = await Promise.all([request.read(urls), readOwner(request.game, request.dataset, owner), request.service ? photocraftInstalled() : false, loaded]);
      if (mine !== turn) return;
      const edit: PageEdits = {
        open: (asset, variant) => events.emit('texture-edit', { game: request.game, dataset: request.dataset, asset, variant }),
        manage: () => events.emit('edits-manage', { game: request.game, dataset: request.dataset }),
      };
      const changed = (): void => events.emit('textures-changed', { game: request.game, dataset: request.dataset });
      const upscale = (asset: string): void => events.emit('texture-upscale', { game: request.game, dataset: request.dataset, asset });
      // Save to Skin…: the main page asks the target and shows each change first (R-VIEW-133).
      const save = (picks: { asset: string; variant: string }[]): Promise<string | null> =>
        new Promise((done) => {
          if (owner) events.emit('texture-save', { game: request.game, dataset: request.dataset, owner, picks, item: request.item ?? null, done });
          else done(null);
        });
      // A variant tile's trash: the main page asks first (R-VIEW-147).
      const remove = (asset: string, variant: string): Promise<boolean> =>
        new Promise((done, fail) => {
          events.emit('texture-remove', { game: request.game, dataset: request.dataset, asset, variant, done: (removed) => (removed instanceof Error ? fail(removed) : done(removed)) });
        });
      await pageOf(frame).show({ user: request.user, game: request.game, dataset: request.dataset, service: request.service, owner: ownerState, textures: found.textures, failed: found.failed, changed, ...(request.service ? { upscale, remove } : {}), ...(ownerState ? { save } : {}), ...(editable ? { edit } : {}) });
      now.edit = editable;
      originals = 'done';
    } catch (error) {
      if (mine === turn) originals = `failed: ${messageOf(error)}`;
      throw error;
    }
  }

  // A change made in the main page (the upscale dialog, a bake) shows in the open window.
  events.on('textures-changed', ({ game, dataset }) => {
    if (!win.isOpen || originals !== 'done' || !shown || shown.dataset !== dataset || shown.game !== game) return;
    const mine = shown;
    readOwner(game, dataset, mine.owner)
      .then((owner) => (shown === mine ? pageOf(frame).refresh(owner) : undefined))
      .catch((error: unknown) => console.error(`the texture window was not read again: ${messageOf(error)}`));
  });

  const editing = (): { game: string; dataset: string } | null => (win.isOpen && originals === 'done' && shown?.edit ? { game: shown.game, dataset: shown.dataset } : null);
  function edits(game: string, dataset: string, sessions: readonly EditSession[]): void {
    const mine = editing();
    if (mine && mine.game === game && mine.dataset === dataset) pageOf(frame).edits(sessions);
  }

  return { open, editing, edits, state: () => ({ open: win.isOpen, user: shown ? shown.user : null, file: shown ? shown.file : null, dataset: shown ? shown.dataset : null, originals }) };
}

// The texture window: the texture viewer page (scripts/hdtex/compare.html)
// in a movable window over the view, one for every game. A game opens it
// on a page (SC2: its built page with the HD pairs; else the bare template,
// /texture-viewer.html) and hands it the textures it shows, decoded
// (ddsdecode.ts), through the page's hdtex.addOriginals.

import type { RenderHost, UiService, WindowPlace } from './context';
import type { DecodedTexture } from './ddsdecode';
import { make, messageOf } from './dom';

const MARGIN = 16;
const TOP = 48; // below the view tools
const SIZE = [900, 620] as const;

/** The texture viewer page as a template, served by the server's core. */
export const TEMPLATE_PAGE = '/texture-viewer.html';

/** One texture for the page: decoded, with facts for its card ([name, value]). */
export type ShownTexture = DecodedTexture & { facts?: [string, string][] };

/** What a game hands the window to show. */
export interface TextureRequest {
  /** Whose textures: the page lists them under this name (its `user`). */
  user: string;
  /** The window's title. */
  name: string;
  /** The page: SC2's built one, or TEMPLATE_PAGE. */
  page: string;
  /** The model file and its dataset: with `user`, what makes two requests the same. */
  file: string;
  dataset: string;
  /** Read the textures; object URLs go in `urls` (the window revokes them). */
  read(urls: string[]): Promise<{ textures: ShownTexture[]; failed: string[] }>;
}

export interface TextureWindow {
  open(request: TextureRequest): Promise<void>;
  /** For the tests (sc2viewer.textureWindow): whether the window is open, whose textures, how the read went. */
  state(): { open: boolean; user: string | null; file: string | null; dataset: string | null; originals: string };
}

/** What the texture viewer page offers the window. */
interface HdTexPage {
  addOriginals(user: string, textures: ShownTexture[], failed: string[]): void;
}

function hdtexOf(frame: HTMLIFrameElement): HdTexPage {
  const hdtex: unknown = frame.contentWindow ? Reflect.get(frame.contentWindow, 'hdtex') : undefined;
  const add: unknown = typeof hdtex === 'object' && hdtex !== null ? Reflect.get(hdtex, 'addOriginals') : undefined;
  if (typeof add !== 'function') throw new Error('the texture viewer page has no hdtex.addOriginals');
  return { addOriginals: (user, textures, failed) => Reflect.apply(add, hdtex, [user, textures, failed]) };
}

/**
 * The one texture window of the page. `viewerKeys`: Ctrl+<key> that belong
 * to the viewer, kept from the browser inside the frame too.
 */
export function createTextureWindow(ui: Pick<UiService, 'floatingWindow'>, render: Pick<RenderHost, 'visibleRect'>, viewerKeys: readonly string[]): TextureWindow {
  const frame = make('iframe', { id: 'texture-frame', title: 'textures' });
  const win = ui.floatingWindow({ id: 'texture-window', title: 'textures' });
  win.body.append(frame);
  // Keys go to the frame once it was clicked: Escape there closes the window
  // too. In the page's search box Escape only leaves the box.
  frame.addEventListener('load', () => {
    frame.contentWindow?.addEventListener('keydown', (e) => {
      const target = e.target;
      if (e.key === 'Escape' && !(target instanceof Element && target.matches('input'))) win.close();
      if (e.ctrlKey && !e.altKey && !e.metaKey && !e.shiftKey && viewerKeys.includes(e.key.toLowerCase())) e.preventDefault();
    });
  });
  let shown: { user: string; file: string; dataset: string } | null = null;
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
    win.title.textContent = `textures · ${request.name}`;
    win.open(firstPlace());
    // The same textures again: the window shows them already, or is reading them.
    if (shown && shown.user === request.user && shown.file === request.file && shown.dataset === request.dataset && !originals.startsWith('failed')) return;
    shown = { user: request.user, file: request.file, dataset: request.dataset };
    const mine = ++turn;
    for (const url of urls) URL.revokeObjectURL(url);
    urls = [];
    originals = 'loading';
    const loaded = frameLoaded();
    frame.src = `${request.page}?${new URLSearchParams({ user: request.user, embed: '1' })}`;
    try {
      const [found] = await Promise.all([request.read(urls), loaded]);
      if (mine !== turn) return;
      hdtexOf(frame).addOriginals(request.user, found.textures, found.failed);
      originals = 'done';
    } catch (error) {
      if (mine === turn) originals = `failed: ${messageOf(error)}`;
      throw error;
    }
  }

  return { open, state: () => ({ open: win.isOpen, user: shown ? shown.user : null, file: shown ? shown.file : null, dataset: shown ? shown.dataset : null, originals }) };
}

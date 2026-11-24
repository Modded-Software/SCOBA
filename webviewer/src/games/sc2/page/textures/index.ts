// The SC2 texture window: the HD texture viewer (scripts/hdtex/compare.html,
// served below /api/sc2/x/textures/) in a movable window over the view. It is hidden
// until a double-click on a unit or doodad: a gallery row, an instance row,
// or an instance in the view (the game's openItem). It then lists that
// unit's or doodad's textures:
// - the ones with an HD version, original beside upscaled (the page's own
//   entries, filtered by ?user=);
// - every other texture its model file names, the original alone (originals.ts).
// The viewer's "used by" chip drops the filter.

import type { Item } from '../../../../page/core/types';
import type { GameContext, WindowPlace } from '../../../../page/core/context';
import { make, messageOf } from '../../../../page/core/dom';
import type { TexturesBody } from '../../shared/records';
import { SC2 } from '../game';
import { originals, type Original } from './originals';

export interface TextureWindow {
  /** The window on a record of the gallery: its record's model file (an SC2 doodad's first variation). */
  openTexturesFor(category: string, id: string): Promise<void>;
  /** The window on an instance of the scene: the model file it shows. */
  openTexturesOf(item: Item): Promise<void>;
  /** For the tests: whether the window is open, whose textures it shows, and how reading the originals went. */
  textureWindow(): { open: boolean; user: string | null; file: string | null; dataset: string | null; originals: string };
}

const MARGIN = 16;
const TOP = 48; // below the view tools
const SIZE = [900, 620] as const;

/** What the texture viewer page offers the window (scripts/hdtex/compare.html). */
interface HdTexPage {
  addOriginals(user: string, textures: Original[], failed: string[]): void;
}

function hdtexOf(frame: HTMLIFrameElement): HdTexPage {
  const hdtex: unknown = frame.contentWindow ? Reflect.get(frame.contentWindow, 'hdtex') : undefined;
  const add: unknown = typeof hdtex === 'object' && hdtex !== null ? Reflect.get(hdtex, 'addOriginals') : undefined;
  if (typeof add !== 'function') throw new Error('the texture viewer page has no hdtex.addOriginals');
  return { addOriginals: (user, textures, failed) => Reflect.apply(add, hdtex, [user, textures, failed]) };
}

export function installTextures(context: GameContext): TextureWindow {
  const { ui, render, api } = context;
  const frame = make('iframe', { id: 'texture-frame', title: 'textures' });
  const win = ui.floatingWindow({ id: 'texture-window', title: 'textures' });
  win.body.append(frame);
  // Keys go to the frame once it was clicked: Escape there closes the window
  // too. In the viewer's search box Escape only leaves the box.
  frame.addEventListener('load', () => {
    frame.contentWindow?.addEventListener('keydown', (e) => {
      const target = e.target;
      if (e.key === 'Escape' && !(target instanceof Element && target.matches('input'))) win.close();
      // Ctrl+H and Ctrl+L belong to the viewer (../hd.ts, features/pick): not the browser's history or address bar here either.
      if (e.ctrlKey && !e.altKey && !e.metaKey && !e.shiftKey && ['h', 'l'].includes(e.key.toLowerCase())) e.preventDefault();
    });
  });
  /** What the window shows; null before the first one. */
  let shown: { user: string; dataset: string; file: string } | null = null;
  /** Counts the opens, so a slow read for an earlier one is dropped. */
  let turn = 0;
  /** Object URLs of the decoded originals handed to the frame. */
  let urls: string[] = [];
  /** 'none', 'loading', 'done', or 'failed: <why>': the originals of what is shown. */
  let originalState = 'none';

  /** Where the window opens first: right of the open panels, as large as fits. */
  function firstPlace(): WindowPlace {
    const left = render.visibleRect().left + MARGIN;
    return { left, top: TOP, width: Math.min(SIZE[0], innerWidth - left - MARGIN), height: Math.min(SIZE[1], innerHeight - TOP - MARGIN) };
  }

  const frameLoaded = (): Promise<void> =>
    new Promise((resolve) => {
      frame.addEventListener('load', () => resolve(), { once: true });
    });

  /**
   * Open the window on the textures of `user` (a unit or doodad id, or a
   * model file's name), called `name`, whose model file is `file` in `dataset`.
   */
  async function openTextures({ user, name, file, dataset }: { user: string; name: string; file: string; dataset: string }): Promise<void> {
    const built = await api.getJson<TexturesBody>(api.extensionUrl('textures', SC2));
    if (!built.built) throw new Error(`the texture viewer is not built; run: ${built.build}`);
    win.title.textContent = `textures · ${name}`;
    win.open(firstPlace());
    if (shown && shown.user === user && shown.file === file && shown.dataset === dataset) return;
    shown = { user, file, dataset };
    const mine = ++turn;
    for (const url of urls) URL.revokeObjectURL(url);
    urls = [];
    originalState = 'loading';
    const loaded = frameLoaded();
    frame.src = `${api.extensionUrl('textures', SC2)}/?${new URLSearchParams({ user, embed: '1' })}`;
    try {
      const [found] = await Promise.all([originals(context, file, dataset, urls), loaded]);
      if (mine !== turn) return;
      hdtexOf(frame).addOriginals(user, found.textures, found.failed);
      originalState = 'done';
    } catch (error) {
      if (mine === turn) originalState = `failed: ${messageOf(error)}`;
      throw error;
    }
  }

  async function openTexturesFor(category: string, id: string): Promise<void> {
    const dataset = api.requireDataset(api.currentDataset(SC2), SC2);
    const record = await api.record(category, id, dataset, SC2);
    if (!record.file) throw new Error(`${record.name} has no model file`);
    return openTextures({ user: id, name: record.name, file: record.file, dataset });
  }

  /** A bare model file goes by its file name. */
  function openTexturesOf(item: Item): Promise<void> {
    const fileName = item.path.split('\\').pop() ?? item.path;
    const record = item.source ? item.source.record : null;
    return openTextures({ user: record ? record.id : fileName, name: record ? record.name : fileName, file: item.path, dataset: item.dataset });
  }

  return {
    openTexturesFor,
    openTexturesOf,
    textureWindow: () => ({ open: win.isOpen, user: shown ? shown.user : null, file: shown ? shown.file : null, dataset: shown ? shown.dataset : null, originals: originalState }),
  };
}

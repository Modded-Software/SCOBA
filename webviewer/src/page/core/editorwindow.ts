// The editor window (SPEC-PHOTOCRAFT 9.2): PhotoCraft in a frame, in a
// movable window over the view, on the scratch of one edit session. The
// frame's address names the session's routes; the editor's bridge reads and
// writes the scratch there and tells this window what happened
// (postMessage). The window takes only messages of its own frame from its
// own address, and sends none: the page never drives the editor.
//
// The window adds no key handler to the frame, and Escape does not close
// it: the keys are the editor's (R-PC-24). It closes by its close button,
// after a question when the editor holds work it has not saved (R-PC-26).

import { editRoutes, type EditSession } from '../../shared/edits';
import type { RenderHost, UiService, WindowPlace } from './context';
import { make } from './dom';

/** The editor site, served by the server's core. */
export const EDITOR_PAGE = '/photocraft/';
/** How long the editor may take to say `ready` (R-PC-27). */
const READY_MS = 60_000;
const MARGIN = 16;
const TOP = 48; // below the view tools
const SIZE = [1100, 720] as const;

/** A session to edit, with the game and the dataset it was opened from. */
export interface EditorAsk {
  game: string;
  dataset: string;
  session: EditSession;
}

/** closed; loading: until the editor opened the scratch; opened; failed: the reason shows, with Reload Editor. */
export type EditorPhase = 'closed' | 'loading' | 'opened' | 'failed';

export interface EditorState {
  open: boolean;
  session: string | null;
  phase: EditorPhase;
  /** Why it failed; empty otherwise. */
  reason: string;
  /** The editor holds work it has not saved, as it said last. */
  unsaved: boolean;
  /** The kinds of the bridge's messages since the frame was loaded, in order. */
  messages: string[];
  /** The frame's address. */
  frame: string;
}

export interface EditorWindow {
  /** Open the editor on a session. One editor at a time: with unsaved work in the open one it asks first. False: the open one was kept. */
  open(ask: EditorAsk): Promise<boolean>;
  /** Close it, after the question when it holds unsaved work. False: kept open. */
  close(): Promise<boolean>;
  /** The session it shows; null: closed. */
  current(): EditorAsk | null;
  state(): EditorState;
}

export interface EditorParts {
  ui: Pick<UiService, 'floatingWindow'>;
  render: Pick<RenderHost, 'visibleRect'>;
  /** Ask whether the editor may close with unsaved work. True: close it, the work is lost. */
  confirmClose(ask: EditorAsk): Promise<boolean>;
  /** The editor saved the scratch. */
  saved(ask: EditorAsk): void;
  /** The window opened on a session, or closed. */
  changed(): void;
  report(failure: unknown): void;
}

export function createEditorWindow(parts: EditorParts): EditorWindow {
  const frame = make('iframe', { id: 'editor-frame', title: 'editor' });
  const reason = make('div', { className: 'editor-reason' });
  const reload = make('button', { id: 'editor-reload', className: 'primary', textContent: 'Reload Editor', hidden: true });
  const note = make('div', { id: 'editor-note' }, [reason, reload]);
  // A close that fails is reported: the window stays as it is.
  const closing = (): void => {
    close().catch(parts.report);
  };
  const win = parts.ui.floatingWindow({ id: 'editor-window', title: 'edit', escape: false, closing });
  win.body.append(frame, note);
  let shown: EditorAsk | null = null;
  let phase: EditorPhase = 'closed';
  let unsaved = false;
  let why = '';
  let waiting: number | null = null;
  const messages: string[] = [];

  function firstPlace(): WindowPlace {
    const left = parts.render.visibleRect().left + MARGIN;
    return { left, top: TOP, width: Math.min(SIZE[0], innerWidth - left - MARGIN), height: Math.min(SIZE[1], innerHeight - TOP - MARGIN) };
  }

  function settle(next: EditorPhase, text: string): void {
    phase = next;
    why = next === 'failed' ? text : '';
    reason.textContent = text;
    reason.classList.toggle('failure', next === 'failed');
    reload.hidden = next !== 'failed';
    note.hidden = next === 'opened';
    if (next !== 'loading' && waiting !== null) {
      window.clearTimeout(waiting);
      waiting = null;
    }
  }

  /** A fresh frame for the session: nothing of the one before stays in it. */
  function load(ask: EditorAsk): void {
    messages.length = 0;
    unsaved = false;
    settle('loading', 'loading the editor');
    if (waiting !== null) window.clearTimeout(waiting);
    waiting = window.setTimeout(() => {
      waiting = null;
      settle('failed', `the editor did not start in ${READY_MS / 1000} s`);
    }, READY_MS);
    frame.src = `${EDITOR_PAGE}?${new URLSearchParams({ host: editRoutes.host(ask.game, ask.session.session) })}`;
  }

  window.addEventListener('message', (event) => {
    // Only the bridge of this window's frame, from the page's own address.
    if (!shown || event.source !== frame.contentWindow || event.origin !== location.origin) return;
    const data: unknown = event.data;
    if (typeof data !== 'object' || data === null || Reflect.get(data, 'source') !== 'photocraft') return;
    const kind = String(Reflect.get(data, 'type'));
    messages.push(kind);
    if (kind === 'ready') {
      // It started in time; it shows "loading" until it opened the scratch.
      if (waiting !== null) window.clearTimeout(waiting);
      waiting = null;
    } else if (kind === 'opened') settle('opened', '');
    else if (kind === 'failed') settle('failed', String(Reflect.get(data, 'reason')));
    else if (kind === 'unsaved') unsaved = Reflect.get(data, 'unsaved') === true;
    else if (kind === 'saved') parts.saved(shown);
  });
  reload.addEventListener('click', () => {
    if (shown) load(shown);
  });

  /** Whether the open editor may go: yes when it holds no unsaved work, else what the person answers. */
  const mayLeave = async (): Promise<boolean> => !shown || !unsaved || parts.confirmClose(shown);

  async function close(): Promise<boolean> {
    if (!shown) return true;
    if (!(await mayLeave())) return false;
    shown = null;
    settle('closed', '');
    // The editor is unloaded: it holds the scratch in memory.
    frame.src = 'about:blank';
    win.close();
    parts.changed();
    return true;
  }

  async function open(ask: EditorAsk): Promise<boolean> {
    if (shown && shown.game === ask.game && shown.session.session === ask.session.session) return true;
    if (!(await mayLeave())) return false;
    shown = ask;
    win.title.textContent = `edit · ${ask.session.asset} · ${ask.session.variant}`;
    win.open(firstPlace());
    load(ask);
    parts.changed();
    return true;
  }

  return {
    open,
    close,
    current: () => shown,
    state: () => ({ open: win.isOpen, session: shown ? shown.session.session : null, phase, reason: why, unsaved, messages: [...messages], frame: frame.getAttribute('src') ?? '' }),
  };
}

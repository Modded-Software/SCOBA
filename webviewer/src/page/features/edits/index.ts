// Texture editing in PhotoCraft (SPEC-PHOTOCRAFT section 9). A tile's Edit
// Texture button (event "texture-edit") opens the edit session of a
// texture's variant in the editor window (core/editorwindow.ts). While the
// texture window or the editor window is open, the dataset's sessions are
// read every 2 s (R-PC-40): the texture window shows their states, and a
// session that turned edited, with planes not offered before, opens the
// transfer dialog once (R-PC-43, R-PC-44). With neither window open nothing
// is asked. Manage Edits… (event "edits-manage") lists the sessions.

import { editRoutes, type EditBody, type EditsBody, type EditSession, type EditTransferBody } from '../../../shared/edits';
import type { Feature } from '../../core/context';
import { make, messageOf } from '../../core/dom';
import { createEditorWindow } from '../../core/editorwindow';
import { settings } from '../../core/settings';
import { ConfirmDialog } from '../../ui/components/dialog';
import { createEditDialogs, type EditTarget } from './dialogs';

/** How often the sessions are read while a window that shows them is open. */
const POLL_MS = 2000;

/** One call of an edit route. A reply that is no success throws with the server's reason. */
async function call<T>(url: string, body?: unknown): Promise<T> {
  const response = await fetch(url, body === undefined ? {} : { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
  const answer: unknown = await response.json();
  if (!response.ok) {
    const error: unknown = Reflect.get(Object(answer), 'error');
    const reason: unknown = Reflect.get(Object(answer), 'reason');
    throw new Error(typeof error === 'string' ? `${error}${typeof reason === 'string' && reason ? `: ${reason}` : ''}` : String(response.status));
  }
  return answer as T;
}

export const editsFeature: Feature = {
  id: 'edits',
  install(context) {
    const { ui, render, events, status, store, textureWindow, testApi } = context;
    const closeAsk = new ConfirmDialog({
      id: 'editor-close-dialog',
      title: 'Close Editor',
      yesText: 'Close Editor',
      noText: 'Keep Editing',
      danger: true,
      content: [make('div', { className: 'edit-note', textContent: 'The editor holds work it has not saved. The work since the last save is lost.' })],
    });
    /** The sessions as read last, by game and dataset. */
    const known = new Map<string, EditSession[]>();
    const keyOf = (game: string, dataset: string): string => `${game}|${dataset}`;

    const editor = createEditorWindow({ ui, render, confirmClose: () => closeAsk.ask(), saved: () => readNow(), changed: () => readNow(), report: status.reportFailure });

    const dialogs = createEditDialogs({
      async transfer(target) {
        await call<EditTransferBody>(editRoutes.transfer(target.game, target.dataset, target.session.session), {});
        status.setStatus(`${target.session.asset}: the edit is transferred to a new variant`);
        // The new variant shows in the tiles as a request, then as a variant (R-PC-56).
        events.emit('textures-changed', { game: target.game, dataset: target.dataset });
        readNow();
      },
      async discard(target) {
        // The editor on this session closes first; with unsaved work it asks, and may stay.
        if (editor.current()?.session.session === target.session.session && !(await editor.close())) return false;
        await call(editRoutes.discard(target.game, target.dataset, target.session.session), {});
        const kept = Object.entries(store.read(settings.editsOffered)).filter(([session]) => session !== target.session.session);
        store.write(settings.editsOffered, Object.fromEntries(kept));
        status.setStatus(`${target.session.asset}: the edit is discarded`);
        readNow();
        return true;
      },
      resume: (target) => {
        editor.open(target).catch(status.reportFailure);
      },
      report: status.reportFailure,
    });

    /** The datasets whose sessions a window shows now: the texture window's, the editor's. */
    function shown(): { game: string; dataset: string }[] {
      const found: { game: string; dataset: string }[] = [];
      const page = textureWindow.editing();
      if (page) found.push(page);
      const edited = editor.current();
      if (edited && !found.some((one) => one.game === edited.game && one.dataset === edited.dataset)) found.push({ game: edited.game, dataset: edited.dataset });
      return found;
    }

    /** Open the transfer dialog for an edited session whose rendered planes were not offered yet. */
    function offer(game: string, dataset: string, sessions: readonly EditSession[]): void {
      if (dialogs.busy() || closeAsk.dialog.isOpen) return;
      const offered = store.read(settings.editsOffered);
      // A scratch that cannot give every plane has a reason: it opens no dialog (R-PC-75).
      const next = sessions.find((one) => one.state === 'edited' && !one.reason && !one.checking && !one.checkError && one.changed.length > 0 && offered[one.session] !== JSON.stringify(one.rendered));
      if (!next) return;
      store.write(settings.editsOffered, { ...offered, [next.session]: JSON.stringify(next.rendered) });
      dialogs.offer({ game, dataset, session: next });
    }

    /** What was said of a scratch that cannot give every plane, or could not be checked, by session. */
    const told = new Map<string, string>();
    /** Such a scratch is reported with its reason when it is found, once per reason (R-PC-75). */
    function tell(sessions: readonly EditSession[]): void {
      for (const one of sessions) {
        const reason = one.state === 'edited' && one.reason ? one.reason : one.checkError ? `its scratch could not be checked: ${one.checkError}` : '';
        if (reason && told.get(one.session) !== reason) status.setStatus(`${one.asset} (${one.variant}): the edit cannot be transferred: ${reason}`, { failure: true });
        if (reason) told.set(one.session, reason);
        else told.delete(one.session);
      }
    }

    let reading = false;
    /** Asked while a read ran: one more follows it. */
    let again = false;
    let failure = '';
    async function read(): Promise<void> {
      for (const { game, dataset } of shown()) {
        const { sessions } = await call<EditsBody>(editRoutes.list(game, dataset));
        known.set(keyOf(game, dataset), sessions);
        textureWindow.edits(game, dataset, sessions);
        dialogs.took(game, dataset, sessions);
        tell(sessions);
        offer(game, dataset, sessions);
      }
    }
    /** Read the sessions now. One read at a time; a failure is reported once, not every 2 s. */
    function readNow(): void {
      if (reading) {
        again = true;
        return;
      }
      if (!shown().length) return;
      reading = true;
      read()
        .then(
          () => {
            failure = '';
          },
          (error: unknown) => {
            const text = `the edit sessions cannot be read: ${messageOf(error)}`;
            if (text !== failure) status.reportFailure(new Error(text));
            failure = text;
          },
        )
        .finally(() => {
          reading = false;
          if (again) {
            again = false;
            readNow();
          }
        });
    }
    window.setInterval(readNow, POLL_MS);

    async function openEdit(target: { game: string; dataset: string; asset: string; variant: string }): Promise<void> {
      status.setStatus(`${target.asset}: opening the edit of ${target.variant}`);
      const { session } = await call<EditBody>(editRoutes.open(target.game, target.dataset), { asset: target.asset, variant: target.variant });
      await editor.open({ game: target.game, dataset: target.dataset, session });
    }
    events.on('texture-edit', (target) => {
      openEdit(target).catch(status.reportFailure);
    });
    events.on('edits-manage', ({ game, dataset }) => {
      call<EditsBody>(editRoutes.list(game, dataset)).then(({ sessions }) => {
        known.set(keyOf(game, dataset), sessions);
        dialogs.manage(game, dataset, sessions);
      }, status.reportFailure);
    });

    testApi.viewer({
      /** The edit sessions: the editor window, the dialogs, what was read and what was offered. */
      edits: {
        state: () => ({ editor: editor.state(), closing: closeAsk.dialog.isOpen, dialogs: dialogs.state(), sessions: Object.fromEntries(known), offered: store.read(settings.editsOffered), told: Object.fromEntries(told) }),
        /** Open the editor window on a session as it was read, as Resume Edit of a list does. */
        resume: (target: EditTarget) => editor.open(target),
      },
    });
  },
};

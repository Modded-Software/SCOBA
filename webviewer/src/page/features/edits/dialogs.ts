// The dialogs of the edit sessions (SPEC-PHOTOCRAFT 9.4, 9.5): the transfer
// of an edit to a new variant, and the list of a dataset's sessions. A
// transfer offers nothing about skins: it only makes the variant (R-PC-51).
// A discard asks again first, naming the texture.

import { editRoutes, type EditSession } from '../../../shared/edits';
import { ORIGINAL } from '../../../shared/textures';
import { make, messageOf } from '../../core/dom';
import { ConfirmDialog, Dialog } from '../../ui/components/dialog';

/** A session with the game and the dataset it is shown for. */
export interface EditTarget {
  game: string;
  dataset: string;
  session: EditSession;
}

export interface EditDialogParts {
  /** Start the transfer. A refusal rejects with its reason, and nothing changed. */
  transfer(target: EditTarget): Promise<void>;
  /** Discard the session. False: it was kept (the editor on it stays open). */
  discard(target: EditTarget): Promise<boolean>;
  /** Open the editor window on the session. */
  resume(target: EditTarget): void;
  report(failure: unknown): void;
}

export interface EditDialogsState {
  transfer: { open: boolean; session: string | null; changed: string[]; lines: string[]; pictures: string[]; error: string; buttons: string[] };
  list: { open: boolean; rows: { session: string; texture: string; variant: string; state: string; lines: string[]; buttons: string[] }[] };
  discard: { open: boolean; text: string };
}

export interface EditDialogs {
  /** Open the transfer dialog on an edited session. */
  offer(target: EditTarget): void;
  /** Open the list of a dataset's sessions. */
  manage(game: string, dataset: string, sessions: readonly EditSession[]): void;
  /** The dataset's sessions were read again: an open list shows them. */
  took(game: string, dataset: string, sessions: readonly EditSession[]): void;
  /** A dialog is open: no other is offered meanwhile. */
  busy(): boolean;
  state(): EditDialogsState;
}

const sizeOf = (session: EditSession): string => session.size.join('x');
const textsOf = (node: ParentNode, selector: string): string[] => [...node.querySelectorAll(selector)].map((one) => one.textContent);

export function createEditDialogs(parts: EditDialogParts): EditDialogs {
  // ---- Discard Edit: the question before a discard ----
  const discardText = make('div', { className: 'edit-note' });
  const discardAsk = new ConfirmDialog({ id: 'edit-discard-dialog', title: 'Discard Edit', yesText: 'Discard Edit', danger: true, content: [discardText] });
  async function discard(target: EditTarget): Promise<boolean> {
    discardText.textContent = `Discard the edit of ${target.session.asset} (${target.session.variant})? Its scratch and its layers are deleted. The variants its transfers made stay.`;
    return (await discardAsk.ask()) && parts.discard(target);
  }

  // ---- Transfer Edit to Texture ----
  const transfer = new Dialog({ id: 'edit-transfer-dialog', title: 'Transfer Edit to Texture' });
  const what = make('div', { className: 'edit-what' });
  const planes = make('div', { className: 'edit-planes' });
  const notes = make('div', { className: 'edit-notes' });
  const error = make('div', { className: 'edit-error failure' });
  const yes = make('button', { id: 'edit-transfer-yes', className: 'primary', textContent: 'Transfer Edit' });
  const keep = make('button', { id: 'edit-transfer-keep', textContent: 'Keep Editing' });
  const drop = make('button', { id: 'edit-transfer-discard', className: 'danger', textContent: 'Discard Edit' });
  transfer.body.append(what, planes, notes, error, make('div', { className: 'answers' }, [drop, keep, yes]));
  let offered: EditTarget | null = null;

  function picture(target: EditTarget, kind: 'base' | 'rendered', plane: string, label: string): HTMLElement {
    // The address carries the plane's pixel hash where it has one: a new picture has a new address.
    const version = kind === 'rendered' ? (target.session.rendered[plane] ?? '') : target.session.session;
    const image = make('img', { src: editRoutes.picture(target.game, target.session.session, kind, plane, version), alt: `${plane}, ${label}`, draggable: false });
    image.dataset['kind'] = kind;
    image.dataset['plane'] = plane;
    return make('figure', {}, [image, make('figcaption', { textContent: label })]);
  }

  function offer(target: EditTarget): void {
    const { session } = target;
    offered = target;
    what.textContent = `${session.asset} · ${session.variant} · ${sizeOf(session)}`;
    planes.replaceChildren(
      ...session.changed.map((plane) => make('div', { className: 'edit-plane' }, [make('div', { className: 'edit-plane-name', textContent: plane }), make('div', { className: 'edit-pair' }, [picture(target, 'base', plane, 'before'), picture(target, 'rendered', plane, 'your edit')])])),
    );
    const same = session.planes.filter((plane) => !session.changed.includes(plane));
    const lines: string[] = [];
    if (same.length) lines.push(`not changed: ${same.join(', ')}`);
    if (session.leftOut.length) lines.push(`not in a plane group, left out: ${session.leftOut.join(', ')}`);
    const kept = session.variant === ORIGINAL ? 'The original stays as it is.' : `${session.variant} and the original stay as they are.`;
    lines.push(`A new variant of ${session.asset} will be made from your edit. ${kept} No skin and no bake changes.`);
    notes.replaceChildren(...lines.map((line) => make('div', { className: 'edit-note', textContent: line })));
    error.textContent = '';
    yes.disabled = false;
    transfer.open();
  }

  yes.addEventListener('click', () => {
    const mine = offered;
    if (!mine) return;
    yes.disabled = true;
    error.textContent = '';
    parts.transfer(mine).then(
      () => {
        offered = null;
        transfer.close();
      },
      // A refused transfer shows its reason here; nothing changed (R-PC-53).
      (failure: unknown) => {
        error.textContent = messageOf(failure);
        yes.disabled = false;
      },
    );
  });
  // Keep Editing: the session stays edited, with its mark and its entry in the list.
  keep.addEventListener('click', () => transfer.close());
  drop.addEventListener('click', () => {
    const mine = offered;
    if (!mine) return;
    discard(mine).then(
      (gone) => {
        if (!gone) return;
        offered = null;
        transfer.close();
      },
      (failure: unknown) => {
        error.textContent = messageOf(failure);
      },
    );
  });

  // ---- Manage Edits ----
  const list = new Dialog({ id: 'edits-dialog', title: 'Manage Edits' });
  const rows = make('div', { className: 'edit-sessions' });
  const listError = make('div', { className: 'edit-error failure' });
  list.body.append(rows, listError);
  let listed: { game: string; dataset: string } | null = null;

  function row(target: EditTarget): HTMLElement {
    const { session } = target;
    const lines = [`${session.variant} · ${sizeOf(session)}`];
    if (session.reason) lines.push(session.reason);
    if (session.checkError) lines.push(`its scratch could not be checked: ${session.checkError}`);
    if (session.changed.length) lines.push(`changed: ${session.changed.join(', ')}`);
    if (session.leftOut.length) lines.push(`not in a plane group, left out: ${session.leftOut.join(', ')}`);
    if (session.transfers.length) lines.push(`transferred to: ${session.transfers.join(', ')}`);
    lines.push(session.scratchChanged === null ? 'the scratch is not there' : `scratch last changed ${new Date(session.scratchChanged).toLocaleString()}`);
    lines.push(session.scratch);
    const resume = make('button', { className: 'edit-resume', textContent: 'Resume Edit' });
    resume.addEventListener('click', () => {
      list.close();
      parts.resume(target);
    });
    const buttons: HTMLElement[] = [resume];
    // A scratch that cannot give every plane has a reason, and no transfer (R-PC-75).
    if (session.state === 'edited' && !session.reason && session.changed.length) {
      const send = make('button', { className: 'edit-transfer', textContent: 'Transfer Edit…' });
      send.addEventListener('click', () => {
        list.close();
        offer(target);
      });
      buttons.push(send);
    }
    const remove = make('button', { className: 'danger edit-discard', textContent: 'Discard Edit' });
    remove.addEventListener('click', () => {
      listError.textContent = '';
      discard(target).catch((failure: unknown) => {
        listError.textContent = messageOf(failure);
      });
    });
    buttons.push(remove);
    const node = make('div', { className: 'edit-session' }, [
      make('div', { className: 'edit-session-name', textContent: session.asset }),
      make('div', { className: `edit-session-state ${session.state}`, textContent: session.checking ? `${session.state}, checking` : session.state }),
      ...lines.map((line) => make('div', { className: 'edit-note', textContent: line })),
      make('div', { className: 'answers' }, buttons),
    ]);
    node.dataset['session'] = session.session;
    return node;
  }

  function fill(game: string, dataset: string, sessions: readonly EditSession[]): void {
    rows.replaceChildren(...(sessions.length ? sessions.map((session) => row({ game, dataset, session })) : [make('div', { className: 'edit-note', textContent: `${dataset} has no edit session.` })]));
  }

  function manage(game: string, dataset: string, sessions: readonly EditSession[]): void {
    listed = { game, dataset };
    listError.textContent = '';
    fill(game, dataset, sessions);
    list.open();
  }

  function took(game: string, dataset: string, sessions: readonly EditSession[]): void {
    if (list.isOpen && listed && listed.game === game && listed.dataset === dataset) fill(game, dataset, sessions);
  }

  function state(): EditDialogsState {
    return {
      transfer: {
        open: transfer.isOpen,
        session: transfer.isOpen && offered ? offered.session.session : null,
        changed: textsOf(planes, '.edit-plane-name'),
        lines: textsOf(notes, '.edit-note'),
        pictures: [...planes.querySelectorAll('img')].map((image) => `${image.dataset['kind'] ?? ''}/${image.dataset['plane'] ?? ''}:${image.complete && image.naturalWidth > 0 ? image.naturalWidth : 'none'}`),
        error: error.textContent,
        buttons: textsOf(transfer.body, 'button'),
      },
      list: {
        open: list.isOpen,
        rows: [...rows.querySelectorAll<HTMLElement>('.edit-session')].map((node) => ({
          session: node.dataset['session'] ?? '',
          texture: node.querySelector('.edit-session-name')?.textContent ?? '',
          variant: (node.querySelector('.edit-note')?.textContent ?? '').split(' · ')[0] ?? '',
          state: node.querySelector('.edit-session-state')?.textContent ?? '',
          lines: textsOf(node, '.edit-note'),
          buttons: textsOf(node, 'button'),
        })),
      },
      discard: { open: discardAsk.dialog.isOpen, text: discardText.textContent },
    };
  }

  return { offer, manage, took, busy: () => transfer.isOpen || list.isOpen || discardAsk.dialog.isOpen, state };
}

// Modal dialogs: a plain one, and one that asks a yes or no question.

import { make } from '../../core/dom';

/**
 * A modal dialog with a title, a body and a close button. Escape, the
 * close button and a click outside the box close it.
 */
export class Dialog {
  readonly node: HTMLDialogElement;
  readonly body: HTMLDivElement;

  constructor({ id, title }: { id: string; title: string }) {
    const close = make('button', { className: 'dialog-close', textContent: '×', title: 'close' });
    close.addEventListener('click', () => this.close());
    const head = make('div', { className: 'dialog-head' }, [make('span', { textContent: title }), close]);
    this.body = make('div', { className: 'dialog-body' });
    this.node = make('dialog', { id, className: 'dialog' }, [head, this.body]);
    this.node.addEventListener('click', (e) => {
      if (e.target === this.node) this.close(); // the backdrop
    });
    document.body.append(this.node);
  }

  open(): void {
    if (!this.node.open) this.node.showModal();
  }

  close(): void {
    if (this.node.open) this.node.close();
  }

  get isOpen(): boolean {
    return this.node.open;
  }
}

export interface ConfirmOptions {
  /** Of the dialog, "<name>-dialog"; the buttons are "<name>-yes" and "<name>-no". */
  id: string;
  title: string;
  yesText: string;
  noText?: string;
  /** Nodes above the buttons. */
  content?: readonly Node[];
  /** The yes button deletes or discards: it is red (R-VIEW-136). */
  danger?: boolean;
}

/**
 * A small dialog with a question and two answer buttons. `ask()` opens it
 * and resolves true (yes) or false (no, Escape, the x, the backdrop).
 */
export class ConfirmDialog {
  readonly dialog: Dialog;
  readonly yes: HTMLButtonElement;
  readonly no: HTMLButtonElement;
  private answer: ((value: boolean) => void) | null = null;

  constructor({ id, title, yesText, noText = 'Cancel', content = [], danger = false }: ConfirmOptions) {
    const name = id.replace(/-dialog$/, '');
    this.dialog = new Dialog({ id, title });
    this.dialog.node.classList.add('confirm-dialog');
    this.yes = make('button', { id: `${name}-yes`, className: danger ? 'primary danger' : 'primary', textContent: yesText });
    this.no = make('button', { id: `${name}-no`, textContent: noText });
    this.dialog.body.append(...content, make('div', { className: 'answers' }, [this.no, this.yes]));
    this.yes.addEventListener('click', () => this.settle(true));
    this.no.addEventListener('click', () => this.settle(false));
    this.dialog.node.addEventListener('close', () => this.settle(false));
  }

  /** Answer the open question, as a button would (the landmark name box answers on Enter). */
  settle(value: boolean): void {
    const done = this.answer;
    this.answer = null;
    this.dialog.close();
    if (done) done(value);
  }

  ask(): Promise<boolean> {
    return new Promise((resolve) => {
      this.answer = resolve;
      this.dialog.open();
    });
  }
}

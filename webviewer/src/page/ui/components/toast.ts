// A note that slides in from an edge of the page: a text and buttons.

import { make } from '../../core/dom';

export interface ToastOptions {
  id: string;
  /** 'bottom' (default) slides up from the bottom edge, 'top' down from the top edge. */
  place?: 'bottom' | 'top';
  role?: string;
}

/** `show(text, centre)` puts it up, centred on the page x `centre`. */
export class Toast {
  readonly text: HTMLSpanElement;
  readonly node: HTMLDivElement;

  constructor({ id, place = 'bottom', role = 'alertdialog' }: ToastOptions) {
    this.text = make('span', { className: 'text' });
    this.node = make('div', { id, className: `toast ${place}` }, [this.text]);
    this.node.setAttribute('role', role);
    document.body.append(this.node);
  }

  addButton(id: string, label: string): HTMLButtonElement {
    const button = make('button', { id, textContent: label });
    this.node.append(button);
    return button;
  }

  show(text: string, centre: number): void {
    this.text.textContent = text;
    this.node.style.left = `${centre}px`;
    this.node.classList.add('up');
  }

  hide(): void {
    this.node.classList.remove('up');
  }

  get isUp(): boolean {
    return this.node.classList.contains('up');
  }
}

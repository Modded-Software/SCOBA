// A button that opens a list below it: the scene list, the landmarks, the
// skin list of the instance menu. A click on the button opens or closes it.
// Escape and a press outside `root` (or the area `within` names) close it. Choosing an entry closes it
// only when the owner calls close() (the skin list stays open, R-VIEW-139).
// With `steps`, the wheel over the button and Up/Down on it choose the
// entry before or after (stepper.ts, SPEC-VIEWER 16.14).

import { stepList, type ListChoices } from './stepper';

export interface DropdownOptions {
  root: HTMLElement;
  button: HTMLElement;
  list: HTMLElement;
  /** The entries the wheel and the keys step through; absent: no stepping. */
  steps?: ListChoices;
  /** The area a press inside of does not close it; absent: `root`. The skin list: its whole menu. */
  within?: () => HTMLElement | null;
}

/** The open drop-downs: one pair of window listeners closes them all. */
const open = new Set<Dropdown>();
let listening = false;

function listen(): void {
  if (listening) return;
  listening = true;
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') for (const one of [...open]) one.close();
  });
  window.addEventListener('mousedown', (e) => {
    for (const one of [...open]) if (!one.root.isConnected || !(e.target instanceof Node) || !one.area().contains(e.target)) one.close();
  });
}

export class Dropdown {
  readonly root: HTMLElement;
  readonly button: HTMLElement;
  readonly list: HTMLElement;
  /** Where a press keeps it open. */
  readonly area: () => HTMLElement;

  constructor({ root, button, list, steps, within }: DropdownOptions) {
    this.root = root;
    this.button = button;
    this.list = list;
    this.area = () => within?.() ?? root;
    root.classList.add('dropdown');
    list.classList.add('dropdown-list');
    button.addEventListener('click', () => this.toggle());
    if (steps) stepList(button, steps);
    listen();
  }

  get isOpen(): boolean {
    return !this.list.hidden;
  }

  toggle(): void {
    if (this.isOpen) this.close();
    else this.show();
  }

  show(): void {
    this.list.hidden = false;
    open.add(this);
  }

  close(): void {
    this.list.hidden = true;
    open.delete(this);
  }
}

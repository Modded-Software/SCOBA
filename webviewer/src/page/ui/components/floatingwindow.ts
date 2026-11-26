// A window that floats over the page: a title bar to move it by (drag.ts),
// a close button, and a body. Hidden until open(). It is not modal. Escape
// closes it, unless its maker keeps Escape out. Its bottom right corner
// resizes it. A maker that must ask before a close takes the close button
// itself (`closing`).

import { make } from '../../core/dom';
import { draggable, placeWithin } from './drag';

/** The window event sent as a window opens; the instance menu closes on it (R-VIEW-157). */
export const WINDOW_OPENED = 'viewer-window-opened';

/** Where a window opens the first time. */
export interface Place {
  left: number;
  top: number;
  width: number;
  height: number;
}

export class FloatingWindow {
  readonly title: HTMLSpanElement;
  readonly head: HTMLDivElement;
  readonly body: HTMLDivElement;
  readonly node: HTMLDivElement;
  private placed = false;

  /**
   * `escape` false: Escape does not close it. `closing`: called for the close
   * button (and Escape) in place of the close; the maker closes it when it may.
   */
  constructor({ id, title, escape = true, closing }: { id: string; title: string; escape?: boolean; closing?: () => void }) {
    this.title = make('span', { className: 'window-title', textContent: title });
    const close = make('button', { className: 'window-close', textContent: '×', title: escape ? 'close (Esc)' : 'close' });
    const asked = (): void => (closing ? closing() : this.close());
    this.head = make('div', { className: 'window-head' }, [this.title, close]);
    this.body = make('div', { className: 'window-body' });
    this.node = make('div', { id, className: 'window', hidden: true }, [this.head, this.body]);
    document.body.append(this.node);
    close.addEventListener('click', asked);
    window.addEventListener('keydown', (e) => {
      if (escape && e.key === 'Escape' && this.isOpen) asked();
    });
    window.addEventListener('resize', () => {
      if (this.isOpen) this.moveTo(this.node.offsetLeft, this.node.offsetTop);
    });
    draggable({ node: this.node, handle: this.head, ignore: (target) => target === close });
  }

  /** Move the top left corner to (left, top), as far as the title bar stays reachable. */
  moveTo(left: number, top: number): void {
    placeWithin(this.node, this.head, left, top);
  }

  /** Show the window. `place` is used the first time only: later it opens where it was left. */
  open(place: Place): void {
    if (this.isOpen) return;
    this.node.hidden = false;
    window.dispatchEvent(new Event(WINDOW_OPENED));
    if (!this.placed) {
      this.node.style.width = `${place.width}px`;
      this.node.style.height = `${place.height}px`;
      this.moveTo(place.left, place.top);
      this.placed = true;
    }
  }

  close(): void {
    this.node.hidden = true;
  }

  get isOpen(): boolean {
    return !this.node.hidden;
  }
}

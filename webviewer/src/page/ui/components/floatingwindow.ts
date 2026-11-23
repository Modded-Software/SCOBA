// A window that floats over the page: a title bar to move it by, a close
// button, and a body. Hidden until open(). It is not modal. Escape closes
// it. Its bottom right corner resizes it.

import { make } from '../../core/dom';

/** Where a window opens the first time. */
export interface Place {
  left: number;
  top: number;
  width: number;
  height: number;
}

export class FloatingWindow {
  /** Pixels of the title bar that stay on the page. */
  static readonly KEEP = 80;

  readonly title: HTMLSpanElement;
  readonly head: HTMLDivElement;
  readonly body: HTMLDivElement;
  readonly node: HTMLDivElement;
  private placed = false;

  constructor({ id, title }: { id: string; title: string }) {
    this.title = make('span', { className: 'window-title', textContent: title });
    const close = make('button', { className: 'window-close', textContent: '×', title: 'close (Esc)' });
    this.head = make('div', { className: 'window-head' }, [this.title, close]);
    this.body = make('div', { className: 'window-body' });
    this.node = make('div', { id, className: 'window', hidden: true }, [this.head, this.body]);
    document.body.append(this.node);
    close.addEventListener('click', () => this.close());
    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') this.close();
    });
    window.addEventListener('resize', () => {
      if (this.isOpen) this.moveTo(this.node.offsetLeft, this.node.offsetTop);
    });
    let grab: { x: number; y: number } | null = null; // where in the window the pointer holds it
    this.head.addEventListener('pointerdown', (e) => {
      if (e.button !== 0 || e.target === close) return;
      e.preventDefault();
      grab = { x: e.clientX - this.node.offsetLeft, y: e.clientY - this.node.offsetTop };
      this.head.setPointerCapture(e.pointerId);
      // A frame in the body would take the pointer when it passes over it.
      this.node.classList.add('dragging');
    });
    this.head.addEventListener('pointermove', (e) => {
      if (grab) this.moveTo(e.clientX - grab.x, e.clientY - grab.y);
    });
    for (const name of ['pointerup', 'pointercancel'] as const) {
      this.head.addEventListener(name, () => {
        grab = null;
        this.node.classList.remove('dragging');
      });
    }
  }

  /** Move the top left corner to (left, top), as far as the title bar stays reachable. */
  moveTo(left: number, top: number): void {
    const keep = FloatingWindow.KEEP;
    const x = Math.min(Math.max(left, keep - this.node.offsetWidth), innerWidth - keep);
    const y = Math.min(Math.max(top, 0), innerHeight - this.head.offsetHeight);
    this.node.style.left = `${x}px`;
    this.node.style.top = `${y}px`;
  }

  /** Show the window. `place` is used the first time only: later it opens where it was left. */
  open(place: Place): void {
    if (this.isOpen) return;
    this.node.hidden = false;
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

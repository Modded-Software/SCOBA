// Selecting many instances, and removing them:
// - alt + left drag that starts off any unit draws a rectangle (features/controls
//   starts it); on release the instances inside it become the selection,
//   or are added to it with shift. An instance is inside when the foot, the
//   middle or the top of its column (features/pick cylinder) is inside on screen.
//   A press released without a drag is a click (features/pick), not a rectangle.
// - Delete removes the selected instances, unless a text field has the keys.
// Copy, cut and paste of the selection: features/clipboard. Moving it: features/controls.

import { app, type CoreApi, type SelectApi, type SelectBox, type Vec2 } from '../../core/app';
import { make } from '../../core/dom';

const MIN_SIZE = 4; // px: the same slop as a click (features/pick CLICK_SLOP)
const SHARES = [0, 0.5, 1]; // heights of the column tested

/** True when `target` is a field being edited: it keeps its own keys. */
export const editingText = (t: EventTarget | null): boolean => t instanceof HTMLElement && (t.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(t.tagName));

export function installSelect(core: CoreApi): SelectApi {
  const { items } = core;
  const node = make('div', { id: 'select-rect', hidden: true });
  document.body.append(node);

  /** The drag in progress, in page pixels, or null. */
  let rect: { x0: number; y0: number; x1: number; y1: number } | null = null;

  const box = (r: NonNullable<typeof rect>): SelectBox => ({ left: Math.min(r.x0, r.x1), top: Math.min(r.y0, r.y1), width: Math.abs(r.x1 - r.x0), height: Math.abs(r.y1 - r.y0) });
  const dragged = (r: NonNullable<typeof rect>): boolean => Math.hypot(r.x1 - r.x0, r.y1 - r.y0) > MIN_SIZE;

  function show(r: NonNullable<typeof rect>): void {
    node.hidden = !dragged(r);
    if (node.hidden) return;
    const b = box(r);
    Object.assign(node.style, { left: `${b.left}px`, top: `${b.top}px`, width: `${b.width}px`, height: `${b.height}px` });
  }

  function start(e: MouseEvent): void {
    rect = { x0: e.clientX, y0: e.clientY, x1: e.clientX, y1: e.clientY };
    show(rect);
  }

  function move(e: MouseEvent): void {
    if (!rect) return;
    rect.x1 = e.clientX;
    rect.y1 = e.clientY;
    show(rect);
  }

  /** Ids of the items with a tested point inside the rectangle. */
  function inside(r: NonNullable<typeof rect>): number[] {
    const b = box(r);
    const within = (p: Vec2 | null): boolean => p !== null && p[0] >= b.left && p[0] <= b.left + b.width && p[1] >= b.top && p[1] <= b.top + b.height;
    return items.filter((item) => SHARES.some((k) => within(app().itemScreen(item.id, k)))).map((item) => item.id);
  }

  function end(e: MouseEvent): void {
    if (!rect) return;
    move(e);
    // Not dragged: a click, which features/pick handles.
    if (dragged(rect)) {
      const ids = inside(rect);
      app().setSelection(e.shiftKey ? [...app().selectedIds().filter((id) => !ids.includes(id)), ...ids] : ids);
    }
    rect = null;
    node.hidden = true;
  }

  window.addEventListener('keydown', (e) => {
    if (e.key !== 'Delete') return;
    // A field being edited keeps its Delete key.
    if (editingText(e.target)) return;
    const ids = app().selectedIds();
    if (!ids.length) return;
    e.preventDefault();
    const count = app().removeMany(ids);
    app().setStatus(`removed ${count} instance${count === 1 ? '' : 's'}`);
  });

  return {
    startSelectRect: start,
    moveSelectRect: move,
    endSelectRect: end,
    editingText,
    /** The rectangle while it is dragged, in page pixels, or null. */
    selectRect: () => (rect && dragged(rect) ? box(rect) : null),
  };
}

// Selecting many instances, and removing them:
// - alt + left drag that starts off any unit draws a rectangle; on release
//   the instances inside it become the selection, or are added to it with
//   shift. An instance is inside when the foot, the middle or the top of
//   its column (core/geometry.ts cylinder) is inside on screen. A press
//   released without a drag is a click (features/pick), not a rectangle.
//   (Alt + left on a unit drags the unit: features/controls.)
// - Delete removes the selected instances, unless a text field has the keys.
// Copy, cut and paste of the selection: features/clipboard.

import type { Feature } from '../../core/context';
import { make } from '../../core/dom';
import type { SelectBox, Vec2 } from '../../core/types';

const MIN_SIZE = 4; // px: the same slop as a click (features/pick CLICK_SLOP)
const SHARES = [0, 0.5, 1]; // heights of the column tested
const LEFT = 0;

interface Drag {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export const selectFeature: Feature = {
  id: 'select',
  install({ render, scene, selection, status }) {
    const node = make('div', { id: 'select-rect', hidden: true });
    document.body.append(node);

    /** The drag in progress, in page pixels, or null. */
    let rect: Drag | null = null;

    const box = (r: Drag): SelectBox => ({ left: Math.min(r.x0, r.x1), top: Math.min(r.y0, r.y1), width: Math.abs(r.x1 - r.x0), height: Math.abs(r.y1 - r.y0) });
    const dragged = (r: Drag): boolean => Math.hypot(r.x1 - r.x0, r.y1 - r.y0) > MIN_SIZE;

    function show(r: Drag): void {
      node.hidden = !dragged(r);
      selection.setRect(dragged(r) ? box(r) : null);
      if (node.hidden) return;
      const b = box(r);
      Object.assign(node.style, { left: `${b.left}px`, top: `${b.top}px`, width: `${b.width}px`, height: `${b.height}px` });
    }

    function move(e: MouseEvent): void {
      if (!rect) return;
      rect.x1 = e.clientX;
      rect.y1 = e.clientY;
      show(rect);
    }

    /** Ids of the items with a tested point inside the rectangle. */
    function inside(r: Drag): number[] {
      const b = box(r);
      const within = (p: Vec2 | null): boolean => p !== null && p[0] >= b.left && p[0] <= b.left + b.width && p[1] >= b.top && p[1] <= b.top + b.height;
      return scene.items.filter((item) => SHARES.some((k) => within(selection.itemScreen(item.id, k)))).map((item) => item.id);
    }

    // Alt + left on the ground or the sky: the rectangle starts.
    render.canvas.addEventListener('mousedown', (e) => {
      if (e.button !== LEFT || !e.altKey || selection.hitAt(e.clientX, e.clientY)) return;
      rect = { x0: e.clientX, y0: e.clientY, x1: e.clientX, y1: e.clientY };
      show(rect);
    });
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', (e) => {
      if (!rect) return;
      move(e);
      // Not dragged: a click, which features/pick handles.
      if (dragged(rect)) {
        const ids = inside(rect);
        selection.setSelection(e.shiftKey ? [...selection.selectedIds().filter((id) => !ids.includes(id)), ...ids] : ids);
      }
      rect = null;
      node.hidden = true;
      selection.setRect(null);
    });

    window.addEventListener('keydown', (e) => {
      if (e.key !== 'Delete') return;
      // A field being edited keeps its Delete key.
      if (selection.editingText(e.target)) return;
      const ids = selection.selectedIds();
      if (!ids.length) return;
      e.preventDefault();
      const count = scene.removeMany(ids);
      status.setStatus(`removed ${count} instance${count === 1 ? '' : 's'}`);
    });
  },
};

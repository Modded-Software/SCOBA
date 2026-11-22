// Selecting many instances, and removing them:
// - alt + left drag that starts off any unit draws a rectangle (controls.js
//   starts it); on release the instances inside it become the selection,
//   or are added to it with shift. An instance is inside when the foot, the
//   middle or the top of its column (pick.js cylinder) is inside on screen.
//   A press released without a drag is a click (pick.js), not a rectangle.
// - Delete removes the selected instances, unless a text field has the keys.
// Copy, cut and paste of the selection: clipboard.js. Moving it: controls.js.
'use strict';

(() => {
  const app = window.SC2App;
  const { items, el } = app;

  const MIN_SIZE = 4; // px: the same slop as a click (pick.js CLICK_SLOP)
  const SHARES = [0, 0.5, 1]; // heights of the column tested

  const node = el('div', { id: 'select-rect', hidden: true });
  document.body.append(node);

  /** The drag in progress: { x0, y0, x1, y1 } in page pixels, or null. */
  let rect = null;

  const box = () => ({ left: Math.min(rect.x0, rect.x1), top: Math.min(rect.y0, rect.y1), width: Math.abs(rect.x1 - rect.x0), height: Math.abs(rect.y1 - rect.y0) });
  const dragged = () => Math.hypot(rect.x1 - rect.x0, rect.y1 - rect.y0) > MIN_SIZE;

  function show() {
    node.hidden = !dragged();
    if (node.hidden) return;
    const b = box();
    Object.assign(node.style, { left: `${b.left}px`, top: `${b.top}px`, width: `${b.width}px`, height: `${b.height}px` });
  }

  function start(e) {
    rect = { x0: e.clientX, y0: e.clientY, x1: e.clientX, y1: e.clientY };
    show();
  }

  function move(e) {
    if (!rect) return;
    rect.x1 = e.clientX;
    rect.y1 = e.clientY;
    show();
  }

  /** Ids of the items with a tested point inside the rectangle. */
  function inside() {
    const b = box();
    const within = (p) => p !== null && p[0] >= b.left && p[0] <= b.left + b.width && p[1] >= b.top && p[1] <= b.top + b.height;
    return items.filter((item) => SHARES.some((k) => within(app.itemScreen(item.id, k)))).map((item) => item.id);
  }

  function end(e) {
    if (!rect) return;
    move(e);
    // Not dragged: a click, which pick.js handles.
    if (dragged()) {
      const ids = inside();
      app.setSelection(e.shiftKey ? [...app.selectedIds().filter((id) => !ids.includes(id)), ...ids] : ids);
    }
    rect = null;
    node.hidden = true;
  }

  /** True when `target` is a field being edited: it keeps its own keys. */
  const editingText = (t) => t instanceof HTMLElement && (t.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(t.tagName));

  window.addEventListener('keydown', (e) => {
    if (e.key !== 'Delete') return;
    // A field being edited keeps its Delete key.
    if (editingText(e.target)) return;
    const ids = app.selectedIds();
    if (!ids.length) return;
    e.preventDefault();
    const count = app.removeMany(ids);
    app.setStatus(`removed ${count} instance${count === 1 ? '' : 's'}`);
  });

  Object.assign(app, {
    startSelectRect: start,
    moveSelectRect: move,
    endSelectRect: end,
    editingText,
    /** The rectangle while it is dragged, in page pixels, or null. */
    selectRect: () => (rect && dragged() ? box() : null),
  });
})();

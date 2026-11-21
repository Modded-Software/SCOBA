// Units under the mouse:
// - mouse-over: the unit brightens, a feathered green glow runs around its
//   outline (outline.js, drawn by main.js) and a thin ring shows under it;
// - left click: selects the unit under the mouse (green ring); a click on
//   the ground or the sky deselects, a click on another unit selects that;
// - ctrl + left hold, with a unit selected: the unit turns to face the
//   ground point under the mouse (controls.js starts it, faceSelected does it);
// - right click on a unit: a menu of its animations, the playing one
//   marked. A click plays one once, then the unit goes back to its own
//   animation; with "loop" checked it becomes the unit's own and loops.
//   The menu stays open until Escape or a click elsewhere.
// A press that moves more than CLICK_SLOP pixels is a drag (camera), not a click.
'use strict';

(() => {
  const app = window.SC2App;
  const { canvas, items, ground, el } = app;

  const CLICK_SLOP = 4; // px
  const MIN_RADIUS = 0.25; // world units: the smallest hit and ring radius
  const SELECT_RING = { width: 0.07, color: [0.2, 1.0, 0.25] };
  const HOVER_RING = { width: 0.035, color: [0.75, 1.0, 0.75] };
  const BUTTON = { left: 0, right: 2 };
  const MODEL_FRONT_OFFSET = 90; // degrees: rotation 0 faces -y, see rotationFacing

  let hovered = null; // item id
  let selected = null; // item id
  let mouse = null; // last [clientX, clientY] over the canvas
  let press = null; // { button, x, y, ctrl, moved }

  const byId = (id) => items.find((item) => item.id === id) || null;

  /** Hit and ring radius: the unit's radius from data, or half the model's reach. */
  function radius(item) {
    const r = item.unit ? item.unit.radius : item.model.bounds.r * 0.5 * Math.max(item.dataScale[0], item.dataScale[1]);
    return Math.max(MIN_RADIUS, r * item.scale);
  }

  /** The hit cylinder: from the unit's height up by the model's reach. */
  function cylinder(item) {
    const base = item.unit ? item.unit.height : 0;
    return { x: item.x, y: item.y, r: radius(item), z0: base, z1: base + Math.max(0.5, item.model.bounds.r * item.dataScale[2] * item.scale) };
  }

  /** Ray parameter where the ray enters the cylinder, or null when it misses. */
  function enter({ from, dir }, c) {
    const ox = from[0] - c.x;
    const oy = from[1] - c.y;
    const a = dir[0] * dir[0] + dir[1] * dir[1];
    let t0 = -Infinity;
    let t1 = Infinity;
    if (a < 1e-12) {
      if (ox * ox + oy * oy > c.r * c.r) return null;
    } else {
      const b = 2 * (ox * dir[0] + oy * dir[1]);
      const disc = b * b - 4 * a * (ox * ox + oy * oy - c.r * c.r);
      if (disc < 0) return null;
      const s = Math.sqrt(disc);
      t0 = (-b - s) / (2 * a);
      t1 = (-b + s) / (2 * a);
    }
    if (Math.abs(dir[2]) < 1e-12) {
      if (from[2] < c.z0 || from[2] > c.z1) return null;
    } else {
      const za = (c.z0 - from[2]) / dir[2];
      const zb = (c.z1 - from[2]) / dir[2];
      t0 = Math.max(t0, Math.min(za, zb));
      t1 = Math.min(t1, Math.max(za, zb));
    }
    if (t0 > t1 || t1 <= 0) return null;
    return Math.max(0, t0);
  }

  /** The nearest item under a page pixel, or null. */
  function itemAt(clientX, clientY) {
    const box = canvas.getBoundingClientRect();
    const ray = app.rayAt(clientX - box.left, clientY - box.top);
    let best = null;
    let bestT = Infinity;
    for (const item of items) {
      const t = enter(ray, cylinder(item));
      if (t !== null && t < bestT) {
        best = item;
        bestT = t;
      }
    }
    return best;
  }

  const ring = (item, look) => (item ? { x: item.x, y: item.y, radius: radius(item), ...look } : null);

  /** Each frame, before drawing: what is under the mouse, highlights and rings. */
  function updatePick() {
    const under = mouse && !menuItem() ? itemAt(mouse[0], mouse[1]) : null;
    hovered = under ? under.id : null;
    for (const item of items) item.instance.highlight = item.id === hovered ? 1 : 0;
    const sel = byId(selected);
    ground.rings[0] = ring(sel, SELECT_RING);
    ground.rings[1] = hovered !== selected ? ring(byId(hovered), HOVER_RING) : null;
    // Called after endOneShots: a one-shot that ended shows as idle again.
    markPlaying();
  }

  /** Turn the selected unit to face the ground point under a mouse event. */
  function faceSelected(e) {
    const item = byId(selected);
    const point = app.eventGround(e);
    if (!item || !point) return;
    const dx = point[0] - item.x;
    const dy = point[1] - item.y;
    if (Math.hypot(dx, dy) < 1e-3) return;
    app.setRotation(item, rotationFacing((Math.atan2(dy, dx) * 180) / Math.PI));
  }

  /**
   * The rotation that makes a model face `angle` (degrees, from +x towards
   * +y). At rotation 0 a model faces -y (operator 2026-11-21: facing the
   * mouse came out 90 degrees clockwise of it). Kept in (-180, 180].
   */
  function rotationFacing(angle) {
    const rot = angle + MODEL_FRONT_OFFSET;
    return rot > 180 ? rot - 360 : rot <= -180 ? rot + 360 : rot;
  }

  /** An item was removed (id), or all were (null). */
  function forget(id) {
    if (id === null || selected === id) selected = null;
    if (id === null || hovered === id) hovered = null;
    if (id === null || (menu && menu.itemId === id)) closeMenu();
    updatePick();
  }

  // ---- animation menu ----

  let menu = null; // { node, itemId }
  const menuItem = () => (menu ? byId(menu.itemId) : null);
  // Loop the chosen animation (it becomes the unit's own), or play it once
  // and go back to idle. Kept from one menu to the next.
  let loopChoice = false;

  function closeMenu() {
    if (menu) menu.node.remove();
    menu = null;
  }

  /** Mark the menu entry of the animation the unit plays now. */
  function markPlaying() {
    const item = menuItem();
    if (!item) return;
    const now = String(item.instance.sequence);
    for (const button of menu.node.querySelectorAll('button[data-sequence]')) button.classList.toggle('playing', button.dataset.sequence === now);
  }

  function openMenu(item, clientX, clientY) {
    closeMenu();
    const entries = item.model.sequences.map((s, i) => {
      const button = el('button', { type: 'button', textContent: s.name });
      button.dataset.sequence = String(i);
      // The menu stays open: the next pick is one click away.
      button.addEventListener('click', () => {
        if (loopChoice) app.loopSequence(item, i);
        else app.playOnce(item, i);
        markPlaying();
      });
      return el('li', {}, [button]);
    });
    const title = el('div', { className: 'title', textContent: item.unit ? item.unit.name : item.path.split('\\').pop() });
    const loop = el('input', { type: 'checkbox', className: 'loop', checked: loopChoice });
    loop.addEventListener('change', () => {
      loopChoice = loop.checked;
    });
    const loopLabel = el('label', { className: 'loop-choice', title: 'checked: the animation loops; unchecked: it plays once, then idle' }, [loop, 'loop']);
    const body = entries.length ? el('ul', {}, entries) : el('div', { className: 'empty', textContent: 'no animations' });
    const node = el('div', { id: 'anim-menu', className: 'anim-menu' }, [title, loopLabel, body]);
    document.body.append(node);
    // Inside the window: flip to the left or up when it would overflow.
    const w = node.offsetWidth;
    const h = node.offsetHeight;
    node.style.left = `${clientX + w > innerWidth ? Math.max(0, clientX - w) : clientX}px`;
    node.style.top = `${clientY + h > innerHeight ? Math.max(0, innerHeight - h) : clientY}px`;
    menu = { node, itemId: item.id };
    markPlaying();
  }

  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeMenu();
  });
  window.addEventListener(
    'mousedown',
    (e) => {
      if (menu && !menu.node.contains(e.target)) closeMenu();
    },
    true,
  );

  // ---- mouse ----

  canvas.addEventListener('mousemove', (e) => {
    mouse = [e.clientX, e.clientY];
  });
  canvas.addEventListener('mouseleave', () => {
    mouse = null;
  });
  canvas.addEventListener('mousedown', (e) => {
    press = { button: e.button, x: e.clientX, y: e.clientY, ctrl: e.ctrlKey, moved: false };
  });
  window.addEventListener('mousemove', (e) => {
    if (press && Math.hypot(e.clientX - press.x, e.clientY - press.y) > CLICK_SLOP) press.moved = true;
  });
  window.addEventListener('mouseup', (e) => {
    const p = press;
    press = null;
    if (!p || p.moved || p.button !== e.button) return;
    if (p.button === BUTTON.left) {
      // Ctrl + left with a selection turns the unit; it keeps the selection.
      if (p.ctrl && selected !== null) return;
      const item = itemAt(e.clientX, e.clientY);
      selected = item ? item.id : null;
      updatePick();
    } else if (p.button === BUTTON.right) {
      const item = itemAt(e.clientX, e.clientY);
      if (item) openMenu(item, e.clientX, e.clientY);
    }
  });

  /** For the tests: ids under the mouse and selected, and the open menu. */
  function pickState() {
    return {
      hovered,
      selected,
      menu: menu
        ? {
            item: menu.itemId,
            entries: [...menu.node.querySelectorAll('button[data-sequence]')].map((b) => b.textContent),
            // The marked entries (exactly one while an animation plays).
            playing: [...menu.node.querySelectorAll('button.playing')].map((b) => b.textContent),
            loop: menu.node.querySelector('input.loop').checked,
          }
        : null,
    };
  }

  Object.assign(app, {
    updatePick,
    faceSelected,
    forget,
    pickState,
    hasSelection: () => selected !== null,
    hoveredItem: () => byId(hovered),
    /** The page pixel of an item's hit cylinder at height share `k` (0 base, 1 top). */
    itemScreen: (id, k = 0.5) => {
      const item = byId(id);
      if (!item) return null;
      const c = cylinder(item);
      return app.screenOf([c.x, c.y, c.z0 + (c.z1 - c.z0) * k]);
    },
  });
})();

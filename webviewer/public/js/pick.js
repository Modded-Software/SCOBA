// Units under the mouse. "Under the mouse" goes by pixel: the unit whose
// solid surface is drawn at the mouse (hitAt, pickbuffer.js). Blended
// parts (glows, haze) are see-through and do not count.
// - mouse-over: the unit brightens, a feathered green glow runs around its
//   outline (outline.js, drawn by main.js) and a thin ring shows under it;
// - left click: selects the unit under the mouse (green ring); a click on
//   the ground or the sky deselects, a click on another unit selects that;
//   the instances panel marks the selected unit's row (and a row click
//   selects its unit);
// - shift + left click: adds the unit under the mouse to the selection, or
//   takes it out; on the ground it keeps the selection. Every selected
//   unit has a ring. (The select rectangle and Delete are in select.js.)
// - ctrl + left hold, with units selected: they turn to face the
//   ground point under the mouse (controls.js starts it, faceSelected does it);
// - alt + left hold on a unit: drags the unit over the ground (controls.js);
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
  // itemPixel (tests): the search around the unit's column, in page pixels.
  const PIXEL_REACH = 60;
  const PIXEL_STEP = 4;
  const PIXEL_MARGINS = [12, 6, 3];
  const MODEL_FRONT_OFFSET = 90; // degrees: rotation 0 faces -y, see rotationFacing

  let hovered = null; // item id
  let selected = null; // item id: the one selected last (it is in `selection`)
  const selection = new Set(); // item ids
  let mouse = null; // last [clientX, clientY] over the canvas
  let press = null; // { button, x, y, ctrl, shift, moved }

  const byId = (id) => items.find((item) => item.id === id) || null;

  /**
   * Ring radius: the unit's radius from data, or half the model's
   * reach. A doodad's data radius is the same 0.5 for a shrub and a ruin,
   * so a doodad takes the model's reach too.
   */
  function radius(item) {
    const r = item.unit && !item.unit.doodad ? item.unit.radius : item.model.bounds.r * 0.5 * Math.max(item.dataScale[0], item.dataScale[1]);
    return Math.max(MIN_RADIUS, r * item.scale);
  }

  /**
   * The unit's column: from the unit's height up by the model's reach. The
   * rings and the select rectangle use it; the mouse hit does not (hitAt).
   */
  function cylinder(item) {
    const base = app.baseHeight(item.unit);
    return { x: item.x, y: item.y, r: radius(item), z0: base, z1: base + Math.max(0.5, item.model.bounds.r * item.dataScale[2] * item.scale) };
  }

  /** The ray through a page pixel. */
  function rayAtPage(clientX, clientY) {
    const box = canvas.getBoundingClientRect();
    return app.rayAt(clientX - box.left, clientY - box.top);
  }

  /** Ray parameter of the point nearest to the item's base centre (0 when that is behind the ray's start). */
  function nearest({ from, dir }, item) {
    const to = [item.x - from[0], item.y - from[1], app.baseHeight(item.unit) - from[2]];
    const t = (to[0] * dir[0] + to[1] * dir[1] + to[2] * dir[2]) / (dir[0] * dir[0] + dir[1] * dir[1] + dir[2] * dir[2]);
    return Math.max(0, t);
  }

  /**
   * Can the ray touch the item at all? The sphere the renderer culls with:
   * the model's reach around the unit, as drawn. Only these items are
   * drawn for the pixel test.
   */
  function inReach(ray, item) {
    const t = nearest(ray, item);
    const reach = item.model.bounds.r * Math.max(...item.dataScale) * item.scale;
    const d = [ray.from[0] + ray.dir[0] * t - item.x, ray.from[1] + ray.dir[1] * t - item.y, ray.from[2] + ray.dir[2] * t - app.baseHeight(item.unit)];
    return d[0] * d[0] + d[1] * d[1] + d[2] * d[2] <= reach * reach;
  }

  /**
   * The item drawn at a page pixel, and the point of the mouse ray nearest
   * to its base centre; or null. By pixel (pickbuffer.js): the item whose
   * solid surface shows there, so the hit follows the picture, not a
   * volume around the unit.
   */
  function hitAt(clientX, clientY) {
    const box = canvas.getBoundingClientRect();
    if (clientX < box.left || clientY < box.top || clientX >= box.right || clientY >= box.bottom) return null;
    const ray = rayAtPage(clientX, clientY);
    const near = items.filter((item) => item.instance.rendered && item.instance.scene && inReach(ray, item));
    const k = canvas.width / canvas.clientWidth;
    const x = Math.min(canvas.width - 1, Math.floor((clientX - box.left) * k));
    const y = Math.min(canvas.height - 1, Math.floor((clientY - box.top) * k));
    const index = app.pickBuffer.read(near.map((item) => item.instance), x, y, canvas.width, canvas.height);
    if (index < 0) return null;
    if (index >= near.length) throw new Error(`pick: pixel names instance ${index} of ${near.length}`);
    const best = near[index];
    const t = nearest(ray, best);
    return { item: best, point: [0, 1, 2].map((i) => ray.from[i] + ray.dir[i] * t) };
  }

  /** The nearest item under a page pixel, or null. */
  function itemAt(clientX, clientY) {
    const hit = hitAt(clientX, clientY);
    return hit ? hit.item : null;
  }

  /** Where the ray through a page pixel meets the level plane at height z, or null (parallel or behind). */
  function planeAt(clientX, clientY, z) {
    const { from, dir } = rayAtPage(clientX, clientY);
    if (Math.abs(dir[2]) < 1e-9) return null;
    const t = (z - from[2]) / dir[2];
    return t > 0 ? [from[0] + dir[0] * t, from[1] + dir[1] * t] : null;
  }

  const ring = (item, look) => (item ? { x: item.x, y: item.y, radius: radius(item), ...look } : null);

  /** Each frame, before drawing: what is under the mouse, highlights and rings. */
  function updatePick() {
    const under = mouse && !menuItem() ? itemAt(mouse[0], mouse[1]) : null;
    hovered = under ? under.id : null;
    for (const item of items) item.instance.highlight = item.id === hovered ? 1 : 0;
    // Rings: [the one selected last, mouse-over, the other selected ones...].
    ground.rings.length = 2;
    ground.rings[0] = ring(byId(selected), SELECT_RING);
    ground.rings[1] = hovered !== null && !selection.has(hovered) ? ring(byId(hovered), HOVER_RING) : null;
    for (const id of selection) if (id !== selected) ground.rings.push(ring(byId(id), SELECT_RING));
    // Called after endOneShots: a one-shot that ended shows as idle again.
    markPlaying();
  }

  /** Turn the selected units to face the ground point under a mouse event. */
  function faceSelected(e) {
    const point = app.eventGround(e);
    if (!point) return;
    for (const id of selection) {
      const item = byId(id);
      const dx = point[0] - item.x;
      const dy = point[1] - item.y;
      if (Math.hypot(dx, dy) < 1e-3) continue;
      app.setRotation(item, rotationFacing((Math.atan2(dy, dx) * 180) / Math.PI));
    }
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

  /**
   * Make the items `ids` the selection (ids of no item are dropped). The
   * last one is the one "selected last". The instances panel marks their
   * rows (scene.js markSelected), so a pick in the view shows in the list.
   */
  function setSelection(ids) {
    selection.clear();
    for (const id of ids) if (byId(id)) selection.add(id);
    selected = selection.size ? [...selection].pop() : null;
    updatePick();
    app.markSelected(selection, selected);
  }

  /** Select one item by id (null: none). */
  const select = (id) => setSelection(id === null ? [] : [id]);

  /** Add an item to the selection, or take it out when it is in. */
  function toggleSelected(id) {
    const next = new Set(selection);
    if (!next.delete(id)) next.add(id);
    setSelection([...next]);
  }

  /** An item was removed (id), or all were (null). */
  function forget(id) {
    if (id === null) setSelection([]);
    else if (selection.has(id)) setSelection([...selection].filter((other) => other !== id));
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
    const choices = [loopLabel];
    // A model with both texture sets: the HD one on or off (hd.js).
    if (item.hdLayers) {
      const hd = el('input', { type: 'checkbox', className: 'hd', checked: item.hd });
      hd.addEventListener('change', () => app.setHd(item, hd.checked).catch(app.reportFailure));
      choices.push(el('label', { className: 'loop-choice hd-choice', title: 'checked: the upscaled HD textures; unchecked: the standard ones (Ctrl+H)' }, [hd, 'hd']));
    }
    const body = entries.length ? el('ul', {}, entries) : el('div', { className: 'empty', textContent: 'no animations' });
    const node = el('div', { id: 'anim-menu', className: 'anim-menu' }, [title, ...choices, body]);
    document.body.append(node);
    // Inside the window: flip to the left or up when it would overflow.
    const w = node.offsetWidth;
    const h = node.offsetHeight;
    node.style.left = `${clientX + w > innerWidth ? Math.max(0, clientX - w) : clientX}px`;
    node.style.top = `${clientY + h > innerHeight ? Math.max(0, innerHeight - h) : clientY}px`;
    menu = { node, itemId: item.id };
    markPlaying();
  }

  /** Show the open menu's checkboxes as the choices are now (changed by a key, hd.js). */
  function refreshMenu() {
    const item = menuItem();
    if (!item) return;
    menu.node.querySelector('input.loop').checked = loopChoice;
    const hd = menu.node.querySelector('input.hd');
    if (hd) hd.checked = item.hd;
  }

  /** Switch the "loop" choice (Ctrl+L). Returns the new choice. */
  function toggleLoop() {
    loopChoice = !loopChoice;
    refreshMenu();
    return loopChoice;
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
    press = { button: e.button, x: e.clientX, y: e.clientY, ctrl: e.ctrlKey, shift: e.shiftKey, moved: false };
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
      // Shift: add the unit or take it out; on the ground, keep the selection.
      if (p.shift) {
        if (item) toggleSelected(item.id);
      } else select(item ? item.id : null);
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
      selection: [...selection].sort((a, b) => a - b),
      // The select rectangle while it is dragged (select.js), in page pixels.
      rect: app.selectRect ? app.selectRect() : null,
      menu: menu
        ? {
            item: menu.itemId,
            entries: [...menu.node.querySelectorAll('button[data-sequence]')].map((b) => b.textContent),
            // The marked entries (exactly one while an animation plays).
            playing: [...menu.node.querySelectorAll('button.playing')].map((b) => b.textContent),
            loop: menu.node.querySelector('input.loop').checked,
            // The "hd" checkbox, when the menu has one (a model with both texture sets).
            hd: menu.node.querySelector('input.hd') ? menu.node.querySelector('input.hd').checked : undefined,
          }
        : null,
      // The "loop" choice, menu open or not.
      loop: loopChoice,
    };
  }

  Object.assign(app, {
    updatePick,
    faceSelected,
    forget,
    pickState,
    select,
    setSelection,
    toggleSelected,
    toggleLoop,
    refreshMenu,
    selectedId: () => selected,
    selectedIds: () => [...selection],
    hasSelection: () => selection.size > 0,
    itemAt,
    hitAt,
    planeAt,
    hoveredItem: () => byId(hovered),
    /**
     * For the tests: a page pixel on the item's picture, where it is the one
     * under the mouse, and so are the pixels a margin around it (the widest
     * of PIXEL_MARGINS that any pixel has). The nearest such to the foot of the item's column, searched over the
     * column's box on screen widened by PIXEL_REACH; null when there is none.
     */
    itemPixel: (id) => {
      const item = byId(id);
      if (!item) return null;
      const c = cylinder(item);
      const foot = app.screenOf([c.x, c.y, c.z0]);
      const top = app.screenOf([c.x, c.y, c.z1]);
      if (!foot || !top) return null;
      const points = [];
      for (let y = Math.min(foot[1], top[1]) - PIXEL_REACH; y <= Math.max(foot[1], top[1]) + PIXEL_REACH; y += PIXEL_STEP) {
        for (let x = Math.min(foot[0], top[0]) - PIXEL_REACH; x <= Math.max(foot[0], top[0]) + PIXEL_REACH; x += PIXEL_STEP) points.push([Math.round(x), Math.round(y)]);
      }
      const far = (p) => Math.hypot(p[0] - foot[0], p[1] - foot[1]);
      points.sort((a, b) => far(a) - far(b));
      const on = (x, y) => itemAt(x, y) === item;
      // The widest margin first: a pixel well inside the picture stays on a unit that moves as it plays.
      for (const m of PIXEL_MARGINS) {
        for (const [x, y] of points) {
          if (on(x, y) && on(x - m, y) && on(x + m, y) && on(x, y - m) && on(x, y + m)) return [x, y];
        }
      }
      return null;
    },
    /** The page pixel of an item's column (cylinder) at height share `k` (0 base, 1 top). */
    itemScreen: (id, k = 0.5) => {
      const item = byId(id);
      if (!item) return null;
      const c = cylinder(item);
      return app.screenOf([c.x, c.y, c.z0 + (c.z1 - c.z0) * k]);
    },
  });
})();

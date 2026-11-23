// Units under the mouse. "Under the mouse" goes by pixel: the unit whose
// solid surface is drawn at the mouse (hitAt, core/render/pickbuffer.ts).
// Blended parts (glows, haze) are see-through and do not count.
// - mouse-over: the unit brightens, a feathered green glow runs around its
//   outline (core/render/outline.ts, drawn by the frame) and a thin ring shows under it;
// - left click: selects the unit under the mouse (green ring); a click on
//   the ground or the sky deselects, a click on another unit selects that;
//   the instances panel marks the selected unit's row (and a row click
//   selects its unit);
// - shift + left click: adds the unit under the mouse to the selection, or
//   takes it out; on the ground it keeps the selection. Every selected
//   unit has a ring. (The select rectangle and Delete are in features/select.)
// - ctrl + left hold, with units selected: they turn to face the
//   ground point under the mouse (features/controls starts it, faceSelected does it);
// - alt + left hold on a unit: drags the unit over the ground (features/controls);
// - right click on a unit: the animation menu (menu.ts).
// A press that moves more than CLICK_SLOP pixels is a drag (camera), not a click.

import type { Ring } from '../../core/render/ground';
import { app, type CoreApi, type Item, type PickApi, type Ray, type Vec2, type Vec3 } from '../../core/app';
import { cylinder, radius } from './geometry';
import { createMenu } from './menu';
import { itemPixelOf } from './probe';

const CLICK_SLOP = 4; // px
const SELECT_RING: Pick<Ring, 'width' | 'color'> = { width: 0.07, color: [0.2, 1.0, 0.25] };
const HOVER_RING: Pick<Ring, 'width' | 'color'> = { width: 0.035, color: [0.75, 1.0, 0.75] };
const BUTTON = { left: 0, right: 2 };
const MODEL_FRONT_OFFSET = 90; // degrees: rotation 0 faces -y, see rotationFacing

/** Ray parameter of the point nearest to the item's base centre (0 when that is behind the ray's start). */
function nearest({ from, dir }: Ray, item: Item): number {
  const to: Vec3 = [item.x - from[0], item.y - from[1], app().baseHeight(item.unit) - from[2]];
  const t = (to[0] * dir[0] + to[1] * dir[1] + to[2] * dir[2]) / (dir[0] * dir[0] + dir[1] * dir[1] + dir[2] * dir[2]);
  return Math.max(0, t);
}

/**
 * Can the ray touch the item at all? The sphere the renderer culls with:
 * the model's reach around the unit, as drawn. Only these items are
 * drawn for the pixel test.
 */
function inReach(ray: Ray, item: Item): boolean {
  const t = nearest(ray, item);
  const reach = item.model.bounds.r * Math.max(...item.dataScale) * item.scale;
  const d = [ray.from[0] + ray.dir[0] * t - item.x, ray.from[1] + ray.dir[1] * t - item.y, ray.from[2] + ray.dir[2] * t - app().baseHeight(item.unit)] as const;
  return d[0] * d[0] + d[1] * d[1] + d[2] * d[2] <= reach * reach;
}

/**
 * The rotation that makes a model face `angle` (degrees, from +x towards
 * +y). At rotation 0 a model faces -y (operator 2026-11-21: facing the
 * mouse came out 90 degrees clockwise of it). Kept in (-180, 180].
 */
function rotationFacing(angle: number): number {
  const rot = angle + MODEL_FRONT_OFFSET;
  return rot > 180 ? rot - 360 : rot <= -180 ? rot + 360 : rot;
}

export function installPick(core: CoreApi): PickApi {
  const { canvas, items, ground } = core;

  let hovered: number | null = null; // item id
  let selected: number | null = null; // item id: the one selected last (it is in `selection`)
  const selection = new Set<number>(); // item ids
  let mouse: Vec2 | null = null; // last [clientX, clientY] over the canvas
  let press: { button: number; x: number; y: number; ctrl: boolean; shift: boolean; moved: boolean } | null = null;

  const byId = (id: number | null): Item | null => items.find((item) => item.id === id) || null;

  /** The ray through a page pixel. */
  function rayAtPage(clientX: number, clientY: number): Ray {
    const box = canvas.getBoundingClientRect();
    return app().rayAt(clientX - box.left, clientY - box.top);
  }

  /**
   * The item drawn at a page pixel, and the point of the mouse ray nearest
   * to its base centre; or null. By pixel (core/render/pickbuffer.ts): the item whose
   * solid surface shows there, so the hit follows the picture, not a
   * volume around the unit.
   */
  function hitAt(clientX: number, clientY: number): { item: Item; point: Vec3 } | null {
    const box = canvas.getBoundingClientRect();
    if (clientX < box.left || clientY < box.top || clientX >= box.right || clientY >= box.bottom) return null;
    const ray = rayAtPage(clientX, clientY);
    const near = items.filter((item) => item.instance.rendered && item.instance.scene && inReach(ray, item));
    const k = canvas.width / canvas.clientWidth;
    const x = Math.min(canvas.width - 1, Math.floor((clientX - box.left) * k));
    const y = Math.min(canvas.height - 1, Math.floor((clientY - box.top) * k));
    const index = app().pickBuffer.read(near.map((item) => item.instance), x, y, canvas.width, canvas.height);
    if (index < 0) return null;
    const best = near[index];
    if (!best) throw new Error(`pick: pixel names instance ${index} of ${near.length}`);
    const t = nearest(ray, best);
    return { item: best, point: [ray.from[0] + ray.dir[0] * t, ray.from[1] + ray.dir[1] * t, ray.from[2] + ray.dir[2] * t] };
  }

  /** The nearest item under a page pixel, or null. */
  function itemAt(clientX: number, clientY: number): Item | null {
    const hit = hitAt(clientX, clientY);
    return hit ? hit.item : null;
  }

  /** Where the ray through a page pixel meets the level plane at height z, or null (parallel or behind). */
  function planeAt(clientX: number, clientY: number, z: number): Vec2 | null {
    const { from, dir } = rayAtPage(clientX, clientY);
    if (Math.abs(dir[2]) < 1e-9) return null;
    const t = (z - from[2]) / dir[2];
    return t > 0 ? [from[0] + dir[0] * t, from[1] + dir[1] * t] : null;
  }

  const ring = (item: Item | null, look: Pick<Ring, 'width' | 'color'>): Ring | null => (item ? { x: item.x, y: item.y, radius: radius(item), ...look } : null);

  const menu = createMenu(byId);

  /** Each frame, before drawing: what is under the mouse, highlights and rings. */
  function updatePick(): void {
    const under = mouse && !menu.item() ? itemAt(mouse[0], mouse[1]) : null;
    hovered = under ? under.id : null;
    for (const item of items) item.instance.highlight = item.id === hovered ? 1 : 0;
    // Rings: [the one selected last, mouse-over, the other selected ones...].
    const others: Ring[] = [];
    for (const id of selection) {
      const r = id !== selected ? ring(byId(id), SELECT_RING) : null;
      if (r) others.push(r);
    }
    ground.rings = [ring(byId(selected), SELECT_RING), hovered !== null && !selection.has(hovered) ? ring(byId(hovered), HOVER_RING) : null, ...others];
    // Called after endOneShots: a one-shot that ended shows as idle again.
    menu.markPlaying();
  }

  /** Turn the selected units to face the ground point under a mouse event. */
  function faceSelected(e: MouseEvent): void {
    const point = app().eventGround(e);
    if (!point) return;
    for (const id of selection) {
      const item = byId(id);
      if (!item) continue;
      const dx = point[0] - item.x;
      const dy = point[1] - item.y;
      if (Math.hypot(dx, dy) < 1e-3) continue;
      app().setRotation(item, rotationFacing((Math.atan2(dy, dx) * 180) / Math.PI));
    }
  }

  /**
   * Make the items `ids` the selection (ids of no item are dropped). The
   * last one is the one "selected last". The instances panel marks their
   * rows (ui/instances.ts markSelected), so a pick in the view shows in the list.
   */
  function setSelection(ids: Iterable<number>): void {
    selection.clear();
    for (const id of ids) if (byId(id)) selection.add(id);
    selected = selection.size ? ([...selection].pop() ?? null) : null;
    updatePick();
    app().markSelected(selection, selected);
  }

  /** Select one item by id (null: none). */
  const select = (id: number | null): void => setSelection(id === null ? [] : [id]);

  /** Add an item to the selection, or take it out when it is in. */
  function toggleSelected(id: number): void {
    const next = new Set(selection);
    if (!next.delete(id)) next.add(id);
    setSelection([...next]);
  }

  /** An item was removed (id), or all were (null). */
  function forget(id: number | null): void {
    if (id === null) setSelection([]);
    else if (selection.has(id)) setSelection([...selection].filter((other) => other !== id));
    if (id === null || hovered === id) hovered = null;
    if (id === null || menu.itemId() === id) menu.close();
    updatePick();
  }

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
      if (item) menu.open(item, e.clientX, e.clientY);
    }
  });

  return {
    updatePick,
    faceSelected,
    forget,
    /** For the tests: ids under the mouse and selected, and the open menu. */
    pickState: () => ({
      hovered,
      selected,
      selection: [...selection].sort((a, b) => a - b),
      // The select rectangle while it is dragged (features/select), in page pixels.
      rect: app().selectRect(),
      menu: menu.state(),
      // The "loop" choice, menu open or not.
      loop: menu.loop(),
    }),
    select,
    setSelection,
    toggleSelected,
    toggleLoop: menu.toggleLoop,
    refreshMenu: menu.refresh,
    selectedId: () => selected,
    selectedIds: () => [...selection],
    hasSelection: () => selection.size > 0,
    itemAt,
    hitAt,
    planeAt,
    hoveredItem: () => byId(hovered),
    itemPixel: (id) => {
      const item = byId(id);
      return item ? itemPixelOf(item, (x, y) => itemAt(x, y) === item) : null;
    },
    /** The page pixel of an item's column (cylinder) at height share `k` (0 base, 1 top). */
    itemScreen: (id, k = 0.5) => {
      const item = byId(id);
      if (!item) return null;
      const c = cylinder(item);
      return app().screenOf([c.x, c.y, c.z0 + (c.z1 - c.z0) * k]);
    },
  };
}

// The selection service (SPEC-VIEWER 6.6): which items are selected, which
// one is under the mouse, the select rectangle, and the hit tests. "Under
// the mouse" goes by pixel: the item whose solid surface is drawn there
// (core/render/pickbuffer.ts). Blended parts (glows, haze) are see-through.
// What the mouse does with them is features/pick and features/controls.

import type { CameraService, SelectionService } from './context';
import type { EventBus, ViewerEvents } from './bus';
import { cylinder } from './geometry';
import type { Host } from './host';
import { itemPixelOf } from './probe';
import type { Hit, Item, Ray, SelectBox, Vec2, Vec3 } from './types';

/** Ray parameter of the point nearest to the item's base centre (0 when that is behind the ray's start). */
function nearest({ from, dir }: Ray, item: Item): number {
  const to: Vec3 = [item.x - from[0], item.y - from[1], item.placement.height - from[2]];
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
  const reach = item.model.bounds.r * Math.max(...item.placement.scale) * item.scale;
  const d = [ray.from[0] + ray.dir[0] * t - item.x, ray.from[1] + ray.dir[1] * t - item.y, ray.from[2] + ray.dir[2] * t - item.placement.height] as const;
  return d[0] * d[0] + d[1] * d[1] + d[2] * d[2] <= reach * reach;
}

/** A key event for a text field: the key is not the viewer's then. */
export const editingText = (t: EventTarget | null): boolean => t instanceof HTMLElement && (t.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(t.tagName));

export interface SelectionDeps {
  readonly host: Host;
  readonly camera: CameraService;
  readonly items: readonly Item[];
  readonly events: EventBus<ViewerEvents>;
}

export function createSelection({ host, camera, items, events }: SelectionDeps): SelectionService {
  const { canvas, pickBuffer } = host;
  let hovered: number | null = null;
  let last: number | null = null; // the one selected last (it is in `selected`)
  const selected = new Set<number>();
  let rect: SelectBox | null = null;

  const byId = (id: number | null): Item | null => items.find((item) => item.id === id) ?? null;

  /** The ray through a page pixel. */
  function rayAtPage(clientX: number, clientY: number): Ray {
    const box = canvas.getBoundingClientRect();
    return camera.rayAt(clientX - box.left, clientY - box.top);
  }

  /**
   * The item drawn at a page pixel, and the point of the mouse ray nearest
   * to its base centre; or null.
   */
  function hitAt(clientX: number, clientY: number): Hit | null {
    const box = canvas.getBoundingClientRect();
    if (clientX < box.left || clientY < box.top || clientX >= box.right || clientY >= box.bottom) return null;
    const ray = rayAtPage(clientX, clientY);
    const near = items.filter((item) => item.instance.shown && item.instance.attached && inReach(ray, item));
    const k = canvas.width / canvas.clientWidth;
    const x = Math.min(canvas.width - 1, Math.floor((clientX - box.left) * k));
    const y = Math.min(canvas.height - 1, Math.floor((clientY - box.top) * k));
    const index = pickBuffer.read(near.map((item) => item.instance), x, y, canvas.width, canvas.height);
    if (index < 0) return null;
    const best = near[index];
    if (!best) throw new Error(`pick: pixel names instance ${index} of ${near.length}`);
    const t = nearest(ray, best);
    return { item: best, point: [ray.from[0] + ray.dir[0] * t, ray.from[1] + ray.dir[1] * t, ray.from[2] + ray.dir[2] * t] };
  }

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

  /**
   * Make the items `ids` the selection (ids of no item are dropped). The
   * last one is the one "selected last". The instances panel marks their rows.
   */
  function setSelection(ids: Iterable<number>): void {
    selected.clear();
    for (const id of ids) if (byId(id)) selected.add(id);
    last = selected.size ? ([...selected].pop() ?? null) : null;
    events.emit('selection-changed', { ids: selected, last });
  }

  // An item that leaves the scene leaves the selection and the hover.
  events.on('items-removed', ({ ids, all }) => {
    if (all || (hovered !== null && ids.includes(hovered))) hovered = null;
    if (all) setSelection([]);
    else if (ids.some((id) => selected.has(id))) setSelection([...selected].filter((id) => !ids.includes(id)));
  });

  return {
    select: (id) => setSelection(id === null ? [] : [id]),
    setSelection,
    toggleSelected(id) {
      const next = new Set(selected);
      if (!next.delete(id)) next.add(id);
      setSelection([...next]);
    },
    selectedId: () => last,
    selectedIds: () => [...selected],
    hasSelection: () => selected.size > 0,
    hovered: () => byId(hovered),
    setHovered(id) {
      hovered = id;
    },
    rect: () => rect,
    setRect(box) {
      rect = box;
    },
    itemAt,
    hitAt,
    planeAt,
    itemPixel(id) {
      const item = byId(id);
      return item ? itemPixelOf(camera.screenOf, item, (x, y) => itemAt(x, y) === item) : null;
    },
    itemScreen(id, k = 0.5) {
      const item = byId(id);
      if (!item) return null;
      const c = cylinder(item);
      return camera.screenOf([c.x, c.y, c.z0 + (c.z1 - c.z0) * k]);
    },
    editingText,
  };
}

// Camera focus: point the camera at an item (ctrl + click on its row).

import { app, type FocusApi, type Item, type Vec3 } from '../../core/app';

const HALF_FOV = Math.PI / 8; // half the vertical field of view (core/camera.ts FOV)
const FOCUS_MARGIN = 1.3; // the instance's sphere fills 1 / 1.3 of the view height
const FOCUS_MIN = 2;
const FOCUS_MIN_REACH = 0.25;

/**
 * Point the camera at the middle of the item's rest-pose vertex box, from
 * where the box's sphere fits the view. The culling sphere (bounds) also
 * holds every animation, so it is several times too big for this. Yaw and
 * pitch stay; the camera jumps.
 */
function focusItem(item: Item): void {
  const s: Vec3 = [item.dataScale[0] * item.scale, item.dataScale[1] * item.scale, item.dataScale[2] * item.scale];
  // A model with no vertices has an empty box: its culling sphere stands in.
  const box = item.model;
  const empty = !Number.isFinite(box.vertexMin[0]);
  const r = box.bounds.r;
  const lo = (i: 0 | 1 | 2): number => (empty ? -r : (box.vertexMin[i] ?? 0));
  const hi = (i: 0 | 1 | 2): number => (empty ? r : (box.vertexMax[i] ?? 0));
  const mid = (i: 0 | 1 | 2): number => ((lo(i) + hi(i)) / 2) * s[i];
  const half = (i: 0 | 1 | 2): number => ((hi(i) - lo(i)) / 2) * s[i];
  const reach = Math.max(FOCUS_MIN_REACH, Math.hypot(half(0), half(1), half(2)));
  const a = (item.rot * Math.PI) / 180;
  const target: Vec3 = [item.x + mid(0) * Math.cos(a) - mid(1) * Math.sin(a), item.y + mid(0) * Math.sin(a) + mid(1) * Math.cos(a), app().baseHeight(item.unit) + mid(2)];
  app().view({ target, distance: Math.max(FOCUS_MIN, (FOCUS_MARGIN * reach) / Math.sin(HALF_FOV)) });
}

export function installFocus(): FocusApi {
  return {
    /** Focus the camera on the item with this id (as ctrl + click on its row does). */
    focus: (id) => {
      const item = app().items.find((i) => i.id === id);
      if (!item) throw new Error(`focus: no instance ${id}`);
      focusItem(item);
    },
    focusItem,
  };
}

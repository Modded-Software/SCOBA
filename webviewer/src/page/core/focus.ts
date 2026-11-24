// Camera focus: point the camera at an item (ctrl + click on its row; core/view.ts).

import type { CameraState, Item, Vec3 } from './types';

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
export function focusItem(view: (next: Partial<CameraState>) => void, item: Item): void {
  const [dx, dy, dz] = item.placement.scale;
  const s: Vec3 = [dx * item.scale, dy * item.scale, dz * item.scale];
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
  const target: Vec3 = [item.x + mid(0) * Math.cos(a) - mid(1) * Math.sin(a), item.y + mid(0) * Math.sin(a) + mid(1) * Math.cos(a), item.placement.height + mid(2)];
  view({ target, distance: Math.max(FOCUS_MIN, (FOCUS_MARGIN * reach) / Math.sin(HALF_FOV)) });
}

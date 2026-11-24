// itemPixel, for the tests: a page pixel on an item's picture.

import type { Item, Vec2, Vec3 } from './types';
import { cylinder } from './geometry';

// The search around the unit's column, in page pixels.
const PIXEL_REACH = 60;
const PIXEL_STEP = 4;
const PIXEL_MARGINS = [12, 6, 3];

/**
 * A page pixel on the item's picture, where it is the one under the mouse,
 * and so are the pixels a margin around it (the widest of PIXEL_MARGINS
 * that any pixel has). The nearest such to the foot of the item's column,
 * searched over the column's box on screen widened by PIXEL_REACH; null
 * when there is none. `on(x, y)`: the item is the one at that pixel.
 */
export function itemPixelOf(screenOf: (point: Vec3) => Vec2 | null, item: Item, on: (x: number, y: number) => boolean): Vec2 | null {
  const c = cylinder(item);
  const foot = screenOf([c.x, c.y, c.z0]);
  const top = screenOf([c.x, c.y, c.z1]);
  if (!foot || !top) return null;
  const points: Vec2[] = [];
  for (let y = Math.min(foot[1], top[1]) - PIXEL_REACH; y <= Math.max(foot[1], top[1]) + PIXEL_REACH; y += PIXEL_STEP) {
    for (let x = Math.min(foot[0], top[0]) - PIXEL_REACH; x <= Math.max(foot[0], top[0]) + PIXEL_REACH; x += PIXEL_STEP) points.push([Math.round(x), Math.round(y)]);
  }
  const far = (p: Vec2): number => Math.hypot(p[0] - foot[0], p[1] - foot[1]);
  points.sort((a, b) => far(a) - far(b));
  // The widest margin first: a pixel well inside the picture stays on a unit that moves as it plays.
  for (const m of PIXEL_MARGINS) {
    for (const [x, y] of points) {
      if (on(x, y) && on(x - m, y) && on(x + m, y) && on(x, y - m) && on(x, y + m)) return [x, y];
    }
  }
  return null;
}

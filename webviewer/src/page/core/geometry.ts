// An item's ring radius and its column: what the rings, the select
// rectangle and itemPixel measure.

import type { Item } from './types';

const MIN_RADIUS = 0.25; // world units: the smallest hit and ring radius

/** The unit's column: from the unit's height up by the model's reach. */
export interface Column {
  x: number;
  y: number;
  r: number;
  z0: number;
  z1: number;
}

/**
 * Ring radius: the placement's hit radius (an SC2 unit's data radius), or
 * half the model's reach. (An SC2 doodad's data radius is the same 0.5 for
 * a shrub and a ruin, so its game gives none: it takes the model's reach.)
 */
export function radius(item: Item): number {
  const own = item.placement.hitRadius;
  const r = own ?? item.model.bounds.r * 0.5 * Math.max(item.placement.scale[0], item.placement.scale[1]);
  return Math.max(MIN_RADIUS, r * item.scale);
}

/**
 * The unit's column: from the unit's height up by the model's reach. The
 * rings and the select rectangle use it; the mouse hit does not (hitAt).
 */
export function cylinder(item: Item): Column {
  const base = item.placement.height;
  return { x: item.x, y: item.y, r: radius(item), z0: base, z1: base + Math.max(0.5, item.model.bounds.r * item.placement.scale[2] * item.scale) };
}

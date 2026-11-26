// An item's ring radius and its column: what the rings, the select
// rectangle and itemPixel measure.

import type { Item, Vec3 } from './types';

/**
 * The middle of the item's rest-pose vertex box in the world, and the
 * box's half diagonal. The culling sphere (bounds) also holds every
 * animation, so it is several times too big for this. A model with no
 * vertices has an empty box: its culling sphere stands in.
 */
export function restBox(item: Item): { centre: Vec3; reach: number } {
  const [dx, dy, dz] = item.placement.scale;
  const s: Vec3 = [dx * item.scale, dy * item.scale, dz * item.scale];
  const box = item.model;
  const empty = !Number.isFinite(box.vertexMin[0]);
  const r = box.bounds.r;
  const lo = (i: 0 | 1 | 2): number => (empty ? -r : (box.vertexMin[i] ?? 0));
  const hi = (i: 0 | 1 | 2): number => (empty ? r : (box.vertexMax[i] ?? 0));
  const mid = (i: 0 | 1 | 2): number => ((lo(i) + hi(i)) / 2) * s[i];
  const half = (i: 0 | 1 | 2): number => ((hi(i) - lo(i)) / 2) * s[i];
  const a = (item.rot * Math.PI) / 180;
  const centre: Vec3 = [item.x + mid(0) * Math.cos(a) - mid(1) * Math.sin(a), item.y + mid(0) * Math.sin(a) + mid(1) * Math.cos(a), item.placement.height + mid(2)];
  return { centre, reach: Math.hypot(half(0), half(1), half(2)) };
}

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

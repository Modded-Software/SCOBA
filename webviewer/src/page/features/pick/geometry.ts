// An item's ring radius and its column: what the rings, the select
// rectangle and itemPixel measure.

import { app, type Item } from '../../core/app';

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
 * Ring radius: the unit's radius from data, or half the model's
 * reach. A doodad's data radius is the same 0.5 for a shrub and a ruin,
 * so a doodad takes the model's reach too.
 */
export function radius(item: Item): number {
  const r = item.unit && !item.unit.doodad ? item.unit.radius : item.model.bounds.r * 0.5 * Math.max(item.dataScale[0], item.dataScale[1]);
  return Math.max(MIN_RADIUS, r * item.scale);
}

/**
 * The unit's column: from the unit's height up by the model's reach. The
 * rings and the select rectangle use it; the mouse hit does not (hitAt).
 */
export function cylinder(item: Item): Column {
  const base = app().baseHeight(item.unit);
  return { x: item.x, y: item.y, r: radius(item), z0: base, z1: base + Math.max(0.5, item.model.bounds.r * item.dataScale[2] * item.scale) };
}

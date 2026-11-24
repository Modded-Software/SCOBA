// What the SC2 unit and doodad data does to the size of an instance.

import type { Vec3 } from '../../../shared/records';
import type { PlacedRecord } from '../shared/records';

/**
 * The data scale of a unit or doodad: actor scale x model scale x
 * creation scale, and for a doodad its random scale (RandomScaleRange,
 * the same on every axis). `pick` chooses inside the ranges.
 */
export function dataScale(unit: PlacedRecord, pick: number): Vec3 {
  const range = unit.doodad ? unit.scaleRange : null;
  const random = range ? range[0] + (range[1] - range[0]) * pick : 1;
  const axis = (i: 0 | 1 | 2): number =>
    unit.actorScale[i] * (unit.modelScaleMin[i] + (unit.modelScaleMax[i] - unit.modelScaleMin[i]) * pick) * unit.eventScale[i] * random;
  return [axis(0), axis(1), axis(2)];
}

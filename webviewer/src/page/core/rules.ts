// What the unit data does to the look. Step 5 moves these rules to the game.

import type M3Model from '@renderer/viewer/handlers/m3/model';
import type { PlacedRecord } from '../../shared/records';
import type { Playing, Vec3 } from './app';

/**
 * The data scale of a unit or doodad: actor scale x model scale x
 * creation scale, and for a doodad its random scale (RandomScaleRange,
 * the same on every axis). `pick` chooses inside the ranges.
 */
export function dataScale(unit: PlacedRecord | null, pick: number): Vec3 {
  if (!unit) return [1, 1, 1];
  const range = unit.doodad ? unit.scaleRange : null;
  const random = range ? range[0] + (range[1] - range[0]) * pick : 1;
  const axis = (i: 0 | 1 | 2): number =>
    unit.actorScale[i] * (unit.modelScaleMin[i] + (unit.modelScaleMax[i] - unit.modelScaleMin[i]) * pick) * unit.eventScale[i] * random;
  return [axis(0), axis(1), axis(2)];
}

/** Height over the ground a record stands at: a unit's Height; a doodad or a bare model stands on it. */
export const baseHeight = (unit: PlacedRecord | null): number => (unit && unit.height) || 0;

/**
 * How fast the current animation plays. The model's speed always counts.
 * A walk also runs faster or slower with the unit's speed: it is made for
 * the actor's WalkAnimMoveSpeed.
 */
export function playRate(item: Playing): number {
  const unit = item.unit;
  if (!unit) return 1;
  let rate = unit.animSpeed * unit.timeScale;
  const sequence = item.model.sequences[item.sequence];
  if (!unit.doodad && sequence && /^walk/i.test(sequence.name) && unit.speed > 0 && unit.walkAnimMoveSpeed !== null && unit.walkAnimMoveSpeed > 0) {
    rate *= unit.speed / unit.walkAnimMoveSpeed;
  }
  return rate;
}

/** The index of the stand animation, or the first one, or none. */
export function defaultSequence(model: M3Model): number {
  if (!model.sequences.length) return -1;
  const stand = model.sequences.findIndex((s) => /^stand/i.test(s.name));
  return stand >= 0 ? stand : 0;
}

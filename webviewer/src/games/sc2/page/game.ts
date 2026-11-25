// SC2 on the page (SPEC-VIEWER 6.4): what the unit and doodad data does
// to an instance. Core applies the placement; only this file reads the data.
// A terrain record is a ground texture (SPEC-VIEWER 17.5): core makes it
// the ground.

import type { DoodadRecord, PlacedRecord, TerrainRecord } from '../shared/records';
import type { GameRecord, PageGame, Placement, PlacementWish, PreviewCard, SequenceInfo } from '../../../page/core/plugin';
import { describeRecord } from './describe';
import { listName } from './names';
import { DOODADS, TERRAIN, UNITS, asPlaced, placedRecord, terrainRecord } from './records';
import { dataScale } from './rules';

export const SC2 = 'sc2';

/** Checked records, by the object core holds. */
const checked = new WeakMap<GameRecord, PlacedRecord>();
/** Checked ground texture records. */
const grounds = new WeakMap<GameRecord, TerrainRecord>();

/** The preview card of a ground texture. */
function terrainCard(record: TerrainRecord): PreviewCard {
  const facts = [`ground texture · ${record.state}`, `colour ${record.file}`, `normal map ${record.normal ?? 'none'}`];
  if (record.users.length) facts.push(`terrain sets: ${record.users.join(', ')}`);
  return { name: record.name, picture: null, facts };
}

/** The SC2 record behind one core holds. */
export function sc2Record(record: GameRecord): PlacedRecord {
  const known = checked.get(record);
  if (known) return known;
  const placed = asPlaced(record);
  checked.set(record, placed);
  return placed;
}

/** A whole variation number inside the doodad's range, or null when `value` is not one. */
function validVariation(doodad: DoodadRecord, value: unknown): number | null {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0 && value < doodad.variations ? value : null;
}

/**
 * What the map editor decides when it places a doodad: which model
 * variation, and the angle. The angle is random unless the doodad's data
 * forbids it (EditorFlags NoAutoRotate, or CanRotate off). A given
 * variation must be one of the doodad's; a given angle wins.
 */
function placeDoodad(doodad: DoodadRecord, wish: PlacementWish): Placement {
  const asked = wish.variant;
  // None asked: the map editor's rule, a random variation. One asked must be the doodad's.
  const variant = asked === undefined || asked === null ? Math.floor(Math.random() * doodad.variations) : validVariation(doodad, asked);
  if (variant === null) throw new Error(`${doodad.id} has no variation ${String(asked)} (it has ${doodad.variations})`);
  const file = doodad.files[variant];
  if (file === undefined) throw new Error(`${doodad.id} has no variation ${variant}`);
  const rot = wish.rot ?? (doodad.autoRotate ? Math.floor(Math.random() * 360) : 0);
  // A doodad is hit where its model is: its data radius is no footprint of the model.
  return { ...common(doodad, wish), file, variant, variants: doodad.variations, rot, team: false, icon: null, hitRadius: null };
}

/** What a unit's and a doodad's placement share. */
function common(record: PlacedRecord, wish: PlacementWish): Pick<Placement, 'scale' | 'height' | 'tint' | 'pick' | 'radius' | 'asBackdrop' | 'clips'> {
  return {
    // An M3 file holds its own animations.
    clips: [],
    scale: dataScale(record, wish.pick),
    // A unit stands at its Height; a doodad stands on the ground.
    height: (!record.doodad && record.height) || 0,
    tint: record.tint ? [record.tint[0], record.tint[1], record.tint[2]] : null,
    pick: wish.pick,
    radius: record.radius,
    asBackdrop: !record.doodad && Boolean(record.skybox),
  };
}

export const sc2Game: PageGame = {
  id: SC2,
  categories: [
    { id: UNITS, noun: 'unit' },
    { id: DOODADS, noun: 'doodad' },
    { id: TERRAIN, noun: 'ground texture', ground: true },
  ],
  backdrop: 'skybox',
  checkRecord(category, body) {
    if (category === TERRAIN) {
      const ground = terrainRecord(body);
      grounds.set(ground, ground);
      return ground;
    }
    const record = placedRecord(category, body);
    checked.set(record, record);
    return record;
  },
  place(category, record, wish) {
    // Core makes a ground texture the ground; it is never placed.
    if (category === TERRAIN) throw new Error(`${record.id} is a ground texture: it becomes the ground, it is not placed`);
    const placed = sc2Record(record);
    if (placed.doodad) {
      if (category !== DOODADS) throw new Error(`${placed.id} is a doodad, not one of ${category}`);
      return placeDoodad(placed, wish);
    }
    if (category !== UNITS) throw new Error(`${placed.id} is a unit, not one of ${category}`);
    return { ...common(placed, wish), file: placed.file, variant: null, variants: 0, rot: wish.rot ?? 0, team: true, icon: { name: placed.icon }, hitRadius: placed.radius };
  },
  placeFile(file, wish) {
    return { file, variant: null, variants: 0, scale: [1, 1, 1], height: 0, rot: wish.rot ?? 0, tint: null, pick: wish.pick, asBackdrop: false, radius: null, hitRadius: null, team: true, icon: null, clips: [] };
  },
  /**
   * How fast an animation plays. The model's speed always counts. A walk
   * also runs faster or slower with the unit's speed: it is made for the
   * actor's WalkAnimMoveSpeed.
   */
  playRate(record, sequence) {
    if (!record) return 1;
    const unit = sc2Record(record);
    let rate = unit.animSpeed * unit.timeScale;
    if (!unit.doodad && sequence && /^walk/i.test(sequence.name) && unit.speed > 0 && unit.walkAnimMoveSpeed !== null && unit.walkAnimMoveSpeed > 0) {
      rate *= unit.speed / unit.walkAnimMoveSpeed;
    }
    return rate;
  },
  describe(category, record) {
    const ground = category === TERRAIN ? grounds.get(record) : undefined;
    return ground ? terrainCard(ground) : describeRecord(sc2Record(record));
  },
  /** The stand animation, or the first one, or none. */
  restSequence(sequences) {
    if (!sequences.length) return -1;
    const stand = sequences.findIndex((s: SequenceInfo) => /^stand/i.test(s.name));
    return stand >= 0 ? stand : 0;
  },
  listName,
};

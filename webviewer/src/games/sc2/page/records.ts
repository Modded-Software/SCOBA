// The SC2 unit, doodad and terrain records as the server sends them, checked
// field by field. A body that is not one is refused with the field that is wrong.

import type { Vec3 } from '../../../shared/records';
import type { DoodadRecord, PlacedRecord, TerrainRecord, UnitRecord } from '../shared/records';

type Body = Readonly<Record<string, unknown>>;

function isBody(value: unknown): value is Body {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/** Reads typed fields of one body; the first wrong one ends with an error naming it. */
class Fields {
  constructor(
    private readonly body: Body,
    private readonly what: string,
  ) {}
  private fail(key: string, want: string): never {
    throw new Error(`${this.what}: ${key} is not ${want}`);
  }
  text(key: string): string {
    const v = this.body[key];
    return typeof v === 'string' ? v : this.fail(key, 'a string');
  }
  textOrNull(key: string): string | null {
    const v = this.body[key];
    return v === null || v === undefined ? null : typeof v === 'string' ? v : this.fail(key, 'a string or null');
  }
  number(key: string): number {
    const v = this.body[key];
    return typeof v === 'number' && Number.isFinite(v) ? v : this.fail(key, 'a number');
  }
  numberOrNull(key: string): number | null {
    const v = this.body[key];
    return v === null || v === undefined ? null : typeof v === 'number' ? v : this.fail(key, 'a number or null');
  }
  flag(key: string): boolean {
    const v = this.body[key];
    return typeof v === 'boolean' ? v : this.fail(key, 'true or false');
  }
  flagOr(key: string, otherwise: boolean): boolean {
    return this.body[key] === undefined ? otherwise : this.flag(key);
  }
  texts(key: string): string[] {
    const v = this.body[key];
    return Array.isArray(v) && v.every((x) => typeof x === 'string') ? v.map(String) : this.fail(key, 'a list of strings');
  }
  vec3(key: string): Vec3 {
    const v = this.body[key];
    if (!Array.isArray(v) || v.length !== 3 || !v.every((x) => typeof x === 'number')) return this.fail(key, 'three numbers');
    return [Number(v[0]), Number(v[1]), Number(v[2])];
  }
  vec3OrNull(key: string): Vec3 | null {
    return this.body[key] === null || this.body[key] === undefined ? null : this.vec3(key);
  }
  rangeOrNull(key: string): [number, number] | null {
    const v = this.body[key];
    if (v === null || v === undefined) return null;
    if (!Array.isArray(v) || v.length !== 2 || !v.every((x) => typeof x === 'number')) return this.fail(key, 'two numbers or null');
    return [Number(v[0]), Number(v[1])];
  }
}

/** What units and doodads share. */
function placedData(f: Fields): Omit<UnitRecord, 'race' | 'kind' | 'family' | 'icon' | 'portrait' | 'speed' | 'walkAnimMoveSpeed' | 'height' | 'skybox' | 'doodad'> {
  return {
    id: f.text('id'),
    name: f.text('name'),
    inMap: f.flag('inMap'),
    actorScale: f.vec3('actorScale'),
    modelScaleMin: f.vec3('modelScaleMin'),
    modelScaleMax: f.vec3('modelScaleMax'),
    eventScale: f.vec3('eventScale'),
    animSpeed: f.number('animSpeed'),
    timeScale: f.number('timeScale'),
    radius: f.number('radius'),
    tint: f.vec3OrNull('tint'),
    file: f.text('file'),
    dataset: f.text('dataset'),
  };
}

export function unitRecord(body: unknown): UnitRecord {
  if (!isBody(body)) throw new Error('unit record: not an object');
  const f = new Fields(body, `unit record ${String(body['id'])}`);
  if (body['doodad'] !== undefined) throw new Error(`unit record ${String(body['id'])}: is a doodad`);
  return {
    ...placedData(f),
    race: f.text('race'),
    kind: f.text('kind'),
    family: f.text('family'),
    icon: f.textOrNull('icon'),
    portrait: f.textOrNull('portrait'),
    speed: f.number('speed'),
    walkAnimMoveSpeed: f.numberOrNull('walkAnimMoveSpeed'),
    height: f.number('height'),
    skybox: f.flagOr('skybox', false),
  };
}

export function doodadRecord(body: unknown): DoodadRecord {
  if (!isBody(body)) throw new Error('doodad record: not an object');
  const f = new Fields(body, `doodad record ${String(body['id'])}`);
  if (body['doodad'] !== true) throw new Error(`doodad record ${String(body['id'])}: doodad is not true`);
  return {
    ...placedData(f),
    doodad: true,
    type: f.text('type'),
    tilesets: f.texts('tilesets'),
    files: f.texts('files'),
    variations: f.number('variations'),
    editorOnly: f.flag('editorOnly'),
    editorModel: f.textOrNull('editorModel'),
    scaleRange: f.rangeOrNull('scaleRange'),
    autoRotate: f.flag('autoRotate'),
    footprint: f.textOrNull('footprint'),
  };
}

/** A ground texture record, checked. */
export function terrainRecord(body: unknown): TerrainRecord {
  if (!isBody(body)) throw new Error('terrain record: not an object');
  const f = new Fields(body, `terrain record ${String(body['id'])}`);
  return {
    id: f.text('id'),
    name: f.text('name'),
    sub: f.text('sub'),
    icon: null,
    placeable: false,
    notPlaceableAs: f.text('notPlaceableAs'),
    file: f.text('file'),
    normal: f.textOrNull('normal'),
    users: f.texts('users'),
    state: f.text('state'),
    dataset: f.text('dataset'),
  };
}

/** The record categories of SC2: the route name and the noun. */
export const UNITS = 'units';
export const DOODADS = 'doodads';
export const TERRAIN = 'terrain';

/** A record of a category, checked. */
export function placedRecord(category: string, body: unknown): PlacedRecord {
  if (category === UNITS) return unitRecord(body);
  if (category === DOODADS) return doodadRecord(body);
  throw new Error(`sc2 has no category ${category}`);
}

/** A record core holds, back as the SC2 record it is: units and doodads keep their fields. */
export function asPlaced(record: unknown): PlacedRecord {
  if (!isBody(record)) throw new Error('not an sc2 record');
  return record['doodad'] === true ? doodadRecord(record) : unitRecord(record);
}

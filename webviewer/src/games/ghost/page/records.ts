// The Ghost actor and model records as the server sends them, checked field
// by field. A body that is not one is refused with the field that is wrong.

import type { ActorRecord, GhostMotion, GhostRecord, ModelRecord } from '../shared/records';

export const ACTORS = 'actors';
export const MODELS = 'models';

type Body = Readonly<Record<string, unknown>>;

const isBody = (value: unknown): value is Body => typeof value === 'object' && value !== null && !Array.isArray(value);

/** Reads typed fields of one body; the first wrong one ends with an error naming it. */
class Fields {
  constructor(
    private readonly body: Body,
    private readonly what: string,
  ) {}
  fail(key: string, want: string): never {
    throw new Error(`${this.what}: ${key} is not ${want}`);
  }
  text(key: string): string {
    const v = this.body[key];
    return typeof v === 'string' ? v : this.fail(key, 'a string');
  }
  textOrNull(key: string): string | null {
    const v = this.body[key];
    return v === null ? null : typeof v === 'string' ? v : this.fail(key, 'a string or null');
  }
  number(key: string): number {
    const v = this.body[key];
    return typeof v === 'number' && Number.isFinite(v) ? v : this.fail(key, 'a number');
  }
  numberOrNull(key: string): number | null {
    return this.body[key] === null ? null : this.number(key);
  }
  texts(key: string): string[] {
    const v = this.body[key];
    return Array.isArray(v) && v.every((x): x is string => typeof x === 'string') ? [...v] : this.fail(key, 'a list of strings');
  }
  numbers(key: string): number[] {
    const v = this.body[key];
    return Array.isArray(v) && v.every((x): x is number => typeof x === 'number') ? [...v] : this.fail(key, 'a list of numbers');
  }
  flag(key: string): boolean {
    const v = this.body[key];
    return typeof v === 'boolean' ? v : this.fail(key, 'true or false');
  }
  motions(key: string): GhostMotion[] {
    const v = this.body[key];
    if (!Array.isArray(v)) return this.fail(key, 'a list of motions');
    return v.map((m, i) => {
      if (!isBody(m)) return this.fail(`${key}[${i}]`, 'a motion');
      const f = new Fields(m, `${this.what} ${key}[${i}]`);
      return { name: f.text('name'), clip: f.text('clip'), flags: f.texts('flags') };
    });
  }
}

function placed(f: Fields): Omit<ActorRecord, 'category' | 'template' | 'model' | 'scale' | 'kind' | 'script'> {
  return {
    id: f.text('id'),
    name: f.text('name'),
    sub: f.text('sub'),
    icon: null,
    placeable: true,
    notPlaceableAs: null,
    file: f.text('file'),
    motionSet: f.textOrNull('motionSet'),
    motions: f.motions('motions'),
    missingClips: f.texts('missingClips'),
    dataset: f.text('dataset'),
  };
}

/** A record of a category, checked. */
export function ghostRecord(category: string, body: unknown): GhostRecord {
  if (!isBody(body)) throw new Error(`ghost ${category} record: not an object`);
  const f = new Fields(body, `ghost ${category} record ${String(body['id'])}`);
  if (body['category'] !== category) f.fail('category', category);
  if (category === ACTORS) {
    const actor: ActorRecord = { ...placed(f), category: ACTORS, template: f.text('template'), model: f.text('model'), scale: f.numberOrNull('scale'), kind: f.numberOrNull('kind'), script: f.textOrNull('script') };
    return actor;
  }
  if (category === MODELS) {
    const model: ModelRecord = { ...placed(f), category: MODELS, materials: f.number('materials'), bones: f.number('bones'), groups: f.number('groups'), vertexTypes: f.numbers('vertexTypes'), skinned: f.flag('skinned') };
    return model;
  }
  throw new Error(`ghost has no category ${category}`);
}

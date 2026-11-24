// The two categories of the Ghost game (SPEC-VIEWER-GHOST 5), built from
// the catalog NODExport writes and the index of the build. A name a file
// gives is matched to a file without regard to case (section 3).

import type { Page } from '../../../shared/records';
import type { ActorRecord, GhostMotion, ModelRecord } from '../shared/records';
import { findIn, type BuildIndex } from './build';

/** Why a template or a motion is left out, for the summary. */
export interface LeftOut {
  name: string;
  reason: string;
}

export interface Catalog {
  readonly actors: ReadonlyMap<string, Omit<ActorRecord, 'dataset'>>;
  readonly models: ReadonlyMap<string, Omit<ModelRecord, 'dataset'>>;
  readonly leftOut: readonly LeftOut[];
  /** Models and motion sets NODExport refused. */
  readonly refused: readonly LeftOut[];
}

// ---- reading the catalog JSON, field by field ----

type Json = Record<string, unknown>;
const isObject = (v: unknown): v is Json => typeof v === 'object' && v !== null && !Array.isArray(v);

function list(of: Json, field: string): Json[] {
  const value = of[field];
  if (!Array.isArray(value) || !value.every(isObject)) throw new Error(`catalog: ${field} is not a list of objects`);
  return value;
}
function text(of: Json, field: string): string {
  const value = of[field];
  if (typeof value !== 'string') throw new Error(`catalog: ${field} is not text: ${JSON.stringify(of)}`);
  return value;
}
function textOrNull(of: Json, field: string): string | null {
  return of[field] === null ? null : text(of, field);
}
function numberOrNull(of: Json, field: string): number | null {
  const value = of[field];
  if (value === null) return null;
  if (typeof value !== 'number') throw new Error(`catalog: ${field} is not a number: ${JSON.stringify(of)}`);
  return value;
}
function count(of: Json, field: string): number {
  const value = numberOrNull(of, field);
  if (value === null) throw new Error(`catalog: ${field} is missing: ${JSON.stringify(of)}`);
  return value;
}
function texts(of: Json, field: string): string[] {
  const value = of[field];
  if (!Array.isArray(value) || !value.every((v): v is string => typeof v === 'string')) throw new Error(`catalog: ${field} is not a list of text`);
  return value;
}
function numbers(of: Json, field: string): number[] {
  const value = of[field];
  if (!Array.isArray(value) || !value.every((v): v is number => typeof v === 'number')) throw new Error(`catalog: ${field} is not a list of numbers`);
  return value;
}

const refusals = (of: Json, field: string): LeftOut[] => list(of, field).map((r) => ({ name: text(r, 'name'), reason: text(r, 'error') }));

// ---- building the records ----

interface MotionSet {
  motions: GhostMotion[];
  missingClips: string[];
}

/** Rigid vertex types: 0 and 3 (SPEC-VIEWER-GHOST 4.1). */
const skinnedType = (type: number): boolean => type % 3 !== 0;

const stem = (file: string): string => file.replace(/\.[^.]*$/, '');

export function buildCatalog(data: Json, index: BuildIndex): Catalog {
  const sets = new Map<string, MotionSet>();
  for (const set of list(data, 'motionSets')) {
    const motions: GhostMotion[] = [];
    const missingClips: string[] = [];
    for (const entry of list(set, 'entries')) {
      const clip = findIn(index, '3D/Anims', text(entry, 'clip'), '.nad');
      if (clip === null) missingClips.push(text(entry, 'clip'));
      else motions.push({ name: text(entry, 'name'), clip: clip.slice('3D/Anims/'.length), flags: texts(entry, 'flags') });
    }
    sets.set(text(set, 'file').toLowerCase(), { motions, missingClips });
  }
  const leftOut: LeftOut[] = [];
  const setOf = (name: string | null, owner: string): { motionSet: string | null } & MotionSet => {
    if (name === null) return { motionSet: null, motions: [], missingClips: [] };
    const rel = findIn(index, '3D/Motions', name, '.nms');
    const file = rel === null ? null : rel.slice('3D/Motions/'.length);
    const set = file === null ? undefined : sets.get(file.toLowerCase());
    if (file === null || !set) {
      leftOut.push({ name: owner, reason: `motion set ${name} is not in 3D/Motions` });
      return { motionSet: null, motions: [], missingClips: [] };
    }
    return { motionSet: file, ...set };
  };

  const models = new Map<string, Omit<ModelRecord, 'dataset'>>();
  for (const model of list(data, 'models')) {
    const file = text(model, 'file');
    const vertexTypes = numbers(model, 'vertexTypes');
    const bones = count(model, 'bones');
    const groups = count(model, 'groups');
    // The motion set of a bare model: the .nms of the same name, when there is one (5.2).
    const own = findIn(index, '3D/Motions', `${stem(file)}.nms`, '.nms');
    const set = own === null ? { motionSet: null, motions: [], missingClips: [] } : setOf(own.slice('3D/Motions/'.length), file);
    models.set(file, {
      category: 'models',
      id: file,
      name: stem(file),
      sub: `${bones} bones, ${groups} groups${set.motions.length ? `, ${set.motions.length} motions` : ''}`,
      icon: null,
      placeable: true,
      notPlaceableAs: null,
      file: `3D/Models/${file}`,
      materials: count(model, 'materials'),
      bones,
      groups,
      vertexTypes,
      skinned: vertexTypes.some(skinnedType),
      ...set,
    });
  }

  const actors = new Map<string, Omit<ActorRecord, 'dataset'>>();
  for (const template of list(data, 'templates')) {
    const name = text(template, 'name');
    const model = textOrNull(template, 'model');
    if (model === null) continue; // a template without a model is no actor: nothing to draw
    const rel = findIn(index, '3D/Models', model, '.nod');
    if (rel === null) {
      leftOut.push({ name, reason: `model ${model} is not in 3D/Models` });
      continue;
    }
    if (!models.has(rel.slice('3D/Models/'.length))) {
      leftOut.push({ name, reason: `model ${model} was refused` });
      continue;
    }
    const set = setOf(textOrNull(template, 'motionSet'), name);
    actors.set(name, {
      category: 'actors',
      id: name,
      name,
      sub: `${model}${set.motions.length ? `, ${set.motions.length} motions` : ''}`,
      icon: null,
      placeable: true,
      notPlaceableAs: null,
      file: rel,
      template: name,
      model,
      scale: numberOrNull(template, 'scale'),
      kind: numberOrNull(template, 'type'),
      script: textOrNull(template, 'script'),
      ...set,
    });
  }
  const refused = [...refusals(data, 'refusedTemplates'), ...refusals(data, 'refusedModels'), ...refusals(data, 'refusedMotionSets')];
  return { actors, models, leftOut, refused };
}

/** The list row of a record. */
const row = ({ id, name, sub, icon, placeable, notPlaceableAs }: Omit<ActorRecord | ModelRecord, 'dataset'>): Record<string, unknown> => ({ id, name, sub, icon, placeable, notPlaceableAs });

/** Every word of `q` in the record's search text; then the filter; then one page. */
function search<T extends Omit<ActorRecord | ModelRecord, 'dataset'>>(records: Iterable<T>, words: (r: T) => string, keep: (r: T) => boolean, q: string, offset: number, limit: number): Page<Record<string, unknown>> {
  const wanted = q.toLowerCase().trim().split(/\s+/).filter(Boolean);
  const hits = [...records].filter((r) => keep(r) && wanted.every((w) => words(r).includes(w))).sort((a, b) => a.name.localeCompare(b.name));
  return { total: hits.length, items: hits.slice(offset, offset + limit).map(row) };
}

/** Filter `motion`: '' all, `with`, `without` a motion set (5.1). */
export function searchActors(catalog: Catalog, q: string, motion: string, offset: number, limit: number): Page<Record<string, unknown>> {
  return search(catalog.actors.values(), (a) => `${a.name} ${a.model}`.toLowerCase(), (a) => !motion || (motion === 'with') === (a.motionSet !== null), q, offset, limit);
}

/** Filter `skin`: '' all, `skinned`, `rigid` (5.2). */
export function searchModels(catalog: Catalog, q: string, skin: string, offset: number, limit: number): Page<Record<string, unknown>> {
  return search(catalog.models.values(), (m) => m.name.toLowerCase(), (m) => !skin || (skin === 'skinned') === m.skinned, q, offset, limit);
}

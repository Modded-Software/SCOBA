// A scene as a document (SPEC-VIEWER section 10.2): the type, and the one
// check that every stored scene and every imported file passes. A document
// that fails is refused whole; nothing of it is read.

import { ID_RULE, type CategoryId, type DatasetId, type GameId } from './protocol';

export type JsonValue = string | number | boolean | null | JsonValue[] | JsonObject;
export interface JsonObject {
  [key: string]: JsonValue;
}

export const SCENE_FORMAT = 'viewer-scene';
export const SCENE_VERSION = 1;
export const SCENE_ID_RULE = /^s-[a-z0-9]{1,40}$/;
export const NAME_MAX = 80;
export const ITEMS_MAX = 20000;

export type SceneSource = { category: CategoryId; record: string; variant: number | null } | { file: string };

export interface SceneItemDocument {
  game: GameId;
  dataset: DatasetId;
  source: SceneSource;
  x: number;
  y: number;
  /** Degrees. */
  rot: number;
  scale: number;
  /** The looping animation; -1 for none. */
  sequence: number;
  /** 0 to 1: chooses inside the data's scale ranges. */
  pick: number;
  /** The game's own item values. */
  options: JsonObject;
}

export interface SceneDocument {
  format: typeof SCENE_FORMAT;
  version: typeof SCENE_VERSION;
  id: string;
  name: string;
  /** ISO 8601 UTC. */
  created: string;
  modified: string;
  items: SceneItemDocument[];
}

/** Why a document was refused: the first fault, by path. */
export class SceneError extends Error {
  readonly path: string;
  constructor(path: string, fault: string) {
    super(path ? `${path}: ${fault}` : fault);
    this.name = 'SceneError';
    this.path = path;
  }
}

type Fields = Record<string, unknown>;

const isObject = (value: unknown): value is Fields => typeof value === 'object' && value !== null && !Array.isArray(value);

/** `value` as an object with exactly the fields `keys`. */
function object(value: unknown, path: string, keys: readonly string[]): Fields {
  if (!isObject(value)) throw new SceneError(path, 'not an object');
  for (const key of Object.keys(value)) if (!keys.includes(key)) throw new SceneError(join(path, key), 'unknown field');
  for (const key of keys) if (!(key in value)) throw new SceneError(join(path, key), 'missing');
  return value;
}

const join = (path: string, key: string): string => (path ? `${path}.${key}` : key);

function text(value: unknown, path: string, max: number): string {
  if (typeof value !== 'string') throw new SceneError(path, 'not a string');
  if (value.length === 0 || value.length > max) throw new SceneError(path, `not 1 to ${max} characters`);
  return value;
}

function id(value: unknown, path: string): string {
  if (typeof value !== 'string' || !ID_RULE.test(value)) throw new SceneError(path, 'not an id (a-z, 0-9, "_", "-", 1 to 40)');
  return value;
}

function finite(value: unknown, path: string): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) throw new SceneError(path, 'not a finite number');
  return value;
}

function integer(value: unknown, path: string, min: number, max: number): number {
  if (typeof value !== 'number' || !Number.isInteger(value) || value < min || value > max) throw new SceneError(path, `not an integer from ${min} to ${max}`);
  return value;
}

function time(value: unknown, path: string): string {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,3})?Z$/.test(value) || Number.isNaN(Date.parse(value))) {
    throw new SceneError(path, 'not an ISO 8601 UTC time');
  }
  return value;
}

function json(value: unknown, path: string): JsonValue {
  if (value === null || typeof value === 'string' || typeof value === 'boolean') return value;
  if (typeof value === 'number') return finite(value, path);
  if (Array.isArray(value)) return value.map((v, i) => json(v, `${path}[${i}]`));
  if (isObject(value)) return jsonObject(value, path);
  throw new SceneError(path, 'not a JSON value');
}

function jsonObject(value: unknown, path: string): JsonObject {
  if (!isObject(value)) throw new SceneError(path, 'not an object');
  const out: JsonObject = {};
  for (const [key, v] of Object.entries(value)) out[key] = json(v, join(path, key));
  return out;
}

function source(value: unknown, path: string): SceneSource {
  if (isObject(value) && 'file' in value) {
    const fields = object(value, path, ['file']);
    return { file: text(fields['file'], join(path, 'file'), 1000) };
  }
  const fields = object(value, path, ['category', 'record', 'variant']);
  const variant = fields['variant'];
  return {
    category: id(fields['category'], join(path, 'category')),
    record: text(fields['record'], join(path, 'record'), 200),
    variant: variant === null ? null : integer(variant, join(path, 'variant'), 0, 9999),
  };
}

const ITEM_KEYS = ['game', 'dataset', 'source', 'x', 'y', 'rot', 'scale', 'sequence', 'pick', 'options'] as const;

function item(value: unknown, path: string): SceneItemDocument {
  const fields = object(value, path, ITEM_KEYS);
  const at = (key: string): string => join(path, key);
  const scale = finite(fields['scale'], at('scale'));
  if (scale <= 0) throw new SceneError(at('scale'), 'not above 0');
  const pick = finite(fields['pick'], at('pick'));
  if (pick < 0 || pick > 1) throw new SceneError(at('pick'), 'not from 0 to 1');
  return {
    game: id(fields['game'], at('game')),
    dataset: id(fields['dataset'], at('dataset')),
    source: source(fields['source'], at('source')),
    x: finite(fields['x'], at('x')),
    y: finite(fields['y'], at('y')),
    rot: finite(fields['rot'], at('rot')),
    scale,
    sequence: integer(fields['sequence'], at('sequence'), -1, 100000),
    pick,
    options: jsonObject(fields['options'], at('options')),
  };
}

const DOCUMENT_KEYS = ['format', 'version', 'id', 'name', 'created', 'modified', 'items'] as const;

/** A stored scene or an imported file, checked. Throws a SceneError naming the first fault. */
export function parseSceneDocument(value: unknown): SceneDocument {
  if (!isObject(value)) throw new SceneError('', 'not an object');
  if (value['format'] !== SCENE_FORMAT) throw new SceneError('format', `not "${SCENE_FORMAT}"`);
  // A later version adds its migration here, from the one before; the check below runs on the result.
  if (value['version'] !== SCENE_VERSION) throw new SceneError('version', `${JSON.stringify(value['version'] ?? null)} is not ${SCENE_VERSION}`);
  const fields = object(value, '', DOCUMENT_KEYS);
  const sceneId = fields['id'];
  if (typeof sceneId !== 'string' || !SCENE_ID_RULE.test(sceneId)) throw new SceneError('id', 'not "s-" then 1 to 40 of a-z, 0-9');
  const name = text(fields['name'], 'name', NAME_MAX);
  if (name !== name.trim()) throw new SceneError('name', 'has spaces at an end');
  const items = fields['items'];
  if (!Array.isArray(items)) throw new SceneError('items', 'not a list');
  if (items.length > ITEMS_MAX) throw new SceneError('items', `more than ${ITEMS_MAX}`);
  return {
    format: SCENE_FORMAT,
    version: SCENE_VERSION,
    id: sceneId,
    name,
    created: time(fields['created'], 'created'),
    modified: time(fields['modified'], 'modified'),
    items: items.map((v, i) => item(v, `items[${i}]`)),
  };
}

/** A new scene id: "s-" and 16 random base-36 characters. */
export function newSceneId(random: () => number = Math.random): string {
  let out = '';
  while (out.length < 16) out += Math.floor(random() * 36).toString(36);
  return `s-${out}`;
}

/** An empty scene named `name`, made now. */
export function emptyScene(name: string, now: Date = new Date()): SceneDocument {
  const stamp = now.toISOString();
  return { format: SCENE_FORMAT, version: SCENE_VERSION, id: newSceneId(), name: name.trim(), created: stamp, modified: stamp, items: [] };
}

/** `wanted`, or with " (2)", " (3)"... when another scene has that name. */
export function freeName(wanted: string, taken: readonly string[]): string {
  const clean = wanted.trim().slice(0, NAME_MAX).trimEnd() || 'scene';
  if (!taken.includes(clean)) return clean;
  // Room for " (9999)".
  const base = clean.slice(0, NAME_MAX - 7).trimEnd();
  let n = 2;
  while (taken.includes(`${base} (${n})`)) n++;
  return `${base} (${n})`;
}

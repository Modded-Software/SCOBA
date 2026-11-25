// The page's stored settings (SPEC-VIEWER section 10.3): every localStorage
// key, its parser, its type and, where it has one, its declared default. A
// module reads and writes only through here. Each value is stored as JSON.
//
// Before the page starts, main.ts checks every stored key (refusedSettings).
// A key that does not parse, or that the page does not know, stops the
// start: the page lists it, and the person may clear it (R-VIEW-73). So a
// read here sees a valid value or none. Nothing stored: a setting with a
// default reads its default; one without (game, scene, dataset) reads null,
// and its module decides by its own rule.
// Scenes are not settings: they are documents in IndexedDB (store/scenes-db.ts).

import { SESSION_RULE } from '../../shared/edits';
import { SCENE_ID_RULE } from '../../shared/scene';
import { ID_RULE } from '../../shared/protocol';
import type { CameraState, GroundChoice, Landmark, SkyChoice } from './types';
import { messageOf } from './dom';

const PREFIX = 'viewer.';

export interface Setting<T> {
  /** Below "viewer.". */
  readonly key: string;
  /** The stored JSON value, checked. Throws, naming the fault. */
  parse(value: unknown): T;
}

/** A setting with a declared default: what it reads when nothing is stored. */
export interface DefaultedSetting<T> extends Setting<T> {
  readonly initial: T;
}

/** A stored key the page refuses: its full key, the stored text, and why. */
export interface RefusedSetting {
  key: string;
  stored: string;
  reason: string;
}

const field = (value: unknown, key: string): unknown => (typeof value === 'object' && value !== null && !Array.isArray(value) ? Reflect.get(value, key) : undefined);
const finite = (n: unknown): n is number => typeof n === 'number' && Number.isFinite(n);
const filled = (v: unknown): v is string => typeof v === 'string' && v !== '';

/** The keys of an object, exactly: a missing or an unknown one is refused. */
function keysOf(value: unknown, keys: readonly string[], what: string): void {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) throw new Error(`${what} is not an object`);
  const have = Object.keys(value);
  const unknown = have.filter((key) => !keys.includes(key));
  if (unknown.length) throw new Error(`${what}: unknown key "${unknown[0]}"`);
  const missing = keys.filter((key) => !have.includes(key));
  if (missing.length) throw new Error(`${what}: no "${missing[0]}"`);
}

function vec3(value: unknown, what: string): [number, number, number] {
  if (!Array.isArray(value) || value.length !== 3) throw new Error(`${what} is not 3 numbers`);
  const [x, y, z]: unknown[] = value;
  if (!finite(x) || !finite(y) || !finite(z)) throw new Error(`${what} is not 3 numbers`);
  return [x, y, z];
}

const VIEW_KEYS = ['yaw', 'pitch', 'distance', 'target'] as const;

/** A camera view: every field a finite number, the distance positive. `extra`: the other keys the stored object has. */
function parseView(value: unknown, what: string, extra: readonly string[] = []): CameraState {
  keysOf(value, [...VIEW_KEYS, ...extra], what);
  const yaw = field(value, 'yaw');
  const pitch = field(value, 'pitch');
  const distance = field(value, 'distance');
  if (!finite(yaw) || !finite(pitch) || !finite(distance)) throw new Error(`${what} is not a view`);
  if (distance <= 0) throw new Error(`${what} has distance ${distance}`);
  return { yaw, pitch, distance, target: vec3(field(value, 'target'), `${what}: the target`) };
}

export interface DrawersSetting {
  gallery: boolean;
  instances: boolean;
}

export interface ViewSetting {
  grid: boolean;
  sky: SkyChoice | null;
  ground: GroundChoice | null;
}

/** A stored sky: a backdrop of one game and dataset; null: none. */
function parseSky(sky: unknown): SkyChoice | null {
  if (sky === null) return null;
  keysOf(sky, ['id', 'name', 'file', 'game', 'dataset'], 'the sky');
  const id = field(sky, 'id');
  const name = field(sky, 'name');
  const file = field(sky, 'file');
  const game = field(sky, 'game');
  const dataset = field(sky, 'dataset');
  if (!filled(id) || !filled(name) || !filled(file)) throw new Error('the sky is not a backdrop');
  if (typeof game !== 'string' || !ID_RULE.test(game) || typeof dataset !== 'string' || !ID_RULE.test(dataset)) throw new Error('the backdrop names no game and dataset');
  return { id, name, file, game, dataset };
}

/** A stored ground texture: a ground record; null: none. */
function parseGround(ground: unknown): GroundChoice | null {
  if (ground === null) return null;
  keysOf(ground, ['game', 'dataset', 'category', 'id', 'name', 'texture'], 'the ground');
  const game = field(ground, 'game');
  const dataset = field(ground, 'dataset');
  const category = field(ground, 'category');
  const id = field(ground, 'id');
  const name = field(ground, 'name');
  const texture = field(ground, 'texture');
  if (typeof game !== 'string' || !ID_RULE.test(game) || typeof dataset !== 'string' || !ID_RULE.test(dataset) || typeof category !== 'string' || !ID_RULE.test(category) || !filled(id) || !filled(name) || !filled(texture)) throw new Error('the ground is not a ground record');
  return { game, dataset, category, id, name, texture };
}

export interface LandmarksSetting {
  /** Without the origin, which is always there. */
  list: Landmark[];
  /** The chosen one: the origin (0), one of the list, or none (null). */
  selected: number | null;
}

/** The origin landmark's id; stored landmarks start at 1. */
export const ORIGIN_LANDMARK = 0;

/** A stored landmark; ids start at 1 (0 is the origin). */
function parseLandmark(value: unknown): Landmark {
  const id = field(value, 'id');
  const name = field(value, 'name');
  if (typeof id !== 'number' || !Number.isInteger(id) || id <= ORIGIN_LANDMARK || !filled(name)) throw new Error('not a landmark');
  return { id, name, ...parseView(value, `"${name}"`, ['id', 'name']) };
}

function parseId(value: unknown, what: string): string {
  if (typeof value !== 'string' || !ID_RULE.test(value)) throw new Error(`not a ${what} id`);
  return value;
}

const camera: DefaultedSetting<CameraState> = {
  key: 'camera',
  /** The view of a first start: the origin seen from the south, a little above. */
  initial: { yaw: -Math.PI / 2, pitch: 0.5, distance: 9, target: [0, 0, 0.8] },
  parse: (value) => parseView(value, 'the camera'),
};

const drawers: DefaultedSetting<DrawersSetting> = {
  key: 'drawers',
  initial: { gallery: true, instances: true },
  parse(value) {
    keysOf(value, ['gallery', 'instances'], 'the drawers');
    const gallery = field(value, 'gallery');
    const instances = field(value, 'instances');
    if (typeof gallery !== 'boolean' || typeof instances !== 'boolean') throw new Error('not two drawer flags');
    return { gallery, instances };
  },
};

const view: DefaultedSetting<ViewSetting> = {
  key: 'view',
  initial: { grid: true, sky: null, ground: null },
  parse(value) {
    keysOf(value, ['grid', 'sky', 'ground'], 'the view');
    const grid = field(value, 'grid');
    if (typeof grid !== 'boolean') throw new Error('no grid setting');
    return { grid, sky: parseSky(field(value, 'sky')), ground: parseGround(field(value, 'ground')) };
  },
};

const landmarks: DefaultedSetting<LandmarksSetting> = {
  key: 'landmarks',
  initial: { list: [], selected: null },
  parse(value) {
    keysOf(value, ['list', 'selected'], 'the landmarks');
    const stored = field(value, 'list');
    if (!Array.isArray(stored)) throw new Error('no landmark list');
    const list = stored.map(parseLandmark);
    if (new Set(list.map((l) => l.id)).size !== list.length) throw new Error('an id is used twice');
    const selected = field(value, 'selected');
    if (selected === null) return { list, selected };
    if (typeof selected !== 'number' || (selected !== ORIGIN_LANDMARK && !list.some((l) => l.id === selected))) throw new Error(`the chosen landmark ${JSON.stringify(selected)} is not one of them`);
    return { list, selected };
  },
};

/** By edit session: the rendered planes the transfer dialog was opened for, as text (SPEC-PHOTOCRAFT 9.3). */
const editsOffered: DefaultedSetting<Record<string, string>> = {
  key: 'edits.offered',
  initial: {},
  parse(value) {
    if (typeof value !== 'object' || value === null || Array.isArray(value)) throw new Error('the offered edits are not an object');
    const offered: Record<string, string> = {};
    for (const [session, planes] of Object.entries(value)) {
      if (!SESSION_RULE.test(session)) throw new Error(`"${session}" is not an edit session`);
      if (typeof planes !== 'string') throw new Error(`the offered planes of ${session} are not text`);
      offered[session] = planes;
    }
    return offered;
  },
};

export const settings = {
  camera,
  drawers,
  editsOffered,
  /** The gallery's game (R-VIEW-22). Nothing stored: the server's default game. */
  game: { key: 'game', parse: (value: unknown): string => parseId(value, 'game') } as Setting<string>,
  view,
  landmarks,
  /** The open scene. Nothing stored: the newest scene, else a new one. */
  scene: {
    key: 'scene',
    parse(value: unknown): string {
      if (typeof value !== 'string' || !SCENE_ID_RULE.test(value)) throw new Error('not a scene id');
      return value;
    },
  } as Setting<string>,
} as const;

/** The full localStorage key of a setting. */
export const keyOf = <T>(setting: Setting<T>): string => PREFIX + setting.key;

const DATASET_KEY = /^dataset\.(.+)$/;

/** The chosen dataset of a game: `dataset.<game>`. Nothing stored: the game's default dataset. */
export function datasetSetting(game: string): Setting<string> {
  if (!ID_RULE.test(game)) throw new Error(`settings: "${game}" is not a game id`);
  return { key: `dataset.${game}`, parse: (value: unknown): string => parseId(value, 'dataset') };
}

/** The setting a stored key below "viewer." is; null: the page knows no such setting. */
function settingOf(key: string): Setting<unknown> | null {
  const known = Object.values(settings).find((one) => one.key === key);
  if (known) return known;
  const game = DATASET_KEY.exec(key)?.[1];
  return game !== undefined && ID_RULE.test(game) ? datasetSetting(game) : null;
}

/** Every stored key of the page that is refused: unknown, not JSON, or not its setting's value. */
export function refusedSettings(): RefusedSetting[] {
  const refused: RefusedSetting[] = [];
  for (let i = 0; i < localStorage.length; i += 1) {
    const full = localStorage.key(i);
    if (full === null || !full.startsWith(PREFIX)) continue;
    const stored = localStorage.getItem(full);
    if (stored === null) continue;
    const setting = settingOf(full.slice(PREFIX.length));
    if (!setting) {
      refused.push({ key: full, stored, reason: 'the page has no such setting' });
      continue;
    }
    try {
      setting.parse(JSON.parse(stored));
    } catch (error) {
      refused.push({ key: full, stored, reason: messageOf(error) });
    }
  }
  return refused.sort((a, b) => a.key.localeCompare(b.key));
}

/** Remove the stored keys named; the page reads its defaults for them on the next start. */
export function clearRefused(keys: readonly string[]): void {
  for (const key of keys) {
    if (!key.startsWith(PREFIX)) throw new Error(`settings: "${key}" is not a key of the page`);
    localStorage.removeItem(key);
  }
}

/** The stored value; null: nothing is stored. A value that does not parse throws (it was checked at start). */
export function findSetting<T>(setting: Setting<T>): T | null {
  const text = localStorage.getItem(PREFIX + setting.key);
  if (text === null) return null;
  try {
    return setting.parse(JSON.parse(text));
  } catch (error) {
    throw new Error(`stored setting ${PREFIX}${setting.key} is refused: ${messageOf(error)}`, { cause: error });
  }
}

/** The stored value, or the setting's declared default when nothing is stored. */
export function readSetting<T>(setting: DefaultedSetting<T>): T {
  const stored = findSetting(setting);
  return stored === null ? structuredClone(setting.initial) : stored;
}

/** Write a setting. The value is checked first: a module cannot store what it could not read back. */
export function writeSetting<T>(setting: Setting<T>, value: T): void {
  setting.parse(JSON.parse(JSON.stringify(value)));
  localStorage.setItem(PREFIX + setting.key, JSON.stringify(value));
}

/** Remove a setting. */
export function clearSetting<T>(setting: Setting<T>): void {
  localStorage.removeItem(PREFIX + setting.key);
}

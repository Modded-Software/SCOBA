// The page's stored settings (SPEC-VIEWER section 10.3): every localStorage
// key, its parser and its type. A module reads and writes only through
// here. Each value is stored as JSON. A stored value that does not parse
// is refused, reported and not used; the next write replaces it (R-VIEW-73).
// Scenes are not settings: they are documents in IndexedDB (store/scenes-db.ts).

import { SCENE_ID_RULE } from '../../shared/scene';
import { ID_RULE } from '../../shared/protocol';
import type { CameraState, Landmark, SkyChoice } from './app';
import { messageOf } from './dom';

const PREFIX = 'viewer.';

/** 'none' (nothing stored), 'restored', or 'refused: <why>'. */
export type Restore = 'none' | 'restored' | `refused: ${string}`;

export interface Setting<T> {
  /** Below "viewer.". */
  readonly key: string;
  /** The stored JSON value, checked. Throws, naming the fault. */
  parse(value: unknown): T;
}

export interface Read<T> {
  value: T | null;
  restore: Restore;
}

const field = (value: unknown, key: string): unknown => (typeof value === 'object' && value !== null && !Array.isArray(value) ? Reflect.get(value, key) : undefined);
const finite = (n: unknown): n is number => typeof n === 'number' && Number.isFinite(n);
const filled = (v: unknown): v is string => typeof v === 'string' && v !== '';

function vec3(value: unknown, what: string): [number, number, number] {
  if (!Array.isArray(value) || value.length !== 3) throw new Error(`${what} is not 3 numbers`);
  const [x, y, z]: unknown[] = value;
  if (!finite(x) || !finite(y) || !finite(z)) throw new Error(`${what} is not 3 numbers`);
  return [x, y, z];
}

/** A camera view: every field a finite number, the distance positive. */
function parseView(value: unknown, what: string): CameraState {
  const yaw = field(value, 'yaw');
  const pitch = field(value, 'pitch');
  const distance = field(value, 'distance');
  if (!finite(yaw) || !finite(pitch) || !finite(distance)) throw new Error(`${what} is not a view`);
  if (distance <= 0) throw new Error(`${what} has distance ${distance}`);
  return { yaw, pitch, distance, target: vec3(field(value, 'target'), `${what}: the target`) };
}

export interface DrawersSetting {
  panel: boolean;
  instances: boolean;
}

export interface ViewSetting {
  grid: boolean;
  sky: SkyChoice | null;
}

export interface LandmarksSetting {
  /** Without the origin, which is always there. */
  list: Landmark[];
  selected: number | null;
}

/** A stored landmark; ids start at 1 (0 is the origin). */
function parseLandmark(value: unknown): Landmark {
  const id = field(value, 'id');
  const name = field(value, 'name');
  if (typeof id !== 'number' || !Number.isInteger(id) || id <= 0 || !filled(name)) throw new Error('not a landmark');
  return { id, name, ...parseView(value, `"${name}"`) };
}

export const settings = {
  camera: {
    key: 'camera',
    parse: (value: unknown): CameraState => parseView(value, 'the camera'),
  },
  drawers: {
    key: 'drawers',
    parse(value: unknown): DrawersSetting {
      const panel = field(value, 'panel');
      const instances = field(value, 'instances');
      if (typeof panel !== 'boolean' || typeof instances !== 'boolean') throw new Error('not two drawer flags');
      return { panel, instances };
    },
  },
  view: {
    key: 'view',
    parse(value: unknown): ViewSetting {
      const grid = field(value, 'grid');
      if (typeof grid !== 'boolean') throw new Error('no grid setting');
      const sky = field(value, 'sky');
      if (sky === null) return { grid, sky: null };
      const id = field(sky, 'id');
      const name = field(sky, 'name');
      const file = field(sky, 'file');
      if (!filled(id) || !filled(name) || !filled(file)) throw new Error('the sky is not a skybox');
      return { grid, sky: { id, name, file } };
    },
  },
  landmarks: {
    key: 'landmarks',
    parse(value: unknown): LandmarksSetting {
      const stored = field(value, 'list');
      if (!Array.isArray(stored)) throw new Error('no landmark list');
      const list = stored.map(parseLandmark);
      if (new Set(list.map((l) => l.id)).size !== list.length) throw new Error('an id is used twice');
      // The chosen one: the origin (0) or one of the list; anything else is none chosen.
      const chosen = field(value, 'selected');
      const selected = typeof chosen === 'number' && (chosen === 0 || list.some((l) => l.id === chosen)) ? chosen : null;
      return { list, selected };
    },
  },
  scene: {
    key: 'scene',
    parse(value: unknown): string {
      if (typeof value !== 'string' || !SCENE_ID_RULE.test(value)) throw new Error('not a scene id');
      return value;
    },
  },
} as const;

/** The chosen dataset of a game: `dataset.<game>`. */
export function datasetSetting(game: string): Setting<string> {
  if (!ID_RULE.test(game)) throw new Error(`settings: "${game}" is not a game id`);
  return {
    key: `dataset.${game}`,
    parse(value: unknown): string {
      if (typeof value !== 'string' || !ID_RULE.test(value)) throw new Error('not a dataset id');
      return value;
    },
  };
}

/** Read a setting. A refused value is reported on the console and not used. */
export function readSetting<T>(setting: Setting<T>): Read<T> {
  const text = localStorage.getItem(PREFIX + setting.key);
  if (text === null) return { value: null, restore: 'none' };
  try {
    return { value: setting.parse(JSON.parse(text)), restore: 'restored' };
  } catch (error) {
    const restore: Restore = `refused: ${messageOf(error)}`;
    console.warn(`viewer: stored ${setting.key} ${restore}`);
    return { value: null, restore };
  }
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

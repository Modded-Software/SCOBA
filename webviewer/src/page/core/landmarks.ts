// Landmarks: named camera views to jump back to; part of the camera
// service. "origin" (looking at 0, 0, 0) is always there and cannot be
// deleted. The landmarks and the one chosen are a setting
// (core/settings.ts). The drop-down and its dialogs are features/landmarks.

import type { Store } from './context';
import type { EventBus, ViewerEvents } from './bus';
import { ORIGIN_LANDMARK, settings } from './settings';
import type { CameraState, Landmark } from './types';

const ORIGIN_ID = ORIGIN_LANDMARK;
const ORIGIN: Landmark = { id: ORIGIN_ID, name: 'origin (0, 0, 0)', target: [0, 0, 0], yaw: -Math.PI / 2, pitch: 0.5, distance: 9 };

const copy = (l: Landmark): Landmark => ({ ...l, target: [...l.target] });

export interface Landmarks {
  /** Add a landmark; a taken name gets " (2)", " (3)"... It becomes the chosen one. Returns its id. */
  addLandmark(view: Omit<Landmark, 'id'>): number;
  goToLandmark(id: number): void;
  /** Delete a landmark. The camera stays; a deleted chosen one leaves none chosen. */
  removeLandmark(id: number): void;
  landmarks(): Landmark[];
  /** The landmarks, the chosen one, and where the start came from: stored, or the declared default. */
  landmarkState(): { list: Landmark[]; selected: number | null; start: 'stored' | 'default' };
  /** The one that cannot be deleted. */
  readonly originId: number;
}

export function createLandmarks(store: Store, events: EventBus<ViewerEvents>, view: (next: Partial<CameraState>) => void): Landmarks {
  const list: Landmark[] = [ORIGIN];
  let nextId = ORIGIN_ID + 1;
  // The stored landmarks, else the setting's declared default: none but the origin.
  const found = store.find(settings.landmarks);
  const start = found === null ? 'default' : 'stored';
  const stored = found === null ? structuredClone(settings.landmarks.initial) : found;
  list.push(...stored.list);
  nextId = Math.max(ORIGIN_ID, ...stored.list.map((l) => l.id)) + 1;
  /** The landmark chosen last, or null. */
  let selected: number | null = stored.selected;

  function changed(): void {
    store.write(settings.landmarks, { list: list.filter((l) => l.id !== ORIGIN_ID).map(copy), selected });
    events.emit('landmarks-changed', { list: list.map(copy), selected });
  }

  return {
    originId: ORIGIN_ID,
    addLandmark(next) {
      let name = next.name;
      for (let n = 2; list.some((l) => l.name === name); n++) name = `${next.name} (${n})`;
      const landmark: Landmark = { id: nextId++, name, target: [...next.target], yaw: next.yaw, pitch: next.pitch, distance: next.distance };
      list.push(landmark);
      selected = landmark.id;
      changed();
      return landmark.id;
    },
    goToLandmark(id) {
      const l = list.find((x) => x.id === id);
      if (!l) throw new Error(`no landmark ${id}`);
      view({ target: [...l.target], yaw: l.yaw, pitch: l.pitch, distance: l.distance });
      selected = id;
      changed();
    },
    removeLandmark(id) {
      if (id === ORIGIN_ID) throw new Error('the origin landmark cannot be deleted');
      const at = list.findIndex((l) => l.id === id);
      if (at < 0) throw new Error(`no landmark ${id}`);
      list.splice(at, 1);
      if (selected === id) selected = null;
      changed();
    },
    landmarks: () => list.map(copy),
    landmarkState: () => ({ list: list.map(copy), selected, start }),
  };
}

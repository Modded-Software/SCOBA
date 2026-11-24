// The page's events (SPEC-VIEWER 6.6): how the services and the features
// tell each other what changed. A listener that throws is reported and the
// others still run: one broken feature must not stop the rest.

import type { CameraState, Item, Landmark, Sky } from './types';

/** A field of an item that its list row shows. */
export type ItemField = 'sequence' | 'rot' | 'x' | 'y';

export interface ViewerEvents {
  /** An item joined the scene. */
  'item-added': { item: Item };
  /** Items left the scene; `all`: the scene was cleared. */
  'items-removed': { ids: readonly number[]; all: boolean };
  /** An item got another model (variant, dataset): its row is rebuilt. */
  'item-swapped': { item: Item };
  /** A field its row shows changed. The document is not written for this alone. */
  'item-changed': { item: Item; field: ItemField };
  /** An edit the scene document keeps is done: write it (features/scenes). */
  'scene-edited': { what: string };
  /** The selection changed. */
  'selection-changed': { ids: ReadonlySet<number>; last: number | null };
  /** The gallery's game changed (and at startup, once the first is read). */
  'game-changed': { game: string };
  /** The gallery's dataset changed (also after a game change). */
  'dataset-changed': { game: string; dataset: string };
  /** The sky or the grid toggle changed (core/sky.ts). */
  'view-changed': { sky: Readonly<Sky> | null; grid: boolean };
  /** The landmarks or the chosen one changed (core/landmarks.ts). */
  'landmarks-changed': { list: readonly Landmark[]; selected: number | null };
  /** The camera moved. */
  'camera-changed': { camera: Readonly<CameraState> };
  /** One frame: after the update, before the draw; dt in ms. */
  frame: { dt: number };
  /**
   * Startup, once the games and the first game's datasets are read. A
   * listener hands its work to `wait`; the page is ready when all of it is done.
   */
  startup: { wait(work: Promise<unknown>): void };
  /** Writes in flight must end (before a dataset reload): a listener hands them to `wait`. */
  flush: { wait(work: Promise<unknown>): void };
}

/** Emit a collecting event (startup, flush) and wait for all the work the listeners handed in. */
export async function collect<K extends 'startup' | 'flush'>(events: EventBus<ViewerEvents>, name: K): Promise<void> {
  const work: Promise<unknown>[] = [];
  events.emit(name, { wait: (p) => work.push(p) });
  await Promise.all(work);
}

export type Listener<T> = (payload: T) => void;

export interface EventBus<E> {
  /** Listen; the result stops listening. */
  on<K extends keyof E>(name: K, listener: Listener<E[K]>): () => void;
  emit<K extends keyof E>(name: K, payload: E[K]): void;
}

type Listeners<E> = { [K in keyof E]?: Listener<E[K]>[] };

export function createEventBus<E>(report: (error: unknown) => void): EventBus<E> {
  const listeners: Listeners<E> = {};
  return {
    on(name, listener) {
      const list = listeners[name] ?? [];
      list.push(listener);
      listeners[name] = list;
      return () => {
        const at = list.indexOf(listener);
        if (at >= 0) list.splice(at, 1);
      };
    },
    emit(name, payload) {
      // A copy: a listener may stop listening while the event runs.
      for (const listener of [...(listeners[name] ?? [])]) {
        try {
          listener(payload);
        } catch (error) {
          report(error);
        }
      }
    },
  };
}

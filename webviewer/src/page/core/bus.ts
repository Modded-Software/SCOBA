// The page's events (SPEC-VIEWER 6.6): how the services and the features
// tell each other what changed. A listener that throws is reported and the
// others still run: one broken feature must not stop the rest.

import type { CameraState, GroundChoice, Item, Landmark, Sky } from './types';

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
  /** The sky, the grid toggle or the ground texture changed (core/sky.ts). */
  'view-changed': { sky: Readonly<Sky> | null; grid: boolean; ground: Readonly<GroundChoice> | null };
  /** The landmarks or the chosen one changed (core/landmarks.ts). */
  'landmarks-changed': { list: readonly Landmark[]; selected: number | null };
  /** The camera moved. */
  'camera-changed': { camera: Readonly<CameraState> };
  /** A variant, a skin or a bake of a game's dataset changed (SPEC-VIEWER 17, R-VIEW-109). */
  'textures-changed': { game: string; dataset: string };
  /** The texture window asks for the upscale dialog on one texture (SPEC-VIEWER 17.5). */
  'texture-upscale': { game: string; dataset: string; asset: string };
  /**
   * The texture window asks to save its picks to a skin of the owner (SPEC-VIEWER 17.3, 17.6.2, R-VIEW-133).
   * `item`: the instance it was opened on, or null. `done` gets the target saved to, or null: cancelled or refused.
   */
  'texture-save': { game: string; dataset: string; owner: string; picks: { asset: string; variant: string }[]; item: number | null; done(target: string | null): void };
  /**
   * A variant tile's trash (SPEC-VIEWER 17.6.1, R-VIEW-147): the main page asks first, then removes it.
   * `done` gets true when it was removed, false when cancelled; an Error when refused.
   */
  'texture-remove': { game: string; dataset: string; asset: string; variant: string; done(removed: boolean | Error): void };
  /** A tile's Edit Texture button: open the edit session of a texture's variant in the editor window (SPEC-PHOTOCRAFT 9.1). */
  'texture-edit': { game: string; dataset: string; asset: string; variant: string };
  /** The texture window's Manage Edits… button: list the edit sessions of a dataset (SPEC-PHOTOCRAFT 9.5). */
  'edits-manage': { game: string; dataset: string };
  /** One frame: after the update, before the draw; dt in ms. */
  frame: { dt: number };
  /**
   * One frame: the units' scene and its post passes are drawn, the mouse-over
   * outline not yet. A listener may draw over the canvas with the scene's depth.
   */
  'scene-drawn': { width: number; height: number };
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

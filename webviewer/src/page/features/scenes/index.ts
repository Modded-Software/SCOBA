// Scenes (SPEC-VIEWER section 10.2): every scene is a document in IndexedDB
// (core/store/scenes-db.ts), checked by src/shared/scene.ts. One is open:
// its items are the instances in the view, and every change to them writes
// it. The page address holds no scene. The scene list: list.ts.

import { emptyScene, freeName, newSceneId, parseSceneDocument, type SceneDocument, type SceneItemDocument } from '../../../shared/scene';
import type { Feature, FeatureContext } from '../../core/context';
import type { AddOptions, Item, RefusedScene, ScenesState } from '../../core/types';
import { messageOf } from '../../core/dom';
import { SettingsRefused } from '../../core/refusals';
import { keyOf, settings } from '../../core/settings';
import { openSceneStore, type SceneStore } from '../../core/store/scenes-db';
import { installSceneList } from './list';

const FIRST_NAME = 'scene 1';

/** An item of the view as a scene item. */
function itemDocument(item: Item): SceneItemDocument {
  const own = item.source;
  const source: SceneItemDocument['source'] = own ? { category: own.category, record: own.record.id, variant: item.placement.variant } : { file: item.path };
  return { game: item.game, dataset: item.dataset, source, x: item.x, y: item.y, rot: item.rot, scale: item.scale, sequence: item.sequence, pick: item.placement.pick, options: { team: item.team, skin: item.skin, ...item.options } };
}

/**
 * The item options (section 10.2): `team` and `skin` are core's; the rest go to the game's itemOptions,
 * which refuses a key it does not know. A `team` or `skin` of the wrong type is refused.
 */
function itemOptions(options: SceneItemDocument['options']): Pick<AddOptions, 'team' | 'skin' | 'options'> {
  const { team, skin, ...rest } = options;
  if (team !== undefined && !(typeof team === 'number' && Number.isInteger(team))) throw new Error(`option team: not a whole number: ${JSON.stringify(team)}`);
  if (skin !== undefined && !(typeof skin === 'string' && skin)) throw new Error(`option skin: not a name: ${JSON.stringify(skin)}`);
  return { ...(team === undefined ? {} : { team }), ...(skin === undefined ? {} : { skin }), options: rest };
}

/** Add one scene item to the view. A fault names the item. */
async function addItem({ games, api, scene }: Pick<FeatureContext, 'games' | 'api' | 'scene'>, entry: SceneItemDocument, index: number): Promise<void> {
  const where = `scene item ${index + 1}`;
  // A game the page has no module for, or one the server cannot open: reported, not added (R-VIEW-80).
  const why = games.gameRefusal(entry.game);
  if (why !== null) throw new Error(`${where}: game "${entry.game}": ${why}`);
  await games.loadGame(entry.game);
  if (!api.hasDataset(entry.dataset, entry.game)) throw new Error(`${where}: no dataset "${entry.dataset}"`);
  const options: AddOptions = { game: entry.game, dataset: entry.dataset, x: entry.x, y: entry.y, rot: entry.rot, scale: entry.scale, sequence: entry.sequence, pick: entry.pick, ...itemOptions(entry.options) };
  const { source } = entry;
  if ('file' in source) {
    await scene.add(source.file, options);
  } else if (games.pluginOf(entry.game).categories.some((c) => c.id === source.category)) {
    await scene.addRecord(source.category, source.record, { ...options, variant: source.variant });
  } else {
    throw new Error(`${where}: no category "${source.category}"`);
  }
}

export const scenesFeature: Feature = {
  id: 'scenes',
  install(context) {
    const { scene: view, status, store: settingsStore, events, testApi } = context;
    let store: SceneStore | null = null;
    /** The scenes that passed the check, by id. */
    const scenes = new Map<string, SceneDocument>();
    let refused: RefusedScene[] = [];
    let openId: string | null = null;
    /** While a scene's items are added: no write. */
    let loading = false;
    /** The address at startup, and what was done with it. */
    let address = '';
    /** Writes run one after another; this is the last. */
    let writes: Promise<void> = Promise.resolve();
    /** Scene opens run one after another too. */
    let opens: Promise<void> = Promise.resolve();

    function needStore(): SceneStore {
      if (!store) throw new Error('scenes: the scene store is not open yet');
      return store;
    }

    function write(scene: SceneDocument): Promise<void> {
      const target = needStore();
      // Checked before it is stored: what is written can be read back.
      const checked = parseSceneDocument(JSON.parse(JSON.stringify(scene)));
      writes = writes.then(() => target.put(checked)).catch((error: unknown) => status.reportFailure(new Error(`scene "${scene.name}" was not saved: ${messageOf(error)}`)));
      return writes;
    }

    /** The open scene as it would be stored now. */
    function current(): SceneDocument | null {
      const scene = openId === null ? undefined : scenes.get(openId);
      if (!scene) return null;
      return { ...scene, items: view.items.map(itemDocument) };
    }

    /** Write the open scene: after every change to the instances. */
    function saveScene(): void {
      if (loading || !store) return;
      const scene = current();
      if (!scene) return;
      const saved = { ...scene, modified: new Date().toISOString() };
      scenes.set(saved.id, saved);
      write(saved).catch(status.reportFailure);
      list.render();
    }

    /** Clear the view and add the scene's items, in order. Nothing is written meanwhile. */
    async function show(scene: SceneDocument): Promise<void> {
      loading = true;
      try {
        view.clear();
        openId = scene.id;
        settingsStore.write(settings.scene, scene.id);
        list.render();
        for (const [index, entry] of scene.items.entries()) {
          await addItem(context, entry, index).catch(status.reportFailure);
        }
      } finally {
        loading = false;
      }
    }

    function openScene(id: string): Promise<void> {
      const run = opens.then(async () => {
        const scene = scenes.get(id);
        if (!scene) throw new Error(`no scene "${id}"`);
        await writes;
        await show(scene);
      });
      // The caller gets the failure through run; the queue logs it and goes on.
      opens = run.catch((error: unknown) => {
        console.warn('scobaeditor: scene open failed:', error);
      });
      return run;
    }

    const names = (except: string | null = null): string[] => [...scenes.values()].filter((s) => s.id !== except).map((s) => s.name);

    async function newScene(name: string): Promise<string> {
      const scene = emptyScene(freeName(name, names()));
      scenes.set(scene.id, scene);
      await write(scene);
      await openScene(scene.id);
      return scene.id;
    }

    async function renameScene(id: string, name: string): Promise<void> {
      const scene = scenes.get(id);
      if (!scene) throw new Error(`no scene "${id}"`);
      const renamed = id === openId ? current() : scene;
      if (!renamed) throw new Error(`no scene "${id}"`);
      const next = { ...renamed, name: freeName(name, names(id)), modified: new Date().toISOString() };
      scenes.set(id, next);
      await write(next);
      list.render();
    }

    /** Delete a scene (the list asks first). The open one: the newest other one opens, or a new empty one. */
    async function deleteScene(id: string): Promise<void> {
      const target = needStore();
      const known = scenes.has(id) || refused.some((r) => r.id === id);
      if (!known) throw new Error(`no scene "${id}"`);
      await writes;
      await target.remove(id);
      scenes.delete(id);
      refused = refused.filter((r) => r.id !== id);
      if (id === openId) {
        openId = null;
        const next = newest();
        if (next) await openScene(next.id);
        else await newScene(FIRST_NAME);
      }
      list.render();
    }

    const newest = (): SceneDocument | undefined => [...scenes.values()].sort((a, b) => b.modified.localeCompare(a.modified))[0];

    /** The open scene as the text of a file. */
    function exportScene(): string {
      const scene = current();
      if (!scene) throw new Error('no scene is open');
      return JSON.stringify(scene, null, 2) + '\n';
    }

    /** Check a file's text; store it under a new id and a free name, and open it. A refused file changes nothing. */
    async function importScene(text: string): Promise<string> {
      let parsed: SceneDocument;
      try {
        parsed = parseSceneDocument(JSON.parse(text));
      } catch (error) {
        throw new Error(`import refused: ${messageOf(error)}`);
      }
      const scene: SceneDocument = { ...parsed, id: newSceneId(), name: freeName(parsed.name, names()), modified: new Date().toISOString() };
      scenes.set(scene.id, scene);
      await write(scene);
      await openScene(scene.id);
      return scene.id;
    }

    /** At startup: refuse an address that holds a scene, read every stored scene, open one. */
    async function setupScenes(): Promise<void> {
      if (location.hash.length > 1) {
        address = 'refused';
        history.replaceState(null, '', location.pathname + location.search);
        status.setStatus('the scene is no longer kept in the address: the address was refused and cleared', { failure: true });
      } else {
        address = 'empty';
      }
      store = await openSceneStore();
      // The store's key path is the id: a record's key is its id.
      for (const { key, value } of await store.all()) {
        try {
          const scene = parseSceneDocument(value);
          scenes.set(scene.id, scene);
        } catch (error) {
          const reason = messageOf(error);
          refused.push({ id: key, name: typeof value === 'object' && value !== null && typeof Reflect.get(value, 'name') === 'string' ? String(Reflect.get(value, 'name')) : null, reason });
          console.warn(`viewer: stored scene "${key}" refused: ${reason}`);
        }
      }
      if (refused.length) status.setStatus(`${refused.length} stored scene(s) refused; see the scene list`, { failure: true });
      // The open scene: the stored one; nothing stored, the newest; no scene, a new one.
      // A stored id that names no readable scene is refused (core/refusals.ts), not replaced.
      const stored = settingsStore.find(settings.scene);
      if (stored !== null) {
        const chosen = scenes.get(stored);
        if (!chosen) {
          const bad = refused.find((one) => one.id === stored);
          throw new SettingsRefused([{ key: keyOf(settings.scene), stored: JSON.stringify(stored), reason: bad ? `the scene is refused: ${bad.reason}` : 'there is no such scene' }]);
        }
        await openScene(chosen.id);
        return;
      }
      const first = newest();
      if (first) await openScene(first.id);
      else await newScene(FIRST_NAME);
    }

    function scenesState(): ScenesState {
      const open = openId === null ? null : (scenes.get(openId) ?? null);
      return {
        open: open ? { id: open.id, name: open.name } : null,
        list: [...scenes.values()].sort((x, y) => x.name.localeCompare(y.name)).map((s) => ({ id: s.id, name: s.name, items: s.id === openId ? view.items.length : s.items.length, modified: s.modified })),
        refused: refused.map((r) => ({ ...r })),
        loading,
        address,
      };
    }

    const list = installSceneList(status, { state: scenesState, openScene, newScene, renameScene, deleteScene, exportScene, importScene });

    // Every edit of the scene is written (core/scene.ts and the features say so).
    events.on('scene-edited', saveScene);
    events.on('startup', ({ wait }) => wait(setupScenes()));
    const flushScenes = async (): Promise<void> => {
      await opens;
      await writes;
    };
    events.on('flush', ({ wait }) => wait(flushScenes()));

    testApi.viewer({
      scenes: {
        state: scenesState,
        document: current,
        flush: flushScenes,
        create: newScene,
        open: openScene,
        rename: renameScene,
        remove: deleteScene,
        exportText: exportScene,
        importText: importScene,
      },
    });
  },
};

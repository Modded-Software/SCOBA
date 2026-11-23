// The loaded datasets of the SC2 game: each one's map layer over the
// storage, its catalogs, and its signatures. Also the skyboxes, which
// follow the files.

import { execFile } from 'node:child_process';
import { join } from 'node:path';
import { promisify } from 'node:util';
import { messageOf } from '../../../server/core/http';
import { builtSignature, DEFAULT_DATASET, listDatasets, signature, type DatasetDef, type DatasetProblem, type Folders } from './datasets';
import { loadDoodads, type Doodads } from './doodads';
import { isSkyboxKey, listSkyboxes, skyboxModels, type Skybox } from './skyboxes';
import type { Storage } from './storage';
import { loadUnits, type Units } from './units';

const run = promisify(execFile);

/** How long a computed dataset signature is good for (the page polls). */
const SIGNATURE_AGE = 1000; // ms
/** The servable path prefix of the default dataset's map layer. */
export const MAP_PREFIX = 'map\\';

/** In-model asset path -> servable path, as one dataset sees it. */
export interface DatasetAssets {
  get(key: string): string | undefined;
  readonly overlay: ReadonlyMap<string, string>;
}

export interface Dataset extends DatasetDef {
  readonly assets: DatasetAssets;
  readonly units: Units;
  readonly doodads: Doodads;
  /** The signature its catalog was built from. */
  readonly loaded: string | null;
  checked: { at: number; value: string } | null;
}

/** What /api/sc2/datasets says of one. */
export interface DatasetView {
  id: string;
  label: string;
  builtin: boolean;
  hasMap: boolean;
  units: number;
  doodads: number;
  signature: string | null;
  current: string;
  changed: boolean;
}

/** The servable path prefix of a dataset's map layer files. */
const layerPrefix = (id: string): string => (id === DEFAULT_DATASET ? MAP_PREFIX : `ds\\${id}\\`);

export interface Loaded {
  readonly datasets: ReadonlyMap<string, Dataset>;
  readonly problems: readonly DatasetProblem[];
  readonly skyboxes: readonly Skybox[];
  describe(state: Dataset): Promise<DatasetView>;
  reload(id: string): Promise<DatasetView>;
}

/**
 * Load every dataset over `storage`. `viewerDir` and `repoRoot` are where
 * scripts/catalog.sh runs, for a reload that rebuilds a catalog.
 */
export async function loadAll(storage: Storage, dirs: Folders, viewerDir: string, repoRoot: string): Promise<Loaded> {
  const datasets = new Map<string, Dataset>();
  let skyboxes: Skybox[] = [];

  /** Load (or load again) one dataset: index its map layer's Assets over the storage, then join its catalogs with the files that can be served. */
  async function loadDataset(def: DatasetDef): Promise<Dataset> {
    const overlay = await storage.addLayer(layerPrefix(def.id), def.mapDir);
    // The map layer first, then the game storage.
    const assets: DatasetAssets = { get: (key) => overlay.get(key) ?? storage.stored.get(key), overlay };
    const state: Dataset = { ...def, assets, units: await loadUnits(def.catalogDir, assets), doodads: await loadDoodads(def.catalogDir, assets), loaded: await builtSignature(def), checked: null };
    datasets.set(def.id, state);
    return state;
  }

  /** After any dataset load: the model list and the skyboxes follow the files. */
  async function refreshShared(): Promise<void> {
    storage.refreshModels();
    const named = await skyboxModels(dirs.stock, dirs.map);
    for (const state of datasets.values()) state.units.markSkyboxes((key) => isSkyboxKey(named, key));
    const main = datasets.get(DEFAULT_DATASET);
    if (!main) throw new Error(`the default dataset "${DEFAULT_DATASET}" is not loaded`);
    skyboxes = listSkyboxes(new Set([...main.assets.overlay.keys(), ...storage.stored.keys()]), main.assets.get, named, MAP_PREFIX);
  }

  /** The dataset's source fingerprint now; computed at most once per SIGNATURE_AGE. */
  async function currentSignature(state: Dataset): Promise<string> {
    const now = Date.now();
    if (!state.checked || now - state.checked.at > SIGNATURE_AGE) state.checked = { at: now, value: await signature(state) };
    return state.checked.value;
  }

  /** `signature`: what is loaded; `current`: its sources now; `changed`: they differ. */
  async function describe(state: Dataset): Promise<DatasetView> {
    const current = await currentSignature(state);
    return { id: state.id, label: state.label, builtin: state.builtin, hasMap: Boolean(state.mapDir), units: state.units.size, doodads: state.doodads.size, signature: state.loaded, current, changed: current !== state.loaded };
  }

  /** One reload at a time: a catalog build is heavy. */
  let reloading: Promise<unknown> = Promise.resolve();

  /** Rebuild a dataset's catalog when its sources changed since it was built, then load it again. */
  function reload(id: string): Promise<DatasetView> {
    const job = reloading.then(async () => {
      const state = datasets.get(id);
      if (!state) throw new Error(`no dataset "${id}"`);
      const current = await signature(state);
      if ((await builtSignature(state)) !== current) {
        await run('bash', [join(viewerDir, 'scripts', 'catalog.sh'), '--dataset', id], { cwd: viewerDir, env: { ...process.env, WEBVIEWER_DIR: viewerDir, REPO_ROOT: repoRoot }, maxBuffer: 64 * 1024 * 1024 }).catch((error: unknown) => {
          const stderr: unknown = typeof error === 'object' && error !== null ? Reflect.get(error, 'stderr') : undefined;
          const why = typeof stderr === 'string' && stderr ? stderr : messageOf(error);
          throw new Error(`catalog build failed for "${id}": ${why.trim().split('\n').slice(-5).join(' | ')}`);
        });
      }
      const { datasets: defs } = await listDatasets(dirs);
      const def = defs.find((d) => d.id === id);
      if (!def) throw new Error(`dataset "${id}" is gone`);
      const next = await loadDataset(def);
      await refreshShared();
      return describe(next);
    });
    // A failed reload must not block the next one. The caller gets the error from `job`; the chain logs it.
    reloading = job.catch((error: unknown) => console.error(`viewer: reload of dataset "${id}" failed: ${messageOf(error)}`));
    return job;
  }

  const found = await listDatasets(dirs);
  for (const problem of found.problems) console.warn(`sc2 webviewer: not a dataset: ${problem.dir}: ${problem.reason}`);
  for (const def of found.datasets) await loadDataset(def);
  await refreshShared();

  return {
    datasets,
    problems: found.problems,
    get skyboxes() {
      return skyboxes;
    },
    describe,
    reload,
  };
}

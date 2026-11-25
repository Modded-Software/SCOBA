// The SC2 game on the server (SPEC-VIEWER-SC2): its settings, its files
// and datasets, and its answers to the protocol of SPEC-VIEWER section 8.
// The record and row bodies are the unit and doodad records of
// src/games/sc2/shared/records.ts.

import { mkdir } from 'node:fs/promises';
import { join } from 'node:path';
import type { CategoryInfo, FilterInfo } from '../../../shared/protocol';
import { HttpError, type GameBackend } from '../../../server/core/backend';
import { requiredPath, type CoreSettings } from '../../../server/core/settings';
import { DEFAULT_DATASET, folders } from './datasets';
import { loadAll, type Dataset } from './loaded';
import { searchSkyboxes } from './skyboxes';
import { createStorage } from './storage';
import { searchTerrain, terrainRecord } from './terrain';
import { messageOf } from '../../../server/core/http';
import { pipelineTextures, storeDirOf } from '../../../server/core/textures';

/** The game id, as the pipeline knows it too (`--game`). */
const SC2 = 'sc2';
/** How the pipeline begins the origin of a file of a dataset's own layer (scripts/hdtex/sc2/storage.py). */
const OWN = 'dataset\\';
/** The category of the ground textures (SPEC-VIEWER 17.5). */
const TERRAIN = 'terrain';

const filter = (id: string, label: string, kind: FilterInfo['kind'], values: readonly string[], labelOf: (v: string) => string = (v) => v): FilterInfo => ({
  id,
  label,
  kind,
  values: values.map((value) => ({ value, label: labelOf(value) })),
});

/** The categories of one dataset; the filter values are its catalogs' facets, the most common first. */
function categories(data: Dataset): CategoryInfo[] {
  const u = data.units.facets;
  const d = data.doodads.facets;
  const lower = (v: string): string => v.toLowerCase();
  return [
    {
      id: 'units',
      label: 'units',
      noun: 'unit',
      addAll: true,
      rows: 'records',
      icons: true,
      filters: [filter('race', 'race', 'buttons', u.races, lower), filter('kind', 'kind', 'select', u.kinds, lower), filter('family', 'family', 'select', u.families, (v) => (v ? v.toLowerCase() : '(no family)'))],
    },
    { id: 'doodads', label: 'doodads', noun: 'doodad', addAll: true, rows: 'records', icons: false, filters: [filter('type', 'type', 'select', d.types, lower), filter('tileset', 'terrain', 'select', [...d.tilesets].sort())] },
    { id: 'models', label: 'models', noun: 'model file', addAll: false, rows: 'files', icons: false, filters: [] },
    { id: TERRAIN, label: 'terrain', noun: 'ground texture', addAll: false, rows: 'records', icons: false, filters: [] },
  ];
}

/** Index the storage, load every dataset, and answer as the SC2 backend. */
export async function startSc2(core: CoreSettings, env: NodeJS.ProcessEnv = process.env): Promise<GameBackend & { banner(): string }> {
  const dirs = folders(core.viewerDir, env);
  const stormex = env['STORMEX'] || join(core.repoRoot, 'tools', 'stormex');
  const gameDir = requiredPath(env, 'SC2_PATH');
  await mkdir(dirs.cache, { recursive: true });
  const storage = createStorage(stormex, gameDir, dirs.cache);
  await storage.index();
  const loaded = await loadAll(storage, dirs, core.viewerDir, core.repoRoot);

  const dataOf = (id: string): Dataset => {
    const data = loaded.datasets.get(id);
    if (!data) throw new HttpError(404, { error: 'no such dataset', dataset: id });
    return data;
  };
  const noCategory = (category: string): HttpError => new HttpError(404, { error: 'no such category', category });
  // The pipeline of SPEC-HD-TEXTURES; a dataset's own folder is its map layer.
  const textures = pipelineTextures({ game: SC2, repoRoot: core.repoRoot, storeDir: storeDirOf(env), layerOf: (id) => dataOf(id).mapDir, logDir: join(dirs.cache, 'textures'), env });
  // The pipeline brings its state index up to date with each dataset's files. Showing a model does not
  // depend on it: a failure is logged, and the states stay as the index holds them (R-VIEW-110).
  const indexTextures = (id: string): Promise<void> => textures.sync(id).catch((error: unknown) => console.error(`viewer: the texture index of dataset "${id}" was not brought up to date: ${messageOf(error)}`));
  // Built only when missing (operator 2026-11-25): a dataset the index already holds is not synced at
  // the start. A reload (the dataset's files changed) brings it up to date.
  for (const id of loaded.datasets.keys()) {
    if (!textures.indexed(id)) await indexTextures(id);
  }

  /**
   * The servable path of a texture (R-VIEW-112). A texture the pipeline indexes lies where it says, so a result
   * and the original shown beside it are of one file; the pipeline knows the archives its dataset loads.
   * One it does not index (another archive's) is the dataset's own lookup. Indexed but not found where the
   * pipeline says is an error, not another file.
   */
  function textureOf(data: Dataset, key: string): string | undefined {
    const origin = textures.origin(data.id, key);
    if (origin === null) return data.assets.get(key);
    if (!origin.startsWith(OWN)) return origin;
    const own = data.assets.overlay.get(key);
    if (own === undefined) throw new HttpError(500, { error: `${key}: the texture index says it is the map's own, and ${data.id}'s map has no such file; reindex the dataset` });
    return own;
  }

  return {
    id: SC2,
    label: 'StarCraft II',
    tab: 'SC2',
    defaultDataset: DEFAULT_DATASET,
    hasDataset: (id) => loaded.datasets.has(id),
    async datasets() {
      const list = [];
      for (const state of loaded.datasets.values()) list.push(await loaded.describe(state));
      return { default: DEFAULT_DATASET, datasets: list, problems: loaded.problems };
    },
    // A reload: the dataset's files changed, so the pipeline lists its textures again.
    reload: async (id) => {
      const view = await loaded.reload(id);
      await indexTextures(id);
      return view;
    },
    categories: (id) => categories(dataOf(id)),
    summary(id) {
      const data = dataOf(id);
      return { models: storage.modelCount, files: storage.size, units: data.units.size, unitsWithoutModelFile: data.units.withoutFile, skyboxes: loaded.skyboxes.length, doodads: data.doodads.size, doodadsWithoutModelFile: data.doodads.withoutFile, datasets: loaded.datasets.size };
    },
    list(id, category, { q, offset, limit, filters }) {
      const data = dataOf(id);
      if (category === 'units') return data.units.search(q, filters['race'] ?? '', filters['kind'] ?? '', filters['family'] ?? null, offset, limit);
      if (category === 'doodads') return data.doodads.search(q, filters['type'] ?? '', filters['tileset'] ?? '', offset, limit);
      // O-SC2-1: the model files of every dataset together, as before.
      if (category === 'models') return storage.search(q, offset, limit);
      if (category === TERRAIN) return searchTerrain(textures, data.id, q, offset, limit);
      throw noCategory(category);
    },
    record(id, category, recordId) {
      const data = dataOf(id);
      if (category === TERRAIN) return { ...terrainRecord(textures, data.id, recordId), dataset: data.id };
      if (category !== 'units' && category !== 'doodads') throw noCategory(category);
      const record = (category === 'units' ? data.units : data.doodads).get(recordId);
      if (!record) throw new HttpError(404, { error: 'not found', id: recordId, dataset: data.id });
      return { ...record, dataset: data.id };
    },
    file: (_id, path) => storage.locate(path),
    async asset(id, kind, reference) {
      // An in-model path, as the dataset sees it: its map layer, then the storage.
      if (kind !== 'model' && kind !== 'texture') throw new HttpError(404, { error: `sc2 has no ${kind} assets`, kind });
      const data = dataOf(id);
      const key = reference.toLowerCase().replaceAll('/', '\\');
      const servable = kind === 'texture' ? textureOf(data, key) : data.assets.get(key);
      return servable === undefined ? null : storage.locate(servable);
    },
    icon(id, name) {
      // Only names the dataset's catalog lists, so no path can leave the icon folder.
      const data = dataOf(id);
      return data.units.icons.has(name) ? join(data.catalogDir, 'icons', name) : null;
    },
    backdrops: ({ q, offset, limit }) => {
      const found = searchSkyboxes(loaded.skyboxes, q, offset, limit);
      return { total: found.total, items: found.items.map((sky) => ({ ...sky, game: 'sc2', dataset: DEFAULT_DATASET })) };
    },
    extensions: {},
    textures,
    banner: () => {
      const lines = [...loaded.datasets.values()].map((d) => `${d.id}: ${d.units.size} units (${d.units.withoutFile} without a model file), ${d.doodads.size} doodads (${d.doodads.withoutFile} without)`);
      return `${storage.modelCount} models; ${lines.join('; ')}`;
    },
  };
}

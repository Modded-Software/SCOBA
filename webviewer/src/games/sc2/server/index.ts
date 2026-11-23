// The SC2 game on the server (SPEC-VIEWER-SC2): its settings, its files
// and datasets, and its answers to the protocol of SPEC-VIEWER section 8.
// The record and row bodies are today's (the unit and doodad records of
// src/shared/records.ts); RecordSummary and RecordDetail are step 5.

import { mkdir } from 'node:fs/promises';
import { homedir } from 'node:os';
import { join } from 'node:path';
import type { CategoryInfo, FilterInfo } from '../../../shared/protocol';
import { HttpError, type GameBackend } from '../../../server/core/backend';
import type { CoreSettings } from '../../../server/core/settings';
import { DEFAULT_DATASET, folders } from './datasets';
import { loadAll, type Dataset } from './loaded';
import { searchSkyboxes } from './skyboxes';
import { createStorage } from './storage';
import { hdModelsRoot, hdRoute, texturesRoot, texturesRoute } from './textures';

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
  return [
    { id: 'units', label: 'units', noun: 'unit', addAll: true, filters: [filter('race', 'race', 'buttons', u.races), filter('kind', 'kind', 'select', u.kinds), filter('family', 'family', 'select', u.families, (v) => v || 'no family')] },
    { id: 'doodads', label: 'doodads', noun: 'doodad', addAll: true, filters: [filter('type', 'type', 'select', d.types), filter('tileset', 'terrain', 'select', d.tilesets)] },
    { id: 'models', label: 'models', noun: 'model file', addAll: false, filters: [] },
  ];
}

/** Index the storage, load every dataset, and answer as the SC2 backend. */
export async function startSc2(core: CoreSettings, env: NodeJS.ProcessEnv = process.env): Promise<GameBackend & { banner(): string }> {
  const dirs = folders(core.viewerDir, env);
  const stormex = env['STORMEX'] || join(core.repoRoot, 'tools', 'stormex');
  const gameDir = env['SC2_PATH'] || env['SC2_INSTALL'] || join(homedir(), 'Games/battlenet-prefix/pfx/drive_c/Program Files (x86)/StarCraft II');
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

  return {
    id: 'sc2',
    label: 'StarCraft II',
    tab: 'SC2',
    defaultDataset: DEFAULT_DATASET,
    hasDataset: (id) => loaded.datasets.has(id),
    async datasets() {
      const list = [];
      for (const state of loaded.datasets.values()) list.push(await loaded.describe(state));
      return { default: DEFAULT_DATASET, datasets: list, problems: loaded.problems };
    },
    reload: (id) => loaded.reload(id),
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
      throw noCategory(category);
    },
    record(id, category, recordId) {
      const data = dataOf(id);
      if (category !== 'units' && category !== 'doodads') throw noCategory(category);
      const record = (category === 'units' ? data.units : data.doodads).get(recordId);
      if (!record) throw new HttpError(404, { error: 'not found', id: recordId, dataset: data.id });
      return { ...record, dataset: data.id };
    },
    file: (_id, path) => storage.locate(path),
    async asset(id, kind, reference) {
      // An in-model path, as the dataset sees it: its map layer, then the storage.
      if (kind !== 'model' && kind !== 'texture') throw new HttpError(404, { error: `sc2 has no ${kind} assets`, kind });
      const servable = dataOf(id).assets.get(reference.toLowerCase().replaceAll('/', '\\'));
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
    extensions: {
      textures: texturesRoute(texturesRoot(core.repoRoot, env)),
      'hd-textures': hdRoute(hdModelsRoot(core.repoRoot, env), 'list'),
      'hd-asset': hdRoute(hdModelsRoot(core.repoRoot, env), 'file'),
    },
    banner: () => {
      const lines = [...loaded.datasets.values()].map((d) => `${d.id}: ${d.units.size} units (${d.units.withoutFile} without a model file), ${d.doodads.size} doodads (${d.doodads.withoutFile} without)`);
      return `${storage.modelCount} models; ${lines.join('; ')}`;
    },
  };
}

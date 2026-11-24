// The StarCraft: Ghost game on the server (SPEC-VIEWER-GHOST): the build
// named by GHOST_PATH, one dataset `build`, the categories `actors` and
// `models`, and the exports of NODExport (exporter.ts). The record and row
// bodies are those of src/games/ghost/shared/records.ts.

import type { CategoryInfo } from '../../../shared/protocol';
import type { DatasetInfo } from '../../../shared/records';
import { HttpError, type GameBackend } from '../../../server/core/backend';
import type { CoreSettings } from '../../../server/core/settings';
import { findIn, ghostSettings, indexBuild, type BuildIndex } from './build';
import { buildCatalog, searchActors, searchModels, type Catalog } from './catalog';
import { createExporter } from './exporter';

export const GHOST_DATASET = 'build';

const CATEGORIES: CategoryInfo[] = [
  {
    id: 'actors',
    label: 'actors',
    noun: 'actor',
    addAll: true,
    rows: 'records',
    icons: false,
    filters: [{ id: 'motion', label: 'motion set', kind: 'buttons', values: [{ value: 'with', label: 'with motions' }, { value: 'without', label: 'without' }] }],
  },
  {
    id: 'models',
    label: 'models',
    noun: 'model',
    addAll: false,
    rows: 'records',
    icons: false,
    filters: [{ id: 'skin', label: 'bones', kind: 'buttons', values: [{ value: 'skinned', label: 'skinned' }, { value: 'rigid', label: 'rigid' }] }],
  },
];

interface Loaded {
  index: BuildIndex;
  catalog: Catalog;
}

/** Index the build and read its catalog; GameUnavailable when the build is not there (R-VIEW-8). */
export async function startGhost(core: CoreSettings, env: NodeJS.ProcessEnv = process.env): Promise<GameBackend & { banner(): string }> {
  const settings = await ghostSettings(core.viewerDir, env);
  const exporter = createExporter(settings.exporter, settings.root, settings.cache);

  async function load(): Promise<Loaded> {
    const index = await indexBuild(settings.root);
    await exporter.keepOnly(index.signature);
    return { index, catalog: buildCatalog(await exporter.catalog(index.signature), index) };
  }
  let state = await load();

  const info = (current: string): DatasetInfo => ({ id: GHOST_DATASET, label: 'Game build', builtin: true, signature: state.index.signature, current, changed: current !== state.index.signature });
  const dataset = (id: string): Loaded => {
    if (id !== GHOST_DATASET) throw new HttpError(404, { error: 'no such dataset', dataset: id });
    return state;
  };
  const noCategory = (category: string): HttpError => new HttpError(404, { error: 'no such category', category });
  /** A relative path of the index, or null; never a path outside the build. */
  const known = (path: string): string | null => state.index.byLower.get(path.replaceAll('\\', '/').toLowerCase()) ?? null;

  return {
    id: 'ghost',
    label: 'StarCraft: Ghost',
    tab: 'Ghost',
    defaultDataset: GHOST_DATASET,
    hasDataset: (id) => id === GHOST_DATASET,
    async datasets() {
      return { default: GHOST_DATASET, datasets: [info((await indexBuild(settings.root)).signature)], problems: [] };
    },
    async reload(id) {
      dataset(id);
      state = await load();
      return info(state.index.signature);
    },
    categories(id) {
      dataset(id);
      return CATEGORIES;
    },
    summary(id) {
      const { index, catalog } = dataset(id);
      return { files: index.files, actors: catalog.actors.size, models: catalog.models.size, leftOut: catalog.leftOut, refused: catalog.refused, caseTwins: index.caseTwins };
    },
    list(id, category, { q, offset, limit, filters }) {
      const { catalog } = dataset(id);
      if (category === 'actors') return searchActors(catalog, q, filters['motion'] ?? '', offset, limit);
      if (category === 'models') return searchModels(catalog, q, filters['skin'] ?? '', offset, limit);
      throw noCategory(category);
    },
    record(id, category, recordId) {
      const { catalog } = dataset(id);
      if (category !== 'actors' && category !== 'models') throw noCategory(category);
      const record = category === 'actors' ? catalog.actors.get(recordId) : catalog.models.get(recordId);
      if (!record) throw new HttpError(404, { error: 'not found', id: recordId, dataset: id });
      return { ...record, dataset: id };
    },
    /** A model file: served as its export container (exporter.ts). Only `.nod` files of 3D/Models. */
    async file(id, path) {
      dataset(id);
      const rel = known(path);
      if (rel === null || !/^3D\/Models\/[^/]+\.nod$/i.test(rel)) return null;
      return exporter.model(state.index.signature, rel);
    },
    async asset(id, kind, reference) {
      const { index } = dataset(id);
      if (kind === 'texture') {
        // A texture file the materials export named, relative to the build.
        const rel = known(reference);
        return rel !== null && /\.dds$/i.test(rel) ? `${settings.root}/${rel}` : null;
      }
      if (kind === 'animation') {
        const rel = findIn(index, '3D/Anims', reference, '.nad');
        return rel === null ? null : exporter.clip(index.signature, rel);
      }
      if (kind === 'material') {
        // A material name is one line of the names file NODExport reads.
        if (/[\u0000-\u001f]/.test(reference)) throw new HttpError(400, { error: 'a material name is one line of text', ref: reference });
        return exporter.material(index.signature, reference);
      }
      throw new HttpError(404, { error: `ghost has no ${kind} assets`, kind });
    },
    icon: () => null,
    backdrops: () => ({ total: 0, items: [] }),
    extensions: {},
    banner: () => `ghost: ${state.catalog.actors.size} actors, ${state.catalog.models.size} models (${state.catalog.leftOut.length} left out, ${state.catalog.refused.length} refused)`,
  };
}

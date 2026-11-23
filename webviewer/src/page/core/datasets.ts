// Datasets: where game data and assets come from (src/games/sc2/server/datasets.ts).
// - The top left of the gallery panel holds the current dataset: the gallery lists it and new
//   instances come from it. The choice is a setting per game (core/settings.ts).
// - Every instance has its own dataset (page/core/scene.ts), so the same unit can
//   stand side by side from two of them.
// - Every request names its dataset, and model and texture URLs carry the
//   dataset's signature, so a reloaded dataset is fetched anew.
// The check for changed datasets is page/features/dataset-reload.

import { routes, type CategoryInfo, type GamesBody } from '../../shared/protocol';
import type { DatasetInfo, DatasetsBody, DoodadRecord, Facets, PlacedRecord, UnitRecord } from '../../shared/records';
import { app, type DatasetsApi } from './app';
import { byIdAs, make } from './dom';
import { datasetSetting, readSetting, writeSetting } from './settings';

export function installDatasets(): DatasetsApi {
  const select = byIdAs('dataset', HTMLSelectElement);
  let gameId: string | null = null;

  /** Id -> the dataset as the server lists it. */
  const known = new Map<string, DatasetInfo>();
  let defaultId: string | null = null; // the server's default dataset
  let current: string | null = null;
  const listeners: ((id: string) => void)[] = [];

  /** The dataset id, checked: an unknown one is an error. */
  function requireDataset(id: string | null): string {
    if (id === null || !known.has(id)) throw new Error(`no dataset "${String(id)}" (have: ${[...known.keys()].join(', ')})`);
    return id;
  }

  const version = (id: string | null): string => known.get(requireDataset(id))?.signature ?? '';
  /** The game the page shows: the server's default one (/api/games). Step 6 adds the game tabs. */
  function game(): string {
    if (gameId === null) throw new Error('the games are not read yet');
    return gameId;
  }
  /** The URL of one page of a category of `dataset` (default: the current one). */
  const records = (category: string, params: Record<string, string> = {}, dataset: string | null = current): string => routes.records(game(), category, requireDataset(dataset), params);

  /** The categories of a dataset (default: the current one). */
  const categories = (dataset: string | null = current): Promise<CategoryInfo[]> => app().getJson<CategoryInfo[]>(routes.categories(game(), requireDataset(dataset)));

  /** What the gallery filters offer, out of the categories of a dataset. */
  async function facets(dataset: string | null = current): Promise<Facets> {
    const list = await categories(dataset);
    const values = (category: string, filter: string): string[] =>
      list
        .find((c) => c.id === category)
        ?.filters.find((f) => f.id === filter)
        ?.values.map((v) => v.value) ?? [];
    return { races: values('units', 'race'), kinds: values('units', 'kind'), families: values('units', 'family'), doodadTypes: values('doodads', 'type'), tilesets: values('doodads', 'tileset') };
  }

  /** A unit or doodad record ('unit', 'doodad') from a dataset. */
  async function fetchRecord(kind: 'unit' | 'doodad', id: string, dataset: string | null = current): Promise<PlacedRecord> {
    const url = routes.record(game(), kind === 'unit' ? 'units' : 'doodads', requireDataset(dataset), id);
    const response = await fetch(url);
    if (response.status === 404) throw new Error(`${id} is not in dataset "${String(dataset)}"`);
    if (!response.ok) throw new Error(`${response.status} ${url}`);
    const body: unknown = await response.json();
    // The server answers the record of the kind asked (src/shared/records.ts).
    return body as PlacedRecord;
  }

  function record(kind: 'unit', id: string, dataset?: string | null): Promise<UnitRecord>;
  function record(kind: 'doodad', id: string, dataset?: string | null): Promise<DoodadRecord>;
  function record(kind: 'unit' | 'doodad', id: string, dataset?: string | null): Promise<PlacedRecord>;
  function record(kind: 'unit' | 'doodad', id: string, dataset?: string | null): Promise<PlacedRecord> {
    return fetchRecord(kind, id, dataset === undefined ? current : dataset);
  }

  function setDataset(id: string): void {
    requireDataset(id);
    if (id === current) return;
    current = id;
    select.value = id;
    writeSetting(datasetSetting(game()), id);
    for (const listener of listeners) listener(id);
  }
  select.addEventListener('change', () => setDataset(select.value));

  function take(body: DatasetsBody): void {
    known.clear();
    for (const dataset of body.datasets) known.set(dataset.id, dataset);
    defaultId = body.default;
  }

  /** Read the datasets and choose the current one: the stored choice when it still exists. */
  async function setupDatasets(): Promise<void> {
    gameId = (await app().getJson<GamesBody>(routes.games())).default;
    const body = await app().getJson<DatasetsBody>(routes.datasets(game()));
    take(body);
    for (const problem of body.problems) console.warn(`sc2viewer: not a dataset: ${problem.dir}: ${problem.reason}`);
    select.replaceChildren(...body.datasets.map((d) => make('option', { value: d.id, textContent: d.label })));
    const stored = readSetting(datasetSetting(game())).value;
    current = stored !== null && known.has(stored) ? stored : defaultId;
    select.value = current ?? '';
    // From now on the page asks now and then whether a dataset changed on disk.
    app().startDatasetPolling();
  }

  /** Take the changed state of a fresh list into the known datasets. */
  function updateDatasets(list: readonly DatasetInfo[]): void {
    for (const dataset of list) {
      const mine = known.get(dataset.id);
      if (mine) Object.assign(mine, { changed: dataset.changed, current: dataset.current });
    }
  }

  return {
    setupDatasets,
    setDataset,
    requireDataset,
    record,
    records,
    categories,
    facets,
    game,
    extensionUrl: (name) => routes.extension(game(), name),
    dataset: () => current,
    defaultDataset: () => defaultId,
    datasets: () => [...known.values()].map((d) => ({ ...d })),
    onDatasetChange: (listener) => listeners.push(listener),
    updateDatasets,
    hasDataset: (id) => known.has(id),
    datasetLabel: (id) => known.get(id)?.label ?? id,
    // A model path is fetched as-is. Anything a model asks for (textures) is
    // an in-model path, resolved by the server for the dataset.
    modelUrl: (path, dataset = current) => routes.file(game(), requireDataset(dataset), path, version(dataset)),
    pathSolver: (dataset = current) => {
      const id = requireDataset(dataset);
      const v = version(dataset);
      const g = game();
      // What a model names (its textures) is an in-model path; a URL of ours is taken as it is.
      return (src) => (typeof src === 'string' && !src.startsWith('/') ? routes.asset(g, id, 'texture', src, v) : src);
    },
    iconUrl: (name, dataset = current) => routes.icon(game(), requireDataset(dataset), name),
  };
}

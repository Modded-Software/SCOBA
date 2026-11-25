// The games and their datasets: where game data and assets come from
// (SC2: src/games/sc2/server/datasets.ts).
// - /api/games lists the games. The gallery shows one of them, chosen by
//   the game tabs (ui/gametabs.ts); a choice is a setting (R-VIEW-22).
// - Each game has its datasets and its current one. The top left of the
//   gallery holds the gallery game's: the gallery lists it and new
//   instances come from it. The choice is a setting per game (core/settings.ts).
// - Every instance has its own game and dataset (page/core/scene.ts), so
//   the same unit can stand side by side from two of them.
// - Every request names its dataset, and model and texture URLs carry the
//   dataset's signature, so a reloaded dataset is fetched anew.
// The check for changed datasets is page/features/dataset-reload.

import { routes, type CategoryInfo, type GameInfo, type GamesBody } from '../../shared/protocol';
import type { DatasetInfo, DatasetsBody } from '../../shared/records';
import type { ApiClient, GameParts, GameRegistry, Store } from './context';
import type { EventBus, ViewerEvents } from './bus';
import type { GameCategory, GameRecord, PageGame } from './plugin';
import { byIdAs, make } from './dom';
import { SettingsRefused } from './refusals';
import { datasetSetting, keyOf, settings } from './settings';

/** One game's datasets as the server lists them, and its current one. */
interface GameDatasets {
  readonly known: Map<string, DatasetInfo>;
  defaultId: string | null;
  current: string | null;
}

/** A server answer as JSON. The server is this viewer's own (src/shared/records.ts and the games' shared records have its shapes). */
async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${response.status} ${url}`);
  const body: unknown = await response.json();
  return body as T;
}

export interface Datasets {
  readonly games: GameRegistry;
  readonly api: ApiClient;
  /** Read /api/games, choose the gallery's game (the stored one when it can open), read its datasets. */
  setupDatasets(): Promise<void>;
}

export function createDatasets(registered: readonly PageGame[], store: Store, events: EventBus<ViewerEvents>): Datasets {
  const first = registered[0];
  if (!first) throw new Error('page: no game is registered');
  const select = byIdAs('dataset', HTMLSelectElement);
  let info: GameInfo[] = [];
  let gameId: string | null = null;
  let plugin: PageGame = first;
  const loaded = new Map<string, GameDatasets>();
  const loading = new Map<string, Promise<void>>();
  const parts = new Map<string, GameParts>();

  function pluginOf(id: string): PageGame {
    const found = registered.find((g) => g.id === id);
    if (!found) throw new Error(`page: no game "${id}" is registered`);
    return found;
  }

  function partsOf(id: string): GameParts {
    const found = parts.get(id);
    if (!found) throw new Error(`page: game "${id}" has no parts`);
    return found;
  }

  /** The gallery's game. */
  function game(): string {
    if (gameId === null) throw new Error('the games are not read yet');
    return gameId;
  }

  function stateOf(id: string = game()): GameDatasets {
    const state = loaded.get(id);
    if (!state) throw new Error(`the datasets of game "${id}" are not read`);
    return state;
  }

  /** The dataset id of a game, checked: an unknown one is an error. */
  function requireDataset(id: string | null, of: string = game()): string {
    const { known } = stateOf(of);
    if (id === null || !known.has(id)) throw new Error(`no dataset "${String(id)}" (have: ${[...known.keys()].join(', ')})`);
    return id;
  }

  /** A dataset argument: null or absent means the game's current one (the API's declared default). */
  const datasetOf = (dataset: string | null | undefined, of: string): string => requireDataset(dataset === null || dataset === undefined ? stateOf(of).current : dataset, of);
  /** A known dataset of a game, checked. */
  function infoOf(dataset: string, of: string): DatasetInfo {
    const found = stateOf(of).known.get(requireDataset(dataset, of));
    if (!found) throw new Error(`no dataset "${dataset}" in ${of}`);
    return found;
  }
  const version = (dataset: string, of: string): string | null => infoOf(dataset, of).signature;

  /**
   * Read a game's datasets. Its current one: the stored choice; nothing stored, the server's default.
   * A stored choice the server does not list is refused (core/refusals.ts), not replaced.
   */
  async function readGame(id: string): Promise<void> {
    const body = await getJson<DatasetsBody>(routes.datasets(id));
    const known = new Map(body.datasets.map((d) => [d.id, d]));
    for (const problem of body.problems) console.warn(`viewer: ${id}: not a dataset: ${problem.dir}: ${problem.reason}`);
    const setting = datasetSetting(id);
    const stored = store.find(setting);
    if (stored !== null && !known.has(stored)) throw new SettingsRefused([{ key: keyOf(setting), stored: JSON.stringify(stored), reason: `${id} has no dataset "${stored}" (have: ${[...known.keys()].join(', ')})` }]);
    loaded.set(id, { known, defaultId: body.default, current: stored === null ? body.default : stored });
  }

  function loadGame(id: string): Promise<void> {
    if (loaded.has(id)) return Promise.resolve();
    const running = loading.get(id) ?? readGame(id);
    loading.set(id, running);
    return running.finally(() => loading.delete(id));
  }

  function gameRefusal(id: string): string | null {
    const found = info.find((g) => g.id === id);
    if (!found) return `the server has no game "${id}"`;
    if (!found.available) return found.reason ?? `${found.label} is not available`;
    if (!registered.some((g) => g.id === id)) return `the page has no module for ${found.label}`;
    return null;
  }

  /** Fill the dataset select with the gallery game's datasets. */
  function showDatasets(): void {
    const state = stateOf();
    select.replaceChildren(...[...state.known.values()].map((d) => make('option', { value: d.id, textContent: d.label })));
    select.value = state.current ?? '';
  }

  function notify(): void {
    const current = stateOf().current;
    if (current !== null) events.emit('dataset-changed', { game: game(), dataset: current });
  }

  /** Show a game in the gallery: its plugin, its datasets. */
  function show(id: string): void {
    gameId = id;
    plugin = pluginOf(id);
    showDatasets();
    events.emit('game-changed', { game: id });
  }

  async function setGame(id: string): Promise<void> {
    const why = gameRefusal(id);
    if (why !== null) throw new Error(why);
    await loadGame(id);
    store.write(settings.game, id);
    if (id === gameId) return;
    show(id);
    notify();
  }

  /**
   * The gallery's game: the stored choice; nothing stored, the server's default.
   * A stored game that cannot open is refused (core/refusals.ts). The server's default that cannot open is an error.
   * Every game that can open has its datasets read, so a stored dataset choice is checked now.
   */
  async function setupDatasets(): Promise<void> {
    const body = await getJson<GamesBody>(routes.games());
    info = body.games;
    const stored = store.find(settings.game);
    if (stored !== null) {
      const why = gameRefusal(stored);
      if (why !== null) throw new SettingsRefused([{ key: keyOf(settings.game), stored: JSON.stringify(stored), reason: why }]);
    }
    const chosen = stored === null ? body.default : stored;
    const why = gameRefusal(chosen);
    if (why !== null) throw new Error(`the server's default game "${chosen}" cannot open: ${why}`);
    const open = info.filter((g) => gameRefusal(g.id) === null).map((g) => g.id);
    const read = await Promise.allSettled(open.map(loadGame));
    const refused = read.flatMap((one) => (one.status === 'rejected' && one.reason instanceof SettingsRefused ? one.reason.refused : []));
    if (refused.length) throw new SettingsRefused(refused);
    const failed = read.find((one): one is PromiseRejectedResult => one.status === 'rejected');
    if (failed) throw failed.reason;
    show(chosen);
  }

  function setDataset(id: string): void {
    requireDataset(id);
    const state = stateOf();
    if (id === state.current) return;
    state.current = id;
    select.value = id;
    store.write(datasetSetting(game()), id);
    notify();
  }
  select.addEventListener('change', () => setDataset(select.value));

  /** A record of a category from a dataset; its game checks what the server sent. */
  async function record(category: string, id: string, dataset: string | null = null, of: string = game()): Promise<GameRecord> {
    const from = datasetOf(dataset, of);
    const url = routes.record(of, category, from, id);
    const response = await fetch(url);
    if (response.status === 404) throw new Error(`${id} is not in dataset "${from}"`);
    if (!response.ok) throw new Error(`${response.status} ${url}`);
    const body: unknown = await response.json();
    return pluginOf(of).checkRecord(category, body);
  }

  /** Take the changed state of a fresh list into the gallery game's known datasets. */
  function updateDatasets(list: readonly DatasetInfo[]): void {
    const { known } = stateOf();
    for (const dataset of list) {
      const mine = known.get(dataset.id);
      if (mine) Object.assign(mine, { changed: dataset.changed, current: dataset.current });
    }
  }

  function categoryOf(noun: string): GameCategory {
    const category = plugin.categories.find((c) => c.noun === noun);
    if (!category) throw new Error(`${plugin.id} has no ${noun} records`);
    return category;
  }

  const games: GameRegistry = {
    games: registered,
    plugin: () => plugin,
    game,
    pluginOf,
    partsOf,
    addParts(id, given) {
      pluginOf(id);
      if (parts.has(id)) throw new Error(`page: game "${id}" has its parts already`);
      parts.set(id, given);
    },
    gamesInfo: () => info.map((g) => ({ ...g })),
    gameRefusal,
    setGame,
    loadGame,
    categoryOf,
    nounOf(item) {
      const { source } = item;
      if (!source) return null;
      const category = pluginOf(item.game).categories.find((c) => c.id === source.category);
      if (!category) throw new Error(`${item.game} has no category "${source.category}"`);
      return category.noun;
    },
  };

  const api: ApiClient = {
    getJson,
    record,
    records: (category, params = {}, dataset = null, of = game()) => routes.records(of, category, datasetOf(dataset, of), params),
    categories: (dataset = null, of = game()) => getJson<CategoryInfo[]>(routes.categories(of, datasetOf(dataset, of))),
    extensionUrl: (name, of = game()) => routes.extension(of, name),
    // A model path is fetched as-is. Anything a model asks for (textures) is
    // an in-model path, resolved by the server for the dataset.
    modelUrl: (path, dataset = null, of = game()) => {
      const id = datasetOf(dataset, of);
      return routes.file(of, id, path, version(id, of));
    },
    pathSolver: (dataset = null, of = game()) => {
      const id = datasetOf(dataset, of);
      const v = version(id, of);
      // What a model names (its textures) is an in-model path; a URL of ours is taken as it is.
      return (src) => (typeof src === 'string' && !src.startsWith('/') ? routes.asset(of, id, 'texture', src, v) : src);
    },
    assetUrl: (kind, reference, dataset = null, of = game()) => {
      const id = datasetOf(dataset, of);
      return routes.asset(of, id, kind, reference, version(id, of));
    },
    iconUrl: (name, dataset = null, of = game()) => routes.icon(of, datasetOf(dataset, of), name),
    dataset: () => (gameId === null ? null : stateOf().current),
    currentDataset: (of = game()) => stateOf(of).current,
    defaultDataset: (of = game()) => stateOf(of).defaultId,
    datasets: (of = game()) => [...stateOf(of).known.values()].map((d) => ({ ...d })),
    setDataset,
    requireDataset,
    hasDataset: (id, of = game()) => stateOf(of).known.has(id),
    datasetLabel: (id, of = game()) => infoOf(id, of).label,
    updateDatasets,
  };

  return { games, api, setupDatasets };
}

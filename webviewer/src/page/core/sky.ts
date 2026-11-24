// The sky and the ground grid toggle: part of the scene service. The
// buttons and the skybox picker are features/sky. Both are a setting
// (core/settings.ts), so a reload shows the view as it was (the camera:
// core/camera.ts).

import type { ApiClient, GameRegistry, SceneService, StatusService, Store } from './context';
import type { EventBus, ViewerEvents } from './bus';
import type { Host } from './host';
import { settings } from './settings';
import type { Sky, SkyChoice } from './types';

export type SkyPart = Pick<SceneService, 'sky' | 'setSky' | 'setGrid' | 'grid'>;

export interface SkyDeps {
  readonly host: Host;
  readonly games: GameRegistry;
  readonly api: ApiClient;
  readonly status: StatusService;
  readonly store: Store;
  readonly events: EventBus<ViewerEvents>;
}

export function createSky({ host, games, api, status, store, events }: SkyDeps): SkyPart {
  const { ground, skyScene } = host;
  let sky: Sky | null = null;

  function saveView(): void {
    const shown = sky;
    const kept = shown ? { id: shown.id, name: shown.name, file: shown.file, ...(shown.game === undefined || shown.dataset === undefined ? {} : { game: shown.game, dataset: shown.dataset }) } : null;
    store.write(settings.view, { grid: ground.enabled, sky: kept });
    events.emit('view-changed', { sky, grid: ground.enabled });
  }

  function setGrid(on: boolean): void {
    ground.enabled = Boolean(on);
    saveView();
  }

  /** Show a skybox, or none (null). */
  async function setSky(choice: SkyChoice | null): Promise<void> {
    if (sky && sky.instance) sky.instance.detach();
    // The choice holds at once; its model follows when loaded.
    const mine: Sky | null = choice ? { ...choice, model: null, instance: null } : null;
    sky = mine;
    saveView();
    if (!mine) return;
    try {
      await status.busy(async () => {
        // A backdrop names its game and dataset; one that does not is the gallery game's default dataset's (SC2: games/sc2/server/skyboxes.ts).
        const game = mine.game ?? games.game();
        await games.loadGame(game);
        const from = mine.dataset ?? api.defaultDataset(game);
        const model = await host.loadModel(api.modelUrl(mine.file, from, game), api.pathSolver(from, game));
        if (!model) throw new Error('cannot load ' + mine.file);
        if (sky !== mine) return; // another sky was chosen meanwhile
        const instance = model.addInstance();
        if (instance.sequences.length) {
          instance.setSequence(0);
          instance.setLoop(true);
        }
        instance.attach(skyScene);
        Object.assign(mine, { model, instance });
        host.reportUndrawn(mine.name, model);
      });
    } catch (error) {
      if (sky === mine) {
        sky = null;
        saveView();
      }
      throw error;
    }
  }

  /**
   * At startup, once the datasets are known: the stored grid toggle and sky.
   * A stored value that is not a view is refused and reported.
   */
  async function restoreView(): Promise<void> {
    const { value: stored, restore } = store.read(settings.view);
    if (restore.startsWith('refused')) saveView();
    if (!stored) return;
    setGrid(stored.grid);
    if (stored.sky) await setSky(stored.sky);
  }
  events.on('startup', ({ wait }) => wait(restoreView()));

  return { sky: () => sky, setSky, setGrid, grid: () => ground.enabled };
}

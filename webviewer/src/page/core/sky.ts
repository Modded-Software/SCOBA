// The sky, the ground grid toggle and the ground texture: part of the
// scene service. The buttons and the pickers are features/sky. All three
// are a setting (core/settings.ts), so a reload shows the view as it was
// (the camera: core/camera.ts). The ground texture is the chosen variant of
// the record's colour file, else its terrain bake (SPEC-VIEWER 17.7); it is
// read again when textures change for that dataset (R-VIEW-109).

import type { ApiClient, GameRegistry, SceneService, StatusService, Store } from './context';
import { ORIGINAL } from '../../shared/textures';
import type { EventBus, ViewerEvents } from './bus';
import type { Host } from './host';
import { Texture } from './library';
import { settings } from './settings';
import type { Skins } from './skins';
import type { GroundChoice, Sky, SkyChoice } from './types';

export type SkyPart = Pick<SceneService, 'sky' | 'setSky' | 'setGrid' | 'grid' | 'ground' | 'setGround'>;

export interface SkyDeps {
  readonly host: Host;
  readonly games: GameRegistry;
  readonly api: ApiClient;
  readonly status: StatusService;
  readonly store: Store;
  readonly events: EventBus<ViewerEvents>;
  readonly skins: Pick<Skins, 'states' | 'variantUrl'>;
}

export function createSky({ host, games, api, status, store, events, skins }: SkyDeps): SkyPart {
  const { ground, skyScene } = host;
  let sky: Sky | null = null;
  let groundChoice: GroundChoice | null = null;

  function saveView(): void {
    const shown = sky;
    const kept = shown ? { id: shown.id, name: shown.name, file: shown.file, game: shown.game, dataset: shown.dataset } : null;
    store.write(settings.view, { grid: ground.enabled, sky: kept, ground: groundChoice });
    events.emit('view-changed', { sky, grid: ground.enabled, ground: groundChoice });
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
        // A backdrop names its game and dataset (the backdrops route says which).
        await games.loadGame(mine.game);
        if (!api.hasDataset(mine.dataset, mine.game)) throw new Error(`the sky ${mine.name}: no dataset "${mine.dataset}" in ${mine.game}`);
        const model = await host.loadModel(api.modelUrl(mine.file, mine.dataset, mine.game), api.pathSolver(mine.dataset, mine.game));
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
   * Read the chosen ground's texture (17.7): the variant chosen; none chosen, its terrain bake; no bake, its original.
   * A chosen or baked variant that cannot be shown is refused.
   */
  async function readGround(mine: GroundChoice): Promise<void> {
    await status.busy(async () => {
      await games.loadGame(mine.game);
      if (!api.hasDataset(mine.dataset, mine.game)) throw new Error(`the ground ${mine.name}: no dataset "${mine.dataset}"`);
      const [state] = (await skins.states(mine.game, mine.dataset, [mine.texture])).textures;
      const wanted = mine.variant ?? state?.bake ?? null;
      const url = wanted === null || wanted === ORIGINAL ? String(api.pathSolver(mine.dataset, mine.game)(mine.texture)) : skins.variantUrl(mine.game, mine.dataset, state, wanted);
      if (url === null) throw new Error(`the ground ${mine.name}: ${wanted} cannot be shown: it is not made, stale or has a problem not accepted`);
      const texture = await host.viewer.load(mine.texture, () => url);
      if (!(texture instanceof Texture)) throw new Error(`cannot load the ground texture ${mine.name}`);
      if (groundChoice === mine) ground.texture = texture;
    });
  }

  /** Make a ground record the ground, or none (null) (R-VIEW-108). */
  async function setGround(choice: GroundChoice | null): Promise<void> {
    groundChoice = choice ? { ...choice } : null;
    ground.texture = null;
    saveView();
    const mine = groundChoice;
    if (!mine) return;
    try {
      await readGround(mine);
    } catch (error) {
      if (groundChoice === mine) {
        groundChoice = null;
        saveView();
      }
      throw error;
    }
  }

  events.on('textures-changed', ({ game, dataset }) => {
    const mine = groundChoice;
    if (mine && mine.game === game && mine.dataset === dataset) readGround(mine).catch(status.reportFailure);
  });

  /**
   * At startup, once the datasets are known: the stored grid toggle, sky
   * and ground, else the setting's declared default (grid on, no sky, no ground).
   */
  async function restoreView(): Promise<void> {
    const stored = store.read(settings.view);
    setGrid(stored.grid);
    await Promise.all([stored.sky ? setSky(stored.sky) : null, stored.ground ? setGround(stored.ground) : null]);
  }
  events.on('startup', ({ wait }) => wait(restoreView()));

  return { sky: () => sky, setSky, setGrid, grid: () => ground.enabled, ground: () => groundChoice, setGround };
}

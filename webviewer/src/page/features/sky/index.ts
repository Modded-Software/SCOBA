// The ground grid toggle and the skybox picker.

import { routes } from '../../../shared/protocol';
import type { Page, SkyboxInfo } from '../../../shared/records';
import { app, type CoreApi, type Sky, type SkyApi, type SkyChoice } from '../../core/app';
import { byId, messageOf } from '../../core/dom';
import { loadM3 } from '../../core/library';
import { readSetting, settings, writeSetting } from '../../core/settings';
import { Picker } from '../../ui/components/picker';

// The grid toggle and the sky are a setting (core/settings.ts), so a reload
// shows the view as it was (the camera: core/camera.ts).

export function installSky(core: CoreApi): SkyApi {
  const { ground, skyScene, viewer } = core;
  const gridButton = byId('grid-toggle');
  const skyButton = byId('sky-button');

  function saveView(): void {
    const shown = app().sky;
    const sky = shown ? { id: shown.id, name: shown.name, file: shown.file } : null;
    writeSetting(settings.view, { grid: ground.enabled, sky });
  }

  function setGrid(on: boolean): void {
    ground.enabled = Boolean(on);
    gridButton.classList.toggle('on', ground.enabled);
    saveView();
  }
  gridButton.addEventListener('click', () => setGrid(!ground.enabled));

  /** Show a skybox, or none (null). */
  async function setSky(choice: SkyChoice | null): Promise<void> {
    const a = app();
    if (a.sky && a.sky.instance) a.sky.instance.detach();
    // The choice holds at once; its model follows when loaded.
    const mine: Sky | null = choice ? { id: choice.id, name: choice.name, file: choice.file, model: null, instance: null } : null;
    a.sky = mine;
    skyButton.classList.toggle('on', Boolean(choice));
    skyButton.title = choice ? 'skybox: ' + choice.name : 'choose a skybox';
    saveView();
    if (!mine) return;
    a.pending++;
    try {
      // Skyboxes are the default dataset's, whatever the current one is (games/sc2/server/skyboxes.ts).
      const from = a.defaultDataset();
      const model = await loadM3(viewer, a.modelUrl(mine.file, from), a.pathSolver(from));
      if (!model) throw new Error('cannot load ' + mine.file);
      if (a.sky !== mine) return; // another sky was chosen meanwhile
      const instance = model.addInstance();
      if (model.sequences.length) {
        instance.setSequence(0);
        instance.setSequenceLoopMode(2);
      }
      skyScene.addInstance(instance);
      Object.assign(mine, { model, instance });
      a.reportUndrawn(mine.name, model);
    } catch (error) {
      if (a.sky === mine) {
        a.sky = null;
        skyButton.classList.remove('on');
        saveView();
      }
      a.setStatus(messageOf(error), { failure: true });
      throw error;
    } finally {
      a.pending--;
    }
  }

  const skyPicker = new Picker<SkyboxInfo>({
    id: 'sky-dialog',
    title: 'skybox',
    hint: 'search skyboxes',
    none: '(none)',
    fetchPage: (q, offset, limit) => app().getJson<Page<SkyboxInfo>>(routes.backdrops(app().game(), { q, offset: String(offset), limit: String(limit) })),
    describe: (s) => ({ id: s.id, name: s.name, sub: s.file }),
    onPick: (choice) => {
      setSky(choice).catch(app().reportFailure);
    },
  });
  skyButton.addEventListener('click', () => skyPicker.open().catch((error: unknown) => app().reportFailure(error)));

  /**
   * At startup, once the datasets are known: the stored grid toggle and sky.
   * A stored value that is not a view is refused and reported.
   */
  async function restoreView(): Promise<void> {
    const { value: stored, restore } = readSetting(settings.view);
    if (restore.startsWith('refused')) saveView();
    if (!stored) return;
    setGrid(stored.grid);
    if (stored.sky) await setSky(stored.sky);
  }

  /** The skybox shown, or null. */
  return { sky: null, setGrid, setSky, restoreView };
}

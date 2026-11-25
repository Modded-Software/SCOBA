// The ground grid button, the ground texture picker and the skybox picker.
// The sky, the ground and the setting that keeps them are core/sky.ts (the
// scene service). The ground button is there only for a gallery game with
// a texture service and a ground category (SPEC-VIEWER 17.7, R-VIEW-100).
// A ground row shows a picture of its colour file; the chosen ground has
// its controls (groundrow.ts).

import { routes, type RecordSummary } from '../../../shared/protocol';
import type { Backdrop, Page } from '../../../shared/records';
import type { Feature } from '../../core/context';
import { byId } from '../../core/dom';
import type { GameCategory } from '../../core/plugin';
import { createPreviews } from '../../core/previews';
import { Picker } from '../../ui/components/picker';
import { createGroundRow } from './groundrow';

/** The colour file of a ground record (SC2: TerrainRecord.file); null: it names none. */
function fileOf(record: RecordSummary): string | null {
  const file: unknown = Reflect.get(record, 'file');
  return typeof file === 'string' && file ? file : null;
}

export const skyFeature: Feature = {
  id: 'sky',
  install(context) {
    const { scene, api, games, status, events, skins, testApi } = context;
    const previews = createPreviews();
    const groundRow = createGroundRow(context);
    const gridButton = byId('grid-toggle');
    const groundButton = byId('ground-button');
    const skyButton = byId('sky-button');

    events.on('view-changed', ({ sky, grid, ground }) => {
      gridButton.classList.toggle('on', grid);
      groundButton.classList.toggle('on', ground !== null);
      groundButton.title = ground ? 'ground texture: ' + ground.name : 'choose a ground texture';
      skyButton.classList.toggle('on', sky !== null);
      skyButton.title = sky ? 'skybox: ' + sky.name : 'choose a skybox';
    });
    gridButton.addEventListener('click', () => scene.setGrid(!scene.grid()));

    /** The gallery game's ground category, when it offers a texture service. */
    const groundCategory = (): GameCategory | undefined => (skins.offered(games.game()) ? games.plugin().categories.find((category) => category.ground) : undefined);
    events.on('game-changed', () => {
      groundButton.hidden = groundCategory() === undefined;
    });

    const groundPicker = new Picker<RecordSummary>({
      id: 'ground-dialog',
      title: 'Ground texture',
      hint: 'search ground textures',
      none: '(none)',
      fetchPage: (q, offset, limit) => {
        const category = groundCategory();
        if (!category) return Promise.resolve({ total: 0, items: [] });
        return api.getJson<Page<RecordSummary>>(api.records(category.id, { q, offset: String(offset), limit: String(limit) }));
      },
      describe: (r) => ({ id: r.id, name: r.name, sub: r.sub }),
      preview: (r) => {
        const file = fileOf(r);
        return file ? previews.node(api.assetUrl('texture', file), file) : null;
      },
      extra: [groundRow.node],
      onPick: (choice) => {
        const category = groundCategory();
        // A ground record, added, becomes the ground (core/scene.ts addRecord).
        const done = choice && category ? scene.addRecord(category.id, choice.id) : scene.setGround(null);
        done.catch(status.reportFailure);
      },
    });
    groundButton.addEventListener('click', () => {
      previews.clear();
      Promise.all([groundPicker.open(), groundRow.update()]).catch(status.reportFailure);
    });
    testApi.viewer({ groundRow: groundRow.state });

    const skyPicker = new Picker<Backdrop>({
      id: 'sky-dialog',
      title: 'Skybox',
      hint: 'search skyboxes',
      none: '(none)',
      fetchPage: (q, offset, limit) => api.getJson<Page<Backdrop>>(routes.backdrops(games.game(), { q, offset: String(offset), limit: String(limit) })),
      describe: (s) => ({ id: s.id, name: s.name, sub: s.file }),
      onPick: (choice) => {
        scene.setSky(choice).catch(status.reportFailure);
      },
    });
    skyButton.addEventListener('click', () => skyPicker.open().catch(status.reportFailure));
  },
};

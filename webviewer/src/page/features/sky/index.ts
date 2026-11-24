// The ground grid button and the skybox picker. The sky itself, and the
// setting that keeps it, are core/sky.ts (the scene service).

import { routes } from '../../../shared/protocol';
import type { Backdrop, Page } from '../../../shared/records';
import type { Feature } from '../../core/context';
import { byId } from '../../core/dom';
import { Picker } from '../../ui/components/picker';

export const skyFeature: Feature = {
  id: 'sky',
  install({ scene, api, games, status, events }) {
    const gridButton = byId('grid-toggle');
    const skyButton = byId('sky-button');

    events.on('view-changed', ({ sky, grid }) => {
      gridButton.classList.toggle('on', grid);
      skyButton.classList.toggle('on', sky !== null);
      skyButton.title = sky ? 'skybox: ' + sky.name : 'choose a skybox';
    });
    gridButton.addEventListener('click', () => scene.setGrid(!scene.grid()));

    const skyPicker = new Picker<Backdrop>({
      id: 'sky-dialog',
      title: 'skybox',
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

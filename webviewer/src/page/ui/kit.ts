// The ui service (SPEC-VIEWER 6.6): the drawers, the gallery and its game
// tabs, the scene list, and the building blocks a feature or a game uses.
// A game's page module may not import ui/: it gets these in its context.

import type { ApiClient, CameraService, GameRegistry, SceneService, SelectionService, StatusService, Store, UiService } from '../core/context';
import { byIdAs, make } from '../core/dom';
import type { EventBus, ViewerEvents } from '../core/bus';
import { FloatingWindow } from './components/floatingwindow';
import { stepSelect } from './components/stepper';
import { installDrawers } from './drawers';
import { installGallery } from './gallery';
import { installGameTabs } from './gametabs';
import { installInstances } from './instances';

export interface UiDeps {
  readonly games: GameRegistry;
  readonly api: ApiClient;
  readonly scene: SceneService;
  readonly selection: SelectionService;
  readonly camera: CameraService;
  readonly status: StatusService;
  readonly store: Store;
  readonly events: EventBus<ViewerEvents>;
}

export function installUi(deps: UiDeps): UiService {
  const { api, status } = deps;
  /** A record icon from a dataset of a game (default: the gallery's, its current one), or an empty box when the record has none. */
  const iconNode: UiService['iconNode'] = (name, dataset, game) =>
    name ? make('img', { className: 'icon', src: api.iconUrl(name, dataset, game), alt: '', draggable: false }) : make('span', { className: 'icon none' });
  const drawers = installDrawers(deps.store, status.placeStatus);
  installInstances({ ...deps, iconNode });
  installGameTabs({ ...deps, drawers });
  const gallery = installGallery({ ...deps, iconNode });
  // The view tools' dataset select (core/datasets.ts fills it) steps by the wheel and the keys (16.14).
  stepSelect(byIdAs('dataset', HTMLSelectElement));
  return {
    ...drawers,
    ...gallery,
    iconNode,
    floatingWindow: (spec) => new FloatingWindow(spec),
  };
}

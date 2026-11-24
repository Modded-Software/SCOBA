// The page. src/tools/build.ts bundles this file for the browser.
//
// main.ts is the composition root (SPEC-VIEWER 6.6): it builds the
// services of core and ui, each from the ones before it, then installs
// the games and the features with one FeatureContext. Nothing reads a
// shared page object: the services and the events are all there is. The
// test API is what the features hand to testApi.

import type { Feature, FeatureContext, Store } from './core/context';
import { createDatasets } from './core/datasets';
import { collect, createEventBus, type ViewerEvents } from './core/bus';
import { createFrame } from './core/frame';
import { createHost, visibleRect } from './core/host';
import { DdsImage } from './core/library';
import { createScene } from './core/scene';
import { createSelection } from './core/selection';
import { clearSetting, readSetting, writeSetting } from './core/settings';
import { createSky } from './core/sky';
import { createProbe, createTestApi } from './core/testapi';
import { createView } from './core/view';
import { installStatus } from './ui/status';
import { installUi } from './ui/kit';
import { datasetReloadFeature } from './features/dataset-reload';
import { controlsFeature } from './features/controls';
import { landmarksFeature } from './features/landmarks';
import { addAllFeature } from './features/addall';
import { dragFeature } from './features/drag';
import { skyFeature } from './features/sky';
import { pickFeature } from './features/pick';
import { selectFeature } from './features/select';
import { clipboardFeature } from './features/clipboard';
import { inspectFeature } from './features/inspect';
import { scenesFeature } from './features/scenes';
import { m3Format } from '../formats/m3/format';
import { DISPLACEMENT } from '../formats/m3/displacement';
import { sc2Game } from '../games/sc2/page/game';
import { installSc2Page } from '../games/sc2/page/parts';

// The model formats, the games and the features: one line each (SPEC-VIEWER 1, 4, 6.6).
const FORMATS = [m3Format];
const GAMES = [{ game: sc2Game, install: installSc2Page }];
/** In the order the old page scripts loaded, so listeners register in the same order. */
const FEATURES: readonly Feature[] = [datasetReloadFeature, controlsFeature, landmarksFeature, addAllFeature, dragFeature, skyFeature, pickFeature, selectFeature, clipboardFeature, inspectFeature, scenesFeature];

// ---- the services, each from the ones before it ----

const status = installStatus(visibleRect);
const events = createEventBus<ViewerEvents>(status.reportFailure);
const store: Store = { read: readSetting, write: writeSetting, clear: clearSetting };
const host = createHost(FORMATS, status.setStatus);
const { games, api, setupDatasets } = createDatasets(
  GAMES.map((g) => g.game),
  store,
  events,
);
const camera = createView(host, store, events);
const sky = createSky({ host, games, api, status, store, events });
const scene = createScene({ host, games, api, status, events, sky });
const selection = createSelection({ host, camera, items: scene.items, events });
const render = createFrame({ host, camera, scene, selection, games, events });
const ui = installUi({ games, api, scene, selection, camera, status, store, events });
const tests = createTestApi();

const context: FeatureContext = { games, render, scene, selection, camera, status, store, events, api, ui, testApi: tests.builder };

// ---- the games, then the features ----

for (const { game, install } of GAMES) games.addParts(game.id, install(context));
for (const feature of FEATURES) feature.install(context);

// ---- the test API (window.SC2App, window.sc2viewer) ----

tests.builder.app({
  canvas: render.canvas,
  ground: render.ground,
  items: scene.items,
  eye: camera.eye,
  view: camera.view,
  zoomGoal: camera.zoomGoal,
  cameraRestore: camera.cameraRestore,
  /** The ground point under the mouse, as a value (the tests read SC2App.pointer). */
  get pointer() {
    return camera.pointer();
  },
  hitAt: selection.hitAt,
  itemAt: selection.itemAt,
  selectedIds: selection.selectedIds,
  setSelection: selection.setSelection,
  toggleSelected: selection.toggleSelected,
  setPosition: scene.setPosition,
  setVariation: scene.setVariation,
  setStatus: status.setStatus,
  statusLog: status.statusLog,
  statusState: status.statusState,
  visibleRect: render.visibleRect,
  drawerState: ui.drawerState,
});
tests.builder.viewer({
  groundUnder: camera.groundAt,
  remove: scene.remove,
  clear: scene.clear,
  restart: scene.restart,
  view: camera.view,
  itemPixel: selection.itemPixel,
  setGrid: scene.setGrid,
  setSky: scene.setSky,
  screenOf: camera.screenOf,
  itemScreen: selection.itemScreen,
  setDisplacement: (on: boolean) => render.setPostPass(DISPLACEMENT, on),
  /** The games: the tabs' list, the gallery's game, and choosing one. */
  games: { list: games.gamesInfo, current: games.game, choose: games.setGame, refusal: games.gameRefusal },
  /** A format's own test members: probe('m3', 'particles', id) (SPEC-VIEWER 6.3). */
  probe: createProbe(FORMATS, context),
  /** The renderer's DDS reader, for the tests that decode a texture in the page. */
  DdsImage,
});

const sc2viewer = tests.viewer();
const sc2App = tests.app();

declare global {
  interface Window {
    SC2App: Readonly<Record<string, unknown>>;
    sc2viewer: Record<string, unknown>;
  }
}

window.SC2App = sc2App;
window.sc2viewer = sc2viewer;

// ---- startup: the datasets first; every list and every item reads one ----

host.resize();
camera.applyCamera();
render.start();
setupDatasets()
  .then(() => Promise.all([collect(events, 'startup'), render.ground.ready, render.outline.ready]))
  .catch(status.reportFailure)
  .finally(() => {
    sc2viewer['ready'] = true;
  });

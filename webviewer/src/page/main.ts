// The page. src/tools/build.ts bundles this file for the browser.
//
// First every stored setting is checked (core/settings.ts). One that is
// refused stops the start: the page shows the refused keys and a way to
// clear them (core/refusals.ts, R-VIEW-73). Else the page starts.
//
// main.ts is the composition root (SPEC-VIEWER 6.6): startViewer builds the
// services of core and ui, each from the ones before it, then installs the
// games and the features with one FeatureContext. Nothing reads a shared
// page object: the services and the events are all there is. The test API
// is what the features hand to testApi.

import type { Feature, FeatureContext, Store } from './core/context';
import { createDatasets } from './core/datasets';
import { collect, createEventBus, type ViewerEvents } from './core/bus';
import { createFrame } from './core/frame';
import { createHost, visibleRect } from './core/host';
import { DdsImage } from './core/library';
import { createScene } from './core/scene';
import { createSelection } from './core/selection';
import { SettingsRefused, showRefusedSettings } from './core/refusals';
import { clearSetting, findSetting, readSetting, refusedSettings, writeSetting } from './core/settings';
import { createSky } from './core/sky';
import { createProbe, createTestApi } from './core/testapi';
import { createSkins } from './core/skins';
import { createTextureWindow } from './core/texturewindow';
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
import { edgesFeature } from './features/edges';
import { skinsFeature } from './features/skins';
import { editsFeature } from './features/edits';
import { m3Format } from '../formats/m3/format';
import { DISPLACEMENT } from '../formats/m3/displacement';
import { nodFormat } from '../formats/nod/format';
import { sc2Game } from '../games/sc2/page/game';
import { installSc2Page } from '../games/sc2/page/parts';
import { ghostGame } from '../games/ghost/page/game';
import { installGhostPage } from '../games/ghost/page/parts';

// The model formats, the games and the features: one line each (SPEC-VIEWER 1, 4, 6.6).
const FORMATS = [m3Format, nodFormat];
const GAMES = [
  { game: sc2Game, install: installSc2Page },
  { game: ghostGame, install: installGhostPage },
];
/** In install order: a feature listens before the ones after it. */
const FEATURES: readonly Feature[] = [datasetReloadFeature, controlsFeature, landmarksFeature, addAllFeature, dragFeature, skyFeature, pickFeature, selectFeature, clipboardFeature, inspectFeature, scenesFeature, edgesFeature, skinsFeature, editsFeature];

declare global {
  interface Window {
    SC2App: Readonly<Record<string, unknown>>;
    sc2viewer: Record<string, unknown>;
  }
}

/** Build the page and start it. The stored settings were checked before. */
function startViewer(): void {
// ---- the services, each from the ones before it ----

const status = installStatus(visibleRect);
const events = createEventBus<ViewerEvents>(status.reportFailure);
const store: Store = { read: readSetting, find: findSetting, write: writeSetting, clear: clearSetting };
const host = createHost(FORMATS, status.setStatus);
const { games, api, setupDatasets } = createDatasets(
  GAMES.map((g) => g.game),
  store,
  events,
);
const camera = createView(host, store, events);
// The scene is made after; the skins read its items only on a later event.
const skins = createSkins({ host, games, status, events, items: () => scene.items });
const sky = createSky({ host, games, api, status, store, events, skins });
const scene = createScene({ host, games, api, status, events, sky, skins });
const selection = createSelection({ host, camera, items: scene.items, events });
const render = createFrame({ host, camera, scene, selection, games, events });
const ui = installUi({ games, api, scene, selection, camera, status, store, events });
const tests = createTestApi();
// Ctrl+L (the loop choice) stays the viewer's inside the texture window's frame.
const textureWindow = createTextureWindow(ui, render, events, ['l']);

const context: FeatureContext = { games, render, scene, selection, camera, status, store, events, api, ui, textureWindow, skins, testApi: tests.builder };

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
  cameraStart: camera.cameraStart,
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
  /** The games: the tabs' list, the gallery's game, choosing one, and the chosen game's categories (ground: listed by the ground button, no pane). */
  games: {
    list: games.gamesInfo,
    current: games.game,
    choose: games.setGame,
    refusal: games.gameRefusal,
    categories: () => games.plugin().categories.map((category) => ({ id: category.id, ground: Boolean(category.ground) })),
  },
  /** A format's own test members: probe('m3', 'particles', id) (SPEC-VIEWER 6.3). */
  probe: createProbe(FORMATS, context),
  /** The renderer's DDS reader, for the tests that decode a texture in the page. */
  DdsImage,
  /** The texture window of every game: open, whose textures, how reading them went. */
  textureWindow: textureWindow.state,
  /** An instance's skin: its owner, its menu's choices, and setting one (SPEC-VIEWER 17.4). */
  skinChoices: (id: number) => {
    const item = scene.items.find((one) => one.id === id);
    return item ? { owner: skins.ownerOf(item), choices: skins.choices(item), state: skins.owner(item), following: skins.following(item) } : null;
  },
  setSkin: async (id: number, skin: string) => {
    const item = scene.items.find((one) => one.id === id);
    if (!item) throw new Error(`no instance ${id}`);
    await skins.set(item, skin);
  },
});

const sc2viewer = tests.viewer();
const sc2App = tests.app();

window.SC2App = sc2App;
window.sc2viewer = sc2viewer;

// ---- startup: the datasets first; every list and every item reads one ----
// A stored game or dataset the server refuses stops the start with the panel (core/refusals.ts).

host.resize();
camera.applyCamera();
render.start();
setupDatasets()
  .then(() => Promise.all([collect(events, 'startup'), render.ground.ready, render.outline.ready]))
  .then(
    () => {
      sc2viewer['ready'] = true;
    },
    (failure: unknown) => {
      // A refused stored choice stops the start: the panel, not the page (ready stays unset).
      if (failure instanceof SettingsRefused) {
        showRefusedSettings(failure.refused);
        return;
      }
      status.reportFailure(failure);
      sc2viewer['ready'] = true;
    },
  );
}

// ---- the start: the stored settings first ----

const refused = refusedSettings();
if (refused.length) showRefusedSettings(refused);
else startViewer();

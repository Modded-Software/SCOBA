// The page. src/tools/build.ts bundles this file for the browser.
//
// The parts install in the order the old page scripts loaded, so event
// listeners register in the same order. Each part gets the parts before
// it; at call time every part reads the whole through app().

import { app, merge, setApp, type App } from './core/app';
import { createCore } from './core/host';
import { installDatasets } from './core/datasets';
import { installScene } from './core/scene';
import { installFrame } from './core/frame';
import { DdsImage } from './core/library';
import { installStatus } from './ui/status';
import { installDrawers } from './ui/drawers';
import { installInstances } from './ui/instances';
import { installUnits } from './ui/gallery/units';
import { installDoodads } from './ui/gallery/doodads';
import { installDatasetReload } from './features/dataset-reload';
import { installControls } from './features/controls';
import { installFocus } from './features/focus';
import { installLandmarks } from './features/landmarks';
import { installAddAll } from './features/addall';
import { installDrag } from './features/drag';
import { installSky } from './features/sky';
import { installPick } from './features/pick';
import { installSelect } from './features/select';
import { installClipboard } from './features/clipboard';
import { installInspect } from './features/inspect';
import { installTextures } from './features/textures';
import { installHd } from './features/hd';
import { installScenes } from './features/scenes';
import { createDisplacement } from '../formats/m3/displacement';
import { particlesApi } from '../formats/m3/particles';
import { billboardsApi } from '../formats/m3/billboards';

// core.js and side.js.
const core = merge(merge(createCore(createDisplacement), installStatus()), installDrawers());
// datasets.js.
const withData = merge(merge(core, installDatasets()), installDatasetReload());
// controls.js, scene.js (with the focus and the scene list), panels.js, doodads.js.
const withScene = merge(merge(merge(merge(withData, installControls(withData)), installScene(withData)), installFocus()), installInstances(withData));
const withGallery = merge(merge(withScene, installUnits(withScene)), installDoodads(withScene));
// landmarks.js, addall.js, drag.js, sky.js.
const withTools = merge(merge(merge(merge(withGallery, installLandmarks(withGallery)), installAddAll()), installDrag(withGallery)), installSky(withGallery));
// pick.js, select.js, clipboard.js.
const withPick = merge(merge(merge(withTools, installPick(withTools)), installSelect(withTools)), installClipboard(withTools));
// inspect.js, textures.js, hd.js, particles.js, billboards.js.
const inspect = installInspect();
const withViews = merge(merge(withPick, installTextures(withPick)), installHd(withPick));
// The scene documents (SPEC-VIEWER section 10.2).
const withScenes = merge(withViews, installScenes());
// main.js.
const frame = installFrame(withScenes);
const whole: App = merge(withScenes, frame);
setApp(whole);

/** What the tests and the console reach: the whole object, inspection included. */
const sc2App = merge(merge(merge(whole, inspect), particlesApi), billboardsApi);

/** The test API: a fixed list of the parts' functions. */
const sc2viewer = {
  ready: false,
  groundUnder: whole.groundAt,
  add: whole.add,
  addUnit: whole.addUnit,
  addDoodad: whole.addDoodad,
  remove: whole.remove,
  clear: whole.clear,
  restart: whole.restart,
  view: whole.view,
  itemPixel: whole.itemPixel,
  setGrid: whole.setGrid,
  setSky: whole.setSky,
  screenOf: whole.screenOf,
  itemScreen: whole.itemScreen,
  pickState: whole.pickState,
  setDisplacement: whole.setDisplacement,
  textureWindow: whole.textureWindow,
  hdAssets: whole.hdAssets,
  /** The scene documents: read the open one, the list; make, open, rename, delete, export, import; wait for writes. */
  scenes: {
    state: whole.scenesState,
    document: whole.sceneDocument,
    flush: whole.flushScenes,
    create: whole.newScene,
    open: whole.openScene,
    rename: whole.renameScene,
    remove: whole.deleteScene,
    exportText: whole.exportScene,
    importText: whole.importScene,
  },
  ...inspect,
  ...particlesApi,
  ...billboardsApi,
  /** The renderer's DDS reader, for the tests that decode a texture in the page. */
  DdsImage,
};

declare global {
  interface Window {
    SC2App: typeof sc2App;
    sc2viewer: typeof sc2viewer;
  }
}

window.SC2App = sc2App;
window.sc2viewer = sc2viewer;

// Startup. The datasets first: every list and every item reads one.
whole.resize();
whole.applyCamera();
frame.start();
const a = app();
a.setupDatasets()
  .then(() => a.setupHd())
  .then(() => Promise.all([a.setupUnits(), a.setupDoodads(), a.setupScenes(), a.restoreView(), a.ground.ready, a.outline.ready]))
  .catch((error: unknown) => a.reportFailure(error))
  .finally(() => {
    sc2viewer.ready = true;
  });

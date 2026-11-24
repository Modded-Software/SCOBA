// What SC2 adds to the shared page (SPEC-VIEWER 6.6): the HD texture sets,
// the texture window, the item option `hd`, and its part of the test API.
// The gallery is core's, built from the categories the server sends.
// main.ts installs this with the same context a feature gets.

import type { GameContext, GameParts } from '../../../page/core/context';
import { sc2SceneApi } from './api';
import { installHd } from './hd';
import { filterName } from './names';
import { installTextures } from './textures';

export function installSc2Page(context: GameContext): GameParts {
  const textures = installTextures(context);
  const hd = installHd(context);
  const gameTestApi = { textureWindow: textures.textureWindow, hdAssets: hd.hdAssets };
  // The SC2 adds (unit, doodad, hd, variation) and the texture window, for the tests.
  context.testApi.viewer({ ...sc2SceneApi(context.scene), ...gameTestApi });
  // The landmark name of a unit query (features/addall).
  context.testApi.app({ ...gameTestApi, filterName });
  return {
    itemReady: hd.applyHd,
    glowOf: (item) => (hd.isHd(item) ? 1 : 0),
    itemFacts: (item) => ({ hd: hd.hdOn(item), hdLayers: hd.hdLayers(item), largestTexture: hd.largestTexture(item), blueGlow: hd.isHd(item) }),
    // The one SC2 option: the HD texture set, on unless set to false.
    itemOptions: (raw) => ({ hd: raw['hd'] !== false }),
    menuToggles: [hd.toggle],
    openItem: textures.openTexturesOf,
    openRecord: textures.openTexturesFor,
    prepareGame: hd.setupHd,
  };
}

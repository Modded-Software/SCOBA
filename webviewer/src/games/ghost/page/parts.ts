// What Ghost adds to the shared page (SPEC-VIEWER 6.6): its textures in
// the shared texture window (textures.ts), opened by a double-click. No
// item options, no menu toggles, no second grid glow (SPEC-VIEWER-GHOST 6,
// 7: no capability but the edge draw). main.ts installs this.

import type { GameContext, GameParts } from '../../../page/core/context';
import { installGhostTextures } from './textures';

export function installGhostPage(context: GameContext): GameParts {
  const textures = installGhostTextures(context);
  return {
    itemReady: async () => {},
    glowOf: () => 0,
    itemFacts: () => ({}),
    itemOptions: () => ({}),
    menuToggles: [],
    openItem: textures.openTexturesOf,
    openRecord: textures.openTexturesFor,
    prepareGame: async () => {},
  };
}

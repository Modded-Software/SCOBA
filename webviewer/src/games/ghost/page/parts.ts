// What Ghost adds to the shared page (SPEC-VIEWER 6.6): its textures in
// the shared texture window (textures.ts), opened by a double-click. No
// item options, no texture service, no second grid glow (SPEC-VIEWER-GHOST
// 6, 7: no capability but the edge draw). main.ts installs this.

import { noItemOptions, type GameContext, type GameParts } from '../../../page/core/context';
import { installGhostTextures } from './textures';

export function installGhostPage(context: GameContext): GameParts {
  const textures = installGhostTextures(context);
  return {
    glowOf: () => 0,
    itemFacts: () => ({}),
    itemOptions: noItemOptions,
    openItem: textures.openTexturesOf,
    openRecord: textures.openTexturesFor,
  };
}

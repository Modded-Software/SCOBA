// What Ghost adds to the shared page (SPEC-VIEWER 6.6): nothing beyond
// core. No item options, no menu toggles, no texture window, no second
// grid glow (SPEC-VIEWER-GHOST 6, 7: no capabilities). main.ts installs this.

import type { GameParts } from '../../../page/core/context';

export function installGhostPage(): GameParts {
  return {
    itemReady: async () => {},
    glowOf: () => 0,
    itemFacts: () => ({}),
    itemOptions: () => ({}),
    menuToggles: [],
    openItem: async () => {},
    openRecord: async () => {},
    prepareGame: async () => {},
  };
}

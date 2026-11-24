// The viewer server. src/tools/build.ts bundles this file into
// build/server.js; the scripts and the test runner start that.
// The games: SC2 first (the default), then Ghost. A game whose data is not
// on the machine is listed as not available, with the reason (R-VIEW-8).
// The protocol's routes first (/api/...), then the page's static files,
// which take GET only.

import { startGhost } from '../games/ghost/server';
import { startSc2 } from '../games/sc2/server';
import { GameUnavailable, type GameBackend, type UnavailableGame } from './core/backend';
import { onlyGet, serve } from './core/http';
import { protocol } from './core/protocol';
import { coreSettings } from './core/settings';
import { staticFiles } from './core/static';

const core = coreSettings();
const sc2 = await startSc2(core);

const games: GameBackend[] = [sc2];
const unavailable: UnavailableGame[] = [];
const banners = [sc2.banner()];
try {
  const ghost = await startGhost(core);
  games.push(ghost);
  banners.push(ghost.banner());
} catch (error) {
  if (!(error instanceof GameUnavailable)) throw error;
  unavailable.push({ id: 'ghost', label: 'StarCraft: Ghost', tab: 'SC: G', reason: error.message });
  banners.push(`ghost: not available: ${error.message}`);
}

serve([protocol(games, unavailable), onlyGet, staticFiles(core.viewerDir)], core.port, core.host, () => {
  console.log(`sc2 webviewer: http://${core.host}:${core.port}/  (${banners.join('; ')})`);
});

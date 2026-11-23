// The viewer server. src/tools/build.ts bundles this file into
// build/server.js; the scripts and the test runner start that.
// SC2 is the one game. The protocol's routes first (/api/...), then the
// page's static files, which take GET only.

import { startSc2 } from '../games/sc2/server';
import { onlyGet, serve } from './core/http';
import { protocol } from './core/protocol';
import { coreSettings } from './core/settings';
import { staticFiles } from './core/static';

const core = coreSettings();
const sc2 = await startSc2(core);

serve([protocol([sc2]), onlyGet, staticFiles(core.viewerDir)], core.port, core.host, () => {
  console.log(`sc2 webviewer: http://${core.host}:${core.port}/  (${sc2.banner()})`);
});

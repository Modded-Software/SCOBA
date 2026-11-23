// The server core's own settings (SPEC-VIEWER section 7): the port, the
// host, and where the viewer folder is. Every other setting is a game's.

import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export interface CoreSettings {
  readonly port: number;
  readonly host: string;
  /** The webviewer folder: public/ and scripts/ are below it. */
  readonly viewerDir: string;
  /** The repository root, the viewer folder's parent. */
  readonly repoRoot: string;
}

/**
 * Read from the environment. The viewer folder is WEBVIEWER_DIR, or the
 * parent of the folder of the running bundle (build/server.js).
 */
export function coreSettings(env: NodeJS.ProcessEnv = process.env): CoreSettings {
  const viewerDir = resolve(env['WEBVIEWER_DIR'] || resolve(dirname(fileURLToPath(import.meta.url)), '..'));
  return {
    port: Number(env['PORT'] || 4517),
    host: env['HOST'] || '127.0.0.1',
    viewerDir,
    repoRoot: resolve(env['REPO_ROOT'] || resolve(viewerDir, '..')),
  };
}

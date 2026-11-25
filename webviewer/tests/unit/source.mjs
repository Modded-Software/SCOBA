// Page and game code in Node, without a browser: one TypeScript module is
// bundled by esbuild (as scripts/tool.sh does) into the work folder and
// imported. For logic only: a module that reaches the DOM, storage or WebGL
// when it is called is tested in tests/e2e. The renderer library
// (`@renderer/*`, page/core/library.ts) is an empty stand-in here: a module
// that only names it may be loaded, and a call into it fails.
import { build } from 'esbuild';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { envPath } from '../fixtures.mjs';

const loaded = new Map();

/** The renderer as an empty CommonJS module: named imports of it are undefined. */
const noRenderer = {
  name: 'no-renderer',
  setup(builder) {
    builder.onResolve({ filter: /^@renderer\// }, (args) => ({ path: args.path, namespace: 'no-renderer' }));
    builder.onLoad({ filter: /.*/, namespace: 'no-renderer' }, () => ({ contents: 'module.exports = {};', loader: 'js' }));
  },
};

/** The exports of `path` (relative to webviewer/, e.g. 'src/page/core/settings.ts'). */
export function source(path) {
  if (!loaded.has(path)) loaded.set(path, bundle(path));
  return loaded.get(path);
}

async function bundle(path) {
  const outfile = join(envPath('WEBVIEWER_WORK'), 'test-units', String(process.pid), `${path.replaceAll('/', '_')}.mjs`);
  await build({ entryPoints: [path], bundle: true, platform: 'node', format: 'esm', target: 'node24', outfile, logLevel: 'warning', plugins: [noRenderer] });
  return import(pathToFileURL(outfile).href);
}

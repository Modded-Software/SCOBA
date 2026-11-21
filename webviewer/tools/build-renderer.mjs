// Bundle the renderer from the ref repo (ref/mdx-m3-viewer).
// Writes public/vendor/renderer.js (browser, global ModelViewer) and
// build/m3parser.cjs (the M3 parser alone, for Node tools).
//
// Every change to the library is a commit in the ref repo. The build
// refuses a ref repo with uncommitted changes, and exports the commits
// on top of the upstream base to patches/, so the patch files always
// match what was built.

import { build } from 'esbuild';
import { execFile } from 'node:child_process';
import { mkdir, readdir, rm } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';

const run = promisify(execFile);
const HERE = join(dirname(fileURLToPath(import.meta.url)), '..');
const REF = join(HERE, 'ref', 'mdx-m3-viewer');
const PATCHES = join(HERE, 'patches');
// Upstream master, 2025-08-27. Its M3, GL, viewer and scene code is the same as npm 5.12.0.
export const BASE = '2ff0bc00c6363f425016e23d88c0fb2929d3b3cc';

const git = async (...args) => (await run('git', ['-C', REF, ...args], { maxBuffer: 64 * 1024 * 1024 })).stdout;

const dirty = (await git('status', '--porcelain', '--untracked-files=no')).trim();
if (dirty) throw new Error(`ref repo has uncommitted changes; commit them first:\n${dirty}`);
const head = (await git('rev-parse', 'HEAD')).trim();
await run('git', ['-C', REF, 'merge-base', '--is-ancestor', BASE, 'HEAD']).catch(() => {
  throw new Error(`ref repo HEAD ${head} does not build on the upstream base ${BASE}`);
});

// patches/ is rewritten from the commits, so it never drifts from them.
await mkdir(PATCHES, { recursive: true });
for (const name of await readdir(PATCHES)) if (name.endsWith('.patch')) await rm(join(PATCHES, name));
await git('format-patch', '--quiet', '--no-signature', '-o', PATCHES, `${BASE}..HEAD`);
const patches = (await readdir(PATCHES)).filter((name) => name.endsWith('.patch')).sort();

const common = { bundle: true, logLevel: 'warning', absWorkingDir: HERE, nodePaths: [join(HERE, 'node_modules')] };

await build({
  ...common,
  entryPoints: ['src/renderer-entry.cjs'],
  outfile: 'public/vendor/renderer.js',
  platform: 'browser',
  format: 'iife',
  globalName: 'ModelViewer',
  minify: true,
  sourcemap: true,
});

await build({
  ...common,
  entryPoints: ['src/parser-entry.cjs'],
  outfile: 'build/m3parser.cjs',
  platform: 'node',
  format: 'cjs',
});

console.log(`renderer built from ref ${head.slice(0, 8)} with ${patches.length} patches on ${BASE.slice(0, 8)}`);
for (const name of patches) console.log(`  ${name}`);

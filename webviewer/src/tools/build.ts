// Bundle the page with the renderer from the ref repo (ref/mdx-m3-viewer),
// and the server. Writes public/vendor/renderer.js (browser,
// src/page/main.ts), build/server.js (Node, src/server/main.ts) and
// build/m3parser.cjs (the M3 parser alone, for Node tools).
//
// Every change to the library is a commit in the ref repo. The build
// refuses a ref repo with uncommitted changes, and exports the commits
// on top of the upstream base to patches/, so the patch files always
// match what was built.
//
// Started by scripts/build.sh, which bundles this file first (scripts/tool.sh).

import { build, type BuildOptions } from 'esbuild';
import { execFile } from 'node:child_process';
import { mkdir, readdir, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { promisify } from 'node:util';

const run = promisify(execFile);

// Upstream master, 2025-08-27. Its M3, GL, viewer and scene code is the same as npm 5.12.0.
// Keep in sync with BASE in scripts/ref-setup.sh.
const BASE = '2ff0bc00c6363f425016e23d88c0fb2929d3b3cc';

/** The viewer folder. scripts/paths.sh exports it. */
function viewerDir(): string {
  const dir = process.env.WEBVIEWER_DIR;
  if (dir === undefined || dir === '') {
    throw new Error('WEBVIEWER_DIR is not set; start this tool with scripts/build.sh');
  }
  return dir;
}

const HERE = viewerDir();
const REF = join(HERE, 'ref', 'mdx-m3-viewer');
const PATCHES = join(HERE, 'patches');

/** Run git in the ref repo; its output. */
async function git(...args: string[]): Promise<string> {
  const { stdout } = await run('git', ['-C', REF, ...args], { maxBuffer: 64 * 1024 * 1024 });
  return stdout;
}

/** The patch files in patches/, sorted. */
async function patchFiles(): Promise<string[]> {
  return (await readdir(PATCHES)).filter((name) => name.endsWith('.patch')).sort();
}

const dirty = (await git('status', '--porcelain', '--untracked-files=no')).trim();
if (dirty !== '') throw new Error(`ref repo has uncommitted changes; commit them first:\n${dirty}`);
const head = (await git('rev-parse', 'HEAD')).trim();
await git('merge-base', '--is-ancestor', BASE, 'HEAD').catch((cause: unknown) => {
  throw new Error(`ref repo HEAD ${head} does not build on the upstream base ${BASE}`, { cause });
});

// patches/ is rewritten from the commits, so it never drifts from them.
await mkdir(PATCHES, { recursive: true });
for (const name of await patchFiles()) await rm(join(PATCHES, name));
await git('format-patch', '--quiet', '--no-signature', '-o', PATCHES, `${BASE}..HEAD`);
const patches = await patchFiles();

const common: BuildOptions = {
  bundle: true,
  logLevel: 'warning',
  absWorkingDir: HERE,
  nodePaths: [join(HERE, 'node_modules')],
};

// The page bundle: src/page/main.ts with the library. Our code imports the
// library as @renderer/..., the source folder of the ref repo.
await build({
  ...common,
  entryPoints: ['src/page/main.ts'],
  outfile: 'public/vendor/renderer.js',
  platform: 'browser',
  format: 'iife',
  alias: { '@renderer': './ref/mdx-m3-viewer/src' },
  minify: true,
  sourcemap: true,
});

// The server bundle: src/server/main.ts with the games' backends. Node
// modules and packages stay imports.
await build({
  ...common,
  entryPoints: ['src/server/main.ts'],
  outfile: 'build/server.js',
  platform: 'node',
  format: 'esm',
  target: 'node24',
  packages: 'external',
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

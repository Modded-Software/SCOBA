// The test fixture every spec imports in place of @playwright/test.
//
// Each Playwright worker gets its own server, its own texture store and its
// own datasets folder (SPEC-VIEWER 11.1). A test can then write variants,
// skins, bakes or dataset files without any other worker seeing them, and
// every test may run in parallel with every other.
//
// The worker's folder is $WEBVIEWER_WORK/test-workers/<parallel index>:
//   datasets/   a copy of $WEBVIEWER_DATASETS (the fx fixture and its catalog)
//   store/      a new texture store: the format file, a copy of the base
//               store's state index, and each game's index/ (the game's
//               own caches) as hard links to the base store's.
//   server.log  the server's output
// The port is 4518 plus the parallel index.
//
// The base store's state index is made once per run, by a server started
// on the base store with none (tests/global-setup.mjs): that start is the
// proof that a store never read comes up (SPEC-VIEWER 17.1). A worker, and a
// worker started again after a failure, copies it and starts in seconds.

import { test as base, expect } from '@playwright/test';
import { execFile, spawn } from 'node:child_process';
import { once } from 'node:events';
import { createWriteStream, existsSync, statSync } from 'node:fs';
import { copyFile, mkdir, readdir, rm, writeFile } from 'node:fs/promises';
import { isAbsolute, join } from 'node:path';
import { promisify } from 'node:util';

export { expect };

/** The first port of the test servers. 4517 is the operator's viewer. */
export const FIRST_PORT = 4518;

/** A path scripts/test.sh exports. Unset is an error: the tests guess no place (SPEC-PATHS). */
export function envPath(name) {
  const value = process.env[name] ?? '';
  if (!isAbsolute(value)) throw new Error(`${name} is not set: run the tests through scripts/test.sh (SPEC-PATHS)`);
  return value;
}

/** Run a program; it throws when the program fails. */
export const run = promisify(execFile);

/**
 * The port of a second server a spec starts for itself (ownServer): past
 * every worker's port, one per worker.
 */
export const extraPort = (index) => FIRST_PORT + 100 + index;

/** The port of the server global setup starts on the base store: past every worker's (at most 99). */
export const BASE_PORT = FIRST_PORT + 99;

/** The state index of a store (scripts/hdtex/core/index.py FILE). */
export const INDEX_FILE = 'index.sqlite';

/**
 * Copy the base store's layout: its format file, its state index, and each
 * game's index/ as hard links (cp -al). The pipeline replaces a cache file
 * by rename, never writes it in place (scripts/hdtex/core/store.py), so a
 * worker's write does not reach the base store. The state index is written
 * in place: it is copied. Global setup folded its log into it (closeIndex),
 * so the file alone holds it all.
 */
export async function seedStore(from, to) {
  await mkdir(to, { recursive: true });
  await copyFile(join(from, 'format'), join(to, 'format'));
  const log = join(from, `${INDEX_FILE}-wal`);
  if (existsSync(log) && statSync(log).size > 0) throw new Error(`${log}: the base state index has a log not folded in`);
  await copyFile(join(from, INDEX_FILE), join(to, INDEX_FILE));
  for (const entry of await readdir(from, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    await mkdir(join(to, entry.name), { recursive: true });
    if (existsSync(join(from, entry.name, 'index'))) await run('cp', ['-al', join(from, entry.name, 'index'), join(to, entry.name, 'index')]);
  }
}

/**
 * Start a server on `port` with the folders and extra environment given,
 * and wait until its health route answers. The caller stops it with stop().
 */
export async function startServer({ port, store, datasets, log, env = {} }) {
  const url = `http://127.0.0.1:${port}`;
  // Negative: a port another server holds (one a killed run left) would answer for this one.
  const taken = await fetch(`${url}/api/health`).then(
    () => true,
    (error) => {
      if (error instanceof TypeError) return false; // nothing listens
      throw error;
    },
  );
  if (taken) throw new Error(`port ${port} is in use: a server a killed run left? (AGENTS.md: clean it up)`);
  const out = createWriteStream(log);
  const child = spawn('node', ['build/server.js'], { env: { ...process.env, PORT: String(port), TEXTURE_STORE: store, WEBVIEWER_DATASETS: datasets, ...env }, stdio: ['ignore', 'pipe', 'pipe'] });
  let output = '';
  const keep = (chunk) => {
    output += chunk;
    out.write(chunk);
  };
  child.stdout.on('data', keep);
  child.stderr.on('data', keep);
  // Poll the health route; the start builds the state index (SPEC-VIEWER 17.1).
  await expect
    .poll(
      async () => {
        if (child.exitCode !== null) throw new Error(`the server on ${port} stopped (${child.exitCode}): ${output}`);
        try {
          return (await fetch(`${url}/api/health`)).ok;
        } catch (error) {
          if (error instanceof TypeError) return false; // not listening yet
          throw error;
        }
      },
      { timeout: 170_000, intervals: [250] },
    )
    .toBe(true);
  return {
    url,
    output: () => output,
    async stop() {
      if (child.exitCode === null) {
        child.kill();
        await once(child, 'exit');
      }
      out.end();
    },
  };
}

/**
 * A server with folders of its own in `root` (emptied first): a copy of the
 * datasets, a store seeded from the base store, its log. Returns
 * { url, port, root, store, datasets, output(), stop() }.
 */
async function serverIn(root, port, env = {}) {
  await rm(root, { recursive: true, force: true });
  await mkdir(root, { recursive: true });
  const datasets = join(root, 'datasets');
  const store = join(root, 'store');
  // cp -a keeps the change times: the fx catalog's signature stays valid (datasets.ts signature).
  await run('cp', ['-a', envPath('WEBVIEWER_DATASETS'), datasets]);
  await seedStore(envPath('TEXTURE_STORE'), store);
  const server = await startServer({ port, store, datasets, log: join(root, 'server.log'), env });
  return { ...server, port, root, store, datasets };
}

/**
 * A second server for a spec that needs one of its own: other settings
 * (`env`), or dataset files it changes and does not put back. Its folders
 * are `<worker root>/<name>`; its port is the worker's extra port, so a spec
 * that uses it runs serially and stops it in afterAll.
 */
export const ownServer = (worker, parallelIndex, name, env = {}) => serverIn(join(worker.root, name), extraPort(parallelIndex), env);

/** The problems a test expects, by test id: allowErrors fills it, the page fixture reads it. */
const allowed = new Map();

/**
 * Name the problems this test expects (SPEC-VIEWER 11). Each pattern (a
 * RegExp, or a string to find) must match one recorded problem, or the
 * test fails: an allowance for a problem that never came is a test that
 * no longer proves its case. Problems look like
 *   pageerror: <message>          an uncaught error in the page
 *   console.<type>: <text>        a console error, or any "viewer:" report
 *   http <status> <method> <url>  a reply of 400 or more
 *   requestfailed <url>: <why>    a request with no reply (not an abort)
 *   server: <line>                an error line in the worker server's log
 */
export function allowErrors(...patterns) {
  const id = base.info().testId;
  allowed.set(id, [...(allowed.get(id) ?? []), ...patterns]);
}

/** A line of the server's log that reports a failure (src/server/core/http.ts, the games' servers). */
const SERVER_PROBLEM = /^(?:\w*Error\b|viewer: |sc2 webviewer: )/;

/** A console report of the viewer's own (src/page/core/host.ts, src/page/ui/status.ts). */
const VIEWER_REPORT = /^(?:scobaeditor|viewer):/;

const matches = (pattern, problem) => (pattern instanceof RegExp ? pattern.test(problem) : problem.includes(pattern));

/** The lock file one browser start holds. scripts/test.sh removes test-workers/, so a killed run leaves none. */
const gpuLock = () => join(envPath('WEBVIEWER_WORK'), 'test-workers', 'gpu-start.lock');

/** Take the GPU start lock: create the file only if none is there; wait for the holder. */
async function takeGpuLock() {
  const file = gpuLock();
  const deadline = Date.now() + 60_000;
  for (;;) {
    try {
      await writeFile(file, String(process.pid), { flag: 'wx' });
      return;
    } catch (error) {
      if (error.code !== 'EEXIST') throw error;
      if (Date.now() > deadline) throw new Error(`the GPU start lock ${file} was held for 60 s`);
      await new Promise((done) => setTimeout(done, 100));
    }
  }
}

/** A canvas, a WebGL context, one linked program: the state of the browser's GPU. */
async function probeWebgl(browser) {
  const page = await browser.newPage();
  try {
    return await page.evaluate(() => {
      const gl = document.createElement('canvas').getContext('webgl');
      if (gl === null) return { live: false, why: 'no WebGL context' };
      if (gl.isContextLost()) return { live: false, why: 'the context is lost' };
      const shader = (type, source) => {
        const s = gl.createShader(type);
        gl.shaderSource(s, source);
        gl.compileShader(s);
        return s;
      };
      const program = gl.createProgram();
      gl.attachShader(program, shader(gl.VERTEX_SHADER, 'void main() { gl_Position = vec4(0.0); }'));
      gl.attachShader(program, shader(gl.FRAGMENT_SHADER, 'void main() { gl_FragColor = vec4(1.0); }'));
      gl.linkProgram(program);
      const linked = Boolean(gl.getProgramParameter(program, gl.LINK_STATUS));
      return { live: linked && !gl.isContextLost(), why: linked ? 'the context was lost after the link' : 'the program did not link', renderer: gl.getParameter(gl.RENDERER) };
    });
  } finally {
    await page.close();
  }
}

export const test = base.extend({
  /**
   * The worker's browser. The browsers start one at a time: four GPU
   * processes starting at once sometimes gave one page a lost WebGL context
   * (runs e2e17, e2e18, e2e21, e2e23: "Shader failed to link: the WebGL
   * context is lost" on the first spec). The start holds a lock until a
   * page of the new browser links a program; a browser that cannot fails
   * the worker with the reason.
   */
  browser: [
    async ({ playwright, launchOptions, channel, headless }, use) => {
      await takeGpuLock();
      let browser;
      try {
        browser = await playwright.chromium.launch({ ...launchOptions, channel, headless });
        const gl = await probeWebgl(browser);
        if (!gl.live) throw new Error(`the browser's WebGL is not live: ${gl.why} (renderer ${gl.renderer ?? 'none'})`);
      } catch (error) {
        await browser?.close();
        throw error;
      } finally {
        await rm(gpuLock(), { force: true });
      }
      await use(browser);
      await browser.close();
    },
    { scope: 'worker', timeout: 60_000 },
  ],


  /**
   * Every page is watched: a test that passes with a page error, a console
   * error, a failed request or a server error line fails (SPEC-VIEWER 11),
   * unless it named that problem with allowErrors.
   */
  page: async ({ page, worker }, use, testInfo) => {
    const problems = [];
    page.on('pageerror', (e) => problems.push(`pageerror: ${e.message}`));
    page.on('console', (m) => {
      if (m.type() === 'error' || VIEWER_REPORT.test(m.text())) problems.push(`console.${m.type()}: ${m.text()}`);
    });
    page.on('response', (r) => {
      if (r.status() >= 400) problems.push(`http ${r.status()} ${r.request().method()} ${r.url()}`);
    });
    page.on('requestfailed', (r) => {
      const why = r.failure()?.errorText ?? '';
      if (why !== 'net::ERR_ABORTED') problems.push(`requestfailed ${r.url()}: ${why}`);
    });
    const logStart = worker.output().length;
    await use(page);
    for (const line of worker.output().slice(logStart).split('\n')) {
      if (SERVER_PROBLEM.test(line)) problems.push(`server: ${line}`);
    }
    const patterns = allowed.get(testInfo.testId) ?? [];
    allowed.delete(testInfo.testId);
    const unexpected = problems.filter((problem) => !patterns.some((pattern) => matches(pattern, problem)));
    const unused = patterns.filter((pattern) => !problems.some((problem) => matches(pattern, problem)));
    if (problems.length > 0) await testInfo.attach('problems', { body: problems.join('\n'), contentType: 'text/plain' });
    // A test that failed already keeps its own failure; the problems are attached to it.
    if (testInfo.status !== testInfo.expectedStatus) return;
    if (unexpected.length > 0) throw new Error(`the page or the server reported ${unexpected.length} problem(s):\n${unexpected.join('\n')}`);
    if (unused.length > 0) throw new Error(`allowed problems that never came: ${unused.map(String).join(', ')}`);
  },


  /** The worker's server and folders: { url, port, root, store, datasets, output() }. */
  worker: [
    async ({}, use, workerInfo) => {
      const index = workerInfo.parallelIndex;
      const server = await serverIn(join(envPath('WEBVIEWER_WORK'), 'test-workers', String(index)), FIRST_PORT + index);
      const { url, port, root, store, datasets, output } = server;
      await use({ url, port, root, store, datasets, output });
      await server.stop();
    },
    { scope: 'worker', timeout: 180_000 },
  ],
  baseURL: async ({ worker }, use) => use(worker.url),
});

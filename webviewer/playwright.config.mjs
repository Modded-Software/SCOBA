import { isAbsolute, join } from 'node:path';
import { defineConfig } from '@playwright/test';

const env = process.env;
const ALL = env.WEBVIEWER_TEST_ALL === '1';

/** A whole number from the environment, or the default. */
function count(name, standard) {
  const raw = env[name];
  if (raw === undefined || raw === '') return standard;
  const value = Number(raw);
  if (!Number.isInteger(value) || value < 0) throw new Error(`${name} must be a whole number, got "${raw}"`);
  return value;
}

/** A folder below WEBVIEWER_WORK, which scripts/paths.sh exports (scripts/test.sh sources it). */
function workFolder(name) {
  const root = env.WEBVIEWER_WORK;
  if (!root || !isAbsolute(root)) throw new Error('WEBVIEWER_WORK is not set: run the tests through scripts/test.sh (SPEC-PATHS)');
  return join(root, name);
}

// Two projects (SPEC-VIEWER 11):
//   unit  tests/unit: no browser. The tools' own checks, page logic bundled
//         for Node (tests/unit/source.mjs), and the server's routes asked
//         directly (make viewer-test).
//   e2e   tests/e2e: the page in a browser (make viewer-test-e2e).
// Every test gets a fresh browser context: its own localStorage and URL.
// Every worker gets its own server, texture store and datasets folder
// (tests/fixtures.mjs), so no test sees another's writes. Global setup makes
// the base store's state index once (tests/global-setup.mjs).
const slow = ALL ? {} : { grepInvert: /@slow/ };

export default defineConfig({
  testDir: './tests',
  globalSetup: './tests/global-setup.mjs',
  // Short limits: a broken page fails fast instead of hanging the run.
  timeout: 20_000,
  expect: { timeout: 5_000 },
  // 0: run everything and report every failure (WEBVIEWER_TEST_MAX_FAILURES=1 stops at the first).
  maxFailures: count('WEBVIEWER_TEST_MAX_FAILURES', 0),
  // Every test in parallel with every other (scripts/test.sh pins the cores).
  fullyParallel: true,
  // With software WebGL, 6 workers starved the renderer on 16 cores (full68) and
  // 4 still did (full69). On the GPU (2026-11-25) the count is not measured yet.
  workers: count('WEBVIEWER_TEST_WORKERS', 4),
  reporter: [['list']],
  // The real folder, not the link webviewer/test-results: Playwright empties
  // its output folder at the start, and would put a real folder on the repo
  // disk in place of the link (SPEC-PATHS).
  outputDir: workFolder('test-results'),
  use: {
    // baseURL: the worker's own server (tests/fixtures.mjs).
    viewport: { width: 1100, height: 700 },
    // The full browser in its new headless mode: the headless shell has no GPU process.
    channel: 'chromium',
    launchOptions: {
      // WebGL on the machine's GPU (Intel Arc A770, run gpu7). Headless
      // Chromium has no display, so EGL falls back to software; ANGLE on
      // Vulkan (Mesa's Intel driver, scripts/test.sh VK_ICD_FILENAMES) needs
      // none. Software WebGL (SwiftShader) starved the run;
      // tests/e2e/gpu.spec.mjs fails when the page renders in software
      // (make viewer-gpu-check runs it alone).
      // --render-node-override names the GPU, as the operator's Brave does.
      // --disable-vulkan-surface: Vulkan with no window surface, so headless works.
      args: ['--use-angle=vulkan', '--use-vulkan', '--disable-vulkan-surface', '--enable-features=Vulkan,VulkanFromANGLE,DefaultANGLEVulkan', '--ignore-gpu-blocklist', '--enable-gpu', '--render-node-override=/dev/dri/renderD128'],
    },
  },
  // @slow tests (whole-catalog surveys) run only with WEBVIEWER_TEST_ALL=1 (make viewer-test-all).
  projects: [
    { name: 'unit', testDir: './tests/unit', ...slow },
    { name: 'e2e', testDir: './tests/e2e', ...slow },
  ],
});

import { defineConfig } from '@playwright/test';

// Not the default server port, so the tests run beside a started viewer.
const PORT = 4518;
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

// Every test file gets a fresh browser context: its own localStorage and URL.
// Only datasets-toast changes what others see (it rewrites a file of the test
// dataset fx and asks the server to reload it), so it runs alone, after the rest.
const SHARED = /datasets-toast\.spec\.mjs/;

export default defineConfig({
  testDir: './tests',
  // Short limits: a broken page fails fast instead of hanging the run.
  timeout: 20_000,
  expect: { timeout: 5_000 },
  // 0: run everything and report every failure (WEBVIEWER_TEST_MAX_FAILURES=1 stops at the first).
  maxFailures: count('WEBVIEWER_TEST_MAX_FAILURES', 0),
  // Test files in parallel, tests of one file in order (scripts/test.sh pins the cores).
  fullyParallel: false,
  // On 16 cores, 6 workers starved the software renderer (11 timeouts, full68),
  // 4 workers still did (3, full69); scripts/test.sh now gives 24 cores.
  workers: count('WEBVIEWER_TEST_WORKERS', 4),
  reporter: [['list']],
  outputDir: './test-results',
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    viewport: { width: 1100, height: 700 },
    launchOptions: {
      // Software WebGL, so the run does not depend on a GPU.
      args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
    },
  },
  // @slow tests (whole-catalog surveys) run only with WEBVIEWER_TEST_ALL=1 (make viewer-test-all),
  // after the rest: beside them, timing tests failed (zoom 345 ms for 250, a grid test's
  // 20 s timeout; full74).
  projects: [
    { name: 'main', testIgnore: SHARED, grepInvert: /@slow/ },
    ...(ALL ? [{ name: 'slow', testIgnore: SHARED, grep: /@slow/, dependencies: ['main'] }] : []),
    { name: 'shared', testMatch: SHARED, dependencies: ALL ? ['main', 'slow'] : ['main'] },
  ],
  webServer: {
    // Built by scripts/test.sh (src/tools/build.ts) before the run.
    command: 'node build/server.js',
    url: `http://127.0.0.1:${PORT}/api/health`,
    env: { PORT: String(PORT) },
    reuseExistingServer: false,
    timeout: 30_000,
  },
});

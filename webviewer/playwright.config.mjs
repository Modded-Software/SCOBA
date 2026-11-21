import { defineConfig } from '@playwright/test';

// Not the default server port, so the tests run beside a started viewer.
const PORT = 4518;

export default defineConfig({
  testDir: './tests',
  // Short limits: a broken page fails fast instead of hanging the run.
  timeout: 20_000,
  expect: { timeout: 5_000 },
  maxFailures: 1,
  fullyParallel: false,
  workers: 1,
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
  webServer: {
    command: 'node server.mjs',
    url: `http://127.0.0.1:${PORT}/api/health`,
    env: { PORT: String(PORT) },
    reuseExistingServer: false,
    timeout: 30_000,
  },
});

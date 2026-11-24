// A game whose data is not on the machine (R-VIEW-8, SPEC-VIEWER 7, 8;
// SPEC-VIEWER-GHOST 9 "Not available"): a second server, started with
// GHOST_PATH empty, lists Ghost as not available with the reason, answers
// its routes with 503, and SC2 still answers.
import { test, expect } from '@playwright/test';
import { spawn } from 'node:child_process';

const PORT = 4519;
const BASE = `http://127.0.0.1:${PORT}`;

test.describe.configure({ timeout: 180_000 });

let server;
let output = '';

test.beforeAll(async () => {
  server = spawn('node', ['build/server.js'], { env: { ...process.env, PORT: String(PORT), GHOST_PATH: '' }, stdio: ['ignore', 'pipe', 'pipe'] });
  server.stdout.on('data', (d) => (output += d));
  server.stderr.on('data', (d) => (output += d));
  const started = Date.now();
  for (;;) {
    if (server.exitCode !== null) throw new Error(`the server stopped (${server.exitCode}): ${output}`);
    try {
      if ((await fetch(`${BASE}/api/health`)).ok) return;
    } catch (error) {
      if (!(error instanceof TypeError)) throw error; // not listening yet
    }
    if (Date.now() - started > 150_000) throw new Error(`the server did not start: ${output}`);
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
});

test.afterAll(() => {
  if (server && server.exitCode === null) server.kill();
});

test('ghost is listed as not available, with the setting named', async () => {
  const games = await (await fetch(`${BASE}/api/games`)).json();
  expect(games.default).toBe('sc2');
  expect(games.games.find((g) => g.id === 'ghost')).toEqual({ id: 'ghost', label: 'StarCraft: Ghost', tab: 'Ghost', available: false, reason: 'GHOST_PATH is not set' });
  const health = await (await fetch(`${BASE}/api/health`)).json();
  expect(health.games).toEqual([
    { id: 'sc2', available: true },
    { id: 'ghost', available: false },
  ]);
  expect(output).toContain('ghost: not available: GHOST_PATH is not set');
});

test('its routes answer 503; the other game still answers', async () => {
  for (const route of ['/api/ghost/datasets', '/api/ghost/categories?dataset=build', '/api/ghost/records/actors?dataset=build']) {
    const res = await fetch(`${BASE}${route}`);
    expect(res.status, route).toBe(503);
    expect(await res.json()).toEqual({ error: 'game not available', game: 'ghost', reason: 'GHOST_PATH is not set' });
  }
  const sc2 = await fetch(`${BASE}/api/sc2/categories?dataset=scoba`);
  expect(sc2.status).toBe(200);
  // An unknown game is still 404, not 503.
  expect((await fetch(`${BASE}/api/nogame/datasets`)).status).toBe(404);
});

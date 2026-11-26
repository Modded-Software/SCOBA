// A game whose data is not on the machine (R-VIEW-8, SPEC-VIEWER 7, 8;
// SPEC-VIEWER-GHOST 9 "Not available"): a second server, started with
// GHOST_PATH empty, lists Ghost as not available with the reason, answers
// its routes with 503, and SC2 still answers. The second server has its own
// store and datasets folder, beside the worker's (SPEC-VIEWER 11.1).
import { test, expect, ownServer } from '../fixtures.mjs';

test.describe.configure({ mode: 'serial', timeout: 180_000 });

let server;

test.beforeAll(async ({ worker }, testInfo) => {
  server = await ownServer(worker, testInfo.parallelIndex, 'no-ghost', { GHOST_PATH: '' });
});

test.afterAll(async () => {
  if (server) await server.stop();
});

test('ghost is listed as not available, with the setting named', async () => {
  const games = await (await fetch(`${server.url}/api/games`)).json();
  expect(games.default).toBe('sc2');
  expect(games.games.find((g) => g.id === 'ghost')).toEqual({ id: 'ghost', label: 'StarCraft: Ghost', tab: 'SC:G', available: false, reason: 'GHOST_PATH is not set', textures: false });
  const health = await (await fetch(`${server.url}/api/health`)).json();
  expect(health.games).toEqual([
    { id: 'sc2', available: true },
    { id: 'ghost', available: false },
  ]);
  expect(server.output()).toContain('ghost: not available: GHOST_PATH is not set');
});

test('its routes answer 503; the other game still answers', async () => {
  for (const route of ['/api/ghost/datasets', '/api/ghost/categories?dataset=build', '/api/ghost/records/actors?dataset=build']) {
    const res = await fetch(`${server.url}${route}`);
    expect(res.status, route).toBe(503);
    expect(await res.json()).toEqual({ error: 'game not available', game: 'ghost', reason: 'GHOST_PATH is not set' });
  }
  const sc2 = await fetch(`${server.url}/api/sc2/categories?dataset=scoba`);
  expect(sc2.status).toBe(200);
  // An unknown game is still 404, not 503.
  expect((await fetch(`${server.url}/api/nogame/datasets`)).status).toBe(404);
});

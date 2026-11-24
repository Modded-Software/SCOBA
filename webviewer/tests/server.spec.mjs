import { test, expect } from '@playwright/test';
import { api } from './api.mjs';

const MARINE = 'mods\\liberty.sc2mod\\base.sc2assets\\assets\\units\\terran\\marine\\marine.m3';

test('the summary reports the model count', async ({ request }) => {
  const res = await request.get(api.summary());
  expect(res.status()).toBe(200);
  const body = await res.json();
  expect(body.models).toBeGreaterThan(1000);
});

test('search finds the marine and honours the limit', async ({ request }) => {
  const res = await request.get(api.records('models', 'q=marine.m3&limit=5'));
  expect(res.status()).toBe(200);
  const body = await res.json();
  expect(body.items.length).toBeLessThanOrEqual(5);
  expect(body.total).toBeGreaterThanOrEqual(body.items.length);
  for (const item of body.items) expect(item.toLowerCase()).toContain('marine.m3');

  const exact = await (await request.get(api.records('models', { q: 'terran\\marine\\marine.m3' }))).json();
  expect(exact.items).toContain(MARINE);
});

test('search with several words needs every word', async ({ request }) => {
  const body = await (await request.get(api.records('models', 'q=zealot+protoss&limit=200'))).json();
  expect(body.items.length).toBeGreaterThan(0);
  for (const item of body.items) {
    expect(item).toContain('zealot');
    expect(item).toContain('protoss');
  }
});

test('search with no match is empty, not an error', async ({ request }) => {
  const res = await request.get(api.records('models', 'q=no-such-model-xyzzy'));
  expect(res.status()).toBe(200);
  expect(await res.json()).toEqual({ total: 0, items: [] });
});

test('a model file is served as M3 bytes', async ({ request }) => {
  const res = await request.get(api.file(MARINE));
  expect(res.status()).toBe(200);
  const bytes = await res.body();
  expect(bytes.length).toBeGreaterThan(10_000);
  // M3 files start with the tag "MD34", stored reversed.
  expect(bytes.subarray(0, 4).toString('latin1')).toBe('43DM');
});

test('a texture is resolved from its in-model path', async ({ request }) => {
  const res = await request.get(api.asset('Assets/Textures/marine_diffuse.dds'));
  expect(res.status()).toBe(200);
  const bytes = await res.body();
  expect(bytes.subarray(0, 4).toString('latin1')).toBe('DDS ');
});

test('map Assets are listed and served from disk', async ({ request }) => {
  const path = 'map\\assets\\units\\terran\\tosh\\toshscoba.m3';
  const body = await (await request.get(api.records('models', 'q=toshscoba'))).json();
  expect(body.items).toEqual([path]);
  const res = await request.get(api.file(path));
  expect(res.status()).toBe(200);
  expect((await res.body()).subarray(0, 4).toString('latin1')).toBe('43DM');
  // A map file wins over a game file with the same in-model path.
  const viaAsset = await request.get(api.asset('Assets/Units/Terran/Tosh/ToshSCOBA.m3', 'scoba', 'model'));
  expect(viaAsset.status()).toBe(200);
  expect((await viaAsset.body()).length).toBe((await res.body()).length);
});

test('unknown and unsafe paths are refused', async ({ request }) => {
  expect((await request.get(api.file('mods\\nope\\nope.m3'))).status()).toBe(404);
  expect((await request.get(api.file('..\\..\\etc\\passwd'))).status()).toBe(404);
  expect((await request.get('/api/sc2/file?dataset=scoba')).status()).toBe(400);
  expect((await request.get(api.asset('assets/textures/nope_nope.dds'))).status()).toBe(404);
  expect((await request.get(api.asset('../../../etc/passwd'))).status()).toBe(404);
  expect((await request.get('/../server.mjs')).status()).toBe(404);
  expect((await request.get('/%2e%2e/server.mjs')).status()).toBe(404);
});

test('the page bundle is served; nothing else under its folder', async ({ request }) => {
  // index.html names one script, the bundle (src/page/main.ts).
  const page = await (await request.get('/')).text();
  const scripts = [...page.matchAll(/<script src="([^"]+)"/g)].map((m) => m[1]);
  expect(scripts).toEqual(['/vendor/renderer.js']);
  const res = await request.get('/vendor/renderer.js');
  expect(res.status()).toBe(200);
  expect(res.headers()['content-type']).toContain('text/javascript');
  expect((await res.body()).length).toBeGreaterThan(100_000);
  // Negative: the old page modules are gone; nothing else under /vendor/; no way out of it.
  for (const path of ['/js/core.js', '/js/main.js', '/vendor/nope.js', '/vendor/renderer.mjs', '/vendor/../server.mjs', '/vendor/%2e%2e/server.mjs', '/vendor/..%2Fserver.mjs', '/vendor/']) {
    expect((await request.get(path)).status(), path).toBe(404);
  }
});

test('health and games name the games; no counts', async ({ request }) => {
  // The test server has GHOST_PATH (ghost-unavailable.spec starts one without it).
  expect(await (await request.get(api.health)).json()).toEqual({
    games: [
      { id: 'sc2', available: true },
      { id: 'ghost', available: true },
    ],
  });
  const games = await (await request.get(api.games)).json();
  expect(games.default).toBe('sc2');
  expect(games.games).toEqual([expect.objectContaining({ id: 'sc2', available: true, reason: null }), expect.objectContaining({ id: 'ghost', available: true, reason: null })]);
  for (const game of games.games) {
    expect(typeof game.label).toBe('string');
    expect(typeof game.tab).toBe('string');
  }
});

test('the categories are the gallery tabs, with their filters', async ({ request }) => {
  const categories = await (await request.get(api.categories())).json();
  expect(categories.map((c) => c.id)).toEqual(['units', 'doodads', 'models']);
  const units = categories.find((c) => c.id === 'units');
  expect(units.filters.map((f) => f.id)).toEqual(expect.arrayContaining(['race', 'kind', 'family']));
  expect(units.filters.find((f) => f.id === 'race').values.map((v) => v.value)).toEqual(expect.arrayContaining(['Terran', 'Zerg']));
});

test('a route that reads a dataset needs one, and a known one', async ({ request }) => {
  for (const route of ['categories', 'summary', 'records/units', 'record/units?id=Marine', 'file?path=x', 'asset?kind=texture&ref=x', 'icon/btn-unit-terran-marine.png']) {
    expect((await request.get(`/api/sc2/${route}`)).status(), route).toBe(400);
    const sep = route.includes('?') ? '&' : '?';
    expect((await request.get(`/api/sc2/${route}${sep}dataset=nosuch`)).status(), route).toBe(404);
  }
});

test('unknown games, categories, kinds and methods are refused', async ({ request }) => {
  expect((await request.get('/api/nogame/datasets')).status()).toBe(404);
  expect((await request.get('/api/SC2/datasets')).status()).toBe(404);
  expect((await request.get('/api/GHOST/datasets')).status()).toBe(404);
  expect((await request.get(api.records('nosuch'))).status()).toBe(404);
  expect((await request.get(api.record('nosuch', 'Marine'))).status()).toBe(404);
  expect((await request.get(api.asset('Assets/Textures/marine_diffuse.dds', 'scoba', 'sound'))).status()).toBe(400);
  expect((await request.get(api.asset('Assets/Textures/marine_diffuse.dds', 'scoba', 'animation'))).status()).toBe(404);
  expect((await request.get(api.x('nosuch'))).status()).toBe(404);
  expect((await request.post(api.records('units'))).status()).toBe(405);
  expect((await request.get(api.reload('scoba'))).status()).toBe(405);
});

test('the old routes are gone', async ({ request }) => {
  const old = ['/api/units', '/api/unit?id=Marine', '/api/doodads', '/api/facets', '/api/models', '/api/skyboxes', '/api/datasets', '/api/textures', '/api/hd-textures'];
  old.push(`/file?path=${encodeURIComponent(MARINE)}`, '/asset?path=x', '/icon/btn-unit-terran-marine.png', '/hd-asset?path=x', '/textures/');
  for (const path of old) expect((await request.get(path)).status(), path).toBe(404);
  expect((await request.post('/api/dataset/reload?id=scoba')).status()).toBe(404);
});

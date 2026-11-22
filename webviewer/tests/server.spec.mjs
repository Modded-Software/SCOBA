import { test, expect } from '@playwright/test';

const MARINE = 'mods\\liberty.sc2mod\\base.sc2assets\\assets\\units\\terran\\marine\\marine.m3';

test('health reports the model count', async ({ request }) => {
  const res = await request.get('/api/health');
  expect(res.status()).toBe(200);
  const body = await res.json();
  expect(body.models).toBeGreaterThan(1000);
});

test('search finds the marine and honours the limit', async ({ request }) => {
  const res = await request.get('/api/models?q=marine.m3&limit=5');
  expect(res.status()).toBe(200);
  const body = await res.json();
  expect(body.items.length).toBeLessThanOrEqual(5);
  expect(body.total).toBeGreaterThanOrEqual(body.items.length);
  for (const item of body.items) expect(item.toLowerCase()).toContain('marine.m3');

  const exact = await (await request.get('/api/models?q=' + encodeURIComponent('terran\\marine\\marine.m3'))).json();
  expect(exact.items).toContain(MARINE);
});

test('search with several words needs every word', async ({ request }) => {
  const body = await (await request.get('/api/models?q=zealot+protoss&limit=200')).json();
  expect(body.items.length).toBeGreaterThan(0);
  for (const item of body.items) {
    expect(item).toContain('zealot');
    expect(item).toContain('protoss');
  }
});

test('search with no match is empty, not an error', async ({ request }) => {
  const res = await request.get('/api/models?q=no-such-model-xyzzy');
  expect(res.status()).toBe(200);
  expect(await res.json()).toEqual({ total: 0, items: [] });
});

test('a model file is served as M3 bytes', async ({ request }) => {
  const res = await request.get('/file?path=' + encodeURIComponent(MARINE));
  expect(res.status()).toBe(200);
  const bytes = await res.body();
  expect(bytes.length).toBeGreaterThan(10_000);
  // M3 files start with the tag "MD34", stored reversed.
  expect(bytes.subarray(0, 4).toString('latin1')).toBe('43DM');
});

test('a texture is resolved from its in-model path', async ({ request }) => {
  const res = await request.get('/asset?path=' + encodeURIComponent('Assets/Textures/marine_diffuse.dds'));
  expect(res.status()).toBe(200);
  const bytes = await res.body();
  expect(bytes.subarray(0, 4).toString('latin1')).toBe('DDS ');
});

test('map Assets are listed and served from disk', async ({ request }) => {
  const path = 'map\\assets\\units\\terran\\tosh\\toshscoba.m3';
  const body = await (await request.get('/api/models?q=toshscoba')).json();
  expect(body.items).toEqual([path]);
  const res = await request.get('/file?path=' + encodeURIComponent(path));
  expect(res.status()).toBe(200);
  expect((await res.body()).subarray(0, 4).toString('latin1')).toBe('43DM');
  // A map file wins over a game file with the same in-model path.
  const viaAsset = await request.get('/asset?path=' + encodeURIComponent('Assets/Units/Terran/Tosh/ToshSCOBA.m3'));
  expect(viaAsset.status()).toBe(200);
  expect((await viaAsset.body()).length).toBe((await res.body()).length);
});

test('unknown and unsafe paths are refused', async ({ request }) => {
  expect((await request.get('/file?path=' + encodeURIComponent('mods\\nope\\nope.m3'))).status()).toBe(404);
  expect((await request.get('/file?path=' + encodeURIComponent('..\\..\\etc\\passwd'))).status()).toBe(404);
  expect((await request.get('/file')).status()).toBe(400);
  expect((await request.get('/asset?path=' + encodeURIComponent('assets/textures/nope_nope.dds'))).status()).toBe(404);
  expect((await request.get('/asset?path=' + encodeURIComponent('../../../etc/passwd'))).status()).toBe(404);
  expect((await request.get('/../server.mjs')).status()).toBe(404);
  expect((await request.get('/%2e%2e/server.mjs')).status()).toBe(404);
});

test('every page module in public/js is served, read at request time; nothing else under /js/', async ({ request }) => {
  // Each script index.html names is served: a module added after the
  // server started is not a 404 (the drawer tabs died that way, 2026-11-22).
  const page = await (await request.get('/')).text();
  const scripts = [...page.matchAll(/<script src="(\/js\/[^"]+)"/g)].map((m) => m[1]);
  expect(scripts.length).toBeGreaterThan(10);
  for (const src of scripts) {
    const res = await request.get(src);
    expect(res.status(), src).toBe(200);
    expect(res.headers()['content-type'], src).toContain('text/javascript');
  }
  // Negative: no such module; not a module name; out of public/js.
  for (const path of ['/js/nope.js', '/js/Core.js', '/js/core.mjs', '/js/../server.mjs', '/js/%2e%2e/server.mjs', '/js/..%2Fserver.mjs', '/js/sub/core.js', '/js/.js']) {
    expect((await request.get(path)).status(), path).toBe(404);
  }
});

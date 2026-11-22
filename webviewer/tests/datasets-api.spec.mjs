import { test, expect } from '@playwright/test';

// Datasets (server-datasets.mjs): "scoba" (this repo's map over the stock
// data, the default), "stock" (the stock data alone) and the test fixture
// "fx" (scripts/test-fixture.sh: Marine at actor scale 2, with the
// Zealot's texture as its skin).

const get = async (request, url) => (await request.get(url)).json();
// The skin of the stock Marine model (marine.m3).
const MARINE_SKIN = 'Assets/Textures/marine_diffuse_blood.dds';

test('the datasets are listed, the built-in ones first; none has changed', async ({ request }) => {
  const body = await get(request, '/api/datasets');
  console.log('datasets', JSON.stringify(body));
  expect(body.default).toBe('scoba');
  expect(body.datasets.map((d) => d.id)).toEqual(['scoba', 'stock', 'fx']);
  expect(body.problems).toEqual([]);
  const [scoba, stock, fx] = body.datasets;
  expect(scoba).toMatchObject({ builtin: true, hasMap: true, changed: false });
  expect(stock).toMatchObject({ builtin: true, hasMap: false, changed: false });
  expect(fx).toMatchObject({ label: 'Test fixture', builtin: false, hasMap: true, changed: false });
  for (const d of body.datasets) {
    expect(d.units).toBeGreaterThan(500);
    expect(d.doodads).toBeGreaterThan(2000);
    expect(d.signature).toMatch(/^[0-9a-f]{40}$/);
  }
  expect((await get(request, '/api/health')).datasets).toBe(3);
});

test('a request without a dataset reads "scoba"', async ({ request }) => {
  const plain = await get(request, '/api/unit?id=Marine');
  const named = await get(request, '/api/unit?id=Marine&dataset=scoba');
  expect(plain.dataset).toBe('scoba');
  expect(plain).toEqual(named);
  expect(await get(request, '/api/units?q=marine&limit=5')).toEqual(await get(request, '/api/units?q=marine&limit=5&dataset=scoba'));
  expect(await get(request, '/api/facets')).toEqual(await get(request, '/api/facets?dataset=scoba'));
});

test('each dataset gives a unit its own data', async ({ request }) => {
  const scoba = await get(request, '/api/unit?id=Marine&dataset=scoba');
  const stock = await get(request, '/api/unit?id=Marine&dataset=stock');
  const fx = await get(request, '/api/unit?id=Marine&dataset=fx');
  console.log('marine actorScale', JSON.stringify({ scoba: scoba.actorScale, stock: stock.actorScale, fx: fx.actorScale }));
  expect(stock).toMatchObject({ dataset: 'stock', inMap: false });
  expect(fx).toMatchObject({ dataset: 'fx', actorScale: [2, 2, 2] });
  // The fixture changes the scale and nothing else of the stock record.
  expect(fx.actorScale).not.toEqual(stock.actorScale);
  expect({ ...fx, dataset: '', actorScale: null }).toEqual({ ...stock, dataset: '', actorScale: null });
  // The fixture keeps the stock model; the map swaps in the remastered one, at 1.25.
  expect(fx.file).toBe(stock.file);
  expect(stock.file).toMatch(/\\marine\\marine\.m3$/);
  expect(scoba.file).toMatch(/\\marine_remastered\\marine_remastered\.m3$/);
  expect(scoba.actorScale).toEqual([1.25, 1.25, 1.25]);
  expect(stock.actorScale).toEqual([1, 1, 1]);
});

test('negative: what only the map defines is not in the stock dataset', async ({ request }) => {
  const mine = await get(request, '/api/unit?id=ToshSCOBA&dataset=scoba');
  expect(mine).toMatchObject({ id: 'ToshSCOBA', inMap: true });
  expect(mine.file.startsWith('map\\')).toBe(true);
  expect((await request.get('/api/unit?id=ToshSCOBA&dataset=stock')).status()).toBe(404);
  expect((await request.get('/api/unit?id=ToshSCOBA&dataset=fx')).status()).toBe(404);
  const found = await get(request, '/api/units?q=toshscoba&dataset=stock');
  expect(found.items.map((i) => i.id)).not.toContain('ToshSCOBA');
  // No stock unit claims to be the map's.
  const all = await get(request, '/api/units?limit=500&dataset=stock');
  expect(all.items.some((i) => i.inMap)).toBe(false);
  // Doodads too: the map's Zerus tree is 4 to 6 times the size; the stock one is not, and is not the map's.
  const tree = await get(request, '/api/doodad?id=ZerusTree&dataset=scoba');
  const stockTree = await get(request, '/api/doodad?id=ZerusTree&dataset=stock');
  expect(tree).toMatchObject({ dataset: 'scoba', inMap: true, scaleRange: [4, 6] });
  expect(stockTree).toMatchObject({ dataset: 'stock', inMap: false });
  expect(stockTree.scaleRange).not.toEqual([4, 6]);
});

test('an in-model asset path is resolved per dataset: the map layer first, then the storage', async ({ request }) => {
  const bytes = async (dataset) => {
    const response = await request.get(`/asset?path=${encodeURIComponent(MARINE_SKIN)}&dataset=${dataset}`);
    expect(response.status(), dataset).toBe(200);
    return response.body();
  };
  const [scoba, stock, fx] = [await bytes('scoba'), await bytes('stock'), await bytes('fx')];
  expect(stock.subarray(0, 4).toString('latin1')).toBe('DDS ');
  expect(fx.subarray(0, 4).toString('latin1')).toBe('DDS ');
  // The fixture's map layer holds its own file under that name.
  expect(fx.equals(stock)).toBe(false);
  // Negative: the map has no file of that name, so "scoba" serves the stock one.
  expect(scoba.equals(stock)).toBe(true);
  // The fixture's file is the Zealot texture.
  const zealot = await (await request.get(`/asset?path=${encodeURIComponent('Assets/Textures/zealot_diffuse.dds')}&dataset=stock`)).body();
  expect(fx.equals(zealot)).toBe(true);
  // A path the fixture does not override comes from the storage.
  const other = 'Assets/Textures/zealot_diffuse.dds';
  expect((await (await request.get(`/asset?path=${encodeURIComponent(other)}&dataset=fx`)).body()).equals(zealot)).toBe(true);
});

test('icons are served per dataset', async ({ request }) => {
  const marine = await get(request, '/api/unit?id=Marine&dataset=stock');
  expect(marine.icon).toBeTruthy();
  for (const dataset of ['scoba', 'stock', 'fx']) {
    const response = await request.get(`/icon/${marine.icon}?dataset=${dataset}`);
    expect(response.status(), dataset).toBe(200);
    expect((await response.body()).subarray(1, 4).toString('latin1')).toBe('PNG');
  }
  // Negative: a name the catalog does not list is not served, whatever the dataset.
  expect((await request.get('/icon/../units.json?dataset=fx')).status()).toBe(404);
});

test('negative: an unknown dataset is refused on every route', async ({ request }) => {
  for (const url of ['/api/unit?id=Marine', '/api/units?q=marine', '/api/doodad?id=ZerusTree', '/api/doodads?q=tree', '/api/facets?x=1', `/asset?path=${encodeURIComponent(MARINE_SKIN)}`, '/icon/btn-unit-terran-marine.png?x=1']) {
    const response = await request.get(`${url}&dataset=nosuch`);
    expect(response.status(), url).toBe(404);
    expect(await response.json(), url).toMatchObject({ error: 'no such dataset', dataset: 'nosuch' });
  }
});

test('negative: a reload is a POST for a known dataset', async ({ request }) => {
  expect((await request.get('/api/dataset/reload?id=fx')).status()).toBe(405);
  expect((await request.post('/api/dataset/reload')).status()).toBe(400);
  expect((await request.post('/api/dataset/reload?id=nosuch')).status()).toBe(404);
  // Other routes still refuse a POST.
  expect((await request.post('/api/units')).status()).toBe(405);
});

import { test, expect } from '../fixtures.mjs';
import { api, facets } from '../api.mjs';

const unit = async (request, id) => (await request.get(api.record('units', id))).json();
const search = async (request, query) => (await request.get(api.records('units', query))).json();

test('the summary reports the unit catalog', async ({ request }) => {
  const body = await (await request.get(api.summary())).json();
  expect(body.units).toBeGreaterThan(500);
  expect(body.unitsWithoutModelFile).toBeGreaterThanOrEqual(0);
});

test('facets list the races and kinds that exist', async ({ request }) => {
  const body = await facets(request);
  expect(body.races).toEqual(expect.arrayContaining(['Terran', 'Protoss', 'Zerg', 'Neutral']));
  expect(body.kinds).toEqual(expect.arrayContaining(['Unit', 'Structure']));
});

test('the family facet lists Melee; family=Melee returns Melee units only; family= is the units without one', async ({ request }) => {
  expect((await facets(request)).families).toContain('Melee');
  const all = await search(request, { limit: '500' });
  const melee = await search(request, { limit: '500', family: 'Melee' });
  expect(melee.total).toBeGreaterThan(50);
  expect(melee.total).toBeLessThan(all.total);
  for (const item of melee.items) expect(item.family).toBe('Melee');
  // Negative: another family has no Melee unit; an empty family is the units without one.
  const campaign = await search(request, { limit: '500', family: 'Campaign' });
  expect(campaign.total).toBeGreaterThan(0);
  for (const item of campaign.items) expect(item.family).not.toBe('Melee');
  expect((await search(request, { limit: '500', family: '' })).items.every((u) => !u.family)).toBe(true);
});

test('search by readable name puts the exact name first', async ({ request }) => {
  const body = await search(request, 'q=marine&limit=20');
  expect(body.total).toBeGreaterThan(1);
  expect(body.items.length).toBeLessThanOrEqual(20);
  expect(body.items[0]).toMatchObject({ id: 'Marine', name: 'Marine', race: 'Terran', kind: 'Unit' });
  expect(body.items[0].icon).toBe('btn-unit-terran-marine.png');
  for (const item of body.items) expect((item.name + ' ' + item.id).toLowerCase()).toContain('marine');
});

test('search matches the unit id as well as the name', async ({ request }) => {
  // The id is VikingFighter, the name is Viking.
  const byId = await search(request, 'q=vikingfighter');
  expect(byId.items.map((i) => i.id)).toContain('VikingFighter');
  const byName = await search(request, 'q=viking');
  expect(byName.items.map((i) => i.id)).toContain('VikingFighter');
});

test('search needs every word, and race and kind filters narrow it', async ({ request }) => {
  const zerg = await search(request, 'race=Zerg&limit=500');
  expect(zerg.items.length).toBeGreaterThan(10);
  expect(zerg.items.every((i) => i.race === 'Zerg')).toBe(true);

  const structures = await search(request, 'race=Terran&kind=Structure&limit=500');
  expect(structures.items.length).toBeGreaterThan(5);
  expect(structures.items.every((i) => i.race === 'Terran' && i.kind === 'Structure')).toBe(true);
  expect(structures.items.map((i) => i.id)).toContain('Barracks');
  expect(structures.items.map((i) => i.id)).not.toContain('Marine');

  const words = await search(request, 'q=siege+tank');
  expect(words.items.length).toBeGreaterThan(0);
  for (const item of words.items) {
    const text = (item.name + ' ' + item.id).toLowerCase();
    expect(text).toContain('siege');
    expect(text).toContain('tank');
  }

  expect(await search(request, 'q=marine&race=Zerg&kind=Structure')).toMatchObject({ total: 0, items: [] });
  expect(await search(request, 'q=no-such-unit-xyzzy')).toEqual({ total: 0, items: [] });
});

test('units come in pages: offset and limit cut one ordered list', async ({ request }) => {
  const whole = await search(request, 'race=Zerg&limit=120');
  const first = await search(request, 'race=Zerg&limit=60&offset=0');
  const second = await search(request, 'race=Zerg&limit=60&offset=60');
  expect(first.total).toBe(whole.total);
  expect(second.total).toBe(whole.total);
  expect([...first.items, ...second.items].map((i) => i.id)).toEqual(whole.items.map((i) => i.id));
  // Past the end: no items, the same total. A bad offset counts as 0.
  expect(await search(request, `race=Zerg&offset=${whole.total}`)).toEqual({ total: whole.total, items: [] });
  expect((await search(request, 'race=Zerg&limit=5&offset=-7')).items).toEqual(whole.items.slice(0, 5));
  expect((await search(request, 'race=Zerg&limit=5&offset=abc')).items).toEqual(whole.items.slice(0, 5));
});

test('model files come in pages too', async ({ request }) => {
  const whole = await (await request.get(api.records('models', 'q=marine&limit=40'))).json();
  const tail = await (await request.get(api.records('models', 'q=marine&limit=20&offset=20'))).json();
  expect(tail.total).toBe(whole.total);
  expect(tail.items).toEqual(whole.items.slice(20, 40));
});

test('a unit record carries the data that changes its look', async ({ request }) => {
  const marine = await unit(request, 'Marine');
  expect(marine).toMatchObject({ id: 'Marine', name: 'Marine', race: 'Terran', actor: 'Marine', model: 'Marine' });
  expect(marine.file.toLowerCase()).toMatch(/marine[^\\]*\.m3$/);
  for (const field of ['actorScale', 'modelScaleMin', 'modelScaleMax', 'eventScale']) {
    expect(marine[field]).toHaveLength(3);
    expect(marine[field].every((v) => v > 0)).toBe(true);
  }
  expect(marine.animSpeed).toBeGreaterThan(0);
  expect(marine.speed).toBeGreaterThan(0);
  expect(marine.walkAnimMoveSpeed).toBeGreaterThan(0);
  expect(marine.height).toBe(0);
  expect(marine.portrait).toMatch(/\.png$/);

  // The model file of a unit is a real, servable M3.
  const file = await request.get(api.file(marine.file));
  expect(file.status()).toBe(200);
  expect((await file.body()).subarray(0, 4).toString('latin1')).toBe('43DM');

  // A flyer has a height. A zergling has a scale range.
  expect((await unit(request, 'Banshee')).height).toBeGreaterThan(0);
  const zergling = await unit(request, 'Zergling');
  expect(zergling.modelScaleMax[0]).toBeGreaterThan(zergling.modelScaleMin[0]);
});

test('a unit of the map itself is in the catalog', async ({ request }) => {
  const tosh = await unit(request, 'ToshSCOBA');
  expect(tosh.inMap).toBe(true);
  expect(tosh.file).toBe('map\\assets\\units\\terran\\tosh\\toshscoba.m3');
});

test('unknown units and missing ids are refused', async ({ request }) => {
  expect((await request.get(api.record('units', 'NoSuchUnitXyzzy'))).status()).toBe(404);
  expect((await request.get('/api/sc2/record/units?dataset=scoba')).status()).toBe(400);
});

test('icons are PNG files, and only catalog icons are served', async ({ request }) => {
  const res = await request.get(api.icon('btn-unit-terran-marine.png'));
  expect(res.status()).toBe(200);
  expect(res.headers()['content-type']).toBe('image/png');
  expect((await res.body()).subarray(1, 4).toString('latin1')).toBe('PNG');

  expect((await request.get(api.icon('no-such-icon.png'))).status()).toBe(404);
  expect((await request.get(api.icon('..%2Funits.json'))).status()).toBe(404);
  expect((await request.get('/api/sc2/icon/../units.json?dataset=scoba')).status()).toBe(404);
  expect((await request.get('/api/sc2/icon/?dataset=scoba')).status()).toBe(404);
});

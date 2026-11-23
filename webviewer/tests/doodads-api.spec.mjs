import { test, expect } from '@playwright/test';
import { api, facets as facetsOf } from './api.mjs';

// The doodad catalog (tools/build_doodads.py, src/games/sc2/server/doodads.ts): every
// CActorDoodad of the game data with a model file the server can serve.

const doodad = async (request, id) => (await request.get(api.record('doodads', id))).json();
const search = async (request, query) => (await request.get(api.records('doodads', query))).json();

test('the summary and the categories report the doodad catalog', async ({ request }) => {
  const health = await (await request.get(api.summary())).json();
  console.log('health', JSON.stringify(health));
  expect(health.doodads).toBeGreaterThan(2000);
  expect(health.doodadsWithoutModelFile).toBeGreaterThanOrEqual(0);
  const facets = await facetsOf(request);
  expect(facets.doodadTypes).toEqual(expect.arrayContaining(['Props', 'Environment', 'Structures', 'CliffRamps']));
  expect(facets.tilesets).toEqual(expect.arrayContaining(['Char', 'Zerus', 'Aiur']));
  // Negative: the unit facets are still there, and hold no doodad type.
  expect(facets.kinds).toEqual(expect.arrayContaining(['Unit', 'Structure']));
  expect(facets.kinds).not.toContain('CliffRamps');
});

test('a doodad record holds its name, type, terrain sets, variations and look data', async ({ request }) => {
  const tree = await doodad(request, 'ZerusTree');
  console.log('ZerusTree', JSON.stringify({ ...tree, files: tree.files.length }));
  expect(tree).toMatchObject({ id: 'ZerusTree', name: 'Zerus Tree', type: 'Environment', doodad: true, inMap: true, editorOnly: false, autoRotate: true });
  expect(tree.tilesets).toEqual(['Zerus']);
  // The map's own data wins over the stock data: scale 4 to 6, z x 1.4, a quarter speed.
  expect(tree.scaleRange).toEqual([4, 6]);
  expect(tree.actorScale).toEqual([1, 1, 1.4]);
  expect(tree.timeScale).toBe(0.25);
  // One file per variation, numbered from 00.
  expect(tree.variations).toBe(tree.files.length);
  expect(tree.variations).toBeGreaterThan(5);
  tree.files.forEach((file, i) => expect(file.toLowerCase()).toMatch(new RegExp(`zerustree_${String(i).padStart(2, '0')}\\.m3$`)));
  expect(new Set(tree.files).size).toBe(tree.files.length);
  // Every listed file is a real M3.
  for (const file of [tree.files[0], tree.files.at(-1)]) {
    const body = await (await request.get(api.file(file))).body();
    expect(body.subarray(0, 4).toString('latin1')).toBe('43DM');
  }
  // Negative: the search text is not sent, and an unknown id is not found.
  expect(tree.text).toBeUndefined();
  expect((await request.get(api.record('doodads', 'NoSuchDoodad'))).status()).toBe(404);
  expect((await request.get('/api/sc2/record/doodads?dataset=scoba')).status()).toBe(400);
});

test('a doodad that draws nothing in game is listed with its editor model', async ({ request }) => {
  const blocker = await doodad(request, 'BuildingBlocker1x1Doodad');
  expect(blocker).toMatchObject({ editorOnly: true, invisible: true, variations: 1 });
  expect(blocker.file.toLowerCase()).toMatch(/pathingblockerhelper\.m3$/);
  // Negative: an ordinary doodad is not editor only.
  expect((await doodad(request, 'AcidFalls')).editorOnly).toBe(false);
});

test('a doodad the editor does not turn has autoRotate off', async ({ request }) => {
  expect((await doodad(request, 'AiurProtossBuildings')).autoRotate).toBe(false);
  // Negative: one with no such flag is turned.
  expect((await doodad(request, 'AcidFalls')).autoRotate).toBe(true);
});

test('search by name and id; type and terrain set filters narrow it', async ({ request }) => {
  const all = await search(request, 'limit=1');
  expect(all.total).toBeGreaterThan(2000);
  expect(all.items).toHaveLength(1);

  const trees = await search(request, 'q=zerus+tree&limit=50');
  expect(trees.items[0]).toMatchObject({ id: 'ZerusTree', name: 'Zerus Tree', type: 'Environment', inMap: true });
  for (const item of trees.items) {
    const text = (item.name + ' ' + item.id).toLowerCase();
    expect(text).toContain('zerus');
    expect(text).toContain('tree');
  }

  const ramps = await search(request, 'type=CliffRamps&limit=500');
  expect(ramps.total).toBeGreaterThan(50);
  expect(ramps.items).toHaveLength(ramps.total);
  expect(ramps.items.every((i) => i.type === 'CliffRamps')).toBe(true);

  const char = await search(request, 'tileset=Char&limit=500');
  expect(char.total).toBeGreaterThan(20);
  expect(char.total).toBeLessThan(all.total);
  const ids = char.items.map((i) => i.id);
  expect(ids).toContain('BubbleAcid');
  // Negative: a doodad of another terrain set is not in it.
  expect(ids).not.toContain('ZerusTree');
  for (const id of ids.slice(0, 5)) expect((await doodad(request, id)).tilesets).toContain('Char');

  // Both filters and a word together.
  const both = await search(request, 'tileset=Char&type=CliffRamps&limit=500');
  expect(both.total).toBeGreaterThan(0);
  expect(both.total).toBeLessThan(Math.min(ramps.total, char.total));
  // Negative: nothing matches nonsense.
  expect((await search(request, 'q=zzzznothing')).total).toBe(0);
});

test('paging walks the whole list without repeats', async ({ request }) => {
  const first = await search(request, 'type=Structures&offset=0&limit=40');
  const second = await search(request, 'type=Structures&offset=40&limit=40');
  expect(first.items).toHaveLength(40);
  expect(second.items.length).toBeGreaterThan(0);
  const ids = [...first.items, ...second.items].map((i) => i.id);
  expect(new Set(ids).size).toBe(ids.length);
});

test('negative: doodads and units stay apart', async ({ request }) => {
  // A doodad id is no unit, and a unit id is no doodad.
  expect((await request.get(api.record('units', 'AcidFalls'))).status()).toBe(404);
  expect((await request.get(api.record('doodads', 'Marine'))).status()).toBe(404);
  const units = await (await request.get(api.records('units', 'q=acidfalls'))).json();
  expect(units.items.map((i) => i.id)).not.toContain('AcidFalls');
});

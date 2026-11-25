// The Ghost game on the server (SPEC-VIEWER-GHOST 5, 7, 8): the protocol
// routes over the build that GHOST_PATH names, read through NODExport.
// Needs GHOST_PATH; without it the first test fails and names the setting.
import { test, expect } from '../fixtures.mjs';

const D = 'build';
const q = (query) => new URLSearchParams({ dataset: D, ...query });
const g = {
  categories: `/api/ghost/categories?${q({})}`,
  summary: `/api/ghost/summary?${q({})}`,
  records: (category, query = {}) => `/api/ghost/records/${category}?${q(query)}`,
  record: (category, id) => `/api/ghost/record/${category}?${q({ id })}`,
  file: (path) => `/api/ghost/file?${q({ path })}`,
  asset: (kind, ref) => `/api/ghost/asset?${q({ kind, ref })}`,
};

/** The export container of a model: { json, bin }. */
function container(bytes) {
  expect(bytes.subarray(0, 4).toString('latin1')).toBe('NODX');
  expect(bytes.readUInt32LE(4)).toBe(1);
  const length = bytes.readUInt32LE(8);
  return { json: JSON.parse(bytes.subarray(12, 12 + length).toString('utf8')), bin: bytes.subarray(12 + length) };
}

test('ghost is available', async ({ request }) => {
  const games = await (await request.get('/api/games')).json();
  const ghost = games.games.find((game) => game.id === 'ghost');
  expect(ghost, 'GHOST_PATH must name the build for this spec').toBeTruthy();
  // Ghost offers no texture service (R-VIEW-100).
  expect(ghost).toEqual({ id: 'ghost', label: 'StarCraft: Ghost', tab: 'SC: G', available: true, reason: null, textures: false });
  expect(games.default).toBe('sc2');
  const health = await (await request.get('/api/health')).json();
  expect(health.games).toContainEqual({ id: 'ghost', available: true });
});

test('one dataset, two categories, the counts of the build', async ({ request }) => {
  const datasets = await (await request.get('/api/ghost/datasets')).json();
  expect(datasets.default).toBe(D);
  expect(datasets.datasets.map((d) => [d.id, d.changed])).toEqual([[D, false]]);
  const categories = await (await request.get(g.categories)).json();
  expect(categories.map((c) => [c.id, c.noun, c.addAll, c.rows])).toEqual([
    ['actors', 'actor', true, 'records'],
    ['models', 'model', false, 'records'],
  ]);
  const summary = await (await request.get(g.summary)).json();
  // 818 templates name a model that is in 3D/Models (757 exact, 49 by case, 12 with .nod added: 4.6).
  expect(summary.actors).toBe(818);
  expect(summary.models).toBe(1401);
  expect(summary.refused).toContainEqual(expect.objectContaining({ name: 'scourge_track' }));
  expect(summary.leftOut.filter((l) => /is not in 3D\/Models/.test(l.reason)).length).toBe(40);
});

test('filters and search', async ({ request }) => {
  const all = await (await request.get(g.records('models', { limit: '1' }))).json();
  const skinned = await (await request.get(g.records('models', { skin: 'skinned', limit: '1' }))).json();
  const rigid = await (await request.get(g.records('models', { skin: 'rigid', limit: '1' }))).json();
  expect([all.total, skinned.total, rigid.total]).toEqual([1401, 162, 1239]);
  const withSet = await (await request.get(g.records('actors', { motion: 'with', limit: '1' }))).json();
  const without = await (await request.get(g.records('actors', { motion: 'without', limit: '1' }))).json();
  expect(withSet.total + without.total).toBe(818);
  expect(withSet.total).toBeGreaterThan(300);
  const zerg = await (await request.get(g.records('actors', { q: 'zergling.nod', limit: '500' }))).json();
  expect(zerg.items.map((r) => r.id)).toEqual(expect.arrayContaining(['zerg_critter', 'zergling_burrowed']));
  for (const row of zerg.items) expect(Object.keys(row).sort()).toEqual(['icon', 'id', 'name', 'notPlaceableAs', 'placeable', 'sub']);
  const none = await (await request.get(g.records('actors', { q: 'no-such-actor-xyzzy' }))).json();
  expect(none).toEqual({ total: 0, items: [] });
});

test('two actors share one model and differ in motions', async ({ request }) => {
  const critter = await (await request.get(g.record('actors', 'zerg_critter'))).json();
  const burrowed = await (await request.get(g.record('actors', 'zergling_burrowed'))).json();
  expect([critter.file, burrowed.file]).toEqual(['3D/Models/zergling.nod', '3D/Models/zergling.nod']);
  expect(critter.motionSet).toBe('zergling.nms');
  expect(burrowed.motionSet).toBe('zergling_burrow.nms');
  expect(critter.motions.map((m) => m.name)).toContain('stand');
  expect(critter.motions.map((m) => m.name)).not.toEqual(burrowed.motions.map((m) => m.name));
  expect(critter.dataset).toBe(D);
  // Every clip of a motion is a file of 3D/Anims, by its name on disk.
  for (const motion of critter.motions) expect(motion.clip).toMatch(/\.nad$/i);
});

test('a model is served as its export container', async ({ request }) => {
  const res = await request.get(g.file('3D/Models/crate.nod'));
  expect(res.status()).toBe(200);
  const { json, bin } = container(await res.body());
  expect(json.model.groups.length).toBe(1);
  expect(bin.length).toBe(json.model.vertexCount * json.model.vertexStride + json.model.indexCount * 4);
  const crate = json.materials.find((m) => m.name === 'chestCrate2');
  expect(crate.step).toBe('texture');
  // The texture file the materials export names is served as a DDS file.
  const texture = await request.get(g.asset('texture', crate.textures.texture));
  expect(texture.status()).toBe(200);
  expect((await texture.body()).subarray(0, 4).toString('latin1')).toBe('DDS ');
  // The name is found without regard to case.
  const upper = await request.get(g.file('3D/MODELS/CRATE.NOD'));
  expect(upper.status()).toBe(200);
});

test('clips and materials are served as JSON', async ({ request }) => {
  const clip = await request.get(g.asset('animation', 'zergling_stand'));
  expect(clip.status()).toBe(200);
  const body = JSON.parse((await clip.body()).toString('utf8'));
  expect([body.length, body.tracks.length]).toEqual([59, 40]);
  const material = JSON.parse((await (await request.get(g.asset('material', 'collide'))).body()).toString('utf8'));
  expect(material).toEqual(expect.objectContaining({ name: 'collide', step: 'none' }));
});

test('unknown, unsafe and wrong-kind requests are refused', async ({ request }) => {
  expect((await request.get(g.file('3D/Models/no-such-model.nod'))).status()).toBe(404);
  expect((await request.get(g.file('3D/Anims/zergling_stand.nad'))).status()).toBe(404);
  expect((await request.get(g.file('../../etc/passwd'))).status()).toBe(404);
  expect((await request.get(g.asset('texture', '../../etc/passwd'))).status()).toBe(404);
  expect((await request.get(g.asset('texture', '3D/Models/crate.nod'))).status()).toBe(404);
  expect((await request.get(g.asset('animation', 'no-such-clip'))).status()).toBe(404);
  expect((await request.get(g.asset('model', 'crate.nod'))).status()).toBe(404);
  expect((await request.get(g.asset('material', 'a\nb'))).status()).toBe(400);
  expect((await request.get(g.record('actors', 'no-such-actor'))).status()).toBe(404);
  expect((await request.get(g.records('nope'))).status()).toBe(404);
  expect((await request.get('/api/ghost/records/actors?dataset=scoba')).status()).toBe(404);
  const backdrops = await (await request.get('/api/ghost/backdrops')).json();
  expect(backdrops).toEqual({ total: 0, items: [] });
});

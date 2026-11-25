import { allowErrors, test, expect } from '../fixtures.mjs';
import { api } from '../api.mjs';

// A sample across the whole doodad catalog (every 29th doodad by default):
// each one must load. What a model holds but the renderer does not draw is
// recorded, so the report can name it.

// DOODAD_SURVEY_STRIDE=7 samples 365 doodads (six minutes); 1 loads them all.
const STRIDE = Number(process.env.DOODAD_SURVEY_STRIDE || 29);
const BATCH = 24;

test('every sampled doodad loads; none is rejected', async ({ page, request }) => {
  // Materials the m3 renderer does not draw (terrain, lens flare): reported, by design.
  allowErrors(/^console\.warning: sc2viewer: .*: not drawn: .*material type (4 \(terrain\)|11 \(lens flare\))/);
  test.setTimeout(600_000);
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto('/');
  await expect.poll(() => errors.join(' | ') || page.evaluate(() => Boolean(window.sc2viewer && window.sc2viewer.ready)), { timeout: 20_000 }).toBe(true);

  const all = [];
  for (let offset = 0; ; offset += 500) {
    const part = await (await request.get(api.records('doodads', { offset: String(offset), limit: '500' }))).json();
    all.push(...part.items);
    if (all.length >= part.total || part.items.length === 0) break;
  }
  const sample = all.filter((_, i) => i % STRIDE === 0);
  expect(sample.length).toBe(Math.ceil(all.length / STRIDE));
  expect(sample.length).toBeGreaterThan(80);
  expect(new Set(sample.map((d) => d.type)).size).toBeGreaterThan(5);

  const failed = [];
  const empty = [];
  const undrawn = [];
  let loaded = 0;
  for (let start = 0; start < sample.length; start += BATCH) {
    const ids = sample.slice(start, start + BATCH).map((d) => d.id);
    const result = await page.evaluate(async (ids) => {
      const failed = [];
      await Promise.all(ids.map((id, i) => window.sc2viewer.addDoodad(id, { x: i * 40, y: 0, rot: 0 }).catch((error) => failed.push(`${id}: ${error.message}`))));
      const items = window.sc2viewer.state().items.map((i) => ({ id: i.doodad, loaded: i.loaded, drawn: i.drawn, vertexCount: i.vertexCount, undrawn: i.undrawn }));
      window.sc2viewer.clear();
      return { failed, items };
    }, ids);
    failed.push(...result.failed);
    for (const item of result.items) {
      if (item.loaded) loaded++;
      else empty.push(`${item.id} (vertices ${item.vertexCount})`);
      if (item.undrawn.length) undrawn.push(`${item.id}: ${item.undrawn.join('; ')}`);
    }
    // Negative: clear leaves nothing behind for the next batch.
    expect((await page.evaluate(() => window.sc2viewer.state())).items).toEqual([]);
  }
  console.log('survey', JSON.stringify({ catalog: all.length, sampled: sample.length, loaded, failed: failed.length, noGeometry: empty.length, withUndrawnParts: undrawn.length }));
  console.log('failed', JSON.stringify(failed));
  console.log('noGeometry', JSON.stringify(empty));
  console.log('undrawn', JSON.stringify(undrawn.slice(0, 40)));
  expect(failed).toEqual([]);
  expect(errors).toEqual([]);
  // Most doodads are plain meshes: geometry must be there for nearly all.
  expect(loaded).toBeGreaterThan(sample.length * 0.8);
});

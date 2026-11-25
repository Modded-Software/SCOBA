import { allowErrors, test, expect } from '../fixtures.mjs';
import { frames, idle, open, state } from '../page.mjs';

// Real models load with no problem at all: no page error, no console
// error, no "viewer:" report, no failed request, no server error line
// (SPEC-VIEWER 11; the page fixture asserts it). The set holds the units
// whose textures and owners failed on the dev service (2026-11-25:
// Snowbeast textures, YetiPlaceholder, WarPig), common units of each race,
// a doodad, and a unit of the stock dataset.

const UNITS = [
  ['YetiPlaceholder', 'scoba'],
  ['GiantYeti', 'scoba'],
  ['WarPig', 'scoba'],
  ['Marine', 'scoba'],
  ['Zealot', 'scoba'],
  ['Zergling', 'scoba'],
  ['Thor', 'scoba'],
  ['Marine', 'stock'],
];
const DOODADS = [['ZerusTree', 'scoba']];

test('real units and a doodad load, are drawn, and nothing reports a problem', async ({ page }) => {
  test.setTimeout(90_000);
  await open(page);
  const ids = [];
  for (const [i, [unit, dataset]] of UNITS.entries()) {
    ids.push(await page.evaluate(([u, x, d]) => window.sc2viewer.addUnit(u, { x, y: 0, pick: 0.5, dataset: d }), [unit, i * 6, dataset]));
  }
  for (const [doodad, dataset] of DOODADS) {
    ids.push(await page.evaluate(([d, s]) => window.sc2viewer.addDoodad(d, { x: 0, y: 12, pick: 0.5, dataset: s }), [doodad, dataset]));
  }
  await idle(page, 60_000);
  await frames(page);
  const items = (await state(page)).items;
  // Every one is in the scene, once.
  expect(items.map((item) => item.id).sort()).toEqual([...ids].sort());
  // Negative: none is missing, none was added twice.
  expect(new Set(ids).size).toBe(UNITS.length + DOODADS.length);
});

// Negative: the watch sees a failing texture route. The textures of a Marine
// are answered 500 here (as the stale dev service answered them); the
// allowance must be used, or the fixture fails this test.
test('the page fixture records a texture request answered 500, and the viewer report of it', async ({ page }) => {
  await page.route('**/api/sc2/asset?**', (route) => route.fulfill({ status: 500, contentType: 'application/json', body: '{"error":"forced"}' }));
  allowErrors(/^http 500 GET .*\/api\/sc2\/asset\?/, /^console\.\w+: viewer: /, /^console\.error: Failed to load resource/);
  await open(page);
  await page.evaluate(() => window.sc2viewer.addUnit('Marine', { x: 0, y: 0, pick: 0.5 }));
  await idle(page);
});

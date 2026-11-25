import { test, expect } from '../fixtures.mjs';

// Models past 65536 vertices (operator 2026-11-21: Valerian's space station
// "has super broken geometry"). Element indices are a region's local index
// plus its first vertex; 16-bit indices wrapped past 65535 and joined far
// vertices. Ref model.ts: 32-bit indices (OES_element_index_uint) then.
// SpaceStationValerian: 200005 vertices, 6 of 8 regions past 65535
// (scripts/m3-regions.sh SJSpaceStationValerian).

async function open(page) {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push(m.text());
  });
  await page.goto('/');
  await page.waitForFunction(() => window.sc2viewer && window.sc2viewer.ready);
  return errors;
}

async function added(page, id) {
  await page.evaluate((u) => window.sc2viewer.addUnit(u, { x: 0, y: 0 }), id);
  await page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 60_000 });
  // `drawn` is the scene's list of instances drawn in the last frame: let two frames run.
  await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))));
  const item = (await page.evaluate(() => window.sc2viewer.state())).items.at(-1);
  console.log(`${id}: vertices ${item.vertexCount}, element bytes ${item.elementBytes}, largest index ${item.elementMax}`);
  return item;
}

test('Valerian space station: 32-bit indices reach every vertex, none wrapped', async ({ page }) => {
  const errors = await open(page);
  const item = await added(page, 'SJSpaceStationValerian');
  expect(item.loaded).toBe(true);
  expect(item.vertexCount).toBe(200005);
  expect(item.elementBytes).toBe(4);
  // The last vertex is indexed: with 16 bits the largest index was at most 65535.
  expect(item.elementMax).toBe(item.vertexCount - 1);
  expect(item.drawn).toBe(true);
  expect(errors).toEqual([]);
});

test('negative: a model under 65536 vertices keeps 16-bit indices', async ({ page }) => {
  const errors = await open(page);
  const item = await added(page, 'Marine');
  expect(item.vertexCount).toBeLessThan(65536);
  expect(item.elementBytes).toBe(2);
  expect(item.elementMax).toBe(item.vertexCount - 1);
  expect(errors).toEqual([]);
});

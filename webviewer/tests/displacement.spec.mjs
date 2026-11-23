import { test, expect } from '@playwright/test';

// Displacement materials (DIS_): drawn after the scene, over a copy of the
// frame, shifted along their normal maps (src/formats/m3/displacement.ts,
// M3ModelInstance.renderDisplacement). Survey: scripts/displacement-survey.sh.

const VIEW = { yaw: -Math.PI / 2, pitch: 0.35, distance: 7, target: [0, 0, 1.2] };

async function open(page) {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => {
    if (m.text().startsWith('viewer:') || m.type() === 'error') errors.push(m.text());
  });
  await page.goto('/');
  await expect.poll(() => errors.join(' | ') || page.evaluate(() => Boolean(window.sc2viewer && window.sc2viewer.ready)), { timeout: 10_000 }).toBe(true);
  return errors;
}

async function place(page, id) {
  await page.evaluate((u) => window.sc2viewer.addUnit(u, { x: 0, y: 0, pick: 0.5 }), id);
  await page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 20_000 });
  await page.evaluate((v) => window.sc2viewer.view(v), VIEW);
  return page.evaluate(() => window.sc2viewer.state());
}

/** Pixels that change when displacement is switched on, the frame held still. */
async function displacementChange(page) {
  return page.evaluate(() => {
    const v = window.sc2viewer;
    v.setDisplacement(false);
    v.mark();
    v.setDisplacement(true);
    const change = v.changedSinceMark();
    return { ...change, drawn: v.state().displacedBatches };
  });
}

test('A.R.E.S.: its displacement batches are drawn, not reported as undrawn', async ({ page }) => {
  const errors = await open(page);
  const s = await place(page, 'Warbot');
  const item = s.items[0];
  console.log('Warbot undrawn', JSON.stringify(item.undrawn), 'displacement', item.displacementBatches);
  expect(item.loaded).toBe(true);
  expect(item.displacementBatches).toBe(2);
  expect(item.undrawn.filter((u) => /displacement/.test(u))).toEqual([]);
  const change = await displacementChange(page);
  console.log('Warbot change', JSON.stringify(change));
  expect(change.drawn).toBe(2);
  // Its strength factor is 0 at rest (survey): drawn, but nothing shifts.
  expect(change.changed).toBeLessThan(50);
  expect(errors).toEqual([]);
});

test('Archon: the distortion bends the picture behind it; switched off, it does not', async ({ page }) => {
  const errors = await open(page);
  const s = await place(page, 'Archon');
  const item = s.items[0];
  expect(item.displacementBatches).toBeGreaterThan(0);
  expect(item.undrawn.filter((u) => /displacement/.test(u))).toEqual([]);
  const change = await displacementChange(page);
  console.log('Archon', item.sequenceName, 'change', JSON.stringify(change));
  expect(change.drawn).toBe(item.displacementBatches);
  expect(change.changed).toBeGreaterThan(200);
  expect(errors).toEqual([]);
});

test('negative: a model without displacement draws none and its frame is unchanged by the switch', async ({ page }) => {
  const errors = await open(page);
  const s = await place(page, 'Marine');
  expect(s.items[0].displacementBatches).toBe(0);
  const change = await displacementChange(page);
  expect(change.drawn).toBe(0);
  expect(change.changed).toBe(0);
  expect(errors).toEqual([]);
});

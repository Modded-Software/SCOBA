import { test, expect } from '../fixtures.mjs';
import { idle, open } from '../page.mjs';

// The ground grid at any zoom (operator 2026-11-21: "the visible part of the
// grid scales with the world"). src/page/core/render/ground.ts: the quad grows
// with the camera distance, and every unit gets a glow spot. How the lines
// and levels look is an operator check (SPEC-VIEWER 14); this test reads what
// the ground draws with: the quad's size and the spots it was given.

/** The ground quad's half size as last drawn, with the camera at `distance`. */
const radiusAt = (page, distance) =>
  page.evaluate(async (d) => {
    window.SC2App.view({ target: [0, 0, 0], yaw: -Math.PI / 2, pitch: 0.9, distance: d });
    await new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)));
    return window.SC2App.ground.drawnRadius;
  }, distance);

test('the ground quad grows with the camera distance', async ({ page }) => {
  const errors = await open(page);
  let last = 0;
  for (const distance of [9, 60, 400, 2000]) {
    const radius = await radiusAt(page, distance);
    console.log(`distance ${distance}: quad ${radius}`);
    expect(radius, `distance ${distance}`).toBeGreaterThanOrEqual(8 * distance);
    expect(radius).toBeGreaterThanOrEqual(last);
    last = radius;
  }
  expect(errors).toEqual([]);
});

test('every unit gets a ground spot, past the old 31-unit cap', async ({ page }) => {
  const errors = await open(page);
  const max = await page.evaluate(() => window.SC2App.ground.maxSpots);
  console.log(`spots the shader holds: ${max}`);
  expect(max).toBeGreaterThanOrEqual(64);
  // 48 units in a row along y = 0, 4 apart.
  const N = 48;
  for (let i = 0; i < N; i++) await page.evaluate((x) => window.sc2viewer.addUnit('Marine', { x, y: 0, pick: 0.5 }), i * 4);
  await idle(page, 60_000);
  await expect.poll(() => page.evaluate(() => window.SC2App.ground.spotsDrawn)).toBe(N);
  expect(errors).toEqual([]);
});

test('negative: with no unit the ground draws no spot', async ({ page }) => {
  const errors = await open(page);
  await radiusAt(page, 20);
  expect(await page.evaluate(() => window.SC2App.ground.spotsDrawn)).toBe(0);
  expect(errors).toEqual([]);
});

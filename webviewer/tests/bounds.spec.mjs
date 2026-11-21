import { test, expect } from '@playwright/test';

// Culling bounds: a unit stays drawn while any part of it is in view, even
// when its origin is off screen. Bounds come from the M3 file (header and
// sequence boxes) and the rest-pose vertices.

async function open(page) {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto('/');
  await expect.poll(() => errors.join(' | ') || page.evaluate(() => Boolean(window.sc2viewer && window.sc2viewer.ready)), { timeout: 10_000 }).toBe(true);
}

const state = (page) => page.evaluate(() => window.sc2viewer.state());
const pixels = (page) => page.evaluate(() => window.sc2viewer.pixels());
const idle = (page) => expect.poll(() => page.evaluate(() => window.sc2viewer.idle()), { timeout: 15_000 }).toBe(true);

const DISTANCE = 10;
const FOV = Math.PI / 4;

/**
 * Look along +y at height z, with the camera target `offset` world units
 * right of where the origin would be at the left edge of the view. Pitch 0,
 * so the left edge at y = 0 is a vertical line at x = target - halfWidth.
 */
async function lookPastLeftEdge(page, offset, z) {
  const aspect = (await state(page)).camera.aspect;
  const halfWidth = DISTANCE * Math.tan(FOV / 2) * aspect;
  await page.evaluate(([x, z, d]) => window.sc2viewer.view({ yaw: -Math.PI / 2, pitch: 0, distance: d, target: [x, 0, z] }), [halfWidth + offset, z, DISTANCE]);
  return halfWidth;
}

async function setup(page) {
  await open(page);
  await page.evaluate(() => window.sc2viewer.setGrid(false));
  await page.evaluate(() => window.sc2viewer.addUnit('Thor', { x: 0, y: 0, rot: 0, pick: 0.5 }));
  await idle(page);
  const item = (await state(page)).items[0];
  expect(item.loaded).toBe(true);
  return item;
}

test('a model has bounds: the sphere is not a point', async ({ page }) => {
  const item = await setup(page);
  console.log('Thor bounds radius', item.boundsRadius, 'data scale', JSON.stringify(item.dataScale));
  expect(item.boundsRadius).toBeGreaterThan(1);
  expect(item.boundsRadius).toBeLessThan(20);
});

test('a unit whose origin is just off screen is still drawn', async ({ page }) => {
  const item = await setup(page);
  // The origin is 0.5 units left of the view; the Thor reaches further right.
  await lookPastLeftEdge(page, 0.5, 1.5);
  const p = await pixels(page);
  const s = (await state(page)).items[0];
  console.log('origin off screen: covered', p.covered, 'minX', p.minX, 'drawn', s.drawn);
  expect(s.drawn).toBe(true);
  expect(p.covered).toBeGreaterThan(200);
  // What is drawn sits at the left edge, where the unit enters the view.
  expect(p.minX).toBeLessThan(5);
});

test('negative: a unit wholly out of view is culled and not drawn', async ({ page }) => {
  const item = await setup(page);
  const scale = Math.max(...item.dataScale);
  // Past the left frustum plane by more than the whole sphere. The plane is
  // slanted by half the horizontal field of view, so the distance from the
  // origin to it is the offset along x times the cosine of that angle.
  const halfAngle = Math.atan(Math.tan(FOV / 2) * (await state(page)).camera.aspect);
  await lookPastLeftEdge(page, (item.boundsRadius * scale + 1) / Math.cos(halfAngle), 1.5);
  const p = await pixels(page);
  const s = (await state(page)).items[0];
  console.log('wholly out: covered', p.covered, 'drawn', s.drawn);
  expect(s.drawn).toBe(false);
  expect(p.covered).toBe(0);
});

import { test, expect } from '../fixtures.mjs';

// The hovered unit is the centre of a press (R-VIEW-149, features/controls):
// a middle drag orbits around its centre, a left drag holds the plane
// through it; off any unit, the ground point is used.

const VIEW = { yaw: -Math.PI / 2, pitch: 0.5, distance: 9, target: [0, 0, 0.8] };

async function setUp(page) {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto('/');
  await expect.poll(() => errors.join(' | ') || page.evaluate(() => Boolean(window.scobaeditor && window.scobaeditor.ready)), { timeout: 10_000 }).toBe(true);
  const id = await page.evaluate(() => window.scobaeditor.addUnit('Marine', { x: 2, y: 0, pick: 0.5 }));
  await page.waitForFunction(() => window.scobaeditor.idle(), null, { timeout: 15_000 });
  await page.evaluate((v) => window.scobaeditor.view(v), VIEW);
  return id;
}

const hovered = (page) => page.evaluate(() => window.scobaeditor.pickState().hovered);
const lastPress = (page) => page.evaluate(() => window.scobaeditor.lastPress());
const screenOf = (page, p) => page.evaluate((q) => window.scobaeditor.screenOf(q), p);

async function hoverUnit(page, id) {
  const at = (await page.evaluate((i) => window.scobaeditor.itemPixel(i), id)).map(Math.round);
  await page.mouse.move(at[0], at[1]);
  await expect.poll(() => hovered(page)).toBe(id);
  return at;
}

async function drag(page, button, from, by) {
  await page.mouse.down({ button });
  await page.mouse.move(from[0] + by[0], from[1] + by[1], { steps: 4 });
  await page.mouse.up({ button });
}

test('middle drag on a hovered unit orbits around its centre; the centre keeps its pixel', async ({ page }) => {
  const id = await setUp(page);
  const at = await hoverUnit(page, id);
  const c0 = (await page.evaluate(() => window.scobaeditor.state())).camera;
  await page.mouse.down({ button: 'middle' });
  const press = await lastPress(page);
  const before = await screenOf(page, press.pivot);
  await page.mouse.move(at[0] + 80, at[1] - 30, { steps: 4 });
  await page.mouse.up({ button: 'middle' });
  const after = await screenOf(page, press.pivot);
  const c1 = (await page.evaluate(() => window.scobaeditor.state())).camera;
  console.log('press', JSON.stringify(press), 'pivot pixel', before, '->', after, 'yaw', c0.yaw, '->', c1.yaw);
  expect(press.mode).toBe('orbit');
  expect(press.unit).toBe(id);
  // The unit's centre: the middle of its rest-pose vertex box, not of its culling sphere.
  const item = (await page.evaluate(() => window.scobaeditor.state())).items.find((i) => i.id === id);
  const [lo, hi] = item.vertexBox;
  const boxMiddle = item.location[2] + ((lo[2] + hi[2]) / 2) * item.engineScale[2];
  console.log('box middle z', boxMiddle, 'bounds radius', item.boundsRadius);
  expect(Math.hypot(press.pivot[0] - 2, press.pivot[1])).toBeLessThan(0.5);
  expect(press.pivot[2]).toBeCloseTo(boxMiddle, 3);
  expect(press.pivot[2]).toBeGreaterThan(0.1);
  // Negative: not the half height of the culling sphere (the old centre, above a Marine's head).
  expect(press.pivot[2]).toBeLessThan(item.boundsRadius / 2);
  expect(Math.hypot(after[0] - before[0], after[1] - before[1])).toBeLessThan(1.5);
  expect(Math.abs(c1.yaw - c0.yaw)).toBeGreaterThan(0.05);
});

test('left drag on a hovered unit centres on it too', async ({ page }) => {
  const id = await setUp(page);
  const at = await hoverUnit(page, id);
  await drag(page, 'left', at, [60, 10]);
  expect(await lastPress(page)).toMatchObject({ mode: 'grab', unit: id });
});

test('negative: a middle drag off any unit orbits around the ground point, not a unit', async ({ page }) => {
  await setUp(page);
  const box = await page.locator('canvas#view').boundingBox();
  const at = [Math.round(box.x + box.width * 0.3), Math.round(box.y + box.height * 0.75)];
  await page.mouse.move(at[0], at[1]);
  await expect.poll(() => hovered(page)).toBe(null);
  await drag(page, 'middle', at, [80, -30]);
  const press = await lastPress(page);
  expect(press.unit).toBe(null);
  expect(press.pivot[2]).toBe(0);
});

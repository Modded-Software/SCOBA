import { test, expect } from '@playwright/test';

// The camera (target, yaw, pitch, distance) is kept in localStorage, so a
// reload shows the same view (public/js/core.js).

const KEY = 'sc2viewer.camera';
const DEFAULT = { yaw: -Math.PI / 2, pitch: 0.5, distance: 9, target: [0, 0, 0.8] };

async function open(page) {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto('/');
  await expect.poll(() => errors.join(' | ') || page.evaluate(() => Boolean(window.sc2viewer && window.sc2viewer.ready)), { timeout: 10_000 }).toBe(true);
  return errors;
}

const camera = async (page) => (await page.evaluate(() => window.sc2viewer.state())).camera;

function expectView(got, want) {
  expect(got.yaw).toBeCloseTo(want.yaw, 6);
  expect(got.pitch).toBeCloseTo(want.pitch, 6);
  expect(got.distance).toBeCloseTo(want.distance, 6);
  for (let i = 0; i < 3; i++) expect(got.target[i]).toBeCloseTo(want.target[i], 6);
}

test('negative: with nothing stored the camera starts at its default view', async ({ page }) => {
  const errors = await open(page);
  expectView(await camera(page), DEFAULT);
  expect(errors).toEqual([]);
});

test('a view set by the page is back after a reload', async ({ page }) => {
  const errors = await open(page);
  const view = { yaw: 0.7, pitch: 0.9, distance: 31, target: [12, -5, 0] };
  await page.evaluate((v) => window.sc2viewer.view(v), view);
  expectView(JSON.parse(await page.evaluate((k) => localStorage.getItem(k), KEY)), view);
  await page.reload();
  await expect.poll(() => page.evaluate(() => Boolean(window.sc2viewer && window.sc2viewer.ready))).toBe(true);
  expectView(await camera(page), view);
  expect(errors).toEqual([]);
});

test('a view reached with the mouse (orbit, then wheel zoom) is back after a reload', async ({ page }) => {
  await open(page);
  const box = await page.locator('canvas#view').boundingBox();
  await page.mouse.move(box.x + 800, box.y + 400);
  await page.mouse.down({ button: 'middle' });
  await page.mouse.move(box.x + 900, box.y + 340, { steps: 6 });
  await page.mouse.up({ button: 'middle' });
  await page.mouse.wheel(0, 300);
  await page.waitForFunction(() => window.SC2App.zoomGoal() === null);
  const before = await camera(page);
  // It did move.
  expect(Math.abs(before.yaw - DEFAULT.yaw)).toBeGreaterThan(0.1);
  expect(before.distance).toBeGreaterThan(DEFAULT.distance * 1.1);
  await page.reload();
  await expect.poll(() => page.evaluate(() => Boolean(window.sc2viewer && window.sc2viewer.ready))).toBe(true);
  expectView(await camera(page), before);
});

test('negative: a stored view that is not a camera is refused, reported and replaced', async ({ page }) => {
  await open(page);
  for (const bad of ['not json', JSON.stringify({ yaw: 1, pitch: 0.5, distance: -3, target: [0, 0, 0] }), JSON.stringify({ yaw: 'x', pitch: 0.5, distance: 9, target: [0, 0] })]) {
    await page.evaluate(([k, v]) => localStorage.setItem(k, v), [KEY, bad]);
    await page.reload();
    await expect.poll(() => page.evaluate(() => Boolean(window.sc2viewer && window.sc2viewer.ready))).toBe(true);
    expectView(await camera(page), DEFAULT);
    expect(await page.evaluate(() => window.SC2App.cameraRestore)).toMatch(/^refused: /);
    // The bad value is gone: the default view took its place.
    expectView(JSON.parse(await page.evaluate((k) => localStorage.getItem(k), KEY)), DEFAULT);
  }
});

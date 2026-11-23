import { test, expect } from '@playwright/test';
import { api } from './api.mjs';

// Landmarks the user makes and keeps (src/page/features/landmarks):
// - the pin button saves the current view as a landmark, after asking a name;
// - each landmark of the drop-down list has a trash button, which asks
//   before it deletes; "origin" has none;
// - landmarks, the one chosen, the grid toggle and the sky are kept in
//   localStorage, and the camera comes back exactly (core/camera.ts, features/sky).

async function open(page) {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push(m.text());
  });
  await page.goto('/');
  await expect.poll(() => errors.join(' | ') || page.evaluate(() => Boolean(window.sc2viewer && window.sc2viewer.ready)), { timeout: 20_000 }).toBe(true);
  return errors;
}

async function reload(page) {
  await page.reload();
  await expect.poll(() => page.evaluate(() => Boolean(window.sc2viewer && window.sc2viewer.ready)), { timeout: 20_000 }).toBe(true);
}

const state = (page) => page.evaluate(() => window.sc2viewer.state());
const camera = async (page) => (await state(page)).camera;
const marks = (page) => page.evaluate(() => window.SC2App.landmarkState());
const names = async (page) => (await marks(page)).list.map((l) => l.name);
const view = (page, v) => page.evaluate((x) => window.sc2viewer.view(x), v);
const row = (page, name) => page.locator('#landmarks-list li', { has: page.locator('.go', { hasText: name }) });

/** Pin the current view under `name`. */
async function pin(page, name) {
  await page.click('#landmark-pin');
  await expect(page.locator('#landmark-name-dialog')).toBeVisible();
  await page.fill('#landmark-name', name);
  await page.click('#landmark-save');
  await expect(page.locator('#landmark-name-dialog')).toBeHidden();
}

test('the pin button saves the current view as a named landmark; the list goes to it', async ({ page }) => {
  const errors = await open(page);
  const there = { yaw: 0.6, pitch: 0.8, distance: 22, target: [7, -4, 0] };
  await view(page, there);
  await page.click('#landmark-pin');
  // The dialog offers a name; cancel adds nothing.
  await expect(page.locator('#landmark-name')).toHaveValue('landmark 1');
  await page.click('#landmark-cancel');
  expect(await names(page)).toEqual(['origin (0, 0, 0)']);
  // Negative: an empty name cannot be saved.
  await page.click('#landmark-pin');
  await page.fill('#landmark-name', '   ');
  await expect(page.locator('#landmark-save')).toBeDisabled();
  await page.fill('#landmark-name', 'my base');
  await page.keyboard.press('Enter');
  await expect(page.locator('#landmark-name-dialog')).toBeHidden();
  let s = await marks(page);
  expect(s.list.map((l) => l.name)).toEqual(['origin (0, 0, 0)', 'my base']);
  expect(s.list[1]).toMatchObject(there);
  expect(s.selected).toBe(s.list[1].id);
  await expect(page.locator('#landmarks-button')).toHaveText('my base');

  // The list: closed at first; a row click goes there and closes it.
  await expect(page.locator('#landmarks-list')).toBeHidden();
  await page.click('#landmarks-button');
  await expect(page.locator('#landmarks-list')).toBeVisible();
  await row(page, 'origin').locator('.go').click();
  await expect(page.locator('#landmarks-list')).toBeHidden();
  expect((await camera(page)).target).toEqual([0, 0, 0]);
  await page.click('#landmarks-button');
  await row(page, 'my base').locator('.go').click();
  const cam = await camera(page);
  expect(cam).toMatchObject(there);
  s = await marks(page);
  expect(s.selected).toBe(s.list[1].id);
  // Escape closes the open list.
  await page.click('#landmarks-button');
  await page.keyboard.press('Escape');
  await expect(page.locator('#landmarks-list')).toBeHidden();
  expect(errors).toEqual([]);
});

test('the trash button asks, then deletes that landmark only; origin has no trash', async ({ page }) => {
  const errors = await open(page);
  await view(page, { target: [5, 5, 0] });
  await pin(page, 'first');
  await view(page, { target: [-9, 2, 0] });
  await pin(page, 'second');
  const before = await camera(page);
  await page.click('#landmarks-button');
  await expect(row(page, 'origin').locator('.trash')).toHaveCount(0);
  await expect(row(page, 'first').locator('.trash')).toHaveCount(1);

  await row(page, 'first').locator('.trash').click();
  await expect(page.locator('#landmark-delete-dialog')).toBeVisible();
  await expect(page.locator('#landmark-delete-dialog .question')).toHaveText('Delete the landmark "first"?');
  // Negative: "cancel" keeps it.
  await page.click('#landmark-delete-no');
  await expect(page.locator('#landmark-delete-dialog')).toBeHidden();
  expect(await names(page)).toEqual(['origin (0, 0, 0)', 'first', 'second']);

  await page.click('#landmarks-button');
  await row(page, 'first').locator('.trash').click();
  await page.click('#landmark-delete-yes');
  await expect(page.locator('#landmark-delete-dialog')).toBeHidden();
  const s = await marks(page);
  expect(s.list.map((l) => l.name)).toEqual(['origin (0, 0, 0)', 'second']);
  // The chosen one ("second") is still chosen; the camera did not move.
  expect(s.selected).toBe(s.list[1].id);
  expect(await camera(page)).toEqual(before);
  await expect(page.locator('#landmarks-list li')).toHaveCount(2);

  // Deleting the chosen one leaves none chosen.
  await page.click('#landmarks-button');
  await row(page, 'second').locator('.trash').click();
  await page.click('#landmark-delete-yes');
  expect(await marks(page)).toMatchObject({ selected: null });
  await expect(page.locator('#landmarks-button')).toHaveText('landmarks');
  // Negative: origin cannot be deleted by any route.
  const refused = await page.evaluate(() => {
    try {
      window.SC2App.removeLandmark(0);
      return null;
    } catch (error) {
      return error.message;
    }
  });
  expect(refused).toBe('the origin landmark cannot be deleted');
  expect(await names(page)).toEqual(['origin (0, 0, 0)']);
  expect(errors).toEqual([]);
});

test('landmarks and the chosen one are back after a reload; a deleted one stays deleted', async ({ page }) => {
  const errors = await open(page);
  const a = { yaw: 1.1, pitch: 0.3, distance: 40, target: [12, 3, 0] };
  const b = { yaw: -0.2, pitch: 1.0, distance: 6, target: [-2, -8, 1.5] };
  await view(page, a);
  await pin(page, 'alpha');
  await view(page, b);
  await pin(page, 'beta');
  // One made by the page itself ("add all" makes them this way).
  await page.evaluate(() => window.SC2App.addLandmark({ name: 'made', target: [1, 1, 0], yaw: 0, pitch: 0.5, distance: 9 }));
  await page.click('#landmarks-button');
  await row(page, 'alpha').locator('.go').click();
  const saved = await marks(page);

  await reload(page);
  const s = await marks(page);
  expect(s).toEqual({ ...saved, restore: 'restored' });
  expect(s.list.map((l) => l.name)).toEqual(['origin (0, 0, 0)', 'alpha', 'beta', 'made']);
  expect(s.list[1]).toMatchObject(a);
  expect(s.list[2]).toMatchObject(b);
  await expect(page.locator('#landmarks-button')).toHaveText('alpha');
  // A new one gets a new id, not a reused one.
  await pin(page, 'gamma');
  const ids = (await marks(page)).list.map((l) => l.id);
  expect(new Set(ids).size).toBe(ids.length);

  await page.click('#landmarks-button');
  await row(page, 'beta').locator('.trash').click();
  await page.click('#landmark-delete-yes');
  await reload(page);
  expect(await names(page)).toEqual(['origin (0, 0, 0)', 'alpha', 'made', 'gamma']);
  expect(errors).toEqual([]);
});

test('negative: stored landmarks that are not landmarks are refused and reported', async ({ page }) => {
  await open(page);
  for (const bad of ['not json', JSON.stringify({ list: [{ id: 1, name: 'x', yaw: 0, pitch: 0, distance: -1, target: [0, 0, 0] }], selected: null }), JSON.stringify({ list: 'no', selected: null })]) {
    await page.evaluate((v) => localStorage.setItem('viewer.landmarks', v), bad);
    await reload(page);
    const s = await marks(page);
    expect(s.list.map((l) => l.name)).toEqual(['origin (0, 0, 0)']);
    expect(s.restore).toMatch(/^refused: /);
  }
});

test('the exact camera, the grid toggle and the sky are back after a reload', async ({ page }) => {
  const errors = await open(page);
  // A view reached with every camera gesture: orbit, mouse-look, pan, grab, zoom.
  const box = await page.locator('canvas#view').boundingBox();
  const drag = async (button, keys, dx, dy) => {
    for (const key of keys) await page.keyboard.down(key);
    await page.mouse.move(box.x + 800, box.y + 400);
    await page.mouse.down({ button });
    await page.mouse.move(box.x + 800 + dx, box.y + 400 + dy, { steps: 5 });
    await page.mouse.up({ button });
    for (const key of keys) await page.keyboard.up(key);
  };
  await drag('middle', [], 70, -30);
  await drag('middle', ['Control'], -40, 25);
  await drag('right', [], 55, 35);
  await drag('left', [], -60, 20);
  await page.mouse.wheel(0, 240);
  await page.waitForFunction(() => window.SC2App.zoomGoal() === null);
  const sky = (await (await page.request.get(api.backdrops('limit=1'))).json()).items[0];
  await page.evaluate((s) => window.sc2viewer.setSky(s), sky);
  await page.click('#grid-toggle');
  await page.waitForFunction(() => window.sc2viewer.idle());
  const before = await state(page);
  expect(before.grid).toBe(false);
  expect(before.sky).toMatchObject({ id: sky.id, file: sky.file });
  const eye = await page.evaluate(() => window.SC2App.eye());

  await reload(page);
  await page.waitForFunction(() => window.sc2viewer.idle());
  const after = await state(page);
  // Exact: the same numbers, not close ones.
  expect(after.camera).toEqual(before.camera);
  expect(await page.evaluate(() => window.SC2App.eye())).toEqual(eye);
  expect(after.grid).toBe(false);
  expect(after.sky).toEqual(before.sky);
  await expect(page.locator('#grid-toggle')).not.toHaveClass(/\bon\b/);
  await expect(page.locator('#sky-button')).toHaveClass(/\bon\b/);

  // Negative: grid on and no sky are kept just the same.
  await page.click('#grid-toggle');
  await page.evaluate(() => window.sc2viewer.setSky(null));
  await reload(page);
  const last = await state(page);
  expect(last.grid).toBe(true);
  expect(last.sky).toBe(null);
  expect(errors).toEqual([]);
});

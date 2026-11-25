import { test, expect } from '../fixtures.mjs';

// Ctrl + click on an instance's row name selects it and points the camera
// at it (src/page/features/focus): the target goes to the instance's middle, the
// distance fits its sphere, yaw and pitch stay. A plain or shift click
// selects only; the camera stays.

const VIEW = { yaw: -Math.PI / 3, pitch: 0.7, distance: 40, target: [0, 0, 0] };

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

async function place(page, units) {
  const ids = [];
  for (const [id, x, y] of units) ids.push(await page.evaluate(([u, ux, uy]) => window.sc2viewer.addUnit(u, { x: ux, y: uy }), [id, x, y]));
  await page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 15_000 });
  await page.evaluate((v) => window.sc2viewer.view(v), VIEW);
  return ids;
}

const state = (page) => page.evaluate(() => window.sc2viewer.state());
const head = (page, id) => page.locator(`#scene li[data-id="${id}"] .head .name`);
const marked = (page) => page.locator('#scene li.selected').evaluateAll((rows) => rows.map((r) => Number(r.dataset.id)));

test('ctrl + click on a row name points the camera at the instance and selects it', async ({ page }) => {
  const errors = await open(page);
  const [marine, ultra] = await place(page, [['Marine', -12, 6], ['Ultralisk', 15, -9]]);

  await head(page, ultra).click({ modifiers: ['Control'] });
  let s = await state(page);
  console.log('ultralisk focus', JSON.stringify(s.camera));
  expect(s.pick.selected).toBe(ultra);
  expect(await marked(page)).toEqual([ultra]);
  // The target is the middle of the model's vertex box: near the unit's
  // place, a little off it, and above the ground.
  expect(Math.hypot(s.camera.target[0] - 15, s.camera.target[1] + 9)).toBeLessThan(1);
  expect(s.camera.target[2]).toBeGreaterThan(0.5);
  expect(s.camera.yaw).toBeCloseTo(VIEW.yaw, 9);
  expect(s.camera.pitch).toBeCloseTo(VIEW.pitch, 9);
  const ultraDistance = s.camera.distance;
  expect(ultraDistance).toBeLessThan(VIEW.distance);

  // The instance is on screen, near the middle of the view.
  const box = await page.locator('canvas#view').boundingBox();
  const at = await page.evaluate((i) => window.sc2viewer.itemPixel(i), ultra);
  expect(at).not.toBeNull();
  expect(Math.abs(at[0] - (box.x + box.width / 2))).toBeLessThan(box.width * 0.25);
  expect(Math.abs(at[1] - (box.y + box.height / 2))).toBeLessThan(box.height * 0.25);

  // A smaller instance: the camera comes nearer.
  await head(page, marine).click({ modifiers: ['Control'] });
  s = await state(page);
  console.log('marine focus', JSON.stringify(s.camera));
  expect(s.pick.selected).toBe(marine);
  expect(Math.hypot(s.camera.target[0] + 12, s.camera.target[1] - 6)).toBeLessThan(0.5);
  expect(s.camera.distance).toBeLessThan(ultraDistance / 4);
  expect(s.camera.yaw).toBeCloseTo(VIEW.yaw, 9);
  expect(s.camera.pitch).toBeCloseTo(VIEW.pitch, 9);
  expect(errors).toEqual([]);
});

test('negative: a plain or shift click on a row name selects and leaves the camera', async ({ page }) => {
  const errors = await open(page);
  const [marine, ultra] = await place(page, [['Marine', -12, 6], ['Ultralisk', 15, -9]]);
  const before = (await state(page)).camera;

  await head(page, ultra).click();
  let s = await state(page);
  expect(s.pick.selected).toBe(ultra);
  expect(s.camera).toEqual(before);

  await head(page, marine).click({ modifiers: ['Shift'] });
  s = await state(page);
  expect((await marked(page)).sort()).toEqual([marine, ultra].sort());
  expect(s.camera).toEqual(before);
  expect(errors).toEqual([]);
});

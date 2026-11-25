import { test, expect } from '../fixtures.mjs';
import { sceneOf } from '../scene.mjs';

// Alt + left hold on a unit drags the unit over the ground; the ground point
// pressed stays under the mouse (src/page/features/controls, mode 'move').

const VIEW = { yaw: -Math.PI / 2, pitch: 0.5, distance: 9, target: [0, 0, 0.8] };

async function open(page) {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => {
    if (m.text().startsWith('viewer:') || m.type() === 'error') errors.push(m.text());
  });
  await page.goto('/');
  await expect.poll(() => errors.join(' | ') || page.evaluate(() => Boolean(window.scobaeditor && window.scobaeditor.ready)), { timeout: 10_000 }).toBe(true);
  return errors;
}

async function place(page, id) {
  const itemId = await page.evaluate((u) => window.scobaeditor.addUnit(u, { x: 0, y: 0, pick: 0.5 }), id);
  await page.waitForFunction(() => window.scobaeditor.idle(), null, { timeout: 15_000 });
  await page.evaluate((v) => window.scobaeditor.view(v), VIEW);
  return itemId;
}

const state = (page) => page.evaluate(() => window.scobaeditor.state());
const itemOf = async (page, id) => (await state(page)).items.find((i) => i.id === id);
// A pixel on the unit's picture: the mouse hit goes by pixel.
const onItem = (page, id) => page.evaluate((i) => window.scobaeditor.itemPixel(i), id);
const onWorld = (page, p) => page.evaluate((q) => window.scobaeditor.screenOf(q), p);

async function altDrag(page, from, to) {
  await page.keyboard.down('Alt');
  await page.mouse.move(from[0], from[1]);
  await page.mouse.down();
  await page.mouse.move(to[0], to[1], { steps: 4 });
  await page.mouse.up();
  await page.keyboard.up('Alt');
}

test('alt + left drag on a unit moves it; the point pressed stays under the mouse', async ({ page }) => {
  const errors = await open(page);
  const marine = await place(page, 'Marine');
  const before = await state(page);
  const stored = (await sceneOf(page)).items[0];
  // Mouse events land on whole pixels.
  const from = (await onItem(page, marine)).map(Math.round);
  const to = (await onWorld(page, [2, 1, 0])).map(Math.round);
  // The point of the unit the press grabs.
  const hit = await page.evaluate(([x, y]) => {
    const h = window.SCOBAEdit.hitAt(x, y);
    return h ? { id: h.item.id, point: h.point } : null;
  }, from);
  expect(hit, 'the press lands on the unit').toBeTruthy();
  expect(hit.id).toBe(marine);
  await altDrag(page, from, to);
  const after = await state(page);
  const item = after.items.find((i) => i.id === marine);
  // That point, carried with the unit, is under the mouse at release.
  const carried = [hit.point[0] + item.x, hit.point[1] + item.y, hit.point[2]];
  const shown = await onWorld(page, carried);
  console.log('grabbed', hit.point, 'unit', [item.x, item.y], 'engine', item.location, 'carried point on screen', shown, 'mouse', to);
  expect(Math.hypot(shown[0] - to[0], shown[1] - to[1])).toBeLessThan(1.5);
  // The engine holds the same place as the script.
  expect(item.location[0]).toBeCloseTo(item.x, 4);
  expect(item.location[1]).toBeCloseTo(item.y, 4);
  // It really moved, and to the right as the mouse did. (Its feet are not
  // under the mouse: the grabbed point is up on the unit.)
  expect(Math.hypot(item.x, item.y)).toBeGreaterThan(1.5);
  expect(item.x).toBeGreaterThan(0.5);
  // The camera stayed; nothing was selected (a drag is not a click).
  expect(after.camera.target).toEqual(before.camera.target);
  expect(after.pick.selected).toBe(null);
  // The list row and the stored scene show the new place.
  expect(Number(await page.locator(`#scene li[data-id="${marine}"] input.x`).inputValue())).toBeCloseTo(item.x, 2);
  expect(Number(await page.locator(`#scene li[data-id="${marine}"] input.y`).inputValue())).toBeCloseTo(item.y, 2);
  const moved = (await sceneOf(page)).items[0];
  expect([moved.x, moved.y]).not.toEqual([stored.x, stored.y]);
  expect(moved.x).toBeCloseTo(item.x, 6);
  expect(moved.y).toBeCloseTo(item.y, 6);
  expect(errors).toEqual([]);
});

// Operator 2026-11-22: alt + left off any unit draws the select rectangle
// (multi-select.spec.mjs); before, it scrolled the camera.
test('negative: alt + left drag on empty ground moves no unit and keeps the camera', async ({ page }) => {
  const errors = await open(page);
  const marine = await place(page, 'Marine');
  const before = await state(page);
  const from = await onWorld(page, [3, 2, 0]);
  // A short drag that stays clear of the unit.
  await altDrag(page, from, [from[0] + 60, from[1]]);
  const after = await state(page);
  const item = after.items.find((i) => i.id === marine);
  expect([item.x, item.y]).toEqual([0, 0]);
  expect(after.camera.target).toEqual(before.camera.target);
  expect(after.pick.selection).toEqual([]);
  expect(errors).toEqual([]);
});

test('negative: a left drag on a unit without alt scrolls the camera and moves no unit', async ({ page }) => {
  const errors = await open(page);
  const marine = await place(page, 'Marine');
  const before = await state(page);
  const from = await onItem(page, marine);
  await page.mouse.move(from[0], from[1]);
  await page.mouse.down();
  await page.mouse.move(from[0] + 80, from[1], { steps: 4 });
  await page.mouse.up();
  const after = await state(page);
  const item = await itemOf(page, marine);
  expect([item.x, item.y]).toEqual([0, 0]);
  expect(after.camera.target).not.toEqual(before.camera.target);
  expect(errors).toEqual([]);
});

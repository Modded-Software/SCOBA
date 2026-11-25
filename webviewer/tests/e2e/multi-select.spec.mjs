import { test, expect } from '../fixtures.mjs';
import { sceneOf } from '../scene.mjs';

// Many instances selected at once (src/page/features/pick, select):
// - alt + left drag from empty ground draws a rectangle; on release the
//   instances inside it are the selection (with shift: added to it);
// - shift + click adds an instance to the selection or takes it out;
// - Delete removes the selected instances.

const VIEW = { yaw: -Math.PI / 2, pitch: 0.5, distance: 12, target: [2, 0, 0.8] };

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

/** Marine and zealot side by side, a zergling far to the right. */
async function place(page) {
  const ids = [];
  for (const [id, x, y] of [['Marine', 0, 0], ['Zealot', 2.5, 0], ['Zergling', 8, 0]]) ids.push(await page.evaluate(([u, ux, uy]) => window.sc2viewer.addUnit(u, { x: ux, y: uy, pick: 0.5 }), [id, x, y]));
  await page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 15_000 });
  await page.evaluate((v) => window.sc2viewer.view(v), VIEW);
  // Two frames with this camera: a unit off screen before was not animated
  // (culled), and the mouse hit goes by what the last frame drew.
  await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))));
  return ids;
}

const state = (page) => page.evaluate(() => window.sc2viewer.state());
const pick = async (page) => (await state(page)).pick;
// With a height share `k`: that point of the unit's column (the select
// rectangle goes by it). Without: a pixel on the unit's picture (the mouse
// hit goes by pixel).
const onItem = (page, id, k) => page.evaluate(([i, h]) => (h === null ? window.sc2viewer.itemPixel(i) : window.sc2viewer.itemScreen(i, h)), [id, k ?? null]);
const onWorld = (page, p) => page.evaluate((q) => window.sc2viewer.screenOf(q), p);
const marked = (page) => page.locator('#scene li.selected').evaluateAll((rows) => rows.map((r) => Number(r.dataset.id)).sort((a, b) => a - b));

/** The rectangle around the items `ids`, from its right bottom corner to its left top one. */
async function around(page, ids) {
  const points = [];
  for (const id of ids) for (const k of [0, 0.5, 1]) points.push(await onItem(page, id, k));
  const xs = points.map((p) => p[0]);
  const ys = points.map((p) => p[1]);
  return { from: [Math.round(Math.max(...xs)) + 50, Math.round(Math.max(...ys)) + 40], to: [Math.round(Math.min(...xs)) - 50, Math.round(Math.min(...ys)) - 40] };
}

/** Alt (+ `keys`) + left drag along `rect`; `during` runs before the release. */
async function dragRect(page, rect, { keys = [], during = null } = {}) {
  for (const key of ['Alt', ...keys]) await page.keyboard.down(key);
  await page.mouse.move(rect.from[0], rect.from[1]);
  await page.mouse.down();
  await page.mouse.move(rect.to[0], rect.to[1], { steps: 8 });
  if (during) await during();
  await page.mouse.up();
  for (const key of ['Alt', ...keys]) await page.keyboard.up(key);
}

test('alt + left drag from the ground draws a rectangle; released, the instances inside are selected', async ({ page }) => {
  const errors = await open(page);
  const [marine, zealot, zergling] = await place(page);
  const rect = await around(page, [marine, zealot]);
  const far = await onItem(page, zergling);
  // The zergling stands outside the rectangle, and the drag starts on bare ground.
  expect(far[0]).toBeGreaterThan(rect.from[0] + 20);
  expect(await page.evaluate(([x, y]) => window.SC2App.itemAt(x, y), rect.from)).toBe(null);
  const before = (await state(page)).camera;

  await dragRect(page, rect, {
    during: async () => {
      // While dragging: the rectangle is shown from the press to the mouse; nothing is selected yet.
      const p = await pick(page);
      expect(p.rect).toEqual({ left: rect.to[0], top: rect.to[1], width: rect.from[0] - rect.to[0], height: rect.from[1] - rect.to[1] });
      expect(p.selection).toEqual([]);
      const box = await page.locator('#select-rect').boundingBox();
      expect(Math.round(box.width)).toBe(Math.round(p.rect.width));
      expect(Math.round(box.height)).toBe(Math.round(p.rect.height));
    },
  });
  const s = await state(page);
  expect(s.pick.selection).toEqual([marine, zealot]);
  expect(s.pick.rect).toBe(null);
  await expect(page.locator('#select-rect')).toBeHidden();
  // Every selected instance has a ring; the rows are marked.
  const ringed = s.rings.filter(Boolean).map((r) => r.x).sort((a, b) => a - b);
  expect(ringed).toEqual([0, 2.5]);
  expect(await marked(page)).toEqual([marine, zealot]);
  // Negative: the zergling is not selected, and the camera did not move.
  expect(s.pick.selection).not.toContain(zergling);
  expect(s.camera.target).toEqual(before.target);
  expect(s.camera.distance).toBe(before.distance);
  expect(s.items).toHaveLength(3);
  expect(errors).toEqual([]);
});

test('a new rectangle replaces the selection; with shift it adds; an empty one clears', async ({ page }) => {
  const errors = await open(page);
  const [marine, zealot, zergling] = await place(page);
  await dragRect(page, await around(page, [marine, zealot]));
  expect((await pick(page)).selection).toEqual([marine, zealot]);

  await dragRect(page, await around(page, [zergling]));
  expect((await pick(page)).selection).toEqual([zergling]);

  await dragRect(page, await around(page, [marine]), { keys: ['Shift'] });
  expect((await pick(page)).selection).toEqual([marine, zergling]);
  expect(await marked(page)).toEqual([marine, zergling]);

  // A rectangle over bare ground: nothing inside, nothing selected.
  const bare = await onWorld(page, [4, -3, 0]);
  await dragRect(page, { from: [bare[0] + 30, bare[1] + 20], to: [bare[0] - 30, bare[1] - 5] });
  const s = await state(page);
  expect(s.pick.selection).toEqual([]);
  expect(s.pick.selected).toBe(null);
  expect(s.rings.filter(Boolean)).toEqual([]);
  expect(errors).toEqual([]);
});

test('negative: a left drag without alt draws no rectangle and selects nothing', async ({ page }) => {
  await open(page);
  const [marine, zealot] = await place(page);
  const rect = await around(page, [marine, zealot]);
  const before = (await state(page)).camera;
  await page.mouse.move(rect.from[0], rect.from[1]);
  await page.mouse.down();
  await page.mouse.move(rect.to[0], rect.to[1], { steps: 8 });
  expect((await pick(page)).rect).toBe(null);
  await expect(page.locator('#select-rect')).toBeHidden();
  await page.mouse.up();
  const s = await state(page);
  expect(s.pick.selection).toEqual([]);
  // It grabbed the ground instead.
  expect(Math.hypot(s.camera.target[0] - before.target[0], s.camera.target[1] - before.target[1])).toBeGreaterThan(0.5);
});

test('shift + click adds an instance to the selection and takes it out again', async ({ page }) => {
  const errors = await open(page);
  const [marine, zealot, zergling] = await place(page);
  const m = await onItem(page, marine);
  const z = await onItem(page, zealot);
  const g = await onItem(page, zergling);
  const bare = await onWorld(page, [4, -3, 0]);

  await page.mouse.click(m[0], m[1]);
  expect((await pick(page)).selection).toEqual([marine]);
  await page.keyboard.down('Shift');
  await page.mouse.click(z[0], z[1]);
  expect((await pick(page)).selection).toEqual([marine, zealot]);
  await page.mouse.click(g[0], g[1]);
  expect((await pick(page)).selection).toEqual([marine, zealot, zergling]);
  expect(await marked(page)).toEqual([marine, zealot, zergling]);
  // Shift + click on a selected one takes it out; the others stay.
  await page.mouse.click(m[0], m[1]);
  expect((await pick(page)).selection).toEqual([zealot, zergling]);
  // Shift + click on the ground keeps the selection.
  await page.mouse.click(bare[0], bare[1]);
  expect((await pick(page)).selection).toEqual([zealot, zergling]);
  await page.keyboard.up('Shift');

  // Negative: without shift a click selects that one alone, and the ground clears.
  await page.mouse.click(m[0], m[1]);
  let s = await state(page);
  expect(s.pick.selection).toEqual([marine]);
  expect(s.pick.selected).toBe(marine);
  await page.mouse.click(bare[0], bare[1]);
  s = await state(page);
  expect(s.pick.selection).toEqual([]);
  expect(errors).toEqual([]);
});

test('shift + click on a row of the instances panel adds and removes too', async ({ page }) => {
  await open(page);
  const [marine, zealot] = await place(page);
  const head = (id) => page.locator(`#scene li[data-id="${id}"] .head .name`);
  await head(marine).click();
  await head(zealot).click({ modifiers: ['Shift'] });
  expect((await pick(page)).selection).toEqual([marine, zealot]);
  await head(marine).click({ modifiers: ['Shift'] });
  expect((await pick(page)).selection).toEqual([zealot]);
  // Negative: a plain row click selects that row alone.
  await head(marine).click();
  expect((await pick(page)).selection).toEqual([marine]);
});

test('Delete removes the selected instances and no others', async ({ page }) => {
  const errors = await open(page);
  const [marine, zealot, zergling] = await place(page);
  // Negative: nothing selected, Delete removes nothing.
  await page.keyboard.press('Delete');
  expect((await state(page)).items).toHaveLength(3);

  await dragRect(page, await around(page, [marine, zealot]));
  expect((await pick(page)).selection).toEqual([marine, zealot]);
  // Negative: while typing in a field, Delete edits the text and removes nothing.
  await page.fill('#search-units', 'abc');
  await page.focus('#search-units');
  await page.keyboard.press('Home');
  await page.keyboard.press('Delete');
  await expect(page.locator('#search-units')).toHaveValue('bc');
  expect((await state(page)).items).toHaveLength(3);
  expect((await pick(page)).selection).toEqual([marine, zealot]);

  await page.locator('#search-units').blur();
  await page.keyboard.press('Delete');
  const s = await state(page);
  expect(s.items.map((i) => i.id)).toEqual([zergling]);
  expect(s.sceneInstances).toBe(1);
  expect(s.pick.selection).toEqual([]);
  expect(s.pick.selected).toBe(null);
  expect(s.rings.filter(Boolean)).toEqual([]);
  await expect(page.locator('#scene li')).toHaveCount(1);
  // The stored scene holds what is left.
  const saved = (await sceneOf(page)).items;
  expect(saved.map((i) => i.source.record)).toEqual(['Zergling']);
  expect(errors).toEqual([]);
});

test('more selected instances than two all get a ring', async ({ page }) => {
  await open(page);
  const ids = await page.evaluate(async () => {
    const out = [];
    for (let i = 0; i < 12; i++) out.push(await window.sc2viewer.addUnit('Marine', { x: (i % 4) * 2, y: Math.floor(i / 4) * 2, pick: 0.5 }));
    return out;
  });
  await page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 15_000 });
  await page.evaluate((list) => window.SC2App.setSelection(list), ids);
  const s = await state(page);
  expect(s.pick.selection).toEqual(ids);
  expect(s.rings.filter(Boolean)).toHaveLength(12);
  // Negative: one taken out loses its ring.
  await page.evaluate((id) => window.SC2App.toggleSelected(id), ids[5]);
  expect((await state(page)).rings.filter(Boolean)).toHaveLength(11);
});

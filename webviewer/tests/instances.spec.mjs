import { test, expect } from '@playwright/test';

// Two panels stacked in one column on the left: the gallery (#gallery: unit
// and model browser) on top, the instances (#instances: the scene list)
// below. Selection is shared:
// a click on a unit in the view marks its row; a click on a row's name
// selects its unit in the view (features/pick select, ui/instances.ts markSelected).

const VIEW = { yaw: -Math.PI / 2, pitch: 0.5, distance: 9, target: [0, 0, 0.8] };

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
  for (const [id, x, y] of units) ids.push(await page.evaluate(([u, ux, uy]) => window.sc2viewer.addUnit(u, { x: ux, y: uy, pick: 0.5 }), [id, x, y]));
  await page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 15_000 });
  await page.evaluate((v) => window.sc2viewer.view(v), VIEW);
  return ids;
}

const state = (page) => page.evaluate(() => window.sc2viewer.state());
// A pixel on the unit's picture: the mouse hit goes by pixel.
const onItem = (page, id) => page.evaluate((i) => window.sc2viewer.itemPixel(i), id);
const onWorld = (page, p) => page.evaluate((q) => window.sc2viewer.screenOf(q), p);
/** Ids of the rows marked selected in the instances panel. */
const marked = (page) => page.locator('#scene li.selected').evaluateAll((rows) => rows.map((r) => Number(r.dataset.id)));

test('the gallery and the instances are two panels, stacked on the left, not overlapping', async ({ page }) => {
  const errors = await open(page);
  await place(page, [['Marine', 0, 0]]);
  // The gallery holds the browser and not the scene list; the instances panel the reverse.
  await expect(page.locator('#gallery #tabs')).toHaveCount(1);
  await expect(page.locator('#gallery #units')).toHaveCount(1);
  await expect(page.locator('#gallery #scene')).toHaveCount(0);
  await expect(page.locator('#instances #scene li')).toHaveCount(1);
  await expect(page.locator('#instances #clear')).toHaveCount(1);
  await expect(page.locator('#instances #units')).toHaveCount(0);
  await expect(page.locator('#instance-count')).toHaveText('(1)');
  // Stacked on the left (operator 2026-11-21): one column, gallery on top.
  const gallery = await page.locator('#gallery').boundingBox();
  const instances = await page.locator('#instances').boundingBox();
  const width = page.viewportSize().width;
  expect(instances.x).toBeCloseTo(gallery.x, 0);
  expect(instances.width).toBeCloseTo(gallery.width, 0);
  expect(gallery.x + gallery.width).toBeLessThan(width / 2);
  // Each exactly half the window height, the gallery from the top edge, the
  // instances to the bottom edge (operator 2026-11-21). Within a pixel.
  const height = page.viewportSize().height;
  expect(Math.abs(gallery.height - height / 2)).toBeLessThanOrEqual(1);
  expect(Math.abs(instances.height - height / 2)).toBeLessThanOrEqual(1);
  expect(gallery.y).toBe(0);
  expect(Math.abs(instances.y - gallery.height)).toBeLessThanOrEqual(1);
  expect(Math.abs(instances.y + instances.height - height)).toBeLessThanOrEqual(1);
  expect(errors).toEqual([]);
});

test('negative: the panel heights do not follow their content', async ({ page }) => {
  const errors = await open(page);
  const height = page.viewportSize().height;
  const heights = async () => [await page.locator('#gallery').boundingBox(), await page.locator('#instances').boundingBox()].map((b) => b.height);
  const empty = await heights();
  await place(page, [['Marine', 0, 0], ['Zealot', 2, 0], ['Probe', -2, 0], ['SCV', 0, 2], ['Drone', 0, -2], ['Stalker', 2, 2], ['Zergling', -2, -2]]);
  const full = await heights();
  console.log(`window ${height}: empty ${empty}, with 7 units ${full}`);
  for (const h of [...empty, ...full]) expect(Math.abs(h - height / 2)).toBeLessThanOrEqual(1);
  // Seven rows overflow half a window: the list scrolls inside the panel.
  const scroll = await page.locator('#scene').evaluate((n) => [n.scrollHeight, n.clientHeight]);
  expect(scroll[0]).toBeGreaterThan(scroll[1]);
  expect(errors).toEqual([]);
});

test('the half-height gallery keeps the unit list usable with a preview open', async ({ page }) => {
  const errors = await open(page);
  await page.locator('#search-units').fill('ultralisk');
  const row = page.locator('#units li[data-id="Ultralisk"]');
  await row.click();
  await expect(page.locator('#preview-units .name')).toHaveText('Ultralisk');
  const list = await page.locator('#units').boundingBox();
  const rowBox = await row.boundingBox();
  const preview = await page.locator('#preview-units').boundingBox();
  const gallery = await page.locator('#gallery').boundingBox();
  console.log(`gallery ${gallery.height}: list ${list.height}, row ${rowBox.height}, preview ${preview.height}`);
  // At least three rows show, and nothing lies over the list.
  expect(list.height).toBeGreaterThanOrEqual(3 * rowBox.height);
  expect(preview.y).toBeGreaterThanOrEqual(list.y + list.height);
  expect(preview.y + preview.height).toBeLessThanOrEqual(gallery.y + gallery.height);
  // The row takes a second click (the failure this guards: covered by the preview).
  await row.click({ timeout: 2_000 });
  expect(errors).toEqual([]);
});

test('a click on a unit in the view marks its row; another unit moves the mark; the ground clears it', async ({ page }) => {
  const errors = await open(page);
  const [marine, zealot] = await place(page, [['Marine', -1.5, 0], ['Zealot', 1.5, 0]]);
  expect(await marked(page)).toEqual([]);

  const m = await onItem(page, marine);
  await page.mouse.click(m[0], m[1]);
  expect((await state(page)).pick.selected).toBe(marine);
  expect(await marked(page)).toEqual([marine]);

  const z = await onItem(page, zealot);
  await page.mouse.click(z[0], z[1]);
  expect((await state(page)).pick.selected).toBe(zealot);
  expect(await marked(page)).toEqual([zealot]);

  // Negative: the ground deselects, and no row stays marked.
  const ground = await onWorld(page, [0, 3, 0]);
  await page.mouse.click(ground[0], ground[1]);
  expect((await state(page)).pick.selected).toBe(null);
  expect(await marked(page)).toEqual([]);
  expect(errors).toEqual([]);
});

test('a click on a row name selects its unit in the view', async ({ page }) => {
  const errors = await open(page);
  const [marine, zealot] = await place(page, [['Marine', -1.5, 0], ['Zealot', 1.5, 0]]);
  await page.locator(`#scene li[data-id="${zealot}"] .head .name`).click();
  let s = await state(page);
  expect(s.pick.selected).toBe(zealot);
  expect(s.rings[0]).toMatchObject({ x: 1.5, y: 0 });
  expect(await marked(page)).toEqual([zealot]);

  await page.locator(`#scene li[data-id="${marine}"] .head .name`).click();
  s = await state(page);
  expect(s.pick.selected).toBe(marine);
  expect(s.rings[0]).toMatchObject({ x: -1.5, y: 0 });
  expect(await marked(page)).toEqual([marine]);
  expect(errors).toEqual([]);
});

test('negative: the selection survives a new row, and goes with a removed unit', async ({ page }) => {
  const errors = await open(page);
  const [marine, zealot] = await place(page, [['Marine', -1.5, 0], ['Zealot', 1.5, 0]]);
  await page.locator(`#scene li[data-id="${marine}"] .head .name`).click();
  // Adding a unit rebuilds the list: the mark stays on the selected unit.
  await place(page, [['Probe', 0, 2]]);
  expect(await marked(page)).toEqual([marine]);
  // Removing the zealot (not selected) neither selects it nor moves the mark.
  await page.locator(`#scene li[data-id="${zealot}"] button.remove`).click();
  await expect(page.locator('#scene li')).toHaveCount(2);
  expect((await state(page)).pick.selected).toBe(marine);
  expect(await marked(page)).toEqual([marine]);
  // Removing the selected unit clears the selection and the mark.
  await page.locator(`#scene li[data-id="${marine}"] button.remove`).click();
  await expect(page.locator('#scene li')).toHaveCount(1);
  const s = await state(page);
  expect(s.pick.selected).toBe(null);
  expect(s.rings[0]).toBe(null);
  expect(await marked(page)).toEqual([]);
  expect(errors).toEqual([]);
});

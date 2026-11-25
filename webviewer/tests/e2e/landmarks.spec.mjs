import { test, expect } from '../fixtures.mjs';
import { api } from '../api.mjs';

// Landmarks (src/page/features/landmarks): named camera views in the view tools
// drop-down. "origin (0, 0, 0)" is always there. Each "add all" run frames its
// new block and keeps that view as a landmark named after the list filters.

async function open(page) {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push(m.text());
  });
  await page.goto('/');
  await page.waitForFunction(() => window.scobaeditor && window.scobaeditor.ready);
  return errors;
}

const landmarks = (page) => page.evaluate(() => window.SCOBAEdit.landmarks());
const camera = async (page) => (await page.evaluate(() => window.scobaeditor.state())).camera;
const run = (page) => page.evaluate(() => window.SCOBAEdit.addAllState());
// The drop-down list's rows (landmarks-store.spec.mjs covers the pin and trash buttons).
const options = (page) => page.locator('#landmarks-list li .go').allTextContents();
/** Open the list and click the row of landmark `id`. */
async function choose(page, id) {
  await page.click('#landmarks-button');
  await page.click(`#landmarks-list li[data-id="${id}"] .go`);
}

async function filterFew(page) {
  await page.selectOption('#filter-units-family', 'is:Melee');
  await page.fill('#search-units', 'zergling');
  const listed = await (await page.request.get(api.records('units', { limit: '500', family: 'Melee', q: 'zergling' }))).json();
  await expect.poll(() => page.locator('#count-units').textContent()).toBe(`${listed.total} units`);
  return listed;
}

async function addAllRun(page, total) {
  await page.locator('#add-all-units').click();
  await page.locator('#add-all-yes').click();
  await expect.poll(async () => {
    const r = await run(page);
    return r.running === false && r.asked === total && r.added + r.failed.length === total;
  }, { timeout: 30_000 }).toBe(true);
  await page.waitForFunction(() => window.scobaeditor.idle(), null, { timeout: 30_000 });
  return run(page);
}

const expectView = (cam, view) => {
  expect(cam.yaw).toBeCloseTo(view.yaw, 6);
  expect(cam.pitch).toBeCloseTo(view.pitch, 6);
  expect(cam.distance).toBeCloseTo(view.distance, 6);
  cam.target.forEach((t, i) => expect(t).toBeCloseTo(view.target[i], 6));
};

test('the origin landmark is there from the start and takes the camera to 0, 0, 0', async ({ page }) => {
  const errors = await open(page);
  expect(await options(page)).toEqual(['origin (0, 0, 0)']);
  const [origin] = await landmarks(page);
  expect(origin.target).toEqual([0, 0, 0]);
  // Elsewhere, then back.
  await page.evaluate(() => window.scobaeditor.view({ target: [40, -25, 0], distance: 60, yaw: 1 }));
  await page.evaluate((id) => window.SCOBAEdit.goToLandmark(id), origin.id);
  expectView(await camera(page), origin);
  expect(errors).toEqual([]);
});

test('add all frames the new block, adds a landmark named after the filters, and the select goes back and forth', async ({ page }) => {
  const errors = await open(page);
  const listed = await filterFew(page);
  const r = await addAllRun(page, listed.total);
  expect(r.failed).toEqual([]);
  const marks = await landmarks(page);
  expect(marks.map((l) => l.name)).toEqual(['origin (0, 0, 0)', 'Melee Units "zergling"']);
  expect(await options(page)).toEqual(['origin (0, 0, 0)', 'Melee Units "zergling"']);
  const block = marks[1];
  expect(r.landmark).toBe(block.id);
  expect((await page.evaluate(() => window.SCOBAEdit.landmarkState())).selected).toBe(block.id);
  await expect(page.locator('#landmarks-button')).toHaveText('Melee Units "zergling"');
  // The camera is the landmark's view, and every new unit stands in the uncovered part of the canvas.
  expectView(await camera(page), block);
  const inside = await page.evaluate((ids) => {
    const rect = window.SCOBAEdit.visibleRect();
    return ids.map((id) => {
      const p = window.scobaeditor.itemScreen(id, 0);
      return Boolean(p) && p[0] >= rect.left && p[0] <= rect.right && p[1] >= rect.top && p[1] <= rect.bottom;
    });
  }, r.layout.map((l) => l.id));
  expect(inside.every(Boolean)).toBe(true);

  // The select: origin, then back to the block.
  await choose(page, marks[0].id);
  expectView(await camera(page), marks[0]);
  await choose(page, block.id);
  expectView(await camera(page), block);
  expect(errors).toEqual([]);
});

test('add all again: a second landmark with a numbered name and its own view', async ({ page }) => {
  const errors = await open(page);
  const listed = await filterFew(page);
  await addAllRun(page, listed.total);
  await addAllRun(page, listed.total);
  const marks = await landmarks(page);
  expect(marks.map((l) => l.name)).toEqual(['origin (0, 0, 0)', 'Melee Units "zergling"', 'Melee Units "zergling" (2)']);
  // The blocks stand apart, so the views differ.
  const [a, b] = [marks[1].target, marks[2].target];
  expect(Math.hypot(a[0] - b[0], a[1] - b[1])).toBeGreaterThan(1);
  expect(errors).toEqual([]);
});

test('negative: a cancelled add all adds no landmark and leaves the camera', async ({ page }) => {
  const errors = await open(page);
  await filterFew(page);
  const before = await camera(page);
  await page.locator('#add-all-units').click();
  await page.locator('#add-all-no').click();
  await expect(page.locator('#add-all-dialog')).toBeHidden();
  expect((await landmarks(page)).map((l) => l.name)).toEqual(['origin (0, 0, 0)']);
  expect(await camera(page)).toEqual(before);
  expect(errors).toEqual([]);
});
// The names from the filters: tests/unit/add-all.spec.mjs.

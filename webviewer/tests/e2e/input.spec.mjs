import { allowErrors, test, expect } from '../fixtures.mjs';
import { open } from '../page.mjs';
import { refusedRows, storeAndReload } from '../refused.mjs';

// The input map in the page (src/page/core/input.ts, R-VIEW-154):
// - a stored binding acts, and the default it replaced stops acting;
// - the controls window rebinds by a press on the binding, and "reset all"
//   clears the stored map;
// - a rebound key acts, the default key no longer does;
// - Escape during a unit move puts the unit back;
// - a stored map with a fault stops the start (R-VIEW-73).
// The rules of each binding without a browser: tests/unit/input.spec.mjs.

const VIEW = { yaw: -Math.PI / 2, pitch: 0.5, distance: 9, target: [0, 0, 0.8] };
const KEY = 'viewer.input';

async function openWith(page, stored) {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  if (stored !== undefined) await page.addInitScript(([key, value]) => localStorage.setItem(key, value), [KEY, JSON.stringify(stored)]);
  await page.goto('/');
  await expect.poll(() => errors.join(' | ') || page.evaluate(() => Boolean(window.scobaeditor && window.scobaeditor.ready)), { timeout: 10_000 }).toBe(true);
  await page.evaluate((v) => window.scobaeditor.view(v), VIEW);
  return page.locator('canvas#view').boundingBox();
}

const camera = async (page) => (await page.evaluate(() => window.scobaeditor.state())).camera;
const centre = (box) => [Math.round(box.x + box.width * 0.6), Math.round(box.y + box.height * 0.6)];

async function drag(page, button, from, by) {
  await page.mouse.move(from[0], from[1]);
  await page.mouse.down({ button });
  await page.mouse.move(from[0] + by[0], from[1] + by[1], { steps: 4 });
  await page.mouse.up({ button });
}

test('a stored binding acts: orbit on the right button; the middle button no longer orbits', async ({ page }) => {
  const box = await openWith(page, { mouse: { orbit: { button: 'right', mods: [] } } });
  const at = centre(box);
  const c0 = await camera(page);
  await drag(page, 'right', at, [80, 0]);
  const c1 = await camera(page);
  console.log('yaw', c0.yaw, '->', c1.yaw);
  expect(Math.abs(c1.yaw - c0.yaw)).toBeGreaterThan(0.05);
  // Negative: the middle button is bound to nothing now; the camera stays.
  await drag(page, 'middle', at, [80, 0]);
  const c2 = await camera(page);
  expect(c2.yaw).toBeCloseTo(c1.yaw, 9);
  expect(c2.target).toEqual(c1.target);
  expect(c2.distance).toBeCloseTo(c1.distance, 9);
});

test('the controls window rebinds by a press on the binding; reset all clears it', async ({ page }) => {
  await openWith(page);
  // The gear button sits at the bottom right of the view, outside the top toolbar.
  const place = await page.evaluate(() => {
    const b = document.getElementById('controls-button').getBoundingClientRect();
    return { right: innerWidth - b.right, bottom: innerHeight - b.bottom, width: b.width, inToolbar: Boolean(document.querySelector('#view-tools #controls-button')) };
  });
  expect(place).toEqual({ right: 8, bottom: 8, width: 26, inToolbar: false });
  await page.locator('#controls-button').click();
  // The window opens above the button, inside the page.
  const win = await page.locator('#controls-window').boundingBox();
  const size = page.viewportSize();
  expect(win.x + win.width).toBeLessThanOrEqual(size.width);
  expect(win.y + win.height).toBeLessThanOrEqual(size.height - 34);
  const orbit = page.locator('#controls-window .controls-binding[data-action="orbit"]');
  await expect(orbit).toHaveText('Middle');
  await orbit.click();
  await expect.poll(() => page.evaluate(() => window.scobaeditor.controlsPanel().listening)).toBe('orbit');
  const b = await orbit.boundingBox();
  await page.keyboard.down('Shift');
  await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2);
  await page.mouse.down({ button: 'right' });
  await page.mouse.up({ button: 'right' });
  await page.keyboard.up('Shift');
  const after = await page.evaluate((key) => ({ map: window.scobaeditor.inputMap().mouse.orbit, stored: JSON.parse(localStorage.getItem(key)), panel: window.scobaeditor.controlsPanel() }), KEY);
  expect(after.map).toEqual({ button: 'right', mods: ['shift'] });
  expect(after.stored).toEqual({ mouse: { orbit: { button: 'right', mods: ['shift'] } } });
  expect(after.panel.listening).toBe(null);
  await expect(page.locator('#controls-window .controls-binding[data-action="orbit"]')).toHaveText('Shift+Right');
  await page.locator('#controls-reset').click();
  const reset = await page.evaluate((key) => ({ map: window.scobaeditor.inputMap().mouse.orbit, stored: localStorage.getItem(key) }), KEY);
  expect(reset).toEqual({ map: { button: 'middle', mods: [] }, stored: null });
});

test('the controls window has a row for every action; the last rows scroll into the window; labels are capitalised', async ({ page }) => {
  await openWith(page);
  await page.locator('#controls-button').click();
  const actions = await page.locator('#controls-window .controls-binding').evaluateAll((nodes) => nodes.map((n) => n.dataset.action));
  const all = await page.evaluate(() => [...Object.keys(window.scobaeditor.defaultInput().mouse), ...Object.keys(window.scobaeditor.defaultInput().keys)]);
  expect(actions.sort()).toEqual(all.sort());
  const original = page.locator('#controls-window .controls-binding[data-action="original"]');
  await expect(original).toHaveText('Ctrl+.');
  await expect(original.locator('xpath=../..')).toContainText('Show Original skin while held');
  // The body scrolls: the Original row and the last rate come inside the body's box.
  const body = page.locator('#controls-window .window-body');
  expect(await body.evaluate((n) => getComputedStyle(n).overflowY)).toBe('auto');
  for (const row of [original, page.locator('#controls-sensitivity'), page.locator('#controls-reset')]) {
    await row.scrollIntoViewIfNeeded();
    const [r, b] = [await row.boundingBox(), await body.boundingBox()];
    expect(r.y).toBeGreaterThanOrEqual(b.y - 0.5);
    expect(r.y + r.height).toBeLessThanOrEqual(b.y + b.height + 0.5);
  }
  // Every label and heading starts with a capital.
  const texts = await page.locator('#controls-table td:first-child, #controls-table th, #controls-window button').allTextContents();
  const lower = texts.filter((t) => /^[a-z]/.test(t));
  expect(lower).toEqual([]);
});

test('a rebound key acts and the default key no longer does: edges on Ctrl+E', async ({ page }) => {
  await openWith(page, { keys: { edges: { code: 'KeyE', key: 'e', mods: ['ctrl'] } } });
  const id = await page.evaluate(() => window.scobaeditor.addUnit('Marine', { x: 0, y: 0, pick: 0.5 }));
  await page.waitForFunction(() => window.scobaeditor.idle(), null, { timeout: 15_000 });
  await page.evaluate((i) => window.SCOBAEdit.setSelection([i]), id);
  const on = async () => (await page.evaluate(() => window.scobaeditor.state())).edges.on;
  // Negative first: Ctrl+/ is no longer the edges key.
  await page.keyboard.press('Control+Slash');
  expect(await on()).toEqual([]);
  await page.keyboard.press('Control+KeyE');
  expect(await on()).toEqual([id]);
});

test('Escape during a unit move puts the unit back and ends the drag', async ({ page }) => {
  await openWith(page);
  const id = await page.evaluate(() => window.scobaeditor.addUnit('Marine', { x: 0, y: 0, pick: 0.5 }));
  await page.waitForFunction(() => window.scobaeditor.idle(), null, { timeout: 15_000 });
  await page.evaluate((v) => window.scobaeditor.view(v), VIEW);
  const itemOf = async () => (await page.evaluate(() => window.scobaeditor.state())).items.find((i) => i.id === id);
  const before = await itemOf();
  const from = (await page.evaluate((i) => window.scobaeditor.itemPixel(i), id)).map(Math.round);
  await page.keyboard.down('Alt');
  await page.mouse.move(from[0], from[1]);
  await page.mouse.down();
  await page.mouse.move(from[0] + 90, from[1] + 20, { steps: 4 });
  const moved = await itemOf();
  await page.keyboard.press('Escape');
  const back = await itemOf();
  // The drag ended: moving on with the button still down moves nothing.
  await page.mouse.move(from[0] + 140, from[1] + 30, { steps: 4 });
  const still = await itemOf();
  await page.mouse.up();
  await page.keyboard.up('Alt');
  console.log('x, y', [before.x, before.y], 'moved', [moved.x, moved.y], 'back', [back.x, back.y]);
  expect(Math.hypot(moved.x - before.x, moved.y - before.y)).toBeGreaterThan(0.3);
  expect([back.x, back.y]).toEqual([before.x, before.y]);
  expect([still.x, still.y]).toEqual([before.x, before.y]);
});

test('negative: a stored map with a fault stops the start and names it', async ({ page }) => {
  allowErrors(/^console\.error: viewer: stored settings refused: viewer\.input: the binding of pan: "thumb" is not a button$/);
  await open(page);
  const bad = JSON.stringify({ mouse: { pan: { button: 'thumb', mods: [] } } });
  await storeAndReload(page, { [KEY]: bad });
  expect(await refusedRows(page)).toEqual([{ key: KEY, stored: bad, reason: 'the binding of pan: "thumb" is not a button' }]);
});

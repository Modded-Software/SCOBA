import { test, expect } from '@playwright/test';
import { reloadScene } from './scene.mjs';
import { add as addGhost } from './ghost.mjs';

// The edges of the selected instances (src/page/features/edges, the
// `edges` capability of the m3 and nod formats):
// - Ctrl+/ switches them for the selected instances, all the same way;
// - they are drawn in green over the model, and only those in front show;
// - they follow the pose;
// - an instance farther than the range from the eye shows none;
// - the choice is not kept: a reload or a paste starts without edges.
// Engine state: the lines the formats drew, and the pixels the edges change
// (sc2viewer.edgePixels: one frame with and one without them, at one moment).
// How thin and how green the lines look is an operator check.

const VIEW = { yaw: -Math.PI / 2, pitch: 0.5, distance: 6, target: [0, 0, 0.5] };

async function open(page) {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => {
    if (m.text().startsWith('viewer:') || m.type() === 'error') errors.push(m.text());
  });
  await page.goto('/');
  await expect.poll(() => errors.join(' | ') || page.evaluate(() => Boolean(window.sc2viewer && window.sc2viewer.ready)), { timeout: 20_000 }).toBe(true);
  await page.evaluate(() => window.sc2viewer.setGrid(false));
  return errors;
}

const idle = (page) => page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 15_000 });
const frames = (page) => page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))));
const edges = async (page) => {
  await frames(page);
  return (await page.evaluate(() => window.sc2viewer.state())).edges;
};
const pixels = (page, rect) => page.evaluate((r) => window.sc2viewer.edgePixels(r ?? undefined), rect ?? null);
const select = (page, ids) => page.evaluate((list) => window.SC2App.setSelection(list), ids);
const statusText = (page) => page.locator('#status');

/** A unit standing still, the camera on it. */
async function place(page, unit, options = {}) {
  const id = await page.evaluate(([u, o]) => window.sc2viewer.addUnit(u, { x: 0, y: 0, pick: 0.5, sequence: -1, ...o }), [unit, options]);
  await idle(page);
  await page.evaluate((v) => window.sc2viewer.view(v), VIEW);
  await page.mouse.move(1000, 80);
  return id;
}

test('unit: the edge list holds each triangle edge once, the lower index first', async ({ page }) => {
  const errors = await open(page);
  const list = (...args) => page.evaluate((a) => window.sc2viewer.probe('nod', 'edges', ...a), args);
  // A quad of two triangles: five edges, the shared one once.
  expect(await list([0, 1, 2, 2, 1, 3])).toEqual([0, 1, 1, 2, 0, 2, 1, 3, 2, 3]);
  // A range of the list: the second triangle only.
  expect(await list([0, 1, 2, 2, 1, 3], 3, 3)).toEqual([1, 2, 1, 3, 2, 3]);
  // Negative: an edge from a vertex to itself, and a part of a triangle, are left out.
  expect(await list([4, 4, 5])).toEqual([4, 5]);
  expect(await list([0, 1, 2, 3])).toEqual([0, 1, 1, 2, 0, 2]);
  expect(await list([])).toEqual([]);
  expect(errors).toEqual([]);
});

test('Ctrl+/ on a selected unit draws green edges on it; again, none', async ({ page }) => {
  const errors = await open(page);
  const marine = await place(page, 'Marine');
  // Negative: off from the start; nothing drawn.
  expect(await edges(page)).toMatchObject({ on: [], lines: 0 });
  expect((await pixels(page)).count).toBe(0);

  await select(page, [marine]);
  await page.keyboard.press('Control+/');
  await expect(statusText(page)).toHaveText('edges on: 1 instance');
  const on = await edges(page);
  const item = (await page.evaluate(() => window.sc2viewer.state())).items[0];
  const seen = await pixels(page);
  console.log('marine edges', JSON.stringify({ lines: on.lines, edgeCount: item.edgeCount, pixels: seen }));
  expect(on.on).toEqual([marine]);
  expect(on.lines).toBeGreaterThan(100);
  expect(on.lines).toBeLessThanOrEqual(item.edgeCount);
  expect(seen.count).toBeGreaterThan(200);
  // On the model: few edge pixels lie off its drawn body.
  expect(seen.outside / seen.count).toBeLessThan(0.05);

  await page.keyboard.press('Control+/');
  await expect(statusText(page)).toHaveText('edges off: 1 instance');
  expect(await edges(page)).toMatchObject({ on: [], lines: 0 });
  expect((await pixels(page)).count).toBe(0);
  expect(errors).toEqual([]);
});

test('negative: no selection, a text field, other modifiers, and an instance not selected', async ({ page }) => {
  const errors = await open(page);
  const left = await place(page, 'Marine', { x: -1 });
  const right = await place(page, 'Marine', { x: 1 });
  /** Whether a keydown on `where` had its default cancelled. */
  const cancelled = (where, mods) =>
    page.evaluate(([w, m]) => {
      const target = w === 'field' ? document.getElementById('search-units') : document.body;
      if (w === 'field') target.focus();
      const sent = new KeyboardEvent('keydown', { key: '/', code: 'Slash', bubbles: true, cancelable: true, ...m });
      const done = !target.dispatchEvent(sent);
      if (w === 'field') target.blur();
      return done;
    }, [where, mods]);

  // Nothing selected: consumed, nothing on, and the toast says why.
  expect(await cancelled('page', { ctrlKey: true })).toBe(true);
  await expect(statusText(page)).toHaveText('Ctrl+/: select an instance first');
  expect((await edges(page)).on).toEqual([]);

  await select(page, [left]);
  // A text field keeps the key.
  expect(await cancelled('field', { ctrlKey: true })).toBe(false);
  expect((await edges(page)).on).toEqual([]);
  // Other modifiers, or none: not the viewer's key.
  expect(await cancelled('page', { ctrlKey: true, altKey: true })).toBe(false);
  expect(await cancelled('page', { ctrlKey: true, key: '?', shiftKey: true })).toBe(false);
  expect(await cancelled('page', {})).toBe(false);
  expect((await edges(page)).on).toEqual([]);

  // Only the selected one gets edges.
  await page.keyboard.press('Control+/');
  const state = await edges(page);
  expect(state.on).toEqual([left]);
  expect(state.on).not.toContain(right);
  expect(state.lines).toBeGreaterThan(0);
  expect(errors).toEqual([]);
});

test('two selected switch the same way: as the one selected last', async ({ page }) => {
  const errors = await open(page);
  const a = await place(page, 'Marine', { x: -1 });
  const b = await place(page, 'Marine', { x: 1 });
  await select(page, [a]);
  await page.keyboard.press('Control+/');
  const one = await edges(page);
  expect(one.on).toEqual([a]);
  // b, selected last, is off: both go on.
  await select(page, [a, b]);
  await page.keyboard.press('Control+/');
  await expect(statusText(page)).toHaveText('edges on: 2 instances');
  const both = await edges(page);
  expect(both.on.sort()).toEqual([a, b].sort());
  expect(both.lines).toBe(one.lines * 2);
  await page.keyboard.press('Control+/');
  expect(await edges(page)).toMatchObject({ on: [], lines: 0 });
  expect(errors).toEqual([]);
});

test('only edges in front show: a unit in front hides the edges behind it', async ({ page }) => {
  const errors = await open(page);
  const marine = await place(page, 'Marine');
  // Far enough that a unit halfway is well clear of the eye.
  await page.evaluate(() => window.sc2viewer.view({ distance: 14 }));
  await select(page, [marine]);
  await page.keyboard.press('Control+/');
  // The marine's box on the page: its pixels with no edges, a little wider.
  const body = await page.evaluate(() => window.sc2viewer.pixels());
  const canvas = await page.locator('#view').boundingBox();
  const k = body.width / canvas.width;
  const box = { left: canvas.x + body.minX / k - 4, right: canvas.x + body.maxX / k + 4, top: canvas.y + body.minY / k - 4, bottom: canvas.y + body.maxY / k + 4 };
  const open_ = await pixels(page, box);
  console.log('in the marine box, nothing in front', JSON.stringify({ box, ...open_ }));
  expect(open_.inRect).toBeGreaterThan(200);

  // A large Thor halfway between the eye and the marine, with no edges of its own.
  const eye = await page.evaluate(() => window.SC2App.eye());
  const thor = await page.evaluate(([x, y]) => window.sc2viewer.addUnit('Thor', { x, y, pick: 0.5, sequence: -1, scale: 1.5 }), [eye[0] * 0.5, eye[1] * 0.5]);
  await idle(page);
  await frames(page);
  // The Thor is what the mouse finds all over the marine's box: it covers it.
  const found = await page.evaluate((r) => {
    const ids = new Set();
    for (let i = 0; i <= 8; i++) for (let j = 0; j <= 8; j++) ids.add(window.SC2App.itemAt(r.left + ((r.right - r.left) * i) / 8, r.top + ((r.bottom - r.top) * j) / 8)?.id ?? null);
    return [...ids];
  }, box);
  console.log('found over the marine box', JSON.stringify(found));
  expect(found).toEqual([thor]);
  const hidden = await pixels(page, box);
  const state = await edges(page);
  console.log('in the marine box, the Thor in front', JSON.stringify(hidden), 'lines', state.lines);
  // The lines are still drawn; the depth test hides them all.
  expect(state.on).toEqual([marine]);
  expect(state.lines).toBeGreaterThan(0);
  expect(hidden.inRect).toBe(0);
  expect(errors).toEqual([]);
});

test('edges follow the pose: a walking unit keeps its edges on its drawn body', async ({ page }) => {
  const errors = await open(page);
  const still = await place(page, 'Marine');
  const walk = (await page.evaluate(() => window.sc2viewer.state())).items[0].sequences.findIndex((s) => /^Walk/.test(s));
  expect(walk).toBeGreaterThanOrEqual(0);
  await page.evaluate((id) => window.sc2viewer.remove(id), still);
  const marine = await place(page, 'Marine', { sequence: walk });
  expect((await page.evaluate(() => window.sc2viewer.state())).items[0].sequence).toBe(walk);
  await select(page, [marine]);
  await page.keyboard.press('Control+/');
  const moments = [];
  for (let k = 0; k < 3; k++) {
    await page.waitForTimeout(250);
    const item = (await page.evaluate(() => window.sc2viewer.state())).items[0];
    moments.push({ frame: item.frame, ...(await pixels(page)) });
  }
  console.log('walking marine edges', JSON.stringify(moments));
  // The playhead moved; at every moment the edges lie on the posed body.
  expect(new Set(moments.map((m) => m.frame)).size).toBe(3);
  for (const m of moments) {
    expect(m.count).toBeGreaterThan(200);
    expect(m.outside / m.count).toBeLessThan(0.05);
  }
  expect(errors).toEqual([]);
});

test('farther than the range from the eye, a unit shows no edges; nearer, it does again', async ({ page }) => {
  const errors = await open(page);
  const marine = await place(page, 'Marine');
  await select(page, [marine]);
  await page.keyboard.press('Control+/');
  const near = await edges(page);
  expect(near.lines).toBeGreaterThan(0);
  expect(near.far).toEqual([]);

  await page.evaluate((d) => window.sc2viewer.view({ distance: d }), near.range * 1.5);
  const far = await edges(page);
  expect(far).toMatchObject({ on: [marine], far: [marine], lines: 0 });
  expect((await pixels(page)).count).toBe(0);

  // Just inside the range: drawn.
  await page.evaluate((d) => window.sc2viewer.view({ distance: d }), near.range * 0.9);
  const inside = await edges(page);
  expect(inside.far).toEqual([]);
  expect(inside.lines).toBe(near.lines);
  expect(errors).toEqual([]);
});

test('not kept: a paste and a reload start without edges', async ({ page }) => {
  const errors = await open(page);
  const marine = await place(page, 'Marine');
  await select(page, [marine]);
  await page.keyboard.press('Control+/');
  expect((await edges(page)).on).toEqual([marine]);

  const at = (await page.evaluate(() => window.sc2viewer.screenOf([2, -2, 0]))).map(Math.round);
  await page.mouse.move(at[0], at[1]);
  await page.keyboard.press('Control+c');
  await page.keyboard.press('Control+v');
  await idle(page);
  const items = (await page.evaluate(() => window.sc2viewer.state())).items;
  expect(items.length).toBe(2);
  expect((await edges(page)).on).toEqual([marine]);

  await reloadScene(page);
  expect((await page.evaluate(() => window.sc2viewer.state())).items.length).toBe(2);
  expect(await edges(page)).toMatchObject({ on: [], lines: 0 });
  expect(errors).toEqual([]);
});

test('Ghost: Ctrl+/ draws the edges of a nod model', async ({ page }) => {
  const errors = await open(page);
  const crate = await addGhost(page, '3D/Models/crate.nod');
  await idle(page);
  await page.evaluate(() => window.sc2viewer.view('front'));
  await page.mouse.move(1000, 80);
  await select(page, [crate]);
  await page.keyboard.press('Control+/');
  await expect(statusText(page)).toHaveText('edges on: 1 instance');
  const state = await edges(page);
  const seen = await pixels(page);
  console.log('crate edges', JSON.stringify({ lines: state.lines, pixels: seen }));
  expect(state.on).toEqual([crate]);
  expect(state.lines).toBeGreaterThan(0);
  expect(seen.count).toBeGreaterThan(50);
  expect(seen.outside / seen.count).toBeLessThan(0.05);
  await page.keyboard.press('Control+/');
  expect(await edges(page)).toMatchObject({ on: [], lines: 0 });
  expect(errors).toEqual([]);
});

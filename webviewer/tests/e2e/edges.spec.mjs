import { test, expect } from '../fixtures.mjs';
import { add as addGhost } from '../ghost.mjs';
import { frames, idle, open as openPage, state as viewState, view } from '../page.mjs';
import { reloadScene } from '../scene.mjs';

// The edges of the selected instances (src/page/features/edges, the
// `edges` capability of the m3 and nod formats):
// - Ctrl+/ switches them for the selected instances, all the same way;
// - an instance farther than the range from the eye shows none;
// - the choice is not kept: a reload or a paste starts without edges.
// Engine state: the lines the formats drew in the last frame. How the
// lines look, that only those in front show and that they follow the pose
// are operator checks (SPEC-VIEWER 14).

const VIEW = { yaw: -Math.PI / 2, pitch: 0.5, distance: 6, target: [0, 0, 0.5] };

const open = (page) => openPage(page, { grid: false });
const edges = async (page) => {
  await frames(page);
  return (await viewState(page)).edges;
};
const select = (page, ids) => page.evaluate((list) => window.SC2App.setSelection(list), ids);
const statusText = (page) => page.locator('#status');

/** A unit standing still, the camera on it. */
async function place(page, unit, options = {}) {
  const id = await page.evaluate(([u, o]) => window.sc2viewer.addUnit(u, { x: 0, y: 0, pick: 0.5, sequence: -1, ...o }), [unit, options]);
  await idle(page);
  await view(page, VIEW);
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

test('Ctrl+/ on a selected unit draws its edges; again, none', async ({ page }) => {
  const errors = await open(page);
  const marine = await place(page, 'Marine');
  // Negative: off from the start; nothing drawn.
  expect(await edges(page)).toMatchObject({ on: [], lines: 0 });

  await select(page, [marine]);
  await page.keyboard.press('Control+/');
  await expect(statusText(page)).toHaveText('edges on: 1 instance');
  const on = await edges(page);
  const item = (await viewState(page)).items[0];
  console.log('marine edges', JSON.stringify({ lines: on.lines, edgeCount: item.edgeCount }));
  expect(on.on).toEqual([marine]);
  expect(on.lines).toBeGreaterThan(100);
  expect(on.lines).toBeLessThanOrEqual(item.edgeCount);

  await page.keyboard.press('Control+/');
  await expect(statusText(page)).toHaveText('edges off: 1 instance');
  expect(await edges(page)).toMatchObject({ on: [], lines: 0 });
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
  const now = await edges(page);
  expect(now.on).toEqual([left]);
  expect(now.on).not.toContain(right);
  expect(now.lines).toBeGreaterThan(0);
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

test('a walking unit draws its edges at every moment of its walk', async ({ page }) => {
  const errors = await open(page);
  const still = await place(page, 'Marine');
  const walk = (await viewState(page)).items[0].sequences.findIndex((s) => /^Walk/.test(s));
  expect(walk).toBeGreaterThanOrEqual(0);
  await page.evaluate((id) => window.sc2viewer.remove(id), still);
  const marine = await place(page, 'Marine', { sequence: walk });
  expect((await viewState(page)).items[0].sequence).toBe(walk);
  await select(page, [marine]);
  await page.keyboard.press('Control+/');
  const moments = [];
  for (let k = 0; k < 3; k++) {
    // On in game time: the playhead has moved since the last moment.
    const last = (await viewState(page)).items[0].frame;
    await page.waitForFunction((f) => window.sc2viewer.state().items[0].frame !== f, last);
    const now = await edges(page);
    moments.push({ frame: (await viewState(page)).items[0].frame, lines: now.lines });
  }
  console.log('walking marine edges', JSON.stringify(moments));
  expect(new Set(moments.map((m) => m.frame)).size).toBe(3);
  for (const m of moments) expect(m.lines).toBeGreaterThan(100);
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
  const items = (await viewState(page)).items;
  expect(items.length).toBe(2);
  expect((await edges(page)).on).toEqual([marine]);

  await reloadScene(page);
  expect((await viewState(page)).items.length).toBe(2);
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
  const now = await edges(page);
  console.log('crate edges', JSON.stringify({ lines: now.lines }));
  expect(now.on).toEqual([crate]);
  expect(now.lines).toBeGreaterThan(0);
  await page.keyboard.press('Control+/');
  expect(await edges(page)).toMatchObject({ on: [], lines: 0 });
  expect(errors).toEqual([]);
});

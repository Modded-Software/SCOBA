import { test, expect } from '@playwright/test';
import { sceneOf } from './scene.mjs';

// The selected instances (src/page/features/clipboard, controls):
// - Ctrl+C copies them; Ctrl+X copies them and removes them;
// - Ctrl+V adds the copies, the group's centre on the ground under the
//   mouse, each keeping its place in the group; the pasted ones become the
//   selection. Off the view the copies go to the places they were copied from;
// - alt + left drag on a selected unit moves every selected unit along;
// - a text field keeps its own Ctrl+C, Ctrl+X and Ctrl+V.

const VIEW = { yaw: -Math.PI / 2, pitch: 0.6, distance: 16, target: [0, 0, 0.5] };

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

/** Marine, Zealot and Zergling in a row, still (no animation), the camera on them. */
async function place(page) {
  const ids = [];
  for (const [unit, x, y, rot] of [['Marine', -3, 0, 30], ['Zealot', 0, 1, 90], ['Zergling', 3, 0, 180]]) {
    ids.push(await page.evaluate(([u, ux, uy, r]) => window.sc2viewer.addUnit(u, { x: ux, y: uy, rot: r, pick: 0.5, sequence: -1, team: 2 }), [unit, x, y, rot]));
  }
  await page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 15_000 });
  await page.evaluate((v) => window.sc2viewer.view(v), VIEW);
  await frames(page);
  return ids;
}

const frames = (page) => page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))));
const items = async (page) => (await page.evaluate(() => window.sc2viewer.state())).items;
const select = (page, ids) => page.evaluate((list) => window.SC2App.setSelection(list), ids);
const selection = (page) => page.evaluate(() => window.SC2App.selectedIds());
const onWorld = (page, p) => page.evaluate((q) => window.sc2viewer.screenOf(q), p);
const onItem = (page, id) => page.evaluate((i) => window.sc2viewer.itemPixel(i), id);
const storedCount = async (page) => (await sceneOf(page)).items.length;
/** What a copy keeps of an instance. */
const kept = (i) => ({ unit: i.unit, doodad: i.doodad, variation: i.variation, path: i.path, dataset: i.dataset, rot: i.rot, scale: i.scale, team: i.team, sequence: i.sequence, hd: i.hd, dataScale: i.dataScale });

/** Put the mouse over a ground point, on the bare view. */
async function mouseOver(page, point) {
  const [x, y] = (await onWorld(page, point)).map(Math.round);
  await page.mouse.move(x, y);
  await frames(page);
}

test('ctrl+c, then ctrl+v: copies of the selected instances, centred under the mouse, become the selection', async ({ page }) => {
  const errors = await open(page);
  const [marine, zealot, zergling] = await place(page);
  await select(page, [marine, zealot]);
  const before = await items(page);
  await mouseOver(page, [0, -4, 0]);
  await page.keyboard.press('Control+c');
  // Negative: copying adds and removes nothing.
  expect((await items(page)).length).toBe(3);
  await page.keyboard.press('Control+v');
  await page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 15_000 });
  const after = await items(page);
  expect(after.length).toBe(5);
  const pasted = after.filter((i) => !before.some((b) => b.id === i.id));
  expect(pasted.map((i) => i.unit)).toEqual(['Marine', 'Zealot']);
  // Each copy keeps what its original has, but its place.
  const original = (unit) => before.find((b) => b.unit === unit);
  for (const p of pasted) expect(kept(p)).toEqual(kept(original(p.unit)));
  // The group keeps its shape; its centre is the ground point under the mouse.
  const ground = await page.evaluate(() => window.SC2App.pointer);
  console.log('pasted', JSON.stringify(pasted.map((p) => [p.unit, p.x, p.y])), 'ground under the mouse', ground);
  const centre = [(pasted[0].x + pasted[1].x) / 2, (pasted[0].y + pasted[1].y) / 2];
  expect(centre[0]).toBeCloseTo(ground[0], 3);
  expect(centre[1]).toBeCloseTo(ground[1], 3);
  expect(pasted[1].x - pasted[0].x).toBeCloseTo(original('Zealot').x - original('Marine').x, 5);
  expect(pasted[1].y - pasted[0].y).toBeCloseTo(original('Zealot').y - original('Marine').y, 5);
  // The pasted ones are the selection; the originals did not move.
  expect((await selection(page)).sort()).toEqual(pasted.map((p) => p.id).sort());
  for (const b of before) {
    const a = after.find((i) => i.id === b.id);
    expect([a.x, a.y, a.rot]).toEqual([b.x, b.y, b.rot]);
  }
  expect(after.some((i) => i.id === zergling)).toBe(true);
  // The stored scene holds all five.
  expect(await storedCount(page)).toBe(5);
  // A second paste adds two more: the copy stays.
  await page.keyboard.press('Control+v');
  await page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 15_000 });
  expect((await items(page)).length).toBe(7);
  expect(errors).toEqual([]);
});

test('ctrl+x removes the selected instances; ctrl+v brings them back under the mouse', async ({ page }) => {
  const errors = await open(page);
  const [marine, zealot, zergling] = await place(page);
  const before = await items(page);
  await select(page, [zealot, zergling]);
  await mouseOver(page, [-1, -3, 0]);
  await page.keyboard.press('Control+x');
  const cut = await items(page);
  expect(cut.map((i) => i.id)).toEqual([marine]);
  expect(await selection(page)).toEqual([]);
  expect(await storedCount(page)).toBe(1);
  await page.keyboard.press('Control+v');
  await page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 15_000 });
  const after = await items(page);
  expect(after.map((i) => i.unit)).toEqual(['Marine', 'Zealot', 'Zergling']);
  for (const p of after.slice(1)) expect(kept(p)).toEqual(kept(before.find((b) => b.unit === p.unit)));
  // Negative: the instance not cut stayed as it was.
  const m = after.find((i) => i.id === marine);
  expect([m.x, m.y]).toEqual([-3, 0]);
  expect(errors).toEqual([]);
});

test('a doodad keeps its variation and dataset, a bare model file its path, when copied and pasted', async ({ page }) => {
  const errors = await open(page);
  const [marine] = await place(page);
  const tree = await page.evaluate(() => window.sc2viewer.addDoodad('ZerusTree', { x: 0, y: 4, pick: 0.5, variation: 7, rot: 30, dataset: 'stock', sequence: -1 }));
  const path = (await items(page)).find((i) => i.id === marine).path;
  const bare = await page.evaluate((p) => window.sc2viewer.add(p, { x: -4, y: 4, pick: 0.5, sequence: -1, hd: false }), path);
  await page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 15_000 });
  const before = await items(page);
  await select(page, [tree, bare]);
  await mouseOver(page, [0, -4, 0]);
  await page.keyboard.press('Control+c');
  await page.keyboard.press('Control+v');
  await page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 15_000 });
  const pasted = (await items(page)).slice(before.length);
  expect(pasted.length).toBe(2);
  const of = (id) => before.find((b) => b.id === id);
  expect(kept(pasted[0])).toEqual(kept(of(tree)));
  expect(kept(pasted[1])).toEqual(kept(of(bare)));
  console.log('pasted', JSON.stringify(pasted.map((p) => [p.doodad, p.variation, p.dataset, p.path, p.hd])));
  expect(pasted[0]).toMatchObject({ doodad: 'ZerusTree', variation: 7, dataset: 'stock' });
  expect(pasted[1]).toMatchObject({ unit: null, doodad: null, path, hd: false });
  expect(errors).toEqual([]);
});

test('off the view, ctrl+v puts the copies where they were copied from', async ({ page }) => {
  const errors = await open(page);
  const [, zealot] = await place(page);
  await select(page, [zealot]);
  // The mouse on the gallery panel, not on the view.
  const panel = await page.locator('#panel').boundingBox();
  await page.mouse.move(panel.x + panel.width / 2, panel.y + panel.height / 2);
  expect(await page.evaluate(() => window.SC2App.pointer)).toBe(null);
  await page.locator('body').press('Control+c');
  await page.locator('body').press('Control+v');
  await page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 15_000 });
  const pasted = (await items(page)).slice(3);
  expect(pasted.map((p) => [p.unit, p.x, p.y])).toEqual([['Zealot', 0, 1]]);
  expect(errors).toEqual([]);
});

test('negative: no selection copies nothing; an empty clipboard pastes nothing; a text field keeps its keys', async ({ page }) => {
  const errors = await open(page);
  const [marine] = await place(page);
  await mouseOver(page, [0, -4, 0]);
  // Nothing copied yet: paste adds nothing and says so.
  await page.keyboard.press('Control+v');
  await frames(page);
  expect((await items(page)).length).toBe(3);
  await expect.poll(() => page.evaluate(() => window.SC2App.statusLog().shown.some((t) => t.startsWith('nothing copied')))).toBe(true);
  // Nothing selected: copy keeps nothing, cut removes nothing.
  await page.keyboard.press('Control+c');
  await page.keyboard.press('Control+x');
  await page.keyboard.press('Control+v');
  await frames(page);
  expect((await items(page)).length).toBe(3);
  // In the instance search the keys are the field's: with a unit selected,
  // nothing is copied, cut or pasted.
  await select(page, [marine]);
  const search = page.locator('#instance-search');
  await search.fill('mar');
  await search.press('Control+a');
  await search.press('Control+x');
  expect(await search.inputValue()).toBe('');
  await search.press('Control+v');
  await search.press('Control+c');
  await frames(page);
  expect((await items(page)).length).toBe(3);
  expect(await selection(page)).toEqual([marine]);
  await search.fill('');
  expect(errors).toEqual([]);
});

test('alt + left drag on a selected unit moves every selected unit by the same step; the others stay', async ({ page }) => {
  const errors = await open(page);
  const [marine, zealot, zergling] = await place(page);
  await select(page, [marine, zealot]);
  const before = await items(page);
  const from = (await onItem(page, zealot)).map(Math.round);
  const to = [from[0] + 60, from[1] + 40];
  await page.keyboard.down('Alt');
  await page.mouse.move(from[0], from[1]);
  await page.mouse.down();
  await page.mouse.move(to[0], to[1], { steps: 8 });
  await page.mouse.up();
  await page.keyboard.up('Alt');
  const after = await items(page);
  const step = (id) => {
    const a = after.find((i) => i.id === id);
    const b = before.find((i) => i.id === id);
    return [a.x - b.x, a.y - b.y];
  };
  console.log('steps', JSON.stringify({ marine: step(marine), zealot: step(zealot), zergling: step(zergling) }));
  expect(Math.hypot(...step(zealot))).toBeGreaterThan(0.5);
  expect(step(marine)[0]).toBeCloseTo(step(zealot)[0], 5);
  expect(step(marine)[1]).toBeCloseTo(step(zealot)[1], 5);
  // Negative: the unit not selected stayed; the selection is the same.
  expect(step(zergling)).toEqual([0, 0]);
  expect((await selection(page)).sort()).toEqual([marine, zealot].sort());
  expect(errors).toEqual([]);
});

test('negative: alt + left drag on a unit not selected moves that unit alone', async ({ page }) => {
  const errors = await open(page);
  const [marine, zealot, zergling] = await place(page);
  await select(page, [marine, zealot]);
  const before = await items(page);
  const from = (await onItem(page, zergling)).map(Math.round);
  await page.keyboard.down('Alt');
  await page.mouse.move(from[0], from[1]);
  await page.mouse.down();
  await page.mouse.move(from[0] - 50, from[1] + 30, { steps: 8 });
  await page.mouse.up();
  await page.keyboard.up('Alt');
  const after = await items(page);
  const moved = (id) => {
    const a = after.find((i) => i.id === id);
    const b = before.find((i) => i.id === id);
    return Math.hypot(a.x - b.x, a.y - b.y);
  };
  expect(moved(zergling)).toBeGreaterThan(0.5);
  expect(moved(marine)).toBe(0);
  expect(moved(zealot)).toBe(0);
  expect(errors).toEqual([]);
});

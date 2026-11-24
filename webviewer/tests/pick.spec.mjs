import { test, expect } from '@playwright/test';
import { sceneOf } from './scene.mjs';

// Units under the mouse: mouse-over highlight, click selection, ctrl + left
// facing, and the right-click animation menu (src/page/features/pick).

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

/** Add units at [x, y] and return their ids, with the test camera. */
async function place(page, units) {
  const ids = [];
  for (const [id, x, y] of units) ids.push(await page.evaluate(([u, ux, uy]) => window.sc2viewer.addUnit(u, { x: ux, y: uy, pick: 0.5 }), [id, x, y]));
  await page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 15_000 });
  await page.evaluate((v) => window.sc2viewer.view(v), VIEW);
  return ids;
}

const state = (page) => page.evaluate(() => window.sc2viewer.state());
const itemOf = async (page, id) => (await state(page)).items.find((i) => i.id === id);
// A pixel on the unit's picture: the mouse hit goes by pixel (pick-pixel.spec.mjs).
const onItem = (page, id) => page.evaluate((i) => window.sc2viewer.itemPixel(i), id);
const onWorld = (page, p) => page.evaluate((q) => window.sc2viewer.screenOf(q), p);
const pick = async (page) => (await state(page)).pick;
// Facings are checked to half a degree: the mouse lands on whole pixels.
/** The facing the renderer holds, in degrees, from its z rotation. */
const facing = (item) => (2 * Math.atan2(item.rotation[2], item.rotation[3]) * 180) / Math.PI;

test('screenOf is the inverse of the picking ray: ground points round-trip', async ({ page }) => {
  const errors = await open(page);
  await page.evaluate((v) => window.sc2viewer.view(v), VIEW);
  for (const p of [[0, 0], [3, 2], [2.5, -1.5]]) {
    const s = await onWorld(page, [p[0], p[1], 0]);
    const back = await page.evaluate(([x, y]) => {
      const box = document.getElementById('view').getBoundingClientRect();
      return window.sc2viewer.groundUnder(x - box.left, y - box.top);
    }, s);
    expect(back[0]).toBeCloseTo(p[0], 3);
    expect(back[1]).toBeCloseTo(p[1], 3);
  }
  expect(errors).toEqual([]);
});

test('mouse-over: the unit under the mouse is highlighted and brighter; off it, nothing is', async ({ page }) => {
  const errors = await open(page);
  const [marine] = await place(page, [['Marine', 0, 0]]);
  // On empty ground: no highlight, no mouse-over ring. (Right of the unit:
  // the side panel covers the left of the view.)
  const ground = await onWorld(page, [3, 2, 0]);
  await page.mouse.move(ground[0], ground[1]);
  await expect.poll(async () => (await state(page)).pointer !== null).toBe(true);
  let s = await state(page);
  expect(s.pick.hovered).toBe(null);
  expect(s.items[0].highlight).toBe(0);
  expect(s.rings[1]).toBe(null);
  // Brightness of the model alone (grid off), away from it.
  await page.evaluate(() => window.sc2viewer.setGrid(false));
  const before = await page.evaluate(() => window.sc2viewer.colorStats());
  // On the unit.
  const at = await onItem(page, marine);
  await page.mouse.move(at[0], at[1]);
  await expect.poll(async () => (await pick(page)).hovered).toBe(marine);
  const after = await page.evaluate(() => window.sc2viewer.colorStats());
  s = await state(page);
  expect(s.items[0].highlight).toBe(1);
  console.log('brightness', before.brightness.toFixed(1), '->', after.brightness.toFixed(1));
  expect(after.brightness).toBeGreaterThan(before.brightness * 1.15);
  // Grid on: the mouse-over ring is at the unit.
  await page.evaluate(() => window.sc2viewer.setGrid(true));
  s = await state(page);
  expect(s.rings[1]).toMatchObject({ x: 0, y: 0 });
  expect(s.rings[0]).toBe(null); // nothing selected
  // Away again: the highlight goes.
  await page.mouse.move(ground[0], ground[1]);
  await expect.poll(async () => (await pick(page)).hovered).toBe(null);
  expect((await itemOf(page, marine)).highlight).toBe(0);
  expect(errors).toEqual([]);
});

test('mouse-over: a feathered green glow surrounds the silhouette, only while hovered', async ({ page }) => {
  const errors = await open(page);
  const [marine] = await place(page, [['Marine', 0, 0]]);
  // Grid off: the drawn pixels are the unit (and its glow) alone.
  await page.evaluate(() => window.sc2viewer.setGrid(false));
  const ground = await onWorld(page, [3, 2, 0]);
  await page.mouse.move(ground[0], ground[1]);
  await expect.poll(async () => (await pick(page)).hovered).toBe(null);
  const plain = await page.evaluate(() => ({ c: window.sc2viewer.colorStats(), p: window.sc2viewer.pixels() }));
  const at = await onItem(page, marine);
  await page.mouse.move(at[0], at[1]);
  await expect.poll(async () => (await pick(page)).hovered).toBe(marine);
  const lit = await page.evaluate(() => ({ c: window.sc2viewer.colorStats(), p: window.sc2viewer.pixels() }));
  console.log('green', plain.c.green, '->', lit.c.green, 'covered', plain.p.covered, '->', lit.p.covered, 'box', JSON.stringify([plain.p.minX, plain.p.maxX, plain.p.minY, plain.p.maxY]), '->', JSON.stringify([lit.p.minX, lit.p.maxX, lit.p.minY, lit.p.maxY]));
  // Not hovered: no green. Hovered: a green band.
  expect(plain.c.green).toBeLessThan(20);
  expect(lit.c.green).toBeGreaterThan(400);
  // The band is outside the silhouette: the drawn area grows on every side,
  // by a feather of a few pixels (not a hard one-pixel line, not a halo
  // across the screen).
  for (const [grown, side] of [[plain.p.minX - lit.p.minX, 'left'], [lit.p.maxX - plain.p.maxX, 'right'], [plain.p.minY - lit.p.minY, 'top'], [lit.p.maxY - plain.p.maxY, 'bottom']]) {
    expect(grown, side).toBeGreaterThanOrEqual(3);
    expect(grown, side).toBeLessThanOrEqual(20);
  }
  // Mouse away: the glow is gone.
  await page.mouse.move(ground[0], ground[1]);
  await expect.poll(async () => (await pick(page)).hovered).toBe(null);
  const after = await page.evaluate(() => window.sc2viewer.colorStats());
  expect(after.green).toBeLessThan(20);
  expect(errors).toEqual([]);
});

test('selected units stay lit, without the glow; a unit not selected is not lit', async ({ page }) => {
  const errors = await open(page);
  const [marine, zealot, zergling] = await place(page, [['Marine', -1.5, 0], ['Zealot', 1.5, 0], ['Zergling', 0, 1.5]]);
  // Grid off: no rings; the drawn pixels are the units alone. The mouse on the ground.
  await page.evaluate(() => window.sc2viewer.setGrid(false));
  const ground = await onWorld(page, [3, -2, 0]);
  await page.mouse.move(ground[0], ground[1]);
  await expect.poll(async () => (await pick(page)).hovered).toBe(null);
  const plain = await page.evaluate(() => window.sc2viewer.colorStats());
  await page.evaluate((ids) => window.SC2App.setSelection(ids), [marine, zealot]);
  await expect.poll(async () => (await itemOf(page, marine)).highlight).toBe(1);
  expect((await itemOf(page, zealot)).highlight).toBe(1);
  const lit = await page.evaluate(() => window.sc2viewer.colorStats());
  console.log('selected brightness', plain.brightness.toFixed(1), '->', lit.brightness.toFixed(1), 'green', plain.green, '->', lit.green);
  expect(lit.brightness).toBeGreaterThan(plain.brightness * 1.1);
  // Negative: no glow; the unit not selected is not lit.
  expect(lit.green).toBeLessThan(20);
  expect((await itemOf(page, zergling)).highlight).toBe(0);
  // Cleared: none is lit.
  await page.evaluate(() => window.SC2App.setSelection([]));
  await expect.poll(async () => (await state(page)).items.map((i) => i.highlight)).toEqual([0, 0, 0]);
  expect(errors).toEqual([]);
});

test('left click selects; another unit takes the selection; the ground clears it; a drag does not select', async ({ page }) => {
  const errors = await open(page);
  const [marine, zealot] = await place(page, [['Marine', -1.5, 0], ['Zealot', 1.5, 0]]);
  const m = await onItem(page, marine);
  const z = await onItem(page, zealot);
  const ground = await onWorld(page, [0, 3, 0]);

  await page.mouse.click(m[0], m[1]);
  let s = await state(page);
  expect(s.pick.selected).toBe(marine);
  expect(s.rings[0]).toMatchObject({ x: -1.5, y: 0 });

  await page.mouse.click(z[0], z[1]);
  s = await state(page);
  expect(s.pick.selected).toBe(zealot);
  expect(s.rings[0]).toMatchObject({ x: 1.5, y: 0 });

  await page.mouse.click(ground[0], ground[1]);
  s = await state(page);
  expect(s.pick.selected).toBe(null);
  expect(s.rings[0]).toBe(null);

  // Negative: a left drag that starts on a unit moves the camera and selects nothing.
  const target = s.camera.target;
  await page.mouse.move(m[0], m[1]);
  await page.mouse.down();
  await page.mouse.move(m[0] + 60, m[1] + 10, { steps: 6 });
  await page.mouse.up();
  s = await state(page);
  expect(s.pick.selected).toBe(null);
  expect(Math.hypot(s.camera.target[0] - target[0], s.camera.target[1] - target[1])).toBeGreaterThan(0.2);
  expect(errors).toEqual([]);
});

test('ctrl + left hold turns the selected unit to face the mouse; released, it stays', async ({ page }) => {
  const errors = await open(page);
  const [marine] = await place(page, [['Marine', 0, 0]]);
  const at = await onItem(page, marine);
  await page.mouse.click(at[0], at[1]);
  expect((await pick(page)).selected).toBe(marine);
  const camera = (await state(page)).camera;

  const north = await onWorld(page, [0, 3, 0]);
  const west = await onWorld(page, [-2, 0, 0]);
  const south = await onWorld(page, [0, -2, 0]);
  await page.keyboard.down('Control');
  await page.mouse.move(north[0], north[1]);
  await page.mouse.down();
  // A model faces -y at rotation 0, so facing a direction takes that
  // direction + 90 degrees (operator 2026-11-21: it was 90 degrees clockwise).
  // Mouse north (+y, 90 degrees): rotation 180.
  let item = await itemOf(page, marine);
  expect(Math.abs(item.rot)).toBeCloseTo(180, 0);
  expect(Math.abs(facing(item))).toBeCloseTo(180, 0);
  // Mouse west (-x, 180 degrees): rotation 270, kept as -90.
  await page.mouse.move(west[0], west[1], { steps: 5 });
  item = await itemOf(page, marine);
  expect(item.rot).toBeCloseTo(-90, 0);
  expect(facing(item)).toBeCloseTo(-90, 0);
  await page.mouse.up();
  await page.keyboard.up('Control');

  // Released: moving the mouse no longer turns it; the camera did not move;
  // the selection is kept.
  await page.mouse.move(south[0], south[1], { steps: 3 });
  const s = await state(page);
  expect(s.items[0].rot).toBeCloseTo(-90, 0);
  expect(s.camera.target).toEqual(camera.target);
  expect(s.pick.selected).toBe(marine);
  // The list row shows the new facing.
  expect(Number(await page.locator(`#scene li[data-id="${marine}"] input.rot`).inputValue())).toBeCloseTo(-90, 0);
  expect(errors).toEqual([]);
});

test('negative: ctrl + left drag with nothing selected turns no unit (it grabs the ground)', async ({ page }) => {
  const errors = await open(page);
  const [marine] = await place(page, [['Marine', 0, 0]]);
  const north = await onWorld(page, [0, 3, 0]);
  const camera = (await state(page)).camera;
  await page.keyboard.down('Control');
  await page.mouse.move(north[0], north[1]);
  await page.mouse.down();
  await page.mouse.move(north[0] - 80, north[1], { steps: 5 });
  await page.mouse.up();
  await page.keyboard.up('Control');
  const s = await state(page);
  expect((await itemOf(page, marine)).rot).toBe(0);
  expect(s.pick.selected).toBe(null);
  expect(s.camera.target).not.toEqual(camera.target);
  expect(errors).toEqual([]);
});

test('right click on a unit: menu of all its animations; one plays once, then back to idle', async ({ page }) => {
  const errors = await open(page);
  const [marine] = await place(page, [['Marine', 0, 0]]);
  const idle = (await itemOf(page, marine)).sequenceName;
  const at = await onItem(page, marine);
  await page.mouse.click(at[0], at[1], { button: 'right' });
  const s = await state(page);
  const item = s.items[0];
  // All animations listed; the playing one (idle) marked; loop unchecked.
  expect(s.pick.menu).toEqual({ item: marine, entries: item.sequences, playing: [idle], loop: false });
  await expect(page.locator('#anim-menu')).toBeVisible();

  const choice = item.sequences.find((n) => /^attack/i.test(n)) ?? item.sequences.find((n) => n !== idle);
  const clicked = Date.now();
  await page.locator('#anim-menu').getByRole('button', { name: choice, exact: true }).click();
  // The menu stays open and marks the one-shot.
  await expect(page.locator('#anim-menu')).toBeVisible();
  expect((await pick(page)).menu.playing).toEqual([choice]);
  const playing = await itemOf(page, marine);
  expect(playing.sequenceName).toBe(choice);
  expect(playing.oneShot).toBe(choice);
  const length = playing.sequenceLength / playing.rate;
  console.log('one-shot', choice, 'length ms', length);

  await page.waitForFunction(([id, name]) => {
    const i = window.sc2viewer.state().items.find((x) => x.id === id);
    return i.sequenceName === name && i.oneShot === null;
  }, [marine, idle], { timeout: length + 5000 });
  const took = Date.now() - clicked;
  // It played through (not cut short), then the idle loops again, and the
  // menu marks the idle again.
  expect(took).toBeGreaterThan(length * 0.8);
  const back = await itemOf(page, marine);
  expect(back.sequenceName).toBe(idle);
  await expect.poll(async () => (await pick(page)).menu.playing).toEqual([idle]);
  // The unit's own animation is unchanged in its list row.
  expect(await page.locator(`#scene li[data-id="${marine}"] select.anim`).inputValue()).toBe(String(item.sequences.indexOf(idle)));
  expect(errors).toEqual([]);
});

test('menu "loop" checked: the picked animation keeps looping and becomes the unit\'s own', async ({ page }) => {
  const errors = await open(page);
  const [marine] = await place(page, [['Marine', 0, 0]]);
  const idle = (await itemOf(page, marine)).sequenceName;
  const at = await onItem(page, marine);
  await page.mouse.click(at[0], at[1], { button: 'right' });
  await page.locator('#anim-menu input.loop').check();
  expect((await pick(page)).menu.loop).toBe(true);
  const sequences = (await itemOf(page, marine)).sequences;
  const choice = sequences.find((n) => /^attack/i.test(n)) ?? sequences.find((n) => n !== idle);
  await page.locator('#anim-menu').getByRole('button', { name: choice, exact: true }).click();
  const playing = await itemOf(page, marine);
  expect(playing.oneShot).toBe(null);
  const length = playing.sequenceLength / playing.rate;
  // Past two whole lengths it still plays, and the menu still marks it.
  await page.waitForTimeout(length * 2 + 300);
  const later = await itemOf(page, marine);
  expect(later.sequenceName).toBe(choice);
  expect((await pick(page)).menu.playing).toEqual([choice]);
  // It is the unit's own now: list row and stored scene.
  expect(await page.locator(`#scene li[data-id="${marine}"] select.anim`).inputValue()).toBe(String(sequences.indexOf(choice)));
  expect((await sceneOf(page)).items[0].sequence).toBe(sequences.indexOf(choice));
  // The choice is kept for the next menu.
  // (The unit plays another animation now: a pixel on its picture as it is.)
  await page.keyboard.press('Escape');
  const now = await onItem(page, marine);
  await page.mouse.click(now[0], now[1], { button: 'right' });
  expect((await pick(page)).menu.loop).toBe(true);
  expect(errors).toEqual([]);
});

test('negative: no menu from a right drag over a unit, a right click on the ground; Escape closes it', async ({ page }) => {
  const errors = await open(page);
  const [marine] = await place(page, [['Marine', 0, 0]]);
  const at = await onItem(page, marine);
  const camera = (await state(page)).camera;
  // Right drag: pans, no menu.
  await page.mouse.move(at[0], at[1]);
  await page.mouse.down({ button: 'right' });
  await page.mouse.move(at[0] + 50, at[1], { steps: 5 });
  await page.mouse.up({ button: 'right' });
  let s = await state(page);
  expect(s.pick.menu).toBe(null);
  expect(s.camera.target).not.toEqual(camera.target);
  // Right click on the ground: no menu.
  await page.evaluate((v) => window.sc2viewer.view(v), VIEW);
  const ground = await onWorld(page, [3, 2, 0]);
  await page.mouse.click(ground[0], ground[1], { button: 'right' });
  expect((await pick(page)).menu).toBe(null);
  await expect(page.locator('#anim-menu')).toHaveCount(0);
  // Opened, then Escape: closed, the animation unchanged.
  const before = (await itemOf(page, marine)).sequenceName;
  await page.mouse.click(at[0], at[1], { button: 'right' });
  expect((await pick(page)).menu).not.toBe(null);
  await page.keyboard.press('Escape');
  s = await state(page);
  expect(s.pick.menu).toBe(null);
  expect(s.items[0].sequenceName).toBe(before);
  expect(s.items[0].oneShot).toBe(null);
  expect(errors).toEqual([]);
});

import { test, expect } from '../fixtures.mjs';
import { idle as settle, itemOf, onItem, open, screenOf as onWorld, state, view } from '../page.mjs';
import { sceneOf } from '../scene.mjs';

// Units under the mouse: mouse-over highlight, click selection, ctrl + left
// facing, and the right-click animation menu (src/page/features/pick).
// How the highlight and the glow look is an operator check (SPEC-VIEWER 14).

const VIEW = { yaw: -Math.PI / 2, pitch: 0.5, distance: 9, target: [0, 0, 0.8] };

/** Add units at [x, y] and return their ids, with the test camera. */
async function place(page, units) {
  const ids = [];
  for (const [id, x, y] of units) ids.push(await page.evaluate(([u, ux, uy]) => window.sc2viewer.addUnit(u, { x: ux, y: uy, pick: 0.5 }), [id, x, y]));
  await settle(page);
  await view(page, VIEW);
  return ids;
}

/**
 * Watch an item's engine frame on every drawn frame while sequence `name`
 * plays. Ends when another sequence plays (`wraps` 0) or when the frame
 * has gone back to the start `wraps` times. Returns the largest frame
 * seen and the wraps counted. Game time, not wall time.
 */
const watchFrames = (page, id, name, wraps = 0) =>
  page.evaluate(
    ([i, n, want]) =>
      new Promise((resolve) => {
        let largest = 0;
        let last = -1;
        let seen = 0;
        const step = () => {
          const item = window.sc2viewer.state().items.find((x) => x.id === i);
          if (item.sequenceName !== n) return resolve({ largest, wraps: seen, now: item.sequenceName, oneShot: item.oneShot });
          if (item.frame < last) seen++;
          last = item.frame;
          largest = Math.max(largest, item.frame);
          if (want > 0 && seen >= want) return resolve({ largest, wraps: seen, now: item.sequenceName, oneShot: item.oneShot });
          requestAnimationFrame(step);
        };
        requestAnimationFrame(step);
      }),
    [id, name, wraps],
  );
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

test('selected units stay highlighted; a unit not selected is not', async ({ page }) => {
  const errors = await open(page);
  const [marine, zealot, zergling] = await place(page, [['Marine', -1.5, 0], ['Zealot', 1.5, 0], ['Zergling', 0, 1.5]]);
  // The mouse on the ground.
  const ground = await onWorld(page, [3, -2, 0]);
  await page.mouse.move(ground[0], ground[1]);
  await expect.poll(async () => (await pick(page)).hovered).toBe(null);
  expect((await state(page)).items.map((i) => i.highlight)).toEqual([0, 0, 0]);
  await page.evaluate((ids) => window.SC2App.setSelection(ids), [marine, zealot]);
  await expect.poll(async () => (await itemOf(page, marine)).highlight).toBe(1);
  expect((await itemOf(page, zealot)).highlight).toBe(1);
  // Negative: the unit not selected is not highlighted.
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
  // Its owner has textures, so the menu has the skin row (SPEC-VIEWER 17.4). Negative: no other spec makes a skin of
  // scoba's Marine, so it offers Original alone, nothing is baked, and Unbake cannot be used.
  expect(s.pick.menu).toEqual({ item: marine, entries: item.sequences, playing: [idle], loop: false, skins: { value: 'original', label: 'Original', dropdown: true, choices: ['original'], rows: [{ name: 'original', label: 'Original', icons: [] }, { name: '', label: 'Add New Skin…', icons: [] }], bake: 'Unbake Skin', bakeDisabled: true, badge: null } });
  await expect(page.locator('#anim-menu')).toBeVisible();

  const choice = item.sequences.find((n) => /^attack/i.test(n)) ?? item.sequences.find((n) => n !== idle);
  await page.locator('#anim-menu').getByRole('button', { name: choice, exact: true }).click();
  // The menu stays open and marks the one-shot.
  await expect(page.locator('#anim-menu')).toBeVisible();
  expect((await pick(page)).menu.playing).toEqual([choice]);
  const playing = await itemOf(page, marine);
  expect(playing.sequenceName).toBe(choice);
  expect(playing.oneShot).toBe(choice);
  const length = playing.sequenceLength;

  // It plays through in game time (not cut short), then the idle plays again.
  const run = await watchFrames(page, marine, choice);
  console.log('one-shot', choice, 'length', length, JSON.stringify(run));
  expect(run.wraps).toBe(0);
  expect(run.largest).toBeGreaterThan(length * 0.8);
  expect(run.now).toBe(idle);
  expect(run.oneShot).toBe(null);
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
  // Past two whole loops it still plays, and the menu still marks it.
  const run = await watchFrames(page, marine, choice, 2);
  expect(run).toMatchObject({ wraps: 2, now: choice, oneShot: null });
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

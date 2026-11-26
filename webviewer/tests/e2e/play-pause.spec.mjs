import { test, expect } from '../fixtures.mjs';
import { frames, idle, itemOf, onItem, open, view } from '../page.mjs';

// The play/pause key (src/page/features/playback, R-VIEW-159): Ctrl+E
// when nothing is stored.
// - with an instance selected it holds that instance's animation at the
//   frame it shows; pressed again the animation runs on from there;
// - an instance that is not selected plays on; with nothing selected the
//   key pauses nothing and the status line says to select first;
// - the page takes the key either way: the browser's own Ctrl+E never acts;
// - the selection acts as one: any playing, all pause; all paused, all play;
// - a held one-shot stays a one-shot; an animation started after, and
//   restart, end the pause;
// - a text field keeps the key; a rebound key acts and Ctrl+E no longer
//   does.
// What is read is the renderer's: the instance's frame and time scale.

const KEY = 'Control+KeyE';
const CODE = 'KeyE';
const VIEW = { yaw: -Math.PI / 2, pitch: 0.5, distance: 12, target: [1.5, 0, 0.8] };

/** Two Marines side by side; the camera on them. */
async function marines(page) {
  const ids = [];
  for (const x of [0, 3]) ids.push(await page.evaluate((ux) => window.scobaeditor.addUnit('Marine', { x: ux, y: 0, pick: 0.5 }), x));
  await idle(page);
  await view(page, VIEW);
  await frames(page);
  return ids;
}

const select = (page, ids) => page.evaluate((list) => window.SCOBAEdit.setSelection(list), ids);

/** The distinct frames each of `ids` showed over `ms` of real time, one reading per drawn frame. */
const sample = (page, ids, ms = 500) =>
  page.evaluate(
    ([list, span]) =>
      new Promise((done) => {
        const seen = new Map(list.map((id) => [id, new Set()]));
        const start = performance.now();
        const step = () => {
          for (const item of window.scobaeditor.state().items) seen.get(item.id)?.add(item.frame);
          if (performance.now() - start >= span) done(Object.fromEntries(list.map((id) => [id, [...seen.get(id)]])));
          else requestAnimationFrame(step);
        };
        step();
      }),
    [ids, ms],
  );

/** Whether the page took the key (preventDefault), for each press from now on. */
const watchTaken = (page) =>
  page.evaluate((code) => {
    window.__taken = [];
    // Added after the viewer's own listeners: it sees what they decided.
    window.addEventListener('keydown', (e) => {
      if (e.code === code) window.__taken.push(e.defaultPrevented);
    });
  }, CODE);
const taken = (page) => page.evaluate(() => window.__taken);

test('the key holds the selected instance at its frame; again, it runs on from there; the other one plays on', async ({ page }) => {
  const errors = await open(page);
  const [a, b] = await marines(page);
  await watchTaken(page);
  await select(page, [a]);
  const before = await itemOf(page, a);
  expect(before.paused).toBe(false);
  expect(before.rate).toBeGreaterThan(0);
  // Pause well inside the animation, so a restart from its first frame would show as a frame before the held one.
  const length = before.sequenceLength;
  expect(length).toBeGreaterThan(1000);
  await page.waitForFunction(([id, len]) => {
    const f = window.scobaeditor.state().items.find((i) => i.id === id).frame;
    return f > len * 0.15 && f < len * 0.4;
  }, [a, length]);

  await page.keyboard.press(KEY);
  const held = await itemOf(page, a);
  expect(held).toMatchObject({ paused: true, rate: 0, sequenceName: before.sequenceName });
  const still = await sample(page, [a, b]);
  console.log('length', length, 'held at', held.frame, 'paused frames', still[a].length, 'other frames', still[b].length);
  expect(still[a]).toEqual([held.frame]);
  // Negative: the instance that is not selected is not paused and its frames move.
  expect(still[b].length).toBeGreaterThan(5);
  expect(await itemOf(page, b)).toMatchObject({ paused: false, rate: before.rate });

  // The key held down repeats; it counts once.
  await page.keyboard.down('Control');
  await page.keyboard.down(CODE);
  await page.keyboard.down(CODE);
  await page.keyboard.up(CODE);
  await page.keyboard.up('Control');
  expect((await itemOf(page, a)).paused).toBe(false);

  // It runs on from the held frame: not from the first frame.
  const on = await itemOf(page, a);
  expect(on.rate).toBe(before.rate);
  expect(on.frame).toBeGreaterThanOrEqual(held.frame);
  expect(on.frame - held.frame).toBeLessThan(length * 0.4);
  const moving = await sample(page, [a]);
  expect(moving[a].length).toBeGreaterThan(5);
  // With a selection the page took every press.
  expect(await taken(page)).toEqual([true, true, true]);
  expect((await page.evaluate(() => window.SCOBAEdit.statusLog())).shown.filter((t) => /^(paused|playing) /.test(t))).toEqual(['paused 1 instance', 'playing 1 instance']);
  expect(errors).toEqual([]);
});

test('negative: with nothing selected the key pauses nothing; the status says to select first; the browser does not get the key', async ({ page }) => {
  const errors = await open(page);
  const [a, b] = await marines(page);
  await watchTaken(page);
  const before = await itemOf(page, a);
  await page.keyboard.press(KEY);
  const after = await sample(page, [a, b]);
  for (const id of [a, b]) {
    expect(await itemOf(page, id)).toMatchObject({ paused: false, rate: before.rate });
    expect(after[id].length).toBeGreaterThan(5);
  }
  expect(await taken(page)).toEqual([true]);
  const shown = (await page.evaluate(() => window.SCOBAEdit.statusLog())).shown;
  expect(shown.filter((t) => /^(paused|playing) /.test(t))).toEqual([]);
  expect(shown).toContain('Ctrl+E: select an instance first');
  expect(errors).toEqual([]);
});

test('the selection acts as one: one paused and one playing, the key pauses both; again, both play', async ({ page }) => {
  const errors = await open(page);
  const [a, b] = await marines(page);
  await select(page, [a]);
  await page.keyboard.press(KEY);
  expect([(await itemOf(page, a)).paused, (await itemOf(page, b)).paused]).toEqual([true, false]);
  const heldA = (await itemOf(page, a)).frame;

  await select(page, [a, b]);
  await page.keyboard.press(KEY);
  const both = [await itemOf(page, a), await itemOf(page, b)];
  expect(both.map((i) => [i.paused, i.rate])).toEqual([[true, 0], [true, 0]]);
  // The one paused before stays at its frame.
  const still = await sample(page, [a, b]);
  expect(still[a]).toEqual([heldA]);
  expect(still[b]).toEqual([both[1].frame]);

  await page.keyboard.press(KEY);
  const moving = await sample(page, [a, b]);
  for (const id of [a, b]) {
    const item = await itemOf(page, id);
    expect(item.paused).toBe(false);
    expect(item.rate).toBeGreaterThan(0);
    expect(moving[id].length).toBeGreaterThan(5);
  }
  expect(errors).toEqual([]);
});

test('a held one-shot stays a one-shot; an animation started from the menu, and restart, end the pause', async ({ page }) => {
  const errors = await open(page);
  const [a] = await marines(page);
  await select(page, [a]);
  const idleName = (await itemOf(page, a)).sequenceName;
  const at = await onItem(page, a);
  await page.mouse.click(at[0], at[1], { button: 'right' });
  await expect(page.locator('#anim-menu')).toBeVisible();
  const names = (await itemOf(page, a)).sequences;
  const choice = names.find((n) => /^attack/i.test(n)) ?? names.find((n) => n !== idleName);
  await page.locator('#anim-menu').getByRole('button', { name: choice, exact: true }).click();
  expect((await itemOf(page, a)).oneShot).toBe(choice);

  // Paused during the one-shot: it holds, and does not go back to the idle animation while held.
  await page.keyboard.press(KEY);
  const held = await itemOf(page, a);
  expect(held).toMatchObject({ paused: true, rate: 0, oneShot: choice, sequenceName: choice });
  const still = await sample(page, [a], Math.max(600, held.sequenceLength + 300));
  expect(still[a]).toEqual([held.frame]);
  expect(await itemOf(page, a)).toMatchObject({ paused: true, oneShot: choice, sequenceName: choice });

  // An animation started from the menu plays: the pause ends.
  await page.locator('#anim-menu').getByRole('button', { name: choice, exact: true }).click();
  const played = await itemOf(page, a);
  expect(played).toMatchObject({ paused: false, oneShot: choice });
  expect(played.rate).toBeGreaterThan(0);
  // It ends as any one-shot: back to the idle animation.
  await expect.poll(async () => (await itemOf(page, a)).oneShot, { timeout: 15_000 }).toBe(null);

  // Restart ends a pause too.
  await page.keyboard.press(KEY);
  expect((await itemOf(page, a)).paused).toBe(true);
  await page.evaluate(() => window.scobaeditor.restart());
  const restarted = await itemOf(page, a);
  expect(restarted.paused).toBe(false);
  expect(restarted.rate).toBeGreaterThan(0);
  expect((await sample(page, [a]))[a].length).toBeGreaterThan(5);
  expect(errors).toEqual([]);
});

test('a text field keeps the key; a rebound key acts and Ctrl+E no longer does', async ({ page }) => {
  await page.addInitScript(([key, value]) => localStorage.setItem(key, value), ['viewer.input', JSON.stringify({ keys: { playPause: { code: 'KeyP', key: 'p', mods: [] } } })]);
  const errors = await open(page);
  const [a] = await marines(page);
  await select(page, [a]);
  // Negative first: Ctrl+E is no longer the binding.
  await page.keyboard.press(KEY);
  expect((await itemOf(page, a)).paused).toBe(false);
  // Negative: typed into a text field, the key is the field's.
  const field = page.locator('#instance-search');
  await field.focus();
  expect(await page.evaluate(() => document.activeElement?.id)).toBe('instance-search');
  await page.keyboard.press('KeyP');
  expect(await field.inputValue()).toBe('p');
  expect((await itemOf(page, a)).paused).toBe(false);
  await field.fill('');
  await field.blur();
  // The search shows every instance again, and the selection is as it was.
  expect((await page.evaluate(() => window.scobaeditor.state())).pick.selection).toEqual([a]);
  await page.keyboard.press('KeyP');
  expect(await itemOf(page, a)).toMatchObject({ paused: true, rate: 0 });
  expect((await sample(page, [a]))[a].length).toBe(1);
  expect(errors).toEqual([]);
});

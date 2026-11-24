import { test, expect } from '@playwright/test';
import { api } from './api.mjs';
import { reloadScene, sceneOf } from './scene.mjs';

// HD textures in the view (src/page/features/hd, src/games/sc2/server/textures.ts hdRoute):
// - a model with a texture that has an upscaled file shows the HD set from
//   the start; its right-click menu has an "hd" checkbox;
// - Ctrl+H switches the selected instances between the two sets;
// - Ctrl+L switches the menu's "loop" choice.
// The tests' cache (tools/hdtex-fixture.mjs) has one HD texture: the
// Zergling's skin, which is the Zealot's picture, so the sets differ in the view.

const VIEW = { yaw: -Math.PI / 2, pitch: 0.5, distance: 6, target: [0, 0, 0.5] };
const SKIN = 'assets\\textures\\zergling_diffuse.dds';

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

const idle = (page) => page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 15_000 });
const state = (page) => page.evaluate(() => window.sc2viewer.state());
const item = async (page, id) => (await state(page)).items.find((i) => i.id === id);
const hdOf = async (page, id) => {
  const found = await item(page, id);
  return { hd: found.hd, layers: found.hdLayers, applied: found.hdApplied };
};
// A pixel on the unit's picture: the mouse hit goes by pixel.
const onItem = (page, id) => page.evaluate((i) => window.sc2viewer.itemPixel(i), id);
const selectRow = (page, id) => page.locator(`#scene li[data-id="${id}"] .head .name`).click();

/** A unit standing still (no animation), alone in the view, the grid off. */
async function place(page, unit, options = {}) {
  const id = await page.evaluate(([u, o]) => window.sc2viewer.addUnit(u, { x: 0, y: 0, pick: 0.5, sequence: -1, ...o }), [unit, options]);
  await idle(page);
  await page.evaluate((v) => {
    window.sc2viewer.setGrid(false);
    window.sc2viewer.view(v);
  }, VIEW);
  return id;
}

/** The mean colour of the drawn pixels, once the frame after a change is drawn. */
async function colour(page) {
  await idle(page);
  await page.mouse.move(1000, 80);
  await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))));
  return (await page.evaluate(() => window.sc2viewer.colorStats())).mean;
}
const distance = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);

async function menu(page, id) {
  const at = await onItem(page, id);
  await page.mouse.click(at[0], at[1], { button: 'right' });
  await expect(page.locator('#anim-menu')).toBeVisible();
}

test('the server lists the textures with an HD file and serves them; nothing else', async ({ request }) => {
  const hdAsset = (path) => `${api.x('hd-asset')}?${new URLSearchParams({ path })}`;
  expect((await (await request.get(api.x('hd-textures'))).json()).assets).toEqual([SKIN, 'assets\\textures\\roach_diffuse.dds']);
  const hd = await request.get(hdAsset('Assets/Textures/Zergling_Diffuse.dds'));
  expect(hd.status()).toBe(200);
  const standard = await request.get(api.asset(SKIN));
  expect(standard.status()).toBe(200);
  const [hdBytes, standardBytes] = [await hd.body(), await standard.body()];
  expect(hdBytes.subarray(0, 4).toString('latin1')).toBe('DDS ');
  expect(hdBytes.equals(standardBytes)).toBe(false);
  // Negative: a texture with no HD file, and a request with no path.
  expect((await request.get(hdAsset('assets\\textures\\zergling_normal.dds'))).status()).toBe(404);
  expect((await request.get(hdAsset('..\\manifest.json'))).status()).toBe(404);
  expect((await request.get(api.x('hd-asset'))).status()).toBe(400);
  // Negative: nothing below the route names.
  expect((await request.get(`${api.x('hd-textures')}/x`)).status()).toBe(404);
  expect((await request.get(`${api.x('hd-asset')}/x?path=x`)).status()).toBe(404);
});

test('a model with both sets shows HD from the start; the menu\'s "hd" checkbox switches the set in the view', async ({ page }) => {
  const errors = await open(page);
  const zergling = await place(page, 'Zergling');
  const first = await hdOf(page, zergling);
  expect(first.hd).toBe(true);
  expect(first.layers).toBeGreaterThan(0);
  expect(first.applied).toBe(first.layers);
  const hd = await colour(page);
  // The same state read twice: how much two reads differ with nothing changed.
  const noise = distance(hd, await colour(page));

  await menu(page, zergling);
  await expect(page.locator('#anim-menu input.hd')).toBeChecked();
  expect((await state(page)).pick.menu.hd).toBe(true);
  await page.locator('#anim-menu input.hd').uncheck();
  await expect.poll(async () => (await hdOf(page, zergling)).applied).toBe(0);
  expect((await hdOf(page, zergling)).hd).toBe(false);
  await page.keyboard.press('Escape');
  const standard = await colour(page);
  console.log(`zergling mean colour: hd ${hd.map((v) => v.toFixed(1))}, standard ${standard.map((v) => v.toFixed(1))}, noise ${noise.toFixed(2)}`);
  expect(noise).toBeLessThan(1);
  expect(distance(hd, standard)).toBeGreaterThan(8);

  await menu(page, zergling);
  await expect(page.locator('#anim-menu input.hd')).not.toBeChecked();
  await page.locator('#anim-menu input.hd').check();
  await expect.poll(async () => (await hdOf(page, zergling)).applied).toBe(first.layers);
  await page.keyboard.press('Escape');
  expect(distance(hd, await colour(page))).toBeLessThan(1);
  expect(errors).toEqual([]);
});

test('negative: a model with one set has no "hd" checkbox, and Ctrl+H changes nothing for it', async ({ page }) => {
  const errors = await open(page);
  const marine = await place(page, 'Marine');
  expect(await hdOf(page, marine)).toEqual({ hd: true, layers: 0, applied: 0 });
  await menu(page, marine);
  await expect(page.locator('#anim-menu input.loop')).toHaveCount(1);
  await expect(page.locator('#anim-menu input.hd')).toHaveCount(0);
  expect((await state(page)).pick.menu.hd).toBeUndefined();
  await page.keyboard.press('Escape');
  await selectRow(page, marine);
  // Selected, so lit (pick): the colour to compare is the selected one.
  const before = await colour(page);
  await page.keyboard.press('Control+h');
  await expect(page.locator('#status')).toHaveText('no HD textures for the selected');
  expect(await hdOf(page, marine)).toEqual({ hd: true, layers: 0, applied: 0 });
  expect(distance(before, await colour(page))).toBeLessThan(1);
  expect(errors).toEqual([]);
});

test('Ctrl+H switches the selected instance only, and back; not with nothing selected, not from a text field', async ({ page }) => {
  const errors = await open(page);
  const near = await place(page, 'Zergling');
  const far = await place(page, 'Zergling', { x: 3 });
  const layers = (await hdOf(page, near)).layers;

  // Negative: nothing is selected.
  await page.keyboard.press('Control+h');
  expect((await hdOf(page, near)).applied).toBe(layers);
  expect((await hdOf(page, far)).applied).toBe(layers);

  await selectRow(page, near);
  const hd = await colour(page);
  await page.keyboard.press('Control+h');
  await expect.poll(async () => (await hdOf(page, near)).applied).toBe(0);
  await expect(page.locator('#status')).toHaveText('standard textures: 1 instance');
  // The other instance of the same model keeps its HD set.
  expect(await hdOf(page, far)).toEqual({ hd: true, layers, applied: layers });
  expect(distance(hd, await colour(page))).toBeGreaterThan(2);

  // Negative: the key in a text field is the field's.
  await page.locator('#search-units').focus();
  await page.keyboard.press('Control+h');
  expect((await hdOf(page, near)).hd).toBe(false);
  await page.locator('#search-units').blur();

  await page.keyboard.press('Control+h');
  await expect.poll(async () => (await hdOf(page, near)).applied).toBe(layers);
  await expect(page.locator('#status')).toHaveText('HD textures: 1 instance');
  expect(distance(hd, await colour(page))).toBeLessThan(1);

  // An open menu follows the key.
  await menu(page, near);
  await expect(page.locator('#anim-menu input.hd')).toBeChecked();
  await page.keyboard.press('Control+h');
  await expect(page.locator('#anim-menu input.hd')).not.toBeChecked();
  expect(errors).toEqual([]);
});

test('Ctrl+H and Ctrl+L never reach the browser: no selection, a selection, a text field, the texture window', async ({ page }) => {
  const errors = await open(page);
  const zergling = await place(page, 'Zergling');
  /** Whether a keydown sent to `where` had its default action cancelled (true: the browser does nothing). */
  const cancelled = (key, where, mods = { ctrlKey: true }) =>
    page.evaluate(([k, w, m]) => {
      const target = w === 'frame' ? document.getElementById('texture-frame').contentDocument.body : w === 'field' ? document.getElementById('search-units') : document.body;
      if (w === 'field') target.focus();
      const sent = new (target.ownerDocument.defaultView.KeyboardEvent)('keydown', { key: k, bubbles: true, cancelable: true, ...m });
      const done = !target.dispatchEvent(sent);
      if (w === 'field') target.blur();
      return done;
    }, [key, where, mods]);

  // Nothing selected: consumed, and the toast says why nothing happened.
  expect(await cancelled('h', 'page')).toBe(true);
  expect(await cancelled('l', 'page')).toBe(true);
  await expect(page.locator('#status')).toHaveText('Ctrl+L: select an instance first');
  expect((await hdOf(page, zergling)).hd).toBe(true);
  // A text field: consumed, and the instance is unchanged.
  expect(await cancelled('h', 'field')).toBe(true);
  expect((await hdOf(page, zergling)).hd).toBe(true);
  // Selected: consumed, and it acts.
  await selectRow(page, zergling);
  expect(await cancelled('h', 'page')).toBe(true);
  await expect.poll(async () => (await hdOf(page, zergling)).hd).toBe(false);
  // The texture window's page: consumed there too.
  await page.locator(`#scene li[data-id="${zergling}"] .head .name`).dblclick();
  await expect(page.locator('#texture-window')).toBeVisible();
  await page.waitForFunction(() => document.getElementById('texture-frame').contentDocument.readyState === 'complete' && window.sc2viewer.textureWindow().originals !== 'loading');
  expect(await cancelled('h', 'frame')).toBe(true);
  expect(await cancelled('l', 'frame')).toBe(true);
  // Negative: other keys keep the browser's meaning.
  expect(await cancelled('j', 'page')).toBe(false);
  expect(await cancelled('h', 'page', { ctrlKey: true, shiftKey: true })).toBe(false);
  expect(await cancelled('h', 'page', {})).toBe(false);
  expect(await cancelled('j', 'frame')).toBe(false);
  expect(errors).toEqual([]);
});

test('Ctrl+L switches the "loop" choice when a unit is selected; the menu shows it', async ({ page }) => {
  const errors = await open(page);
  const marine = await place(page, 'Marine');
  expect((await state(page)).pick.loop).toBe(false);
  // Negative: nothing is selected.
  await page.keyboard.press('Control+l');
  expect((await state(page)).pick.loop).toBe(false);

  await selectRow(page, marine);
  await page.keyboard.press('Control+l');
  expect((await state(page)).pick.loop).toBe(true);
  await expect(page.locator('#status')).toHaveText('loop on');
  await menu(page, marine);
  await expect(page.locator('#anim-menu input.loop')).toBeChecked();
  // With the choice on, a picked animation loops: it becomes the unit's own.
  const standing = await item(page, marine);
  const name = standing.sequences.find((s) => s !== standing.sequenceName && /Walk/.test(s));
  expect(name).toBeTruthy();
  await page.locator('#anim-menu button', { hasText: new RegExp(`^${name}$`) }).click();
  expect((await item(page, marine)).oneShot).toBeNull();
  expect((await item(page, marine)).sequenceName).toBe(name);

  await page.keyboard.press('Control+l');
  await expect(page.locator('#anim-menu input.loop')).not.toBeChecked();
  expect((await state(page)).pick.loop).toBe(false);
  await expect(page.locator('#status')).toHaveText('loop off');
  expect(errors).toEqual([]);
});

test('the grid glows blue around a model with a 2048 texture, stock or upscaled, and green around the rest', async ({ page }) => {
  const errors = await open(page);
  // Far apart: no glow reaches another. The mouse stays off the view (its glow is green).
  // [name here, unit, x, dataset]
  const UNITS = [
    ['Remastered', 'Marine', 0, 'scoba'], // the remastered Marine: stock textures of 2048, no upscaled file
    ['Roach', 'Roach', 30, 'scoba'], // stock 1024 or less, an upscaled file of 2048
    ['Zergling', 'Zergling', 60, 'scoba'], // an upscaled file, but no larger than 1024: not HD
    ['Marine', 'Marine', 90, 'stock'], // the old Marine model: one texture set, none of 2048
  ];
  const ids = {};
  for (const [name, unit, x, dataset] of UNITS) ids[name] = await page.evaluate(([u, ux, d]) => window.sc2viewer.addUnit(u, { x: ux, y: 0, pick: 0.5, sequence: -1, dataset: d }), [unit, x, dataset]);
  await idle(page);
  // The grid line on the hex sides x = k ± 1.5, left and right of the unit at (k, 0), seen from above.
  const border = async (x) => {
    await page.evaluate((tx) => window.sc2viewer.view({ yaw: -Math.PI / 2, pitch: Math.PI / 2 - 0.01, distance: 8, target: [tx, 0, 0] }), x);
    await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))));
    const peaks = await page.evaluate((tx) => window.sc2viewer.groundPeaks([[tx - 1.5, 0], [tx + 1.5, 0]], 1), x);
    return peaks.map((peak) => peak.rgb);
  };
  const seen = {};
  for (const [name, , x] of UNITS) {
    const found = await item(page, ids[name]);
    seen[name] = { largest: found.largestTexture, hdLayers: found.hdLayers, blue: found.blueGlow, line: await border(x) };
  }
  console.log(`glow ${JSON.stringify(seen)}`);
  expect(seen.Remastered).toMatchObject({ largest: 2048, hdLayers: 0, blue: true });
  expect(seen.Roach).toMatchObject({ largest: 2048, blue: true });
  expect(seen.Roach.hdLayers).toBeGreaterThan(0);
  // Negative: an upscaled file alone does not make a model HD (the operator's Blackhammer, 2026-11-22).
  expect(seen.Zergling.hdLayers).toBeGreaterThan(0);
  expect(seen.Zergling.largest).toBeLessThan(2048);
  expect(seen.Zergling.blue).toBe(false);
  expect(seen.Marine).toMatchObject({ hdLayers: 0, blue: false });
  expect(seen.Marine.largest).toBeLessThan(2048);
  for (const unit of ['Remastered', 'Roach']) {
    for (const [r, g, b] of seen[unit].line) {
      expect(b, unit).toBeGreaterThan(g + 15);
      expect(b, unit).toBeGreaterThan(r + 40);
    }
  }
  for (const unit of ['Zergling', 'Marine']) {
    for (const [r, g, b] of seen[unit].line) {
      expect(g, unit).toBeGreaterThan(b + 15);
      expect(g, unit).toBeGreaterThan(r + 40);
    }
  }
  expect(errors).toEqual([]);
});

test('the standard set of an instance is kept in the scene; a reload shows it again', async ({ page }) => {
  const errors = await open(page);
  const zergling = await place(page, 'Zergling');
  expect((await sceneOf(page)).items[0].options.hd).toBe(true);
  await selectRow(page, zergling);
  await page.keyboard.press('Control+h');
  await expect.poll(async () => (await hdOf(page, zergling)).applied).toBe(0);
  expect((await sceneOf(page)).items[0].options.hd).toBe(false);
  // Negative: the address holds none of it.
  expect(new URL(page.url()).hash).toBe('');
  await reloadScene(page);
  const again = (await state(page)).items[0];
  expect(again.hd).toBe(false);
  expect(again.hdLayers).toBeGreaterThan(0);
  expect(again.hdApplied).toBe(0);
  expect(errors).toEqual([]);
});

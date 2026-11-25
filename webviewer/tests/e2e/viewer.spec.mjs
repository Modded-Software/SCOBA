import { allowErrors, test, expect } from '../fixtures.mjs';
import { idle, open as openPage, state, watch } from '../page.mjs';
import { reloadScene, sceneOf } from '../scene.mjs';

const MARINE = 'mods\\liberty.sc2mod\\base.sc2assets\\assets\\units\\terran\\marine\\marine.m3';
const ZEALOT = 'mods\\liberty.sc2mod\\base.sc2assets\\assets\\units\\protoss\\zealot\\zealot.m3';

/** Page errors and failed responses, so every test can assert none. */
async function open(page) {
  const problems = watch(page);
  page.on('response', (r) => {
    if (r.status() >= 400) problems.push(`http ${r.status()}: ${r.url()}`);
  });
  // These tests cover raw model files, which live on the models tab.
  const errors = await openPage(page, { tab: 'models' });
  return { problems, errors };
}

/** Add a model through the UI: type in the search box, click the result. */
async function addByUi(page, query, path) {
  const before = await page.locator('#scene li').count();
  await page.fill('#search-models', query);
  await page.locator(`#models button[data-path="${path.replaceAll('\\', '\\\\')}"]`).click();
  await expect(page.locator('#scene li')).toHaveCount(before + 1);
  await idle(page);
}

/** Wait for the next drawn frame, then read whether each item was drawn. */
const drawn = async (page) => {
  await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))));
  return (await state(page)).items.map((item) => item.drawn);
};

test('empty page: canvas, search box, empty scene', async ({ page }) => {
  const { problems } = await open(page);
  await expect(page.locator('canvas#view')).toBeVisible();
  await expect(page.locator('#search-models')).toBeVisible();
  await expect(page.locator('#scene li')).toHaveCount(0);
  const s = await state(page);
  expect(s.items).toEqual([]);
  expect(s.sceneInstances).toBe(0);
  expect(problems).toEqual([]);
});

test('search lists models and narrows as typed', async ({ page }) => {
  const { problems } = await open(page);
  await page.fill('#search-models', 'marine');
  await expect(page.locator('#models button').first()).toBeVisible();
  expect(await page.locator('#models button').count()).toBeGreaterThan(1);
  await page.fill('#search-models', 'terran\\marine\\marine.m3');
  await expect(page.locator('#models button')).toHaveCount(1);
  await page.fill('#search-models', 'no-such-model-xyzzy');
  await expect(page.locator('#models button')).toHaveCount(0);
  expect(problems).toEqual([]);
});

test('adding a model loads it with its textures and draws it', async ({ page }) => {
  const textures = [];
  page.on('response', (r) => {
    if (r.url().includes('/asset?')) textures.push(r.status());
  });
  const { problems } = await open(page);
  await addByUi(page, 'terran\\marine\\marine.m3', MARINE);
  const s = await state(page);
  expect(s.items).toHaveLength(1);
  expect(s.items[0]).toMatchObject({ path: MARINE, loaded: true });
  expect(s.items[0].sequences.length).toBeGreaterThan(0);
  expect(s.items[0].texturesLoaded).toBeGreaterThan(0);
  expect(textures.length).toBeGreaterThan(0);
  expect(textures.every((code) => code === 200)).toBe(true);
  expect(await drawn(page)).toEqual([true]);
  expect(problems).toEqual([]);
});

test('two models share one scene and can be removed one by one', async ({ page }) => {
  const { problems } = await open(page);
  await addByUi(page, 'terran\\marine\\marine.m3', MARINE);
  await addByUi(page, 'protoss\\zealot\\zealot.m3', ZEALOT);
  const s = await state(page);
  expect(s.items.map((i) => i.path)).toEqual([MARINE, ZEALOT]);
  expect(s.items.every((i) => i.loaded)).toBe(true);
  expect(s.sceneInstances).toBe(2);
  // The second model is placed beside the first, not on top of it.
  expect(s.items[1].x).not.toBe(s.items[0].x);
  expect(await drawn(page)).toEqual([true, true]);

  // Remove the marine: the zealot stays.
  await page.locator('#scene li').first().locator('button.remove').click();
  await expect(page.locator('#scene li')).toHaveCount(1);
  const after = await state(page);
  expect(after.items.map((i) => i.path)).toEqual([ZEALOT]);
  expect(after.sceneInstances).toBe(1);

  await page.locator('#scene li button.remove').click();
  await expect(page.locator('#scene li')).toHaveCount(0);
  expect((await state(page)).sceneInstances).toBe(0);
  expect(problems).toEqual([]);
});

test('the same model can be added twice as separate instances', async ({ page }) => {
  const { problems } = await open(page);
  await addByUi(page, 'terran\\marine\\marine.m3', MARINE);
  await addByUi(page, 'terran\\marine\\marine.m3', MARINE);
  const s = await state(page);
  expect(s.items).toHaveLength(2);
  expect(s.items[0].id).not.toBe(s.items[1].id);
  expect(s.sceneInstances).toBe(2);
  expect(problems).toEqual([]);
});

test('position, rotation and scale inputs move the engine instance', async ({ page }) => {
  const { problems } = await open(page);
  await addByUi(page, 'terran\\marine\\marine.m3', MARINE);
  const row = page.locator('#scene li').first();
  const set = async (field, value) => {
    await row.locator(`input.${field}`).fill(value);
    await row.locator(`input.${field}`).dispatchEvent('change');
    return (await state(page)).items[0];
  };
  let item = await set('x', '2');
  expect(item.x).toBe(2);
  expect(item.location[0]).toBeCloseTo(2, 5);
  item = await set('y', '-1.5');
  expect(item.location[1]).toBeCloseTo(-1.5, 5);
  const rot0 = item.rotation;
  item = await set('rot', '90');
  expect(item.rot).toBe(90);
  expect(item.rotation).not.toEqual(rot0);
  // 90 degrees about the up axis: quaternion (0, 0, sin 45, cos 45).
  expect(Math.abs(item.rotation[2])).toBeCloseTo(Math.SQRT1_2, 3);
  const scale0 = item.engineScale;
  item = await set('scale', '2');
  expect(item.scale).toBe(2);
  item.engineScale.forEach((v, k) => expect(v).toBeCloseTo(scale0[k] * 2, 5));

  // Negative: junk input changes nothing.
  await row.locator('input.x').evaluate((el) => {
    el.value = '';
    el.dispatchEvent(new Event('change', { bubbles: true }));
  });
  item = (await state(page)).items[0];
  expect(item.x).toBe(2);
  expect(item.location[0]).toBeCloseTo(2, 5);
  expect(problems).toEqual([]);
});

test('an animation can be chosen per instance and it plays', async ({ page }) => {
  const { problems } = await open(page);
  await addByUi(page, 'terran\\marine\\marine.m3', MARINE);
  await addByUi(page, 'terran\\marine\\marine.m3', MARINE);

  const first = page.locator('#scene li').nth(0).locator('select.anim');
  const options = await first.locator('option').allTextContents();
  expect(options.length).toBeGreaterThan(2);
  expect(options[0]).toBe('(none)');

  const pick = options.findIndex((name) => /^Walk/.test(name));
  expect(pick).toBeGreaterThan(0);
  await first.selectOption({ index: pick });

  let s = await state(page);
  expect(s.items[0].sequence).toBe(pick - 1);
  expect(s.items[0].sequenceName).toBe(options[pick]);
  // Negative: the other instance keeps its own animation.
  expect(s.items[1].sequence).not.toBe(pick - 1);

  // It plays: the engine frame advances.
  const f0 = s.items[0].frame;
  await page.waitForFunction((f) => Math.abs(window.sc2viewer.state().items[0].frame - f) > 150, f0);

  // Negative: with no animation on either instance, the frame stands still
  // while the page draws on (several frames, measured in drawn frames).
  await first.selectOption({ index: 0 });
  await page.locator('#scene li').nth(1).locator('select.anim').selectOption({ index: 0 });
  s = await state(page);
  expect(s.items[0].sequence).toBe(-1);
  expect(s.items[1].sequence).toBe(-1);
  const still = s.items[0].frame;
  for (let k = 0; k < 5; k++) await drawn(page);
  expect((await state(page)).items[0].frame).toBe(still);
  expect(problems).toEqual([]);
});

test('mouse orbits, zooms and pans the camera', async ({ page }) => {
  const { problems } = await open(page);
  await addByUi(page, 'terran\\marine\\marine.m3', MARINE);
  const box = await page.locator('canvas#view').boundingBox();
  const cx = box.x + box.width / 2;
  const cy = box.y + box.height / 2;
  const c0 = (await state(page)).camera;

  // Middle drag orbits (around the ground under the mouse: see camera.spec).
  await page.mouse.move(cx, cy);
  await page.mouse.down({ button: 'middle' });
  await page.mouse.move(cx + 120, cy + 40, { steps: 5 });
  await page.mouse.up({ button: 'middle' });
  const c1 = (await state(page)).camera;
  expect(c1.yaw).not.toBeCloseTo(c0.yaw, 3);
  expect(c1.pitch).not.toBeCloseTo(c0.pitch, 3);
  // A rigid move: the eye keeps its distance to the target.
  expect(c1.distance).toBeCloseTo(c0.distance, 4);

  // Negative: moving without a button held does nothing.
  await page.mouse.move(cx - 80, cy - 80, { steps: 3 });
  expect((await state(page)).camera).toEqual(c1);

  await page.mouse.move(cx, cy);
  // The wheel zoom glides: wait until it has arrived.
  const settled = () => expect.poll(async () => (await state(page)).camera.zoomGoal).toBe(null);
  await page.mouse.wheel(0, 400);
  await settled();
  const c2 = (await state(page)).camera;
  expect(c2.distance).toBeGreaterThan(c1.distance);
  await page.mouse.wheel(0, -800);
  await settled();
  expect((await state(page)).camera.distance).toBeLessThan(c2.distance);

  const c3 = (await state(page)).camera;
  await page.mouse.down({ button: 'right' });
  await page.mouse.move(cx + 60, cy + 30, { steps: 4 });
  await page.mouse.up({ button: 'right' });
  const c4 = (await state(page)).camera;
  expect(c4.target).not.toEqual(c3.target);
  expect(c4.yaw).toBeCloseTo(c3.yaw, 6);

  // Pitch stays inside the poles however far the drag goes.
  await page.mouse.move(cx, cy);
  await page.mouse.down({ button: 'middle' });
  await page.mouse.move(cx, cy + 3000, { steps: 10 });
  await page.mouse.up({ button: 'middle' });
  expect(Math.abs((await state(page)).camera.pitch)).toBeLessThan(Math.PI / 2);
  expect(problems).toEqual([]);
});

test('drag sensitivity: rotate 0.004 rad per pixel, pan 0.0006 x distance per pixel', async ({ page }) => {
  await open(page);
  const box = await page.locator('canvas#view').boundingBox();
  const cx = box.x + box.width / 2;
  const cy = box.y + box.height / 2;
  const c0 = (await state(page)).camera;

  // Middle drag 100 px right: yaw turns 0.4 rad (was 1.0). Pitch unchanged.
  await page.mouse.move(cx, cy);
  await page.mouse.down({ button: 'middle' });
  await page.mouse.move(cx + 100, cy, { steps: 5 });
  await page.mouse.up({ button: 'middle' });
  const c1 = (await state(page)).camera;
  expect(c0.yaw - c1.yaw).toBeCloseTo(0.4, 3);
  expect(c1.pitch).toBeCloseTo(c0.pitch, 6);

  // Right drag 100 px right: the target moves 0.06 x distance (was 0.15 x).
  await page.mouse.move(cx, cy);
  await page.mouse.down({ button: 'right' });
  await page.mouse.move(cx + 100, cy, { steps: 5 });
  await page.mouse.up({ button: 'right' });
  const c2 = (await state(page)).camera;
  const moved = Math.hypot(...c2.target.map((v, i) => v - c1.target[i]));
  expect(moved).toBeCloseTo(0.06 * c1.distance, 3);
  // Negative: panning does not turn the camera.
  expect(c2.yaw).toBeCloseTo(c1.yaw, 6);
});

test('a model that fails to load is reported and not added', async ({ page }) => {
  allowErrors(/^http 404 GET .*\/api\/sc2\/file\?.*path=mods%5Cnope%5Cnope\.m3/, /^console\.error: Failed to load resource: the server responded with a status of 4\d\d/, /^console\.warning: viewer: Failed to fetch a resource: .*nope/);
  await open(page);
  await addByUi(page, 'terran\\marine\\marine.m3', MARINE);
  const result = await page.evaluate(() => window.sc2viewer.add('mods\\nope\\nope.m3').then(() => 'added', (e) => 'failed: ' + e.message));
  expect(result).toContain('failed');
  await expect(page.locator('#status')).toContainText('nope.m3');
  const s = await state(page);
  expect(s.items.map((i) => i.path)).toEqual([MARINE]);
  expect(s.sceneInstances).toBe(1);
  await expect(page.locator('#scene li')).toHaveCount(1);
});

test('clear: an empty scene asks nothing; it asks first; cancel, Escape and the backdrop keep everything; yes empties it, stored too', async ({ page }) => {
  const { problems } = await open(page);
  // Negative: with an empty scene it asks nothing and removes nothing.
  await page.locator('#clear').click();
  await expect(page.locator('#clear-dialog')).toBeHidden();
  expect((await state(page)).items).toEqual([]);
  await addByUi(page, 'terran\\marine\\marine.m3', MARINE);
  await addByUi(page, 'protoss\\zealot\\zealot.m3', ZEALOT);
  const stored = (await sceneOf(page)).items;
  const dialog = page.locator('#clear-dialog');
  await page.locator('#clear').click();
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText('2 instances');
  // Nothing goes while the question is open.
  expect((await state(page)).items.length).toBe(2);
  await page.locator('#clear-no').click();
  await expect(dialog).toBeHidden();
  await page.locator('#clear').click();
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  await page.locator('#clear').click();
  const box = await dialog.boundingBox();
  await page.mouse.click(box.x + box.width / 2, box.y + box.height + 40);
  await expect(dialog).toBeHidden();
  const s = await state(page);
  expect(s.items.map((i) => i.path)).toEqual([MARINE, ZEALOT]);
  expect(s.sceneInstances).toBe(2);
  expect((await sceneOf(page)).items).toEqual(stored);
  // Yes empties the scene, stored too.
  await page.locator('#clear').click();
  await page.locator('#clear-yes').click();
  await expect(page.locator('#clear-dialog')).toBeHidden();
  await expect(page.locator('#scene li')).toHaveCount(0);
  const cleared = await state(page);
  expect(cleared.items).toEqual([]);
  expect(cleared.sceneInstances).toBe(0);
  expect((await sceneOf(page)).items).toEqual([]);
  await reloadScene(page);
  expect((await state(page)).items).toEqual([]);
  expect(problems).toEqual([]);
});

test('a model from the map Assets loads beside a game model', async ({ page }) => {
  const TOSH = 'map\\assets\\units\\terran\\tosh\\toshscoba.m3';
  const { problems } = await open(page);
  await addByUi(page, 'toshscoba', TOSH);
  await addByUi(page, 'protoss\\zealot\\zealot.m3', ZEALOT);
  const s = await state(page);
  expect(s.items.map((i) => i.path)).toEqual([TOSH, ZEALOT]);
  expect(s.items.every((i) => i.loaded && i.texturesLoaded > 0)).toBe(true);
  expect(problems).toEqual([]);
});

test('the canvas follows the window size', async ({ page }) => {
  const { problems } = await open(page);
  const size = () => page.locator('canvas#view').evaluate((c) => [c.width, c.height]);
  const [w0, h0] = await size();
  await page.setViewportSize({ width: 700, height: 500 });
  await expect.poll(async () => (await size())[0]).toBeLessThan(w0);
  await drawn(page);
  const [w1, h1] = await size();
  expect(h1).toBeLessThan(h0);
  expect((await state(page)).camera.aspect).toBeCloseTo(w1 / h1, 2);
  expect(problems).toEqual([]);
});

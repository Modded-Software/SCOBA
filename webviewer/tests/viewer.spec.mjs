import { test, expect } from '@playwright/test';

const MARINE = 'mods\\liberty.sc2mod\\base.sc2assets\\assets\\units\\terran\\marine\\marine.m3';
const ZEALOT = 'mods\\liberty.sc2mod\\base.sc2assets\\assets\\units\\protoss\\zealot\\zealot.m3';

/** Collect page errors and failed responses, so every test can assert none. */
function watch(page) {
  const problems = [];
  page.on('pageerror', (e) => problems.push('pageerror: ' + e.message));
  page.on('console', (m) => {
    if (m.type() === 'error') problems.push('console: ' + m.text());
  });
  page.on('response', (r) => {
    if (r.status() >= 400) problems.push(`http ${r.status()}: ${r.url()}`);
  });
  return problems;
}

async function open(page, hash = '') {
  await page.goto('/' + hash);
  await page.waitForFunction(() => window.sc2viewer && window.sc2viewer.ready);
  // These tests measure model pixels: no ground grid behind them.
  await page.evaluate(() => window.sc2viewer.setGrid(false));
  // These tests cover raw model files, which live on the models tab.
  await page.locator('#tab-models').click();
}

/** Add a model through the UI: type in the search box, click the result. */
async function addByUi(page, query, path) {
  const before = await page.locator('#scene li').count();
  await page.fill('#search', query);
  await page.locator(`#results button[data-path="${path.replaceAll('\\', '\\\\')}"]`).click();
  await expect(page.locator('#scene li')).toHaveCount(before + 1);
  await page.waitForFunction(() => window.sc2viewer.idle());
}

const state = (page) => page.evaluate(() => window.sc2viewer.state());
/** Rendered pixel statistics, read back from the GL framebuffer. */
const pixels = (page) => page.evaluate(() => window.sc2viewer.pixels());

test('empty page: canvas, search box, empty scene, blank render', async ({ page }) => {
  const problems = watch(page);
  await open(page);
  await expect(page.locator('canvas#view')).toBeVisible();
  await expect(page.locator('#search')).toBeVisible();
  await expect(page.locator('#scene li')).toHaveCount(0);
  expect((await state(page)).items).toEqual([]);
  expect((await pixels(page)).covered).toBe(0);
  expect(problems).toEqual([]);
});

test('search lists models and narrows as typed', async ({ page }) => {
  const problems = watch(page);
  await open(page);
  await page.fill('#search', 'marine');
  await expect(page.locator('#results button').first()).toBeVisible();
  const many = await page.locator('#results button').count();
  expect(many).toBeGreaterThan(1);
  await page.fill('#search', 'terran\\marine\\marine.m3');
  await expect(page.locator('#results button')).toHaveCount(1);
  await page.fill('#search', 'no-such-model-xyzzy');
  await expect(page.locator('#results button')).toHaveCount(0);
  expect(problems).toEqual([]);
});

test('adding a model renders it with its textures', async ({ page }) => {
  const problems = watch(page);
  const textures = [];
  page.on('response', (r) => {
    if (r.url().includes('/asset?')) textures.push(r.status());
  });
  await open(page);
  await addByUi(page, 'terran\\marine\\marine.m3', MARINE);

  const s = await state(page);
  expect(s.items).toHaveLength(1);
  expect(s.items[0].path).toBe(MARINE);
  expect(s.items[0].loaded).toBe(true);
  expect(s.items[0].sequences.length).toBeGreaterThan(0);
  expect(s.items[0].texturesLoaded).toBeGreaterThan(0);

  expect(textures.length).toBeGreaterThan(0);
  expect(textures.every((code) => code === 200)).toBe(true);

  const p = await pixels(page);
  expect(p.covered).toBeGreaterThan(500);
  // A textured model is not one flat colour.
  expect(p.colors).toBeGreaterThan(20);
  expect(problems).toEqual([]);
});

test('two models share one scene and can be removed one by one', async ({ page }) => {
  const problems = watch(page);
  await open(page);
  await addByUi(page, 'terran\\marine\\marine.m3', MARINE);
  const one = await pixels(page);

  await addByUi(page, 'protoss\\zealot\\zealot.m3', ZEALOT);
  const s = await state(page);
  expect(s.items.map((i) => i.path)).toEqual([MARINE, ZEALOT]);
  expect(s.items.every((i) => i.loaded)).toBe(true);
  expect(s.sceneInstances).toBe(2);
  // The second model is placed beside the first, not on top of it.
  expect(s.items[1].x).not.toBe(s.items[0].x);
  const two = await pixels(page);
  expect(two.covered).toBeGreaterThan(one.covered * 1.3);

  // Remove the marine: the zealot stays.
  await page.locator('#scene li').first().locator('button.remove').click();
  await expect(page.locator('#scene li')).toHaveCount(1);
  const after = await state(page);
  expect(after.items.map((i) => i.path)).toEqual([ZEALOT]);
  expect(after.sceneInstances).toBe(1);
  expect((await pixels(page)).covered).toBeLessThan(two.covered);

  await page.locator('#scene li button.remove').click();
  await expect(page.locator('#scene li')).toHaveCount(0);
  expect((await state(page)).sceneInstances).toBe(0);
  expect((await pixels(page)).covered).toBe(0);
  expect(problems).toEqual([]);
});

test('the same model can be added twice as separate instances', async ({ page }) => {
  const problems = watch(page);
  await open(page);
  await addByUi(page, 'terran\\marine\\marine.m3', MARINE);
  await addByUi(page, 'terran\\marine\\marine.m3', MARINE);
  const s = await state(page);
  expect(s.items).toHaveLength(2);
  expect(s.items[0].id).not.toBe(s.items[1].id);
  expect(s.sceneInstances).toBe(2);
  expect(problems).toEqual([]);
});

test('position, rotation and scale inputs move the instance and the pixels', async ({ page }) => {
  const problems = watch(page);
  await open(page);
  await addByUi(page, 'terran\\marine\\marine.m3', MARINE);
  const before = await pixels(page);

  const row = page.locator('#scene li').first();
  await row.locator('input.x').fill('2');
  await row.locator('input.x').dispatchEvent('change');
  let item = (await state(page)).items[0];
  expect(item.x).toBe(2);
  expect(item.location[0]).toBeCloseTo(2, 5);
  const moved = await pixels(page);
  expect(Math.abs(moved.centerX - before.centerX)).toBeGreaterThan(20);

  await row.locator('input.y').fill('-1.5');
  await row.locator('input.y').dispatchEvent('change');
  item = (await state(page)).items[0];
  expect(item.location[1]).toBeCloseTo(-1.5, 5);

  const rot0 = item.rotation;
  await row.locator('input.rot').fill('90');
  await row.locator('input.rot').dispatchEvent('change');
  item = (await state(page)).items[0];
  expect(item.rot).toBe(90);
  expect(item.rotation).not.toEqual(rot0);
  // 90 degrees about the up axis: quaternion (0, 0, sin 45, cos 45).
  expect(Math.abs(item.rotation[2])).toBeCloseTo(Math.SQRT1_2, 3);

  const small = await pixels(page);
  await row.locator('input.scale').fill('2');
  await row.locator('input.scale').dispatchEvent('change');
  item = (await state(page)).items[0];
  expect(item.scale).toBe(2);
  expect((await pixels(page)).covered).toBeGreaterThan(small.covered * 2);

  // Negative: junk input changes nothing.
  await row.locator('input.x').evaluate((el) => {
    el.value = '';
    el.dispatchEvent(new Event('change', { bubbles: true }));
  });
  expect((await state(page)).items[0].x).toBe(2);
  expect(problems).toEqual([]);
});

test('an animation can be chosen per instance and it plays', async ({ page }) => {
  const problems = watch(page);
  await open(page);
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

  // It plays: the engine frame advances, and the rendered pixels change.
  const f0 = s.items[0].frame;
  await page.evaluate(() => window.sc2viewer.mark());
  await page.waitForFunction((f) => Math.abs(window.sc2viewer.state().items[0].frame - f) > 150, f0);
  const playing = await page.evaluate(() => window.sc2viewer.changedSinceMark());
  expect(playing.changed, JSON.stringify(playing)).toBeGreaterThan(150);

  // Negative: with no animation on either instance, nothing moves.
  await first.selectOption({ index: 0 });
  await page.locator('#scene li').nth(1).locator('select.anim').selectOption({ index: 0 });
  s = await state(page);
  expect(s.items[0].sequence).toBe(-1);
  expect(s.items[1].sequence).toBe(-1);
  const still = s.items[0].frame;
  await page.evaluate(() => window.sc2viewer.mark());
  await page.waitForTimeout(300);
  expect((await state(page)).items[0].frame).toBe(still);
  const resting = await page.evaluate(() => window.sc2viewer.changedSinceMark());
  expect(resting.changed, JSON.stringify(resting)).toBeLessThan(15);
  expect(problems).toEqual([]);
});

test('mouse orbits, zooms and pans the camera', async ({ page }) => {
  const problems = watch(page);
  await open(page);
  await addByUi(page, 'terran\\marine\\marine.m3', MARINE);
  const box = await page.locator('canvas#view').boundingBox();
  const cx = box.x + box.width / 2;
  const cy = box.y + box.height / 2;
  const c0 = (await state(page)).camera;

  await page.mouse.move(cx, cy);
  await page.mouse.down();
  await page.mouse.move(cx + 120, cy + 40, { steps: 5 });
  await page.mouse.up();
  const c1 = (await state(page)).camera;
  expect(c1.yaw).not.toBeCloseTo(c0.yaw, 3);
  expect(c1.pitch).not.toBeCloseTo(c0.pitch, 3);
  expect(c1.distance).toBeCloseTo(c0.distance, 5);
  expect(c1.target).toEqual(c0.target);

  // Negative: moving without a button held does nothing.
  await page.mouse.move(cx - 80, cy - 80, { steps: 3 });
  expect((await state(page)).camera).toEqual(c1);

  await page.mouse.move(cx, cy);
  const big = await pixels(page);
  await page.mouse.wheel(0, 400);
  const c2 = (await state(page)).camera;
  expect(c2.distance).toBeGreaterThan(c1.distance);
  expect((await pixels(page)).covered).toBeLessThan(big.covered);
  await page.mouse.wheel(0, -800);
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
  await page.mouse.down();
  await page.mouse.move(cx, cy + 3000, { steps: 10 });
  await page.mouse.up();
  const c5 = (await state(page)).camera;
  expect(Math.abs(c5.pitch)).toBeLessThan(Math.PI / 2);
  expect((await pixels(page)).covered).toBeGreaterThan(0);
  expect(problems).toEqual([]);
});

test('drag sensitivity: rotate 0.004 rad per pixel, pan 0.0006 x distance per pixel', async ({ page }) => {
  await open(page);
  const box = await page.locator('canvas#view').boundingBox();
  const cx = box.x + box.width / 2;
  const cy = box.y + box.height / 2;
  const c0 = (await state(page)).camera;

  // Left drag 100 px right: yaw turns 0.4 rad (was 1.0). Pitch unchanged.
  await page.mouse.move(cx, cy);
  await page.mouse.down();
  await page.mouse.move(cx + 100, cy, { steps: 5 });
  await page.mouse.up();
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

test('the scene survives a reload through the URL', async ({ page }) => {
  const problems = watch(page);
  await open(page);
  await addByUi(page, 'terran\\marine\\marine.m3', MARINE);
  await addByUi(page, 'protoss\\zealot\\zealot.m3', ZEALOT);
  const row = page.locator('#scene li').nth(1);
  await row.locator('input.x').fill('3');
  await row.locator('input.x').dispatchEvent('change');
  await row.locator('input.rot').fill('45');
  await row.locator('input.rot').dispatchEvent('change');
  const anim = page.locator('#scene li').nth(0).locator('select.anim');
  await anim.selectOption({ index: 2 });
  const before = await state(page);
  expect(page.url()).toContain('#');

  await page.reload();
  await page.waitForFunction(() => window.sc2viewer && window.sc2viewer.ready && window.sc2viewer.state().items.length === 2);
  await page.waitForFunction(() => window.sc2viewer.idle());
  const after = await state(page);
  const key = (i) => ({ path: i.path, x: i.x, y: i.y, rot: i.rot, scale: i.scale, sequence: i.sequence });
  expect(after.items.map(key)).toEqual(before.items.map(key));
  expect(after.items[1].x).toBe(3);
  expect(after.items[0].sequence).toBe(1);
  await expect(page.locator('#scene li')).toHaveCount(2);
  await expect(page.locator('#scene li').nth(1).locator('input.x')).toHaveValue('3');
  expect((await pixels(page)).covered).toBeGreaterThan(500);
  expect(problems).toEqual([]);
});

test('a model that fails to load is reported and not added', async ({ page }) => {
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

test('clear empties the scene and the URL', async ({ page }) => {
  const problems = watch(page);
  await open(page);
  await addByUi(page, 'terran\\marine\\marine.m3', MARINE);
  await addByUi(page, 'protoss\\zealot\\zealot.m3', ZEALOT);
  await page.locator('#clear').click();
  await expect(page.locator('#scene li')).toHaveCount(0);
  const s = await state(page);
  expect(s.items).toEqual([]);
  expect(s.sceneInstances).toBe(0);
  expect((await pixels(page)).covered).toBe(0);
  await page.reload();
  await page.waitForFunction(() => window.sc2viewer && window.sc2viewer.ready);
  expect((await state(page)).items).toEqual([]);
  expect(problems).toEqual([]);
});

test('a model from the map Assets loads beside a game model', async ({ page }) => {
  const problems = watch(page);
  const TOSH = 'map\\assets\\units\\terran\\tosh\\toshscoba.m3';
  await open(page);
  await addByUi(page, 'toshscoba', TOSH);
  await addByUi(page, 'protoss\\zealot\\zealot.m3', ZEALOT);
  const s = await state(page);
  expect(s.items.map((i) => i.path)).toEqual([TOSH, ZEALOT]);
  expect(s.items.every((i) => i.loaded && i.texturesLoaded > 0)).toBe(true);
  expect((await pixels(page)).covered).toBeGreaterThan(500);
  // For a person to look at. It decides nothing.
  await page.screenshot({ path: 'test-results/shots/tosh-zealot.png' });
  expect(problems).toEqual([]);
});

test('the canvas follows the window size', async ({ page }) => {
  const problems = watch(page);
  await open(page);
  await addByUi(page, 'terran\\marine\\marine.m3', MARINE);
  const a = await pixels(page);
  await page.setViewportSize({ width: 700, height: 500 });
  await page.waitForFunction((w) => window.sc2viewer.pixels().width !== w, a.width);
  const b = await pixels(page);
  expect(b.width).toBeLessThan(a.width);
  expect(b.height).toBeLessThan(a.height);
  expect(b.covered).toBeGreaterThan(0);
  const s = await state(page);
  expect(s.camera.aspect).toBeCloseTo(b.width / b.height, 2);
  expect(problems).toEqual([]);
});

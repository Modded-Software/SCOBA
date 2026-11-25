import { test, expect } from '../fixtures.mjs';
import { frames, idle, open as openPage, state, watch as watchPage } from '../page.mjs';
import { api } from '../api.mjs';

/** Page errors and failed responses. */
function watch(page) {
  const problems = watchPage(page);
  page.on('response', (r) => {
    if (r.status() >= 400) problems.push(`http ${r.status()}: ${r.url()}`);
  });
  return problems;
}

const open = (page) => openPage(page);
const row = (page, id) => page.locator(`#units li[data-id="${id}"]`);
const unitData = async (page, id) => (await page.request.get(api.record('units', id))).json();
const times = (a, b) => a.map((v, i) => v * b[i]);

/** Find a unit in the panel and select it, so the preview shows it. */
async function find(page, query, id) {
  await page.fill('#search-units', query);
  await expect(row(page, id)).toBeVisible();
  await row(page, id).click();
  await expect(page.locator('#preview-units .name')).toBeVisible();
}

/** Add a unit with the preview's add button. */
async function addUnit(page, query, id) {
  const before = await page.locator('#scene li').count();
  await find(page, query, id);
  await page.locator('#preview-add-units').click();
  await expect(page.locator('#scene li')).toHaveCount(before + 1);
  await idle(page);
}

test('the unit panel opens first and lists units with names and icons', async ({ page }) => {
  const problems = watch(page);
  await open(page);
  await expect(page.locator('#search-units')).toBeVisible();
  await expect(page.locator('#search-models')).toBeHidden();
  // With no query the panel lists units and says how many there are.
  await expect(page.locator('#units li').first()).toBeVisible();
  const total = Number.parseInt(await page.locator('#count-units').textContent(), 10);
  expect(total).toBeGreaterThan(500);

  await page.fill('#search-units', 'zergling');
  const zergling = row(page, 'Zergling');
  await expect(zergling).toBeVisible();
  await expect(zergling.locator('.name')).toHaveText('Zergling');
  await expect(zergling.locator('.sub')).toContainText('Zerg');
  // The first hit is the exact name.
  await expect(page.locator('#units li').first()).toHaveAttribute('data-id', 'Zergling');
  // The icon is a real image that loaded.
  const icon = zergling.locator('img.icon');
  // Icons are served per dataset (datasets-api.spec.mjs).
  await expect(icon).toHaveAttribute('src', api.icon('btn-unit-zerg-zergling.png'));
  await expect.poll(() => icon.evaluate((img) => img.complete && img.naturalWidth)).toBeGreaterThan(0);
  const filtered = Number.parseInt(await page.locator('#count-units').textContent(), 10);
  expect(filtered).toBeLessThan(total);

  await page.fill('#search-units', 'no-such-unit-xyzzy');
  await expect(page.locator('#units li')).toHaveCount(0);
  await expect(page.locator('#count-units')).toHaveText('0 units');
  expect(problems).toEqual([]);
});

test('race and kind filters narrow the list', async ({ page }) => {
  const problems = watch(page);
  await open(page);
  await page.locator('#filter-units-race button[data-race="Protoss"]').click();
  await expect(page.locator('#filter-units-race button[data-race="Protoss"]')).toHaveClass(/on/);
  await expect(page.locator('#units li').first()).toBeVisible();
  await expect(page.locator('#units li .sub').first()).toContainText('Protoss');
  const subs = await page.locator('#units li .sub').allTextContents();
  expect(subs.every((text) => text.includes('Protoss'))).toBe(true);

  await page.selectOption('#filter-units-kind', 'Structure');
  await page.fill('#search-units', 'gateway');
  await expect(row(page, 'Gateway')).toBeVisible();
  // Negative: a Protoss unit that is not a structure is filtered out.
  await page.fill('#search-units', 'zealot');
  await expect(page.locator('#units li')).toHaveCount(0);
  await page.selectOption('#filter-units-kind', '');
  await expect(row(page, 'Zealot')).toBeVisible();
  // Negative: a Terran unit does not show under Protoss.
  await page.fill('#search-units', 'marine');
  await expect(row(page, 'Marine')).toHaveCount(0);
  await page.locator('#filter-units-race button[data-race=""]').click();
  await expect(row(page, 'Marine')).toBeVisible();
  expect(problems).toEqual([]);
});

test('selecting a unit shows a preview with portrait and data, and adds it', async ({ page }) => {
  const problems = watch(page);
  await open(page);
  await expect(page.locator('#preview-units .name')).toHaveCount(0);
  await find(page, 'marine', 'Marine');
  await expect(row(page, 'Marine')).toHaveClass(/selected/);
  await expect(page.locator('#preview-units .name')).toHaveText('Marine');
  await expect(page.locator('#preview-units .facts')).toContainText('Terran');
  await expect(page.locator('#preview-units .facts')).toContainText('scale');
  const portrait = page.locator('#preview-units img.portrait');
  await expect(portrait).toHaveAttribute('src', /^\/api\/sc2\/icon\/.+\.png\?dataset=scoba$/);
  await expect.poll(() => portrait.evaluate((img) => img.complete && img.naturalWidth)).toBeGreaterThan(0);
  // Selecting does not add.
  expect((await state(page)).items).toEqual([]);

  await page.locator('#preview-add-units').click();
  await expect(page.locator('#scene li')).toHaveCount(1);
  await idle(page);
  const s = await state(page);
  expect(s.items[0]).toMatchObject({ unit: 'Marine', name: 'Marine', loaded: true });
  expect(s.items[0].texturesLoaded).toBeGreaterThan(0);
  const sceneRow = page.locator('#scene li').first();
  await expect(sceneRow.locator('.name')).toContainText('Marine');
  await expect(sceneRow.locator('img.icon')).toHaveAttribute('src', api.icon('btn-unit-terran-marine.png'));
  await frames(page);
  expect((await state(page)).items[0].drawn).toBe(true);
  expect(problems).toEqual([]);
});

test('a unit with no portrait image previews with its icon', async ({ page }) => {
  const problems = watch(page);
  await open(page);
  expect((await unitData(page, 'Barracks')).portrait).toBeNull();
  await find(page, 'barracks', 'Barracks');
  const portrait = page.locator('#preview-units img.portrait');
  await expect(portrait).toHaveAttribute('src', api.icon('btn-building-terran-barracks.png'));
  await expect.poll(() => portrait.evaluate((img) => img.complete && img.naturalWidth)).toBeGreaterThan(0);
  expect(problems).toEqual([]);
});

test('a drag that ends off the canvas places nothing', async ({ page }) => {
  const problems = watch(page);
  await open(page);
  await page.fill('#search-units', 'marine');
  await expect(row(page, 'Marine')).toBeVisible();
  await row(page, 'Marine').dragTo(page.locator('#search-units'));
  await frames(page);
  await idle(page);
  expect((await state(page)).items).toEqual([]);
  await expect(page.locator('#scene li')).toHaveCount(0);
  expect(problems).toEqual([]);
});

test('a drop above the horizon places nothing and says why', async ({ page }) => {
  const problems = watch(page);
  await open(page);
  // Tilt the camera level (middle drag), so the top of the view shows sky:
  // 112 px up at 0.004 rad/px lowers the pitch from 0.5 to 0.052.
  await page.mouse.move(700, 400);
  await page.mouse.down({ button: 'middle' });
  await page.mouse.move(700, 288, { steps: 5 });
  await page.mouse.up({ button: 'middle' });
  const pitch = (await state(page)).camera.pitch;
  expect(pitch).toBeLessThan(0.1);
  expect(pitch).toBeGreaterThan(0);
  await page.fill('#search-units', 'marine');
  await expect(row(page, 'Marine')).toBeVisible();
  await row(page, 'Marine').dragTo(page.locator('canvas#view'), { targetPosition: { x: 700, y: 40 } });
  await expect(page.locator('#status')).toContainText('horizon');
  expect((await state(page)).items).toEqual([]);
  // The same drag lower down, onto the ground, does place it.
  await row(page, 'Marine').dragTo(page.locator('canvas#view'), { targetPosition: { x: 700, y: 600 } });
  await expect(page.locator('#scene li')).toHaveCount(1);
  expect(problems).toEqual([]);
});

test('the preview\'s "add to scene" adds a unit; a double-click on the row does not', async ({ page }) => {
  const problems = watch(page);
  await open(page);
  await page.fill('#search-units', 'zergling');
  // Negative: a double-click opens the texture window (texture-window.spec) and adds nothing.
  await row(page, 'Zergling').dblclick();
  await expect(page.locator('#texture-window')).toBeVisible();
  await expect(page.locator('#preview-units .name')).toHaveText('Zergling');
  expect((await state(page)).items).toEqual([]);
  await page.click('#texture-window .window-close');
  await page.click('#preview-add-units');
  await expect(page.locator('#scene li')).toHaveCount(1);
  await idle(page);
  const s = await state(page);
  expect(s.items.map((i) => i.unit)).toEqual(['Zergling']);
  expect(s.sceneInstances).toBe(1);
  expect(problems).toEqual([]);
});

test('a placed unit takes its scale from the unit data', async ({ page }) => {
  const problems = watch(page);
  await open(page);
  const data = await unitData(page, 'Ultralisk');
  const want = times(times(data.actorScale, data.modelScaleMax), data.eventScale);
  expect(want[0]).not.toBeCloseTo(1, 2);

  await addUnit(page, 'ultralisk', 'Ultralisk');
  let item = (await state(page)).items[0];
  expect(item.dataScale[0]).toBeCloseTo(want[0], 4);
  expect(item.dataScale[2]).toBeCloseTo(want[2], 4);
  // The engine instance has that scale, not only the script.
  expect(item.engineScale[0]).toBeCloseTo(want[0], 4);

  // Negative: the same model file with no unit data is at scale 1.
  await page.locator('#clear').click();
  await page.locator('#clear-yes').click();
  await page.evaluate((path) => window.sc2viewer.add(path), data.file);
  await idle(page);
  const raw = (await state(page)).items[0];
  expect(raw.unit).toBeNull();
  expect(raw.engineScale[0]).toBeCloseTo(1, 5);

  // The scale input multiplies the data scale.
  await page.locator('#clear').click();
  await page.locator('#clear-yes').click();
  await addUnit(page, 'ultralisk', 'Ultralisk');
  const input = page.locator('#scene li').first().locator('input.scale');
  await expect(input).toHaveValue('1');
  await input.fill('2');
  await input.dispatchEvent('change');
  item = (await state(page)).items[0];
  expect(item.engineScale[0]).toBeCloseTo(want[0] * 2, 4);
  expect(problems).toEqual([]);
});

test('a unit with a scale range gets a scale inside it', async ({ page }) => {
  const problems = watch(page);
  await open(page);
  const data = await unitData(page, 'Zergling');
  const low = data.actorScale[0] * data.modelScaleMin[0];
  const high = data.actorScale[0] * data.modelScaleMax[0];
  expect(high).toBeGreaterThan(low);
  for (let i = 0; i < 4; i++) await addUnit(page, 'zergling', 'Zergling');
  const scales = (await state(page)).items.map((item) => item.engineScale[0]);
  for (const scale of scales) {
    expect(scale).toBeGreaterThanOrEqual(low - 1e-4);
    expect(scale).toBeLessThanOrEqual(high + 1e-4);
  }
  // It is a range: four units are not all the same size.
  expect(new Set(scales.map((v) => v.toFixed(4))).size).toBeGreaterThan(1);
  expect(problems).toEqual([]);
});

test('a flying unit is raised by its height, a ground unit is not', async ({ page }) => {
  const problems = watch(page);
  await open(page);
  const banshee = await unitData(page, 'Banshee');
  expect(banshee.height).toBeGreaterThan(0);
  await addUnit(page, 'banshee', 'Banshee');
  await addUnit(page, 'marine', 'Marine');
  const s = await state(page);
  expect(s.items[0].location[2]).toBeCloseTo(banshee.height, 4);
  expect(s.items[1].location[2]).toBe(0);
  expect(problems).toEqual([]);
});

test('animation speed follows the model data and the walk speed', async ({ page }) => {
  const problems = watch(page);
  await open(page);
  const tosh = await unitData(page, 'ToshSCOBA');
  expect(tosh.animSpeed).not.toBe(1);
  const walkRate = tosh.animSpeed * (tosh.speed / tosh.walkAnimMoveSpeed);

  // The unit, and the same model file with no unit data, side by side.
  await addUnit(page, 'toshscoba', 'ToshSCOBA');
  await page.evaluate((path) => window.sc2viewer.add(path), tosh.file);
  await idle(page);

  const pick = async (index, pattern) => {
    const select = page.locator('#scene li').nth(index).locator('select.anim');
    const names = await select.locator('option').allTextContents();
    const at = names.findIndex((name) => pattern.test(name));
    expect(at, names.join(',')).toBeGreaterThan(0);
    await select.selectOption({ index: at });
  };
  /** Engine frames advanced by both instances over the same real time. */
  const measure = async () => {
    await page.evaluate(() => window.sc2viewer.restart());
    await page.waitForFunction(() => window.sc2viewer.state().items[1].frame > 250);
    return page.evaluate(() => {
      const items = window.sc2viewer.state().items;
      return { unit: items[0].frame, model: items[1].frame, rate: items[0].rate, modelRate: items[1].rate };
    });
  };

  await pick(0, /^Stand$/);
  await pick(1, /^Stand$/);
  const stand = await measure();
  expect(stand.modelRate).toBe(1);
  expect(stand.rate).toBeCloseTo(tosh.animSpeed, 4);
  expect(stand.unit / stand.model, JSON.stringify(stand)).toBeGreaterThan(tosh.animSpeed * 0.85);
  expect(stand.unit / stand.model, JSON.stringify(stand)).toBeLessThan(tosh.animSpeed * 1.15);

  await pick(0, /^Walk$/);
  await pick(1, /^Walk$/);
  const walk = await measure();
  expect(walk.modelRate).toBe(1);
  expect(walk.rate).toBeCloseTo(walkRate, 4);
  expect(walk.unit / walk.model, JSON.stringify(walk)).toBeGreaterThan(walkRate * 0.85);
  expect(walk.unit / walk.model, JSON.stringify(walk)).toBeLessThan(walkRate * 1.15);
  // The walk rate is not the stand rate: the walk speed counts.
  expect(walk.rate).not.toBeCloseTo(stand.rate, 2);
  expect(problems).toEqual([]);
});

test('a tint from the actor data reaches the engine instance', async ({ page }) => {
  const problems = watch(page);
  await open(page);
  const tinted = await unitData(page, 'BeaconArmy');
  expect(tinted.tint).toHaveLength(3);
  await addUnit(page, 'BeaconArmy', 'BeaconArmy');
  await addUnit(page, 'marine', 'Marine');
  const s = await state(page);
  expect(s.items[0].tint.slice(0, 3).map((v) => +v.toFixed(3))).toEqual(tinted.tint.map((v) => +v.toFixed(3)));
  // Negative: a unit with no tint keeps white.
  expect(s.items[1].tint.slice(0, 3)).toEqual([1, 1, 1]);
  expect(problems).toEqual([]);
});

test('team colour can be set per unit and reaches the engine instance', async ({ page }) => {
  const problems = watch(page);
  await open(page);
  await addUnit(page, 'marine', 'Marine');
  await addUnit(page, 'marine', 'Marine');
  const before = await state(page);
  const team = page.locator('#scene li').first().locator('select.team');
  await team.selectOption('1');
  const after = await state(page);
  expect(after.items[0].team).toBe(1);
  expect(after.items[0].engineTeam).toBe(1);
  expect(after.items[0].engineTeam).not.toBe(before.items[0].engineTeam);
  // Negative: the other marine keeps its team.
  expect(after.items[1].engineTeam).toBe(before.items[1].engineTeam);
  expect(problems).toEqual([]);
});

test('units and raw models share one scene', async ({ page }) => {
  const problems = watch(page);
  await open(page);
  await addUnit(page, 'marine', 'Marine');
  await page.locator('#tab-models').click();
  await expect(page.locator('#search-models')).toBeVisible();
  await expect(page.locator('#search-units')).toBeHidden();
  await page.fill('#search-models', 'protoss\\zealot\\zealot.m3');
  await page.locator('#models button').first().click();
  await expect(page.locator('#scene li')).toHaveCount(2);
  await idle(page);
  const s = await state(page);
  expect(s.items.map((i) => i.unit)).toEqual(['Marine', null]);
  expect(s.sceneInstances).toBe(2);
  await page.locator('#tab-units').click();
  await expect(page.locator('#search-units')).toBeVisible();
  expect(problems).toEqual([]);
});

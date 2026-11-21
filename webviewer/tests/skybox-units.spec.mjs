import { test, expect } from '@playwright/test';

// Units whose model is a skybox (operator 2026-11-21: Terran Campaign holds
// SS_BackgroundSpaceTerran00..02 and ...Large). The server marks them
// (`skybox`: model in assets\skyboxes\ or assets\storymodeskyboxes\, or
// named by a CModel with parent Skybox). Added alone, such a unit becomes
// the sky and is not placed; "add all" leaves them out and names them.

const SKY_UNITS = ['SS_BackgroundSpaceTerran00', 'SS_BackgroundSpaceTerran01', 'SS_BackgroundSpaceTerran02', 'SS_BackgroundSpaceTerranLarge'];
const SKY_DIR = /^assets[\\/](storymode)?skyboxes[\\/]/i;

async function open(page) {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push(m.text());
  });
  page.on('response', (r) => {
    if (r.status() >= 400) errors.push(`http ${r.status()}: ${decodeURIComponent(r.url())}`);
  });
  await page.goto('/');
  await page.waitForFunction(() => window.sc2viewer && window.sc2viewer.ready);
  return errors;
}

const units = async (page, query) => (await page.request.get('/api/units?' + new URLSearchParams({ limit: '500', ...query }))).json();
const unit = async (page, id) => (await page.request.get('/api/unit?id=' + encodeURIComponent(id))).json();
const run = (page) => page.evaluate(() => window.SC2App.addAllState());

test('api: the skybox units of Terran Campaign are marked; units are not', async ({ request, page }) => {
  const listed = await units(page, { family: 'Campaign', race: 'Terran' });
  const marked = listed.items.filter((u) => u.skybox).map((u) => u.id).sort();
  console.log(`Terran Campaign: ${listed.total} units, skybox: ${marked.join(', ')}`);
  expect(marked).toEqual(SKY_UNITS);
  for (const id of SKY_UNITS) expect((await unit(page, id)).m3).toMatch(SKY_DIR);
  // Negative: ordinary units, and a doodad with "sky" in its name, are not marked.
  for (const id of ['Marine', 'Ghost', 'VikingSky_Unit']) expect((await unit(page, id)).skybox).toBe(false);
  // Every marked unit, any family, has a skybox model.
  const all = await units(page, { q: '' });
  let offset = 0;
  const everyMarked = [];
  for (let total = all.total; offset < total; offset += 500) {
    const pageOf = await (await request.get('/api/units?' + new URLSearchParams({ limit: '500', offset: String(offset) }))).json();
    everyMarked.push(...pageOf.items.filter((u) => u.skybox).map((u) => u.id));
  }
  console.log(`all units: ${everyMarked.length} skybox: ${everyMarked.join(', ')}`);
  // Their models lie in a skybox folder (the CModel rule adds none today; a
  // failure here lists one it added, to check by hand).
  for (const id of everyMarked) expect((await unit(page, id)).m3, id).toMatch(SKY_DIR);
});

test('a skybox unit added alone becomes the sky and is not placed', async ({ page }) => {
  const errors = await open(page);
  const result = await page.evaluate(() => window.sc2viewer.addUnit('SS_BackgroundSpaceTerran00'));
  expect(result).toBe(null);
  await page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 30_000 });
  const s = await page.evaluate(() => window.sc2viewer.state());
  expect(s.items).toEqual([]);
  expect(s.sceneInstances).toBe(0);
  expect(s.sky.id).toBe('SS_BackgroundSpaceTerran00');
  expect(s.skyLoaded).toBe(true);
  const name = (await unit(page, 'SS_BackgroundSpaceTerran00')).name;
  await expect(page.locator('#status')).toHaveText(`${name} is a skybox: set as the sky`);
  // Negative: an ordinary unit is placed and leaves the sky as it was.
  const marine = await page.evaluate(() => window.sc2viewer.addUnit('Marine'));
  expect(marine).not.toBe(null);
  await page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 30_000 });
  const after = await page.evaluate(() => window.sc2viewer.state());
  expect(after.items.map((i) => i.unit)).toEqual(['Marine']);
  expect(after.sky.id).toBe('SS_BackgroundSpaceTerran00');
  expect(errors).toEqual([]);
});

test('add all on Terran Campaign units (the operator\'s 142): the dialog names the skybox units left out; the run places none of them', async ({ page }) => {
  test.setTimeout(300_000);
  const errors = await open(page);
  const listed = await units(page, { family: 'Campaign', race: 'Terran', kind: 'Unit' });
  console.log(`listed ${listed.total}; skybox among them: ${listed.items.filter((u) => u.skybox).map((u) => u.id).join(', ')}`);
  await page.selectOption('#family', 'is:Campaign');
  await page.locator('#races button[data-race="Terran"]').click();
  await page.selectOption('#kind', 'Unit');
  await expect.poll(() => page.locator('#unit-count').textContent()).toBe(`${listed.total} units`);
  const want = listed.total - SKY_UNITS.length;
  await page.locator('#add-all').click();
  await expect(page.locator('#add-all-dialog .question')).toHaveText(
    `Are you sure you want to add ${want} units to the map? 4 skybox units are left out: ${SKY_UNITS.join(', ')}.`,
  );
  await page.locator('#add-all-yes').click();
  await expect.poll(async () => {
    const r = await run(page);
    return r.running === false && r.asked === want && r.added + r.failed.length === want;
  }, { timeout: 240_000 }).toBe(true);
  await page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 60_000 });
  const r = await run(page);
  const s = await page.evaluate(() => window.sc2viewer.state());
  const sizes = r.layout.map((l) => l.size).sort((a, b) => a - b);
  const biggest = [...r.layout].sort((a, b) => b.size - a.size).slice(0, 10).map((l) => {
    const it = s.items.find((i) => i.id === l.id);
    return [it.unit, +l.size.toFixed(1), +it.boundsRadius.toFixed(1), it.dataScale.map((v) => +v.toFixed(2))];
  });
  console.log('biggest: ' + JSON.stringify(biggest));
  console.log(`run: added ${r.added}, failed ${JSON.stringify(r.failed)}, skipped ${r.skipped.join(', ')}; largest sizes ${sizes.slice(-5).map((v) => v.toFixed(1)).join(', ')}; camera distance ${s.camera.distance.toFixed(1)}`);
  expect(r.skipped).toEqual(SKY_UNITS);
  // No skybox unit stands on the map.
  for (const id of SKY_UNITS) expect(s.items.some((i) => i.unit === id)).toBe(false);
  expect(s.items.length).toBe(r.added);
  // The landmark reads like the list (operator 2026-11-21).
  expect((await page.evaluate(() => window.SC2App.landmarks())).at(-1).name).toBe('Terran Campaign Units');
  // The sky was not touched by the run.
  expect(s.sky).toBe(null);
  // Known gap A4 (video textures): two layers name .ogv files the viewer
  // cannot load; the server answers 404 and the browser logs each twice
  // (the response and the console). Exactly these, nothing else.
  const VIDEO = ['assets/textures/ipistolad.ogv', 'assets/textures/nukenoodles.ogv'];
  const other = errors.filter((e) => !VIDEO.some((v) => e.includes(v)) && e !== 'Failed to load resource: the server responded with a status of 404 (Not Found)');
  expect(other).toEqual([]);
  for (const v of VIDEO) expect(errors.some((e) => e.includes(v)), v).toBe(true);
  expect(errors.length).toBe(2 * VIDEO.length);
});

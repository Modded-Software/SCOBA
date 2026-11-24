// The Ghost texture window (SPEC-VIEWER-GHOST 8): a double-click on an
// instance or a gallery row opens one card per material, with the texture
// decoded in the page. Needs GHOST_PATH. The state of the window and the
// DOM decide; how the cards look is an operator check.
import { test, expect } from '@playwright/test';
import { open, add, frameItem } from './ghost.mjs';

const windowOf = (page) => page.evaluate(() => window.sc2viewer.ghostTextureWindow());
const done = (page) => expect.poll(async () => (await windowOf(page)).state, { timeout: 20_000 }).toBe('done');
const card = (page, material) => page.locator(`#ghost-texture-list .card[data-material="${material}"]`);

/** Double-click the item in the view. */
async function openOn(page, id) {
  await frameItem(page, id);
  const at = await page.evaluate((i) => window.sc2viewer.itemPixel(i), id);
  expect(at, 'the item has a pixel to click').not.toBeNull();
  await page.mouse.dblclick(at[0], at[1]);
}

test('a double-click on a Ghost instance opens its materials; each texture decoded at its size', async ({ page }) => {
  const errors = await open(page);
  const id = await add(page, '3D/Models/crate.nod');
  await openOn(page, id);
  await done(page);
  const w = await windowOf(page);
  expect([w.open, w.file]).toEqual([true, '3D/Models/crate.nod']);
  expect(w.cards.map((c) => [c.material, c.kind, c.groups])).toEqual([['chestCrate2', 'solid', [0]]]);
  const [crate] = w.cards;
  expect(crate.texture).toMatch(/\.dds$/i);
  expect(crate.failed).toBeNull();
  expect(crate.decoded.size[0]).toBeGreaterThan(0);
  expect(crate.decoded.planes[0]).toBe('color');
  // The picture in the card is the decoded texture, at its size.
  const img = card(page, 'chestCrate2').locator('figure.color img');
  await expect(img).toHaveCount(1);
  await expect.poll(() => img.evaluate((n) => n.naturalWidth)).toBe(crate.decoded.size[0]);
  expect(await img.evaluate((n) => n.naturalHeight)).toBe(crate.decoded.size[1]);
  await expect(card(page, 'chestCrate2')).toContainText('drawn solid');
  // Negative: the SC2 texture window did not open.
  expect((await page.evaluate(() => window.sc2viewer.textureWindow())).open).toBe(false);
  // Escape in the list closes the window.
  await page.locator('#ghost-texture-list').focus();
  await page.keyboard.press('Escape');
  expect((await windowOf(page)).open).toBe(false);
  expect(errors).toEqual([]);
});

test('a double-click on a gallery row opens the actor model; a cutout material shows its alpha', async ({ page }) => {
  const errors = await open(page);
  await page.locator('#game-tabs button[data-game="ghost"]').click();
  await page.fill('#search-actors', 'zerg_critter');
  await page.locator('#actors li[data-id="zerg_critter"]').dblclick();
  await done(page);
  const w = await windowOf(page);
  expect(w.file).toBe('3D/Models/zergling.nod');
  expect(w.cards.length).toBeGreaterThan(0);
  for (const c of w.cards) expect([c.material, c.failed, c.decoded === null]).toEqual([c.material, null, c.texture === null]);
  // Negative: nothing was added to the scene.
  expect((await page.evaluate(() => window.sc2viewer.state())).items).toEqual([]);
  // A cutout material: its texture has an alpha plane, shown beside the colour.
  // The window covers the view: close it first.
  await page.locator('#ghost-texture-list').focus();
  await page.keyboard.press('Escape');
  const vine = await add(page, '3D/Models/AR_Plant_Vine_01.nod');
  await openOn(page, vine);
  await expect.poll(async () => (await windowOf(page)).file).toBe('3D/Models/AR_Plant_Vine_01.nod');
  await done(page);
  const cut = (await windowOf(page)).cards.find((c) => c.kind === 'cutout');
  expect(cut, 'a cutout card').toBeDefined();
  expect(cut.decoded.planes).toEqual(['color', 'alpha']);
  await expect(card(page, cut.material).locator('figure.alpha img')).toHaveCount(1);
  expect(errors).toEqual([]);
});

test('materials not drawn: the reason in words; no texture, no picture; sky hidden by its shader', async ({ page }) => {
  const errors = await open(page);
  const cases = [
    ['3_3_2_Room01_FieldPanel02', (c) => c.undrawn !== null && c.undrawn.endsWith('shader dynamic is not drawn'), 'not drawn: shader dynamic is not drawn'],
    ['pCannon_collide', (c) => c.undrawn !== null && c.undrawn.endsWith('found by no step of the material lookup'), 'not drawn: found by no step of the material lookup'],
    ['swdemoSKY', (c) => c.shader === 'sky', 'not drawn (hidden by its shader)'],
  ];
  for (const [name, which, words] of cases) {
    const id = await add(page, `3D/Models/${name}.nod`);
    // The instance row: a model that draws little may have no pixel in the view to click.
    await page.locator(`#scene li[data-id="${id}"] .head .name`).dblclick();
    await expect.poll(async () => (await windowOf(page)).file).toBe(`3D/Models/${name}.nod`);
    await done(page);
    const found = (await windowOf(page)).cards.filter(which);
    expect(found.length, `${name}: ${JSON.stringify((await windowOf(page)).cards)}`).toBeGreaterThan(0);
    for (const c of found) {
      expect(c.kind).toBeNull();
      await expect(card(page, c.material)).toContainText(words);
      // Negative: a material with no texture file has no picture.
      if (c.texture === null) await expect(card(page, c.material).locator('img')).toHaveCount(0);
    }
    await page.evaluate((i) => window.sc2viewer.remove(i), id);
  }
  expect(errors).toEqual([]);
});

test('negative: a texture that does not load is named on its card; the window still lists the model', async ({ page }) => {
  const errors = await open(page);
  // The crate loads with its texture; only after that does its texture answer 404.
  const id = await add(page, '3D/Models/crate.nod');
  let gone = 0;
  await page.route('**/api/ghost/asset?*', (route) => {
    const url = new URL(route.request().url());
    if (url.searchParams.get('kind') === 'texture') {
      gone++;
      return route.fulfill({ status: 404, body: 'gone' });
    }
    return route.continue();
  });
  await page.locator(`#scene li[data-id="${id}"] .head .name`).dblclick();
  await done(page);
  const [only] = (await windowOf(page)).cards;
  expect([only.material, only.failed, only.decoded]).toEqual(['chestCrate2', '404', null]);
  await expect(card(page, 'chestCrate2')).toContainText('texture not read: 404');
  await expect(card(page, 'chestCrate2').locator('img')).toHaveCount(0);
  expect(gone).toBe(1);
  // Negative: the instance in the scene keeps its texture.
  expect((await page.evaluate(() => window.sc2viewer.probe('nod', 'groups', window.sc2viewer.state().items[0].id)))[0].textureLoaded).toBe(true);
  expect(errors).toEqual([]);
});

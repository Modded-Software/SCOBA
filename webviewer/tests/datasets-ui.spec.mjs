import { test, expect } from '@playwright/test';
import { flush, reloadScene, sceneOf, settled } from './scene.mjs';

// Datasets in the page (src/page/core/datasets.ts, scene.ts): the dataset the
// gallery lists and new instances come from, and the dataset of each
// placed instance, which can be swapped to compare data and textures.
// Datasets here: scoba (default), stock, and the fixture fx (Marine at
// actor scale 2 with the Zealot's skin; scripts/test-fixture.sh).

async function open(page) {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto('/');
  await expect.poll(() => errors.join(' | ') || page.evaluate(() => Boolean(window.sc2viewer && window.sc2viewer.ready)), { timeout: 20_000 }).toBe(true);
  return errors;
}

const state = (page) => page.evaluate(() => window.sc2viewer.state());
const idle = (page) => page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 30_000 });
const addUnit = (page, id, options = {}) => page.evaluate(([id, options]) => window.sc2viewer.addUnit(id, options), [id, options]);
const rowSelect = (page, id) => page.locator(`#scene li[data-id="${id}"] select.dataset`);
/** Asset requests the page made for a texture, by the dataset they named. */
const assetRequests = (page, name) =>
  page.evaluate((n) => performance.getEntriesByType('resource').map((e) => decodeURIComponent(e.name)).filter((u) => u.includes('/asset?') && u.toLowerCase().includes(n)).map((u) => new URL(u).searchParams.get('dataset')), name);

async function swap(page, id, dataset) {
  await rowSelect(page, id).selectOption(dataset);
  await page.waitForFunction(([i, d]) => window.sc2viewer.state().items.find((x) => x.id === i).dataset === d, [id, dataset]);
  await idle(page);
}

test('the gallery panel lists the datasets at its top left; the default one is chosen', async ({ page }) => {
  const errors = await open(page);
  const select = page.locator('#dataset');
  await expect(select).toBeVisible();
  expect(await select.locator('option').evaluateAll((o) => o.map((x) => [x.value, x.textContent]))).toEqual([
    ['scoba', 'SCOBA (map over stock)'],
    ['stock', 'Stock'],
    ['fx', 'Test fixture'],
  ]);
  await expect(select).toHaveValue('scoba');
  // It sits at the top left of the gallery panel, in one row with the tabs.
  // (A row of its own leaves the unit list under three rows: instances.spec.mjs.)
  await expect(page.locator('#gallery #dataset')).toHaveCount(1);
  const [box, tabs, panel, search] = [await select.boundingBox(), await page.locator('#tabs').boundingBox(), await page.locator('#gallery').boundingBox(), await page.locator('#search-units').boundingBox()];
  expect(box.y - panel.y).toBeLessThan(12);
  expect(box.x - panel.x).toBeLessThan(12);
  expect(box.x + box.width).toBeLessThanOrEqual(tabs.x);
  expect(Math.abs(box.y - tabs.y)).toBeLessThan(2);
  expect(box.y + box.height).toBeLessThanOrEqual(search.y);
  // The three tabs still fit beside it.
  await expect(page.locator('#tab-models')).toBeVisible();
  expect(tabs.x + tabs.width).toBeLessThanOrEqual(panel.x + panel.width);
  // Negative: it is no longer among the view tools.
  await expect(page.locator('#view-tools #dataset')).toHaveCount(0);
  // A new instance comes from it.
  const id = await addUnit(page, 'Marine', { x: 0, y: 0, pick: 0.5 });
  await idle(page);
  const item = (await state(page)).items[0];
  expect(item).toMatchObject({ id, dataset: 'scoba' });
  expect(item.dataScale).toEqual([1.25, 1.25, 1.25]);
  expect(errors).toEqual([]);
});

test('choosing a dataset relists the gallery; new instances come from it; the choice survives a reload', async ({ page }) => {
  const errors = await open(page);
  await page.fill('#search-units', 'toshscoba');
  await expect(page.locator('#units li[data-id="ToshSCOBA"]')).toBeVisible();
  await page.selectOption('#dataset', 'stock');
  // The map's own unit is not in the stock data.
  await expect(page.locator('#count-units')).toHaveText('0 units');
  await expect(page.locator('#units li[data-id="ToshSCOBA"]')).toHaveCount(0);
  await page.fill('#search-units', 'marine');
  await expect(page.locator('#units li[data-id="Marine"]')).toBeVisible();
  // The preview card and the add button read the stock data.
  await page.locator('#units li[data-id="Marine"]').click();
  await expect(page.locator('#preview-units .facts')).toContainText('scale 1');
  await page.click('#preview-add-units');
  await idle(page);
  let item = (await state(page)).items[0];
  expect(item).toMatchObject({ unit: 'Marine', dataset: 'stock' });
  expect(item.dataScale).toEqual([1, 1, 1]);
  expect(item.path).toMatch(/\\marine\\marine\.m3$/);
  // Doodads follow too: the stock Zerus tree is not the map's.
  await page.click('#tab-doodads');
  await page.fill('#search-doodads', 'zerus tree');
  await expect(page.locator('#doodads li[data-id="ZerusTree"] .sub')).not.toContainText('in map');

  await reloadScene(page);
  await expect(page.locator('#dataset')).toHaveValue('stock');
  // The instance from the stored scene keeps its own dataset.
  item = (await state(page)).items[0];
  expect(item).toMatchObject({ unit: 'Marine', dataset: 'stock' });
  // Negative: back on scoba the map's unit is listed again.
  await page.selectOption('#dataset', 'scoba');
  await page.fill('#search-units', 'toshscoba');
  await expect(page.locator('#units li[data-id="ToshSCOBA"]')).toBeVisible();
  expect(errors).toEqual([]);
});

test('an instance can be swapped to another dataset: its data and model follow; place, angle and id stay', async ({ page }) => {
  const errors = await open(page);
  const id = await addUnit(page, 'Marine', { x: 3, y: -2, rot: 45, pick: 0.5, team: 3 });
  await idle(page);
  const select = rowSelect(page, id);
  await expect(select).toHaveValue('scoba');
  expect(await select.locator('option').evaluateAll((o) => o.map((x) => x.value))).toEqual(['scoba', 'stock', 'fx']);
  const before = (await state(page)).items[0];
  expect(before.path).toMatch(/marine_remastered\.m3$/);

  await swap(page, id, 'stock');
  let s = await state(page);
  expect(s.items).toHaveLength(1);
  expect(s.sceneInstances).toBe(1);
  expect(s.items[0]).toMatchObject({ id, unit: 'Marine', dataset: 'stock', x: 3, y: -2, rot: 45, team: 3, loaded: true, drawn: true });
  expect(s.items[0].path).toMatch(/\\marine\\marine\.m3$/);
  expect(s.items[0].dataScale).toEqual([1, 1, 1]);
  expect(s.items[0].engineScale).toEqual([1, 1, 1]);
  await expect(rowSelect(page, id)).toHaveValue('stock');

  await swap(page, id, 'fx');
  s = await state(page);
  expect(s.items[0]).toMatchObject({ id, dataset: 'fx', x: 3, y: -2, rot: 45 });
  expect(s.items[0].dataScale).toEqual([2, 2, 2]);
  expect(s.items[0].engineScale).toEqual([2, 2, 2]);

  // And back: the map's data again.
  await swap(page, id, 'scoba');
  s = await state(page);
  expect(s.items[0].path).toBe(before.path);
  expect(s.items[0].dataScale).toEqual([1.25, 1.25, 1.25]);
  expect(errors).toEqual([]);
});

test('textures come from the instance\'s dataset: the same model, another skin', async ({ page }) => {
  const errors = await open(page);
  await page.evaluate(() => window.sc2viewer.setGrid(false));
  await page.evaluate(() => window.sc2viewer.view({ yaw: -Math.PI / 2, pitch: 0.5, distance: 7, target: [0, 0, 0.8] }));
  const skin = 'marine_diffuse_blood.dds';
  // Stock Marine: the stock skin, asked from the stock dataset.
  const id = await addUnit(page, 'Marine', { x: 0, y: 0, rot: 0, pick: 0.5, dataset: 'stock' });
  await idle(page);
  expect((await state(page)).items[0]).toMatchObject({ dataset: 'stock' });
  expect(await assetRequests(page, skin)).toEqual(['stock']);
  const stock = await page.evaluate(() => window.sc2viewer.colorStats());

  // The fixture: the same model file at twice the size, with the Zealot's skin.
  await swap(page, id, 'fx');
  const item = (await state(page)).items[0];
  expect(item.path).toMatch(/\\marine\\marine\.m3$/);
  expect((await assetRequests(page, skin)).sort()).toEqual(['fx', 'stock']);
  // Drawn at the stock size, so only the skin differs.
  await page.locator(`#scene li[data-id="${id}"] input.scale`).fill('0.5');
  await page.locator(`#scene li[data-id="${id}"] input.scale`).dispatchEvent('change');
  expect((await state(page)).items[0].engineScale).toEqual([1, 1, 1]);
  const fx = await page.evaluate(() => window.sc2viewer.colorStats());
  console.log('mean colour', JSON.stringify({ stock: stock.mean.map(Math.round), fx: fx.mean.map(Math.round), pixels: [stock.pixels, fx.pixels] }));
  const distance = Math.hypot(...stock.mean.map((v, i) => v - fx.mean[i]));
  expect(distance).toBeGreaterThan(8);
  // The same silhouette: about as many pixels.
  expect(Math.abs(fx.pixels - stock.pixels)).toBeLessThan(stock.pixels * 0.1);

  // Negative: swapped back to stock it looks as it did.
  await swap(page, id, 'stock');
  await page.locator(`#scene li[data-id="${id}"] input.scale`).fill('1');
  await page.locator(`#scene li[data-id="${id}"] input.scale`).dispatchEvent('change');
  const again = await page.evaluate(() => window.sc2viewer.colorStats());
  expect(Math.hypot(...stock.mean.map((v, i) => v - again.mean[i]))).toBeLessThan(3);
  expect(errors).toEqual([]);
});

test('instances of different datasets stand side by side and are kept in the scene', async ({ page }) => {
  await open(page);
  await addUnit(page, 'Marine', { x: -3, y: 0, pick: 0.5 });
  await addUnit(page, 'Marine', { x: 0, y: 0, pick: 0.5, dataset: 'stock' });
  await addUnit(page, 'Marine', { x: 3, y: 0, pick: 0.5, dataset: 'fx' });
  await page.evaluate(() => window.sc2viewer.addDoodad('ZerusTree', { x: 9, y: 0, pick: 0.5, variation: 2, rot: 0, dataset: 'stock' }));
  await idle(page);
  const scales = (s) => s.items.map((i) => [i.dataset, i.dataScale[0]]);
  let s = await state(page);
  expect(scales(s).slice(0, 3)).toEqual([['scoba', 1.25], ['stock', 1], ['fx', 2]]);
  expect(s.items[3]).toMatchObject({ doodad: 'ZerusTree', dataset: 'stock', variation: 2 });
  // The stock tree does not have the map's 4 to 6 times scale.
  expect(s.items[3].dataScale[0]).toBeLessThan(4);

  const saved = await sceneOf(page);
  // Every item names its dataset, the default one too.
  expect(saved.items.map((e) => e.dataset)).toEqual(['scoba', 'stock', 'fx', 'stock']);
  // Negative: the address holds none of it.
  expect(new URL(page.url()).hash).toBe('');
  // A fresh page of the same browser opens the same stored scene.
  await flush(page);
  const fresh = await page.context().newPage();
  await open(fresh);
  await settled(fresh);
  s = await state(fresh);
  expect(scales(s).slice(0, 3)).toEqual([['scoba', 1.25], ['stock', 1], ['fx', 2]]);
  expect(s.items[3]).toMatchObject({ doodad: 'ZerusTree', dataset: 'stock', variation: 2 });
});

test('negative: a unit the other dataset does not have stays as it is, and the reason is shown', async ({ page }) => {
  await open(page);
  const id = await addUnit(page, 'ToshSCOBA', { x: 0, y: 0, pick: 0.5 });
  await idle(page);
  const before = (await state(page)).items[0];
  await rowSelect(page, id).selectOption('stock');
  await expect(page.locator('#status')).toContainText('ToshSCOBA is not in dataset "stock"');
  await idle(page);
  const after = (await state(page)).items[0];
  expect(after).toMatchObject({ id, dataset: 'scoba', path: before.path });
  await expect(rowSelect(page, id)).toHaveValue('scoba');
  // Adding from a dataset that does not exist fails too.
  const error = await page.evaluate(() => window.sc2viewer.addUnit('Marine', { dataset: 'nosuch' }).then(() => null, (e) => e.message));
  expect(error).toContain('no dataset "nosuch"');
  expect((await state(page)).items).toHaveLength(1);
});

test('a doodad swaps dataset too and keeps its variation', async ({ page }) => {
  await open(page);
  const id = await page.evaluate(() => window.sc2viewer.addDoodad('ZerusTree', { x: 0, y: 0, pick: 0.5, variation: 7, rot: 30 }));
  await idle(page);
  expect((await state(page)).items[0].dataScale.map((v) => +v.toFixed(4))).toEqual([5, 5, 7]);
  await swap(page, id, 'stock');
  const item = (await state(page)).items[0];
  expect(item).toMatchObject({ id, doodad: 'ZerusTree', dataset: 'stock', variation: 7, rot: 30 });
  expect(item.path.toLowerCase()).toContain('zerustree_07.m3');
  expect(item.dataScale[0]).toBeLessThan(4);
  await expect(page.locator(`#scene li[data-id="${id}"] select.variation`)).toHaveValue('7');
});

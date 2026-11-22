import { test, expect } from '@playwright/test';

// The doodads tab of the gallery, and doodads in the scene: variations,
// random scale, the editor's angle rule, the URL, drag and "add all".

async function open(page, hash = '') {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto('/' + hash);
  await expect.poll(() => errors.join(' | ') || page.evaluate(() => Boolean(window.sc2viewer && window.sc2viewer.ready)), { timeout: 20_000 }).toBe(true);
  return errors;
}

const state = (page) => page.evaluate(() => window.sc2viewer.state());
const idle = (page) => page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 30_000 });
const row = (page, id) => page.locator(`#doodads li[data-id="${id}"]`);
const add = (page, id, options = {}) => page.evaluate(([id, options]) => window.sc2viewer.addDoodad(id, options), [id, options]);

async function showDoodads(page) {
  await page.click('#tab-doodads');
  await expect(page.locator('#pane-doodads')).toBeVisible();
}

test('the doodads tab lists the doodads; search and the two filters narrow the list', async ({ page }) => {
  const errors = await open(page);
  // Negative: the tab is closed at first, the units tab open.
  await expect(page.locator('#pane-doodads')).toBeHidden();
  await expect(page.locator('#pane-units')).toBeVisible();
  await showDoodads(page);
  await expect(page.locator('#pane-units')).toBeHidden();
  await expect(page.locator('#tab-doodads')).toHaveClass(/\bon\b/);
  await expect(page.locator('#doodads li').first()).toBeVisible();
  const total = (text) => Number.parseInt(text, 10);
  const all = total(await page.locator('#doodad-count').textContent());
  expect(all).toBeGreaterThan(2000);

  await page.selectOption('#doodad-type', 'CliffRamps');
  await expect.poll(async () => total(await page.locator('#doodad-count').textContent())).toBeLessThan(all);
  const ramps = total(await page.locator('#doodad-count').textContent());
  expect(ramps).toBeGreaterThan(50);
  await page.selectOption('#doodad-tileset', 'Char');
  await expect.poll(async () => total(await page.locator('#doodad-count').textContent())).toBeLessThan(ramps);
  for (const text of await page.locator('#doodads li .sub').allTextContents()) expect(text).toContain('CliffRamps');

  await page.selectOption('#doodad-type', '');
  await page.selectOption('#doodad-tileset', '');
  await page.fill('#doodad-search', 'zerus tree');
  await expect(row(page, 'ZerusTree')).toBeVisible();
  await expect(row(page, 'ZerusTree').locator('.sub')).toContainText('variations');
  await expect(row(page, 'ZerusTree').locator('.sub')).toContainText('in map');
  // Negative: a doodad that does not match is gone from the list.
  await expect(row(page, 'AcidFalls')).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('a click previews a doodad; "add to scene" places it with a variation and a scale from its range', async ({ page }) => {
  const errors = await open(page);
  await showDoodads(page);
  await page.fill('#doodad-search', 'zerus tree');
  await row(page, 'ZerusTree').click();
  await expect(page.locator('#doodad-preview .name')).toHaveText('Zerus Tree');
  await expect(page.locator('#doodad-preview .facts')).toContainText('scale 4 to 6');
  await expect(page.locator('#doodad-preview .facts')).toContainText('random angle');
  await expect(page.locator('#doodad-preview .facts')).toContainText('anim ×0.25');
  await expect(page.locator('#doodad-preview .facts')).toContainText('terrain sets: Zerus');
  // Negative: previewing adds nothing.
  expect((await state(page)).items).toEqual([]);

  await page.click('#doodad-preview-add');
  await idle(page);
  const s = await state(page);
  expect(s.items).toHaveLength(1);
  const item = s.items[0];
  console.log('placed', JSON.stringify({ doodad: item.doodad, variation: item.variation, rot: item.rot, dataScale: item.dataScale, path: item.path }));
  expect(item).toMatchObject({ doodad: 'ZerusTree', unit: null, name: 'Zerus Tree', loaded: true, drawn: true });
  expect(item.variation).toBeGreaterThanOrEqual(0);
  expect(item.variation).toBeLessThan(12);
  expect(item.path.toLowerCase()).toContain(`zerustree_${String(item.variation).padStart(2, '0')}.m3`);
  // Scale: 4 to 6, the same on x and y; z is 1.4 times that (the map's actor scale).
  expect(item.dataScale[0]).toBeGreaterThanOrEqual(4);
  expect(item.dataScale[0]).toBeLessThanOrEqual(6);
  expect(item.dataScale[1]).toBeCloseTo(item.dataScale[0], 6);
  expect(item.dataScale[2]).toBeCloseTo(item.dataScale[0] * 1.4, 6);
  expect(s.sceneInstances).toBe(1);
  // The instances panel: a doodad row with a variation select, and no team colour.
  const placed = page.locator('#scene li[data-doodad="ZerusTree"]');
  await expect(placed).toHaveCount(1);
  await expect(placed.locator('select.variation')).toHaveValue(String(item.variation));
  await expect(placed.locator('select.team')).toHaveCount(0);
  // Negative: it is not listed as a unit.
  await expect(page.locator('#scene li[data-unit]')).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('the scale pick chooses inside the random scale range; a fixed doodad keeps scale 1', async ({ page }) => {
  await open(page);
  await add(page, 'ZerusTree', { x: 0, y: 0, pick: 0, variation: 0, rot: 0 });
  await add(page, 'ZerusTree', { x: 20, y: 0, pick: 1, variation: 0, rot: 0 });
  await add(page, 'ZerusTree', { x: 40, y: 0, pick: 0.5, variation: 0, rot: 0 });
  // AcidFalls has RandomScaleRange 1,1.
  await add(page, 'AcidFalls', { x: 60, y: 0, pick: 0.9, variation: 0, rot: 0 });
  await idle(page);
  const scales = (await state(page)).items.map((i) => i.dataScale.map((v) => +v.toFixed(4)));
  console.log('scales', JSON.stringify(scales));
  expect(scales[0]).toEqual([4, 4, 5.6]);
  expect(scales[1]).toEqual([6, 6, 8.4]);
  expect(scales[2]).toEqual([5, 5, 7]);
  // Negative: no range, no random scale.
  expect(scales[3]).toEqual([1, 1, 1]);
});

test('the editor angle rule: a doodad is turned at random unless its data forbids it', async ({ page }) => {
  await open(page);
  // AiurProtossBuildings has EditorFlags NoAutoRotate; ZerusTree has not.
  for (let i = 0; i < 6; i++) await add(page, 'AiurProtossBuildings', { x: i * 30, y: 0 });
  for (let i = 0; i < 6; i++) await add(page, 'ZerusTree', { x: i * 30, y: 60, variation: 0 });
  // A given angle always wins.
  await add(page, 'ZerusTree', { x: 0, y: 120, variation: 0, rot: 45 });
  await idle(page);
  const items = (await state(page)).items;
  const fixed = items.filter((i) => i.doodad === 'AiurProtossBuildings').map((i) => i.rot);
  const turned = items.filter((i) => i.doodad === 'ZerusTree').map((i) => i.rot);
  console.log('fixed', JSON.stringify(fixed), 'turned', JSON.stringify(turned));
  expect(fixed).toEqual([0, 0, 0, 0, 0, 0]);
  for (const rot of turned) {
    expect(rot).toBeGreaterThanOrEqual(0);
    expect(rot).toBeLessThan(360);
  }
  // Six random angles are not all one value (chance of a false failure: 360^-5).
  expect(new Set(turned.slice(0, 6)).size).toBeGreaterThan(1);
  expect(turned[6]).toBe(45);
});

test('the variation select swaps the model file and keeps place, angle and scale', async ({ page }) => {
  const errors = await open(page);
  await add(page, 'ZerusTree', { x: 3, y: -2, pick: 0.25, variation: 0, rot: 90 });
  await idle(page);
  const before = (await state(page)).items[0];
  expect(before.variation).toBe(0);
  expect(before.path.toLowerCase()).toContain('zerustree_00.m3');
  const select = page.locator('#scene li[data-doodad="ZerusTree"] select.variation');
  await expect(select.locator('option')).toHaveCount(12);
  await select.selectOption('7');
  await page.waitForFunction(() => window.sc2viewer.state().items[0].variation === 7);
  await idle(page);
  // "drawn" is what the last frame drew: let one draw the new instance.
  await page.waitForFunction(() => window.sc2viewer.state().items[0].drawn);
  const s = await state(page);
  const after = s.items[0];
  console.log('variation swap', JSON.stringify({ before: before.path, after: after.path, vertices: [before.vertexCount, after.vertexCount] }));
  expect(after.path.toLowerCase()).toContain('zerustree_07.m3');
  expect(after).toMatchObject({ id: before.id, x: 3, y: -2, rot: 90, loaded: true, drawn: true });
  expect(after.dataScale).toEqual(before.dataScale);
  // Negative: the old instance is gone, not left beside the new one.
  expect(s.items).toHaveLength(1);
  expect(s.sceneInstances).toBe(1);
  await expect(page.locator('#scene li[data-doodad="ZerusTree"] select.variation')).toHaveValue('7');
  // Negative: a variation the doodad does not have is refused.
  const bad = await page.evaluate(() => window.SC2App.setVariation(window.SC2App.items[0], 12).then(() => 'swapped', (error) => error.message));
  expect(bad).toBe('ZerusTree has no variation 12');
  expect((await state(page)).items[0].variation).toBe(7);
  expect(errors).toEqual([]);
});

test('a doodad with one variation has no variation select', async ({ page }) => {
  await open(page);
  await add(page, 'BuildingBlocker1x1Doodad', { x: 0, y: 0 });
  await idle(page);
  const item = (await state(page)).items[0];
  // It draws nothing in game: the editor model stands in.
  expect(item).toMatchObject({ doodad: 'BuildingBlocker1x1Doodad', variation: 0 });
  expect(item.path.toLowerCase()).toMatch(/pathingblockerhelper\.m3$/);
  await expect(page.locator('#scene li[data-doodad="BuildingBlocker1x1Doodad"]')).toHaveCount(1);
  await expect(page.locator('#scene li select.variation')).toHaveCount(0);
});

test('doodads are kept in the URL with their variation, next to units', async ({ page }) => {
  await open(page);
  await add(page, 'ZerusTree', { x: 4, y: 1, pick: 0.5, variation: 9, rot: 30 });
  await page.evaluate(() => window.sc2viewer.addUnit('Marine', { x: -3, y: 0, team: 2, pick: 0.5 }));
  await idle(page);
  const hash = await page.evaluate(() => location.hash);
  const saved = JSON.parse(decodeURIComponent(hash.slice(1)));
  expect(saved[0]).toMatchObject({ d: 'ZerusTree', v: 9, x: 4, y: 1, r: 30, k: 0.5 });
  expect(saved[0].u).toBeUndefined();
  expect(saved[1]).toMatchObject({ u: 'Marine', x: -3 });
  expect(saved[1].d).toBeUndefined();

  // A fresh page with that URL shows the same scene.
  const fresh = await page.context().newPage();
  await open(fresh, hash);
  await idle(fresh);
  const items = (await state(fresh)).items;
  expect(items).toHaveLength(2);
  expect(items[0]).toMatchObject({ doodad: 'ZerusTree', unit: null, variation: 9, x: 4, y: 1, rot: 30 });
  expect(items[0].path.toLowerCase()).toContain('zerustree_09.m3');
  expect(items[0].dataScale.map((v) => +v.toFixed(4))).toEqual([5, 5, 7]);
  expect(items[1]).toMatchObject({ unit: 'Marine', doodad: null, variation: null });
});

test('dragging a doodad shows its preview; the drop keeps the previewed variation and angle', async ({ page }) => {
  await open(page);
  await page.evaluate(() => window.sc2viewer.setGrid(false));
  await showDoodads(page);
  await page.fill('#doodad-search', 'zerus tree');
  await expect(row(page, 'ZerusTree')).toBeVisible();
  await row(page, 'ZerusTree').hover();
  await page.mouse.down();
  const box = await page.locator('canvas#view').boundingBox();
  await page.mouse.move(box.x + 700, box.y + 450, { steps: 8 });
  await idle(page);
  await page.mouse.move(box.x + 701, box.y + 450, { steps: 2 });
  const ghost = (await state(page)).ghost;
  console.log('ghost', JSON.stringify(ghost));
  expect(ghost).toMatchObject({ kind: 'doodad', unit: 'ZerusTree', shown: true });
  expect(ghost.variation).toBeGreaterThanOrEqual(0);
  // Negative: the preview is not a scene item.
  expect((await state(page)).items).toEqual([]);
  const at = await page.evaluate(([x, y]) => window.sc2viewer.groundUnder(x, y), [701, 450]);
  await page.mouse.up();
  await idle(page);
  const s = await state(page);
  expect(s.ghost).toBe(null);
  expect(s.items).toHaveLength(1);
  expect(s.items[0]).toMatchObject({ doodad: 'ZerusTree', variation: ghost.variation, rot: ghost.rot });
  expect(s.items[0].x).toBeCloseTo(at[0], 2);
  expect(s.items[0].y).toBeCloseTo(at[1], 2);
});

test('"add all" on the doodads tab adds every doodad of the list after a confirm', async ({ page }) => {
  const errors = await open(page);
  await showDoodads(page);
  await page.fill('#doodad-search', 'aiur tree');
  await expect(page.locator('#doodads li').first()).toBeVisible();
  const listed = await (await page.request.get('/api/doodads?q=aiur+tree&limit=500')).json();
  expect(listed.total).toBeGreaterThan(1);
  expect(listed.total).toBeLessThan(20);
  await page.click('#doodad-add-all');
  await expect(page.locator('#add-all-dialog .question')).toHaveText(`Are you sure you want to add ${listed.total} doodads to the map?`);
  // Negative: "cancel" adds nothing.
  await page.click('#add-all-no');
  expect((await state(page)).items).toEqual([]);

  await page.click('#doodad-add-all');
  await page.click('#add-all-yes');
  await page.waitForFunction(() => !window.SC2App.addAllState().running && window.SC2App.addAllState().asked > 0, null, { timeout: 60_000 });
  await idle(page);
  const run = await page.evaluate(() => window.SC2App.addAllState());
  console.log('run', JSON.stringify({ asked: run.asked, added: run.added, failed: run.failed, landmark: run.landmark }));
  expect(run).toMatchObject({ asked: listed.total, added: listed.total, failed: [] });
  const items = (await state(page)).items;
  expect(items.map((i) => i.doodad).sort()).toEqual(listed.items.map((i) => i.id).sort());
  // Negative: no units came along.
  expect(items.every((i) => i.unit === null)).toBe(true);
  // The landmark is named after the doodad list.
  const names = await page.evaluate(() => window.SC2App.landmarks().map((l) => l.name));
  expect(names).toContain('Doodads "aiur tree"');
  expect(errors).toEqual([]);
});

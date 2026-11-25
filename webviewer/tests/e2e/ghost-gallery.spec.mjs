// The shared gallery features with Ghost as the gallery game (SPEC-VIEWER-GHOST
// 9, "In the page"): the preview and its add button, a row dragged into the
// view, the filter buttons, add all with its landmark name, and the dataset
// reload. Needs GHOST_PATH. The build is the game's own files: the reload is
// asked with nothing changed, never by editing them. Engine state, the
// state API and the server's answers decide.
import { allowErrors, test, expect } from '../fixtures.mjs';
import { FOREIGN_CLIP, open } from '../ghost.mjs';

const D = 'build';
const records = async (request, category, query) => (await request.get(`/api/ghost/records/${category}?${new URLSearchParams({ dataset: D, limit: '500', ...query })}`)).json();
const state = (page) => page.evaluate(() => window.sc2viewer.state());
const idle = (page) => page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 30_000 });
const run = (page) => page.evaluate(() => window.SC2App.addAllState());

async function ghostTab(page) {
  await page.locator('#game-tabs button[data-game="ghost"]').click();
  await expect.poll(() => page.evaluate(() => window.sc2viewer.games.current())).toBe('ghost');
  await expect(page.locator('#actors li[data-id]').first()).toBeAttached({ timeout: 15_000 });
}

test('the preview describes an actor; its add button adds it; a row dragged into the view adds one there', async ({ page, request }) => {
  allowErrors(FOREIGN_CLIP);
  const errors = await open(page);
  await ghostTab(page);
  const record = await (await request.get(`/api/ghost/record/actors?dataset=${D}&id=zerg_critter`)).json();
  await page.fill('#search-actors', 'zerg_critter');
  const row = page.locator('#actors li[data-id="zerg_critter"]');
  await row.click();
  await expect(page.locator('#preview-actors .name')).toHaveText(record.name);
  await expect(page.locator('#preview-actors .facts')).toContainText(`model ${record.model}`);
  // Negative: one click adds nothing.
  expect((await state(page)).items).toEqual([]);
  await page.locator('#preview-add-actors').click();
  await expect(page.locator('#scene li')).toHaveCount(1);
  await idle(page);
  const [added] = (await state(page)).items;
  expect([added.game, added.path, added.loaded]).toEqual(['ghost', record.file, true]);
  // Dragged into the view: a second one, away from the first.
  await row.dragTo(page.locator('canvas#view'), { targetPosition: { x: 500, y: 420 } });
  await expect(page.locator('#scene li')).toHaveCount(2);
  await idle(page);
  const [, dropped] = (await state(page)).items;
  expect([dropped.game, dropped.path, dropped.loaded]).toEqual(['ghost', record.file, true]);
  expect(Math.hypot(dropped.x - added.x, dropped.y - added.y)).toBeGreaterThan(0.01);
  expect(errors).toEqual([]);
});

test('the filter buttons narrow the lists as the server does; "all" brings the rest back', async ({ page, request }) => {
  const errors = await open(page);
  await ghostTab(page);
  const all = (await records(request, 'actors', {})).total;
  const withMotions = (await records(request, 'actors', { motion: 'with' })).total;
  expect(withMotions).toBeGreaterThan(0);
  expect(withMotions).toBeLessThan(all);
  await expect.poll(() => page.locator('#count-actors').textContent()).toBe(`${all} actors`);
  await page.locator('#filter-actors-motion button[data-motion="with"]').click();
  await expect(page.locator('#filter-actors-motion button[data-motion="with"]')).toHaveClass(/on/);
  await expect.poll(() => page.locator('#count-actors').textContent()).toBe(`${withMotions} actors`);
  await page.locator('#filter-actors-motion button[data-motion=""]').click();
  await expect.poll(() => page.locator('#count-actors').textContent()).toBe(`${all} actors`);
  // The models pane: skinned and rigid add up to all.
  await page.locator('#tab-models').click();
  const [models, skinned, rigid] = await Promise.all([{}, { skin: 'skinned' }, { skin: 'rigid' }].map(async (q) => (await records(request, 'models', q)).total));
  expect(skinned + rigid).toBe(models);
  await page.locator('#filter-models-skin button[data-skin="rigid"]').click();
  await expect.poll(() => page.locator('#count-models').textContent()).toBe(`${rigid} models`);
  // Negative: no skinned model is listed under rigid.
  const skinnedIds = new Set((await records(request, 'models', { skin: 'skinned', q: 'zergling' })).items.map((r) => r.id));
  await page.fill('#search-models', 'zergling');
  await expect.poll(async () => (await page.locator('#models li[data-id]').evaluateAll((list) => list.map((li) => li.dataset.id))).filter((id) => skinnedIds.has(id))).toEqual([]);
  expect(errors).toEqual([]);
});

test('add all adds the listed actors and keeps a landmark named by the Ghost list', async ({ page, request }) => {
  // The zergling models' invisible_scan group names a texture the build lacks: not drawn, reported.
  allowErrors(FOREIGN_CLIP, /: not drawn: group 6 invisible_scan: its texture file is missing$/);
  const errors = await open(page);
  await ghostTab(page);
  const listed = await records(request, 'actors', { q: 'zergling', motion: 'with' });
  expect(listed.total, 'a small list').toBeGreaterThan(0);
  expect(listed.total).toBeLessThan(40);
  await page.fill('#search-actors', 'zergling');
  await page.locator('#filter-actors-motion button[data-motion="with"]').click();
  await expect.poll(() => page.locator('#count-actors').textContent()).toBe(`${listed.total} actors`);
  // Negative: cancelled, nothing added.
  await page.locator('#add-all-actors').click();
  await page.locator('#add-all-no').click();
  expect((await state(page)).items).toEqual([]);
  await page.locator('#add-all-actors').click();
  await expect(page.locator('#add-all-dialog .question')).toContainText(`${listed.total} actor`);
  await page.locator('#add-all-yes').click();
  await expect.poll(async () => {
    const r = await run(page);
    return r.running === false && r.asked === listed.total && r.added + r.failed.length === listed.total;
  }, { timeout: 60_000 }).toBe(true);
  await idle(page);
  const r = await run(page);
  expect(r.failed).toEqual([]);
  const items = (await state(page)).items;
  expect(items.map((i) => i.game)).toEqual(listed.items.map(() => 'ghost'));
  // The files of the listed records, one instance each.
  const files = await Promise.all(listed.items.map(async (row) => (await (await request.get(`/api/ghost/record/actors?dataset=${D}&id=${encodeURIComponent(row.id)}`)).json()).file));
  expect(items.map((i) => i.path).sort()).toEqual(files.sort());
  const names = (await page.evaluate(() => window.SC2App.landmarks())).map((l) => l.name);
  expect(names).toEqual(['origin (0, 0, 0)', 'Animated Ghost actors "zergling"']);
  expect(errors).toEqual([]);
});

test('landmark names from the Ghost filters', async ({ page }) => {
  const errors = await open(page);
  await ghostTab(page);
  const names = await page.evaluate(() => [
    ['actors', {}],
    ['actors', { q: '', motion: 'without' }],
    ['actors', { q: 'zerg', motion: 'with' }],
    ['models', { q: '', skin: 'skinned' }],
    ['models', { q: 'crate', skin: 'rigid' }],
    ['models', { q: 'crate' }],
  ].map(([category, query]) => window.SC2App.listName(category, query)));
  expect(names).toEqual(['All Ghost actors', 'Still Ghost actors', 'Animated Ghost actors "zerg"', 'Skinned Ghost models', 'Rigid Ghost models "crate"', 'Ghost models "crate"']);
  // Negative: the SC2 tab names its lists its own way.
  await page.locator('#game-tabs button[data-game="sc2"]').click();
  await expect.poll(() => page.evaluate(() => window.sc2viewer.games.current())).toBe('sc2');
  expect(await page.evaluate(() => window.SC2App.listName('units', {}))).toBe('All Units');
  expect(errors).toEqual([]);
});

test('the dataset reload: nothing changed, the same signature and lists; no toast; GET and other datasets refused', async ({ page, request }) => {
  const errors = await open(page);
  const before = (await (await request.get('/api/ghost/datasets')).json()).datasets[0];
  const summary = await (await request.get(`/api/ghost/summary?dataset=${D}`)).json();
  const response = await request.post(`/api/ghost/datasets/${D}/reload`, { timeout: 240_000 });
  expect(response.status()).toBe(200);
  const after = await response.json();
  expect([after.id, after.signature, after.changed]).toEqual([D, before.signature, false]);
  expect(await (await request.get(`/api/ghost/summary?dataset=${D}`)).json()).toEqual(summary);
  // Negative: nothing changed on disk, so the page raises no toast.
  await page.evaluate(() => window.SC2App.checkDatasets());
  expect((await page.evaluate(() => window.SC2App.datasetToast())).up).toBe(false);
  expect((await request.get(`/api/ghost/datasets/${D}/reload`)).status()).toBe(405);
  expect((await request.post('/api/ghost/datasets/nosuch/reload')).status()).toBe(404);
  expect(errors).toEqual([]);
});

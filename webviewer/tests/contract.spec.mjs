// The contract tests (SPEC-VIEWER 11, R-VIEW-91): one suite, run once for
// every game /api/games lists as available. Each game passes the same
// checks through the shared protocol and the shared page; nothing here
// names a game's own records or files. A game not available is skipped
// with its reason (ghost-unavailable.spec covers that case).
//   protocol: every route answers in its shape; paging walks a list without
//   repeats; an unknown id or category gives 404;
//   page: the tab shows the game's categories; a record is previewed,
//   added, selected, moved, copied, pasted, kept over a reload, removed.
import { test, expect } from '@playwright/test';
import { reloadScene } from './scene.mjs';

const PAGE = 7;

async function gamesOf(request) {
  const body = await (await request.get('/api/games')).json();
  expect(Array.isArray(body.games)).toBe(true);
  return body.games;
}

const get = async (request, url) => {
  const response = await request.get(url);
  expect(response.status(), url).toBe(200);
  return response.json();
};

/** The first placeable record of the game's first record category, with that category. */
async function firstRecord(request, game, dataset, categories) {
  const category = categories.find((c) => c.rows === 'records');
  expect(category, `${game}: a record category`).toBeDefined();
  for (let offset = 0; offset < 2000; offset += 100) {
    const page = await get(request, `/api/${game}/records/${category.id}?${new URLSearchParams({ dataset, offset: String(offset), limit: '100' })}`);
    const found = page.items.find((r) => r.placeable);
    if (found) return { category, record: found };
    if (offset + 100 >= page.total) break;
  }
  throw new Error(`${game}: no placeable record in ${category.id}`);
}

test('protocol: every available game answers the shared routes in their shapes', async ({ request }) => {
  const games = await gamesOf(request);
  const available = games.filter((g) => g.available);
  expect(available.length, 'two games under test (R-VIEW-91)').toBeGreaterThanOrEqual(2);
  for (const g of games.filter((x) => !x.available)) console.log(`contract: ${g.id} skipped: ${g.reason}`);
  for (const { id: game } of available) {
    const datasets = await get(request, `/api/${game}/datasets`);
    expect(datasets.datasets.map((d) => d.id), game).toContain(datasets.default);
    const dataset = datasets.default;
    const categories = await get(request, `/api/${game}/categories?${new URLSearchParams({ dataset })}`);
    expect(categories.length, game).toBeGreaterThan(0);
    for (const c of categories) {
      expect(Object.keys(c).sort(), `${game} ${c.id}`).toEqual(expect.arrayContaining(['id', 'label', 'noun', 'rows', 'filters']));
      if (c.rows !== 'records') continue;
      // Paging: three pages, no id twice, each page the size asked while the list lasts.
      const seen = new Set();
      let total = null;
      for (let offset = 0; offset < PAGE * 3; offset += PAGE) {
        const page = await get(request, `/api/${game}/records/${c.id}?${new URLSearchParams({ dataset, offset: String(offset), limit: String(PAGE) })}`);
        total ??= page.total;
        expect(page.total, `${game} ${c.id}: the total does not change between pages`).toBe(total);
        expect(page.items.length).toBe(Math.max(0, Math.min(PAGE, total - offset)));
        for (const row of page.items) {
          expect(typeof row.id === 'string' && typeof row.name === 'string' && typeof row.placeable === 'boolean', JSON.stringify(row)).toBe(true);
          expect(seen.has(row.id), `${game} ${c.id}: ${row.id} twice`).toBe(false);
          seen.add(row.id);
        }
      }
      const [one] = seen;
      if (one !== undefined) {
        const body = await get(request, `/api/${game}/record/${c.id}?${new URLSearchParams({ dataset, id: one })}`);
        expect([body.id, body.dataset], `${game} ${c.id}`).toEqual([one, dataset]);
      }
      // Negative: an unknown id is 404.
      expect((await request.get(`/api/${game}/record/${c.id}?${new URLSearchParams({ dataset, id: 'no-such-record-xyzzy' })}`)).status(), game).toBe(404);
    }
    // Negative: an unknown category and an unknown dataset are 404.
    expect((await request.get(`/api/${game}/records/no-such-category?${new URLSearchParams({ dataset })}`)).status(), game).toBe(404);
    expect((await request.get(`/api/${game}/categories?dataset=no-such-dataset`)).status(), game).toBe(404);
  }
});

test('page: in every available game a record is previewed, added, selected, moved, copied, pasted, kept, removed', async ({ page, request }) => {
  test.setTimeout(180_000);
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto('/');
  await expect.poll(() => errors.join(' | ') || page.evaluate(() => Boolean(window.sc2viewer && window.sc2viewer.ready)), { timeout: 20_000 }).toBe(true);
  const state = () => page.evaluate(() => window.sc2viewer.state());
  const idle = () => page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 60_000 });
  for (const { id: game } of (await gamesOf(request)).filter((g) => g.available)) {
    const dataset = (await get(request, `/api/${game}/datasets`)).default;
    const categories = await get(request, `/api/${game}/categories?${new URLSearchParams({ dataset })}`);
    await page.locator(`#game-tabs button[data-game="${game}"]`).click();
    await expect.poll(() => page.evaluate(() => window.sc2viewer.games.current())).toBe(game);
    for (const c of categories) await expect(page.locator(`#pane-${c.id}`), `${game}: pane ${c.id}`).toHaveCount(1);
    const { category, record } = await firstRecord(request, game, dataset, categories);
    await page.locator(`#tab-${category.id}`).click();
    await page.fill(`#search-${category.id}`, record.id);
    const row = page.locator(`#${category.id} li[data-id="${record.id.replaceAll('"', '\\"')}"]`);
    await row.click();
    await expect(page.locator(`#preview-${category.id} .name`), game).toHaveText(record.name);
    // Negative: the preview adds nothing.
    expect((await state()).items, game).toEqual([]);
    await page.locator(`#preview-add-${category.id}`).click();
    await expect(page.locator('#scene li')).toHaveCount(1);
    await idle();
    const [item] = (await state()).items;
    // `loaded` says whether the model has something to draw (a Ghost actor
    // may name a model whose groups are all left out): logged, then held
    // the same over the reload below.
    console.log(`contract: ${game} ${category.id} ${record.id}: ${item.path}, loaded ${item.loaded}`);
    expect(item.game, game).toBe(game);
    // Selected, then moved by its x field.
    await page.evaluate((ids) => window.SC2App.setSelection(ids), [item.id]);
    expect(await page.evaluate(() => window.SC2App.selectedIds())).toEqual([item.id]);
    const field = page.locator('#scene li').first().locator('input.x');
    await field.fill(String(item.x + 2));
    await field.press('Enter');
    expect((await state()).items[0].x, game).toBeCloseTo(item.x + 2, 6);
    // Copied and pasted with the keys, off the view.
    await page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement.blur());
    const panel = await page.locator('#gallery').boundingBox();
    await page.mouse.move(panel.x + panel.width / 2, panel.y + panel.height / 2);
    await page.evaluate((ids) => window.SC2App.setSelection(ids), [item.id]);
    await page.locator('body').press('Control+c');
    await page.locator('body').press('Control+v');
    await idle();
    const pasted = (await state()).items;
    expect(pasted.map((i) => [i.game, i.path]), game).toEqual([[game, item.path], [game, item.path]]);
    // Kept over a reload.
    await reloadScene(page);
    const back = (await state()).items;
    expect(back.map((i) => [i.game, i.path, i.loaded]), game).toEqual(pasted.map((i) => [i.game, i.path, item.loaded]));
    // Removed: the scene is empty again for the next game.
    for (const i of back) await page.evaluate((id) => window.sc2viewer.remove(id), i.id);
    expect((await state()).items, game).toEqual([]);
  }
  expect(errors).toEqual([]);
});

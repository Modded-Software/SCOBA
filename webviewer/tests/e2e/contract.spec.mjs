// The contract tests (SPEC-VIEWER 11, R-VIEW-91), page part: one suite, run
// once for every game /api/games lists as available. Each game passes the
// same checks through the shared page; nothing here names a game's own
// records or files. The tab shows a pane for each of the game's categories
// but a ground one (its records are listed by the ground button, R-VIEW-107);
// a record is previewed, added, selected, moved, copied, pasted, kept over a
// reload, removed. The protocol part is unit/contract-api.spec.mjs.
import { allowErrors, test, expect } from '../fixtures.mjs';
import { idle as settle, open, state as viewState } from '../page.mjs';
import { reloadScene } from '../scene.mjs';

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

test('page: in every available game a record is previewed, added, selected, moved, copied, pasted, kept, removed', async ({ page, request }) => {
  // The first Ghost actor's model has a group no material step finds: it is not drawn and is reported.
  allowErrors('scobaeditor: _actorProps: not drawn: group 0 dflt: found by no step of the material lookup');
  test.setTimeout(120_000);
  const errors = await open(page);
  const state = () => viewState(page);
  const idle = () => settle(page, 60_000);
  for (const { id: game } of (await gamesOf(request)).filter((g) => g.available)) {
    const dataset = (await get(request, `/api/${game}/datasets`)).default;
    const categories = await get(request, `/api/${game}/categories?${new URLSearchParams({ dataset })}`);
    await page.locator(`#game-tabs button[data-game="${game}"]`).click();
    await expect.poll(() => page.evaluate(() => window.scobaeditor.games.current())).toBe(game);
    // The game's page part names only categories the server lists (a file category such as models has no
    // record kind there). A ground category has no pane (negative); every other server category has one.
    const shown = await page.evaluate(() => window.scobaeditor.games.categories());
    expect(categories.map((c) => c.id), game).toEqual(expect.arrayContaining(shown.map((c) => c.id)));
    const ground = new Set(shown.filter((c) => c.ground).map((c) => c.id));
    for (const c of categories) await expect(page.locator(`#pane-${c.id}`), `${game}: pane ${c.id}`).toHaveCount(ground.has(c.id) ? 0 : 1);
    const { category, record } = await firstRecord(request, game, dataset, categories.filter((c) => !ground.has(c.id)));
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
    await page.evaluate((ids) => window.SCOBAEdit.setSelection(ids), [item.id]);
    expect(await page.evaluate(() => window.SCOBAEdit.selectedIds())).toEqual([item.id]);
    const field = page.locator('#scene li').first().locator('input.x');
    await field.fill(String(item.x + 2));
    await field.press('Enter');
    expect((await state()).items[0].x, game).toBeCloseTo(item.x + 2, 6);
    // Copied and pasted with the keys, off the view.
    await page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement.blur());
    const panel = await page.locator('#gallery').boundingBox();
    await page.mouse.move(panel.x + panel.width / 2, panel.y + panel.height / 2);
    await page.evaluate((ids) => window.SCOBAEdit.setSelection(ids), [item.id]);
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
    for (const i of back) await page.evaluate((id) => window.scobaeditor.remove(id), i.id);
    expect((await state()).items, game).toEqual([]);
  }
  expect(errors).toEqual([]);
});

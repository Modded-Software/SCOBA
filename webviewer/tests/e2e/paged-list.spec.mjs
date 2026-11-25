import { test, expect } from '../fixtures.mjs';
import { api } from '../api.mjs';
import { frames, idle, open } from '../page.mjs';

// The unit list loads a page at a time, as it is scrolled.

const PAGE = 60;

const rows = (page) => page.locator('#units li');
const scrollToEnd = (page) => page.locator('#units').evaluate((list) => list.scrollTo(0, list.scrollHeight));
const ids = (page) => rows(page).evaluateAll((list) => list.map((li) => li.dataset.id));

/**
 * Wait until the page has handled what it was told: the scroll events
 * fired (two frames), and nothing it asked for is still loading.
 */
async function settled(page) {
  await frames(page);
  await idle(page);
  await frames(page);
}

/** Count the units list requests made while `action` runs. */
async function requestsDuring(page, action) {
  let count = 0;
  const seen = (request) => {
    if (new URL(request.url()).pathname === '/api/sc2/records/units') count++;
  };
  page.on('request', seen);
  await action();
  await settled(page);
  page.off('request', seen);
  return count;
}

test('the unit list shows one page first and the whole total', async ({ page }) => {
  await open(page);
  await expect(rows(page)).toHaveCount(PAGE);
  const total = (await (await page.request.get(api.records('units', 'limit=1'))).json()).total;
  await expect(page.locator('#count-units')).toHaveText(`${total} units`);
});

test('scrolling to the end loads the next page, in order, without repeats', async ({ page }) => {
  await open(page);
  await expect(rows(page)).toHaveCount(PAGE);
  await scrollToEnd(page);
  await expect(rows(page)).toHaveCount(2 * PAGE);
  const shown = await ids(page);
  expect(new Set(shown).size).toBe(shown.length);
  const expected = (await (await page.request.get(api.records('units', { limit: String(2 * PAGE) }))).json()).items.map((i) => i.id);
  expect(shown).toEqual(expected);
});

test('a filtered list loads to its end and then asks for nothing more', async ({ page }) => {
  await open(page);
  await page.locator('#filter-units-race button[data-race="Zerg"]').click();
  const total = (await (await page.request.get(api.records('units', 'race=Zerg&limit=1'))).json()).total;
  expect(total).toBeGreaterThan(PAGE);
  await expect(page.locator('#count-units')).toHaveText(`${total} units`);
  // Each scroll to the end loads the next page, until all are shown.
  for (let shown = PAGE; shown < total; shown += PAGE) {
    await expect(rows(page)).toHaveCount(shown);
    await scrollToEnd(page);
  }
  await expect(rows(page)).toHaveCount(total);
  // Negative: at the end, scrolling makes no request and adds no row.
  expect(await requestsDuring(page, () => scrollToEnd(page))).toBe(0);
  await expect(rows(page)).toHaveCount(total);
});

test('negative: a hidden list asks for its first page only; shown, it fills its box', async ({ page }) => {
  /** By category: the offsets asked for. */
  const asked = {};
  page.on('request', (request) => {
    const url = new URL(request.url());
    const match = /^\/api\/sc2\/records\/(\w+)$/.exec(url.pathname);
    if (match) (asked[match[1]] ??= []).push(Number(url.searchParams.get('offset')));
  });
  await open(page);
  await expect(rows(page)).toHaveCount(PAGE);
  // Every list has had its chance to ask for more: none must have.
  await settled(page);
  console.log(`asked ${JSON.stringify(asked)}`);
  // The models pane asks for nothing without a search; every other list, its first page alone.
  // The terrain category has no pane (the ground button lists it), so it asks for nothing here.
  expect(Object.keys(asked).sort()).toEqual(['doodads', 'units']);
  for (const [category, offsets] of Object.entries(asked)) expect(offsets, category).toEqual([0]);
  // Shown, the doodad list pages as it is scrolled.
  await page.click('#tab-doodads');
  await expect(page.locator('#doodads li')).toHaveCount(PAGE);
  await page.locator('#doodads').evaluate((list) => list.scrollTo(0, list.scrollHeight));
  await expect(page.locator('#doodads li')).toHaveCount(2 * PAGE);
  expect(asked.doodads).toEqual([0, PAGE]);
});

test('a new search starts again at the first page', async ({ page }) => {
  await open(page);
  await scrollToEnd(page);
  await expect(rows(page)).toHaveCount(2 * PAGE);
  await page.fill('#search-units', 'marine');
  await expect(rows(page).first()).toHaveAttribute('data-id', 'Marine');
  const count = await rows(page).count();
  expect(count).toBeLessThanOrEqual(PAGE);
  const shown = await ids(page);
  expect(new Set(shown).size).toBe(shown.length);
});

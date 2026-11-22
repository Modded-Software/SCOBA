import { test, expect } from '@playwright/test';

// The unit list loads a page at a time, as it is scrolled.

const PAGE = 60;

async function open(page) {
  await page.goto('/');
  await page.waitForFunction(() => window.sc2viewer && window.sc2viewer.ready);
}

const rows = (page) => page.locator('#units li');
const scrollToEnd = (page) => page.locator('#units').evaluate((list) => list.scrollTo(0, list.scrollHeight));
const ids = (page) => rows(page).evaluateAll((list) => list.map((li) => li.dataset.id));

/** Count the /api/units requests made while `action` runs. */
async function requestsDuring(page, action) {
  let count = 0;
  const seen = (request) => {
    if (new URL(request.url()).pathname === '/api/units') count++;
  };
  page.on('request', seen);
  await action();
  await page.waitForTimeout(500);
  page.off('request', seen);
  return count;
}

test('the unit list shows one page first and the whole total', async ({ page }) => {
  await open(page);
  await expect(rows(page)).toHaveCount(PAGE);
  const total = (await (await page.request.get('/api/units?limit=1')).json()).total;
  await expect(page.locator('#unit-count')).toHaveText(`${total} units`);
});

test('scrolling to the end loads the next page, in order, without repeats', async ({ page }) => {
  await open(page);
  await expect(rows(page)).toHaveCount(PAGE);
  await scrollToEnd(page);
  await expect(rows(page)).toHaveCount(2 * PAGE);
  const shown = await ids(page);
  expect(new Set(shown).size).toBe(shown.length);
  const expected = (await (await page.request.get(`/api/units?limit=${2 * PAGE}`)).json()).items.map((i) => i.id);
  expect(shown).toEqual(expected);
});

test('a filtered list loads to its end and then asks for nothing more', async ({ page }) => {
  await open(page);
  await page.locator('#races button[data-race="Zerg"]').click();
  const total = (await (await page.request.get('/api/units?race=Zerg&limit=1')).json()).total;
  expect(total).toBeGreaterThan(PAGE);
  await expect(page.locator('#unit-count')).toHaveText(`${total} units`);
  for (let i = 0; i < Math.ceil(total / PAGE) + 1; i++) {
    await scrollToEnd(page);
    await page.waitForTimeout(150);
  }
  await expect(rows(page)).toHaveCount(total);
  // Negative: at the end, scrolling makes no request and adds no row.
  expect(await requestsDuring(page, () => scrollToEnd(page))).toBe(0);
  await expect(rows(page)).toHaveCount(total);
});

test('a new search starts again at the first page', async ({ page }) => {
  await open(page);
  await scrollToEnd(page);
  await expect(rows(page)).toHaveCount(2 * PAGE);
  await page.fill('#unit-search', 'marine');
  await expect(rows(page).first()).toHaveAttribute('data-id', 'Marine');
  const count = await rows(page).count();
  expect(count).toBeLessThanOrEqual(PAGE);
  const shown = await ids(page);
  expect(new Set(shown).size).toBe(shown.length);
});

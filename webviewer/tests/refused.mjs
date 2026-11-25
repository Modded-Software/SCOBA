import { expect } from './fixtures.mjs';

// The refused-settings panel (src/page/core/refusals.ts, R-VIEW-73): a
// stored setting the page cannot use stops the start. The page shows the
// panel, and `ready` stays unset.

/** Store `entries` (full key -> stored text) and reload. */
export async function storeAndReload(page, entries) {
  await page.evaluate((all) => {
    for (const [key, text] of Object.entries(all)) localStorage.setItem(key, text);
  }, entries);
  await page.reload();
}

/** Wait for the panel; its rows as { key, stored, reason }. The page did not start. */
export async function refusedRows(page) {
  await expect(page.locator('#settings-refused')).toBeVisible({ timeout: 10_000 });
  const rows = await page.locator('#settings-refused li[data-key]').evaluateAll((items) =>
    items.map((li) => ({
      key: li.dataset.key,
      stored: li.querySelector('.refused-stored').textContent,
      reason: li.querySelector('.refused-reason').textContent,
    })),
  );
  expect(await page.evaluate(() => Boolean(window.scobaeditor && window.scobaeditor.ready)), 'negative: the page did not start').toBe(false);
  return rows;
}

/** Every stored key of the page, with its text. */
export const storedKeys = (page) =>
  page.evaluate(() => Object.fromEntries(Object.keys(localStorage).filter((k) => k.startsWith('viewer.')).sort().map((k) => [k, localStorage.getItem(k)])));

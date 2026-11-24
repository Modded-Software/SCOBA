import { test, expect } from '@playwright/test';

// The game tabs and the drawer handles (src/page/ui/gametabs.ts, drawers.ts;
// REQ-VIEWER R-VIEW-20 to 24 and 27). The server lists sc2 and ghost. A
// routed /api/games replaces ghost with one the server cannot open and adds
// one the page has no module for. Both tabs must be disabled.

async function open(page) {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto('/');
  await expect.poll(() => errors.join(' | ') || page.evaluate(() => Boolean(window.sc2viewer && window.sc2viewer.ready)), { timeout: 20_000 }).toBe(true);
  return errors;
}

/** Answer /api/games with the server's list, these games replacing the ones of the same id. */
async function withGames(page, extra) {
  await page.route('**/api/games', async (route) => {
    const body = await (await route.fetch()).json();
    const ids = new Set(extra.map((g) => g.id));
    await route.fulfill({ json: { ...body, games: [...body.games.filter((g) => !ids.has(g.id)), ...extra] } });
  });
}

const box = (page, selector) => page.locator(selector).boundingBox();
const settled = (page) =>
  page.waitForFunction(() => ['gallery', 'instances', 'gallery-handle', 'instances-handle', 'game-tabs'].every((id) => document.getElementById(id).getAnimations().length === 0));

test('one tab per game, vertical, at the top of the gallery right edge; sc2 is chosen', async ({ page }) => {
  const errors = await open(page);
  const tabs = page.locator('#game-tabs button[data-game]');
  await expect(tabs).toHaveCount(2);
  const sc2 = page.locator('#game-tabs button[data-game="sc2"]');
  await expect(sc2).toBeEnabled();
  await expect(sc2).toHaveAttribute('aria-pressed', 'true');
  // Ghost is the second tab, open to choose, not chosen.
  const ghostTab = page.locator('#game-tabs button[data-game="ghost"]');
  await expect(ghostTab).toBeEnabled();
  await expect(ghostTab).toHaveAttribute('aria-pressed', 'false');
  expect(await page.evaluate(() => window.sc2viewer.games.current())).toBe('sc2');
  const [tab, gallery] = [await box(page, '#game-tabs button[data-game="sc2"]'), await box(page, '#gallery')];
  // At the right edge, from the top.
  expect(Math.abs(tab.x - (gallery.x + gallery.width))).toBeLessThan(3);
  expect(tab.y - gallery.y).toBeLessThan(12);
  // Vertical: taller than wide, the text turned.
  expect(tab.height).toBeGreaterThan(tab.width);
  expect(await sc2.evaluate((n) => getComputedStyle(n).writingMode)).toBe('vertical-rl');
  // Negative: the startup pick is not a choice and is not stored.
  expect(await page.evaluate(() => localStorage.getItem('viewer.game'))).toBeNull();
  // A click is a choice: it is stored (R-VIEW-22).
  await sc2.click();
  await expect.poll(() => page.evaluate(() => localStorage.getItem('viewer.game'))).toBe('"sc2"');
  // The labels; 14 px; the chosen tab bold, the other not.
  await expect(sc2).toHaveText('SC2');
  await expect(ghostTab).toHaveText('SC: G');
  const style = (n) => {
    const s = getComputedStyle(n);
    return [s.fontSize, s.fontWeight];
  };
  expect(await sc2.evaluate(style)).toEqual(['14px', '700']);
  expect(await ghostTab.evaluate(style)).toEqual(['14px', '400']);
  await ghostTab.click();
  await expect(ghostTab).toHaveAttribute('aria-pressed', 'true');
  expect(await ghostTab.evaluate(style)).toEqual(['14px', '700']);
  expect(await sc2.evaluate(style)).toEqual(['14px', '400']);
  expect(errors).toEqual([]);
});

test('a game the server cannot open and one with no page module: disabled, the reason as the title', async ({ page }) => {
  await withGames(page, [
    { id: 'ghost', label: 'StarCraft: Ghost', tab: 'SC: G', available: false, reason: 'GHOST_PATH is not set' },
    { id: 'other', label: 'Other Game', tab: 'Other', available: true, reason: null },
  ]);
  const errors = await open(page);
  await expect(page.locator('#game-tabs button[data-game]')).toHaveCount(3);
  const ghost = page.locator('#game-tabs button[data-game="ghost"]');
  const other = page.locator('#game-tabs button[data-game="other"]');
  await expect(ghost).toBeDisabled();
  await expect(ghost).toHaveAttribute('title', 'StarCraft: Ghost: GHOST_PATH is not set');
  await expect(other).toBeDisabled();
  await expect(other).toHaveAttribute('title', 'Other Game: the page has no module for Other Game');
  expect(await page.evaluate(() => [window.sc2viewer.games.refusal('ghost'), window.sc2viewer.games.refusal('sc2')])).toEqual(['GHOST_PATH is not set', null]);
  // Negative: choosing a refused game fails and leaves the gallery on sc2.
  const failed = await page.evaluate(() => window.sc2viewer.games.choose('ghost').then(() => 'chose', (e) => e.message));
  expect(failed).toBe('GHOST_PATH is not set');
  expect(await page.evaluate(() => window.sc2viewer.games.current())).toBe('sc2');
  await expect(page.locator('#game-tabs button[data-game="sc2"]')).toHaveAttribute('aria-pressed', 'true');
  // A refused choice is not stored.
  expect(await page.evaluate(() => localStorage.getItem('viewer.game'))).toBeNull();
  // Negative: a click on a disabled tab changes nothing.
  await ghost.click({ force: true });
  expect(await page.evaluate(() => [window.sc2viewer.games.current(), localStorage.getItem('viewer.game')])).toEqual(['sc2', null]);
  expect(errors).toEqual([]);
});

test('negative: a stored game that is refused falls back to the default; the stored sc2 is kept over a reload', async ({ page }) => {
  await withGames(page, [{ id: 'ghost', label: 'StarCraft: Ghost', tab: 'SC: G', available: false, reason: 'GHOST_PATH is not set' }]);
  await page.addInitScript(() => {
    if (!sessionStorage.getItem('seeded')) {
      localStorage.setItem('viewer.game', '"ghost"');
      sessionStorage.setItem('seeded', '1');
    }
  });
  const errors = await open(page);
  expect(await page.evaluate(() => window.sc2viewer.games.current())).toBe('sc2');
  // The units list of sc2 shows.
  await expect(page.locator('#search-units')).toBeVisible();
  // The fallback keeps the stored game for when it opens again.
  expect(await page.evaluate(() => localStorage.getItem('viewer.game'))).toBe('"ghost"');
  await page.evaluate(() => window.sc2viewer.games.choose('sc2'));
  expect(await page.evaluate(() => localStorage.getItem('viewer.game'))).toBe('"sc2"');
  await page.reload();
  await expect.poll(() => page.evaluate(() => Boolean(window.sc2viewer && window.sc2viewer.ready)), { timeout: 20_000 }).toBe(true);
  expect(await page.evaluate(() => window.sc2viewer.games.current())).toBe('sc2');
  expect(errors.filter((e) => !e.includes('stored game'))).toEqual([]);
});

test('the handles sit at the bottom of each panel right edge', async ({ page }) => {
  await open(page);
  for (const [panel, handle] of [['#gallery', '#gallery-handle'], ['#instances', '#instances-handle']]) {
    const [p, h] = [await box(page, panel), await box(page, handle)];
    expect(Math.abs(h.x - (p.x + p.width)), handle).toBeLessThan(3);
    // The bottom: its lower edge near the panel's, not at its top.
    expect(p.y + p.height - (h.y + h.height), handle).toBeLessThan(16);
    expect(p.y + p.height - (h.y + h.height), handle).toBeGreaterThanOrEqual(0);
    expect(h.y - p.y, `${handle} not at the top`).toBeGreaterThan(p.height / 2);
  }
  // Negative: no handle covers a game tab.
  const [tab, handle] = [await box(page, '#game-tabs button[data-game="sc2"]'), await box(page, '#gallery-handle')];
  expect(tab.y + tab.height).toBeLessThanOrEqual(handle.y);
});

test('with the gallery closed the tabs stay at the window edge; a click opens the gallery', async ({ page }) => {
  const errors = await open(page);
  await page.locator('#gallery-handle').click();
  await settled(page);
  expect(await page.evaluate(() => window.SC2App.drawerState())).toEqual({ gallery: false, instances: true });
  const tab = await box(page, '#game-tabs button[data-game="sc2"]');
  expect(tab.x).toBeLessThan(2);
  await expect(page.locator('#game-tabs button[data-game="sc2"]')).toBeVisible();
  // The tab opens the gallery on its game; the instances drawer stays as it was.
  await page.locator('#game-tabs button[data-game="sc2"]').click();
  await settled(page);
  expect(await page.evaluate(() => window.SC2App.drawerState())).toEqual({ gallery: true, instances: true });
  const [after, gallery] = [await box(page, '#game-tabs button[data-game="sc2"]'), await box(page, '#gallery')];
  expect(Math.abs(after.x - (gallery.x + gallery.width))).toBeLessThan(3);
  expect(await page.evaluate(() => window.sc2viewer.games.current())).toBe('sc2');
  expect(errors).toEqual([]);
});

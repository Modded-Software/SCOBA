import { test, expect } from '../fixtures.mjs';
import { frames, idle, open, state, view } from '../page.mjs';

// The hex grid ground and the skybox. What the grid and the sky look like
// (hexagons, line width, glow, colours) is an operator check (SPEC-VIEWER 14);
// these tests read what the ground and the sky hold. The skybox list route:
// tests/unit/backdrops-api.spec.mjs.

/** Look straight down on the origin. */
const topDown = (page) => view(page, { yaw: -Math.PI / 2, pitch: Math.PI / 2 - 0.01, distance: 8, target: [0, 0, 0] });

/** The ground spots the last frame drew. */
const spots = async (page) => {
  await frames(page);
  return page.evaluate(() => window.SC2App.ground.spotsDrawn);
};

test('the ground grid is on by default; its button turns it off and on', async ({ page }) => {
  const errors = await open(page);
  expect((await state(page)).grid).toBe(true);
  await expect(page.locator('#grid-toggle')).toHaveClass(/\bon\b/);
  await page.click('#grid-toggle');
  expect((await state(page)).grid).toBe(false);
  await expect(page.locator('#grid-toggle')).not.toHaveClass(/\bon\b/);
  await page.click('#grid-toggle');
  expect((await state(page)).grid).toBe(true);
  await expect(page.locator('#grid-toggle')).toHaveClass(/\bon\b/);
  expect(errors).toEqual([]);
});

test('a unit gives the grid a spot where it stands; removed, the spot goes', async ({ page }) => {
  const errors = await open(page);
  await topDown(page);
  expect(await spots(page)).toBe(0);
  const id = await page.evaluate(() => window.sc2viewer.addUnit('Marine', { x: 0, y: 0, team: 1, pick: 0.5 }));
  await idle(page);
  expect(await spots(page)).toBe(1);
  await page.evaluate((i) => window.sc2viewer.remove(i), id);
  expect(await spots(page)).toBe(0);
  expect(errors).toEqual([]);
});

test('the ground point under the mouse is the pointer; over a panel there is none', async ({ page }) => {
  const errors = await open(page);
  await topDown(page);
  const at = await page.evaluate(() => window.sc2viewer.screenOf([1.3, 0, 0]));
  await page.mouse.move(at[0], at[1]);
  const pointer = (await state(page)).pointer;
  expect(pointer[0]).toBeCloseTo(1.3, 1);
  expect(pointer[1]).toBeCloseTo(0, 1);
  // Negative: over the panel the pointer is off the ground.
  await page.mouse.move(100, 100);
  expect((await state(page)).pointer).toBe(null);
  expect(errors).toEqual([]);
});

test('the sky button opens a dialog; Escape closes it and changes nothing; a picked skybox loads and is drawn; "none" takes it away', async ({ page }) => {
  const errors = await open(page);
  await expect(page.locator('#sky-dialog')).toBeHidden();
  // Negative: Escape closes the dialog without changing the sky.
  await page.click('#sky-button');
  await expect(page.locator('#sky-dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.locator('#sky-dialog')).toBeHidden();
  expect((await state(page)).sky).toBe(null);

  await page.click('#sky-button');
  await expect(page.locator('#sky-dialog')).toBeVisible();
  await expect(page.locator('#sky-dialog .picker-list li').first()).toBeVisible();
  await page.fill('#sky-dialog input[type=search]', 'aiur');
  await page.locator('#sky-dialog .picker-list li[data-id="AiurSkybox"]').click();
  await expect(page.locator('#sky-dialog')).toBeHidden();
  expect((await state(page)).sky).toMatchObject({ id: 'AiurSkybox' });
  await expect(page.locator('#sky-button')).toHaveClass(/\bon\b/);
  await idle(page);
  await page.waitForFunction(() => window.sc2viewer.state().skyLoaded);
  await frames(page);
  const s = await state(page);
  expect(s.skyDrawn).toBe(true);
  expect(s.skyTextures).toBeGreaterThan(0);

  await page.click('#sky-button');
  await page.locator('#sky-dialog .picker-list li[data-id=""]').click();
  const none = await state(page);
  expect(none.sky).toBe(null);
  expect(none.skyDrawn).toBe(false);
  await expect(page.locator('#sky-button')).not.toHaveClass(/\bon\b/);
  expect(errors).toEqual([]);
});

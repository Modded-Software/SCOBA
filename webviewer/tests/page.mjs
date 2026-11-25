// The page helpers every spec shares: open the viewer, read its state,
// wait for it. One copy here; the specs do not keep their own.

import { expect } from './fixtures.mjs';

/**
 * Open the viewer at `path` and wait until it is ready. Returns the list
 * the page's errors go into: uncaught errors, console errors and the
 * viewer's own "viewer:" reports. `grid` and `particles` false switch the
 * ground grid and the particles off; `tab` clicks a gallery tab.
 */
export async function open(page, { path = '/', grid = true, particles = true, tab = null } = {}) {
  const errors = watch(page);
  await page.goto(path);
  await expect.poll(() => errors.join(' | ') || page.evaluate(() => Boolean(window.sc2viewer && window.sc2viewer.ready)), { timeout: 20_000 }).toBe(true);
  if (!grid) await page.evaluate(() => window.sc2viewer.setGrid(false));
  if (!particles) await page.evaluate(() => window.sc2viewer.probe('m3', 'setParticles', false));
  if (tab) await page.locator(`#tab-${tab}`).click();
  return errors;
}

/** Collect the page's errors from now on (see open). */
export function watch(page) {
  const errors = [];
  page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`));
  page.on('console', (m) => {
    if (m.type() === 'error' || m.text().startsWith('viewer:')) errors.push(`console: ${m.text()}`);
  });
  return errors;
}

/** The scene state (src/page/features/inspect/state.ts). */
export const state = (page) => page.evaluate(() => window.sc2viewer.state());

/** One item of the scene state, by id. */
export const itemOf = async (page, id) => (await state(page)).items.find((item) => item.id === id);

/** Wait until nothing loads: no model being added, no texture in flight. */
export const idle = (page, timeout = 30_000) => page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout });

/** Wait two animation frames: the page has drawn what it was told. */
export const frames = (page) => page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))));

/** Set the camera (yaw, pitch, distance, target). */
export const view = (page, camera) => page.evaluate((c) => window.sc2viewer.view(c), camera);

/** A page point on the instance's picture, from the pick buffer; null when none is in view. */
export const onItem = (page, id) => page.evaluate((i) => window.sc2viewer.itemPixel(i), id);

/** Where a world point lands, in page coordinates. */
export const screenOf = (page, point) => page.evaluate((p) => window.sc2viewer.screenOf(p), point);

/** The texture window's page, once it is open. */
export const textureFrame = (page) => page.frames().find((frame) => frame.url().includes('/texture-viewer.html'));

/**
 * Make `asset` the texture page's current entry by a click on its row. The
 * list is drawn again when states arrive, so a click can land on a row just
 * replaced: the row is found again and clicked until the entry is current.
 * Returns the row's place in the list.
 */
export async function chooseRow(frame, asset) {
  let index = -1;
  await expect(async () => {
    index = (await frame.evaluate(() => window.hdtex.entries())).findIndex((entry) => entry.asset === asset);
    expect(index, asset).toBeGreaterThanOrEqual(0);
    await frame.locator('#list .row').nth(index).click();
    expect(await frame.evaluate(() => window.hdtex.state().current?.asset)).toBe(asset);
  }).toPass();
  return index;
}

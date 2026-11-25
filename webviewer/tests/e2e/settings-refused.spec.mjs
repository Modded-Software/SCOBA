import { allowErrors, test, expect } from '../fixtures.mjs';
import { open } from '../page.mjs';
import { refusedRows, storeAndReload, storedKeys } from '../refused.mjs';

// The refused-settings panel in the page (src/page/core/refusals.ts,
// SPEC-VIEWER 10.3, R-VIEW-73): a stored key the page cannot use stops the
// start. The panel lists each with what is stored and why; "Clear refused
// settings" removes exactly those keys. Each key's own check is
// tests/unit/settings.spec.mjs.

const GOOD_DRAWERS = JSON.stringify({ gallery: true, instances: false });
const DEFAULT_VIEW = { yaw: -Math.PI / 2, pitch: 0.5, distance: 9, target: [0, 0, 0.8] };
const ready = (page) => expect.poll(() => page.evaluate(() => Boolean(window.sc2viewer && window.sc2viewer.ready)), { timeout: 20_000 }).toBe(true);

test('every refused key is listed, sorted, with its stored text and reason; Clear removes those only', async ({ page }) => {
  allowErrors(/^console\.error: viewer: stored settings refused: viewer\.camera: .*viewer\.nosuch: the page has no such setting; viewer\.view: the view: no "ground"$/);
  await open(page);
  await storeAndReload(page, {
    'viewer.drawers': GOOD_DRAWERS,
    'viewer.view': JSON.stringify({ grid: true, sky: null }),
    'viewer.nosuch': '1',
    'viewer.camera': 'not json',
    // Not a key of the page: not checked, not cleared.
    'other.thing': 'x',
  });
  const rows = await refusedRows(page);
  expect(rows.map((r) => r.key)).toEqual(['viewer.camera', 'viewer.nosuch', 'viewer.view']);
  expect(rows[0]).toMatchObject({ key: 'viewer.camera', stored: 'not json' });
  expect(rows[0].reason).toMatch(/JSON/);
  expect(rows[1]).toEqual({ key: 'viewer.nosuch', stored: '1', reason: 'the page has no such setting' });
  expect(rows[2]).toEqual({ key: 'viewer.view', stored: JSON.stringify({ grid: true, sky: null }), reason: 'the view: no "ground"' });
  // Negative: a good key is not listed, and no refused key was overwritten.
  expect(rows.map((r) => r.key)).not.toContain('viewer.drawers');
  expect((await storedKeys(page))['viewer.camera']).toBe('not json');

  await page.locator('#settings-refused-clear').click();
  await ready(page);
  await expect(page.locator('#settings-refused')).toHaveCount(0);
  const kept = await storedKeys(page);
  // The bad text is gone; the start writes the camera's declared default in its place.
  expect(JSON.parse(kept['viewer.camera'])).toEqual(DEFAULT_VIEW);
  expect(kept['viewer.nosuch'], 'cleared').toBeUndefined();
  // The start writes the view again (restoreView sets the grid): the declared default.
  expect(JSON.parse(kept['viewer.view'])).toEqual({ grid: true, sky: null, ground: null });
  expect(kept['viewer.drawers'], 'negative: a good key is kept').toBe(GOOD_DRAWERS);
  expect(await page.evaluate(() => localStorage.getItem('other.thing')), 'negative: a key of another page is kept').toBe('x');
  expect(await page.evaluate(() => window.SC2App.drawerState())).toEqual({ gallery: true, instances: false });
  // Nothing stored for the camera now: the declared default view.
  expect(await page.evaluate(() => window.SC2App.cameraStart)).toBe('default');
  const camera = (await page.evaluate(() => window.sc2viewer.state())).camera;
  expect(camera.distance).toBeCloseTo(DEFAULT_VIEW.distance, 6);
  expect(camera.yaw).toBeCloseTo(DEFAULT_VIEW.yaw, 6);
});

test('negative: stored landmarks whose chosen one is not listed stop the start; a listed one does not', async ({ page }) => {
  allowErrors(/^console\.error: viewer: stored settings refused: viewer\.landmarks: the chosen landmark 5 is not one of them$/);
  await open(page);
  const mark = { id: 1, name: 'x', yaw: 0, pitch: 0, distance: 9, target: [0, 0, 0] };
  const bad = JSON.stringify({ list: [mark], selected: 5 });
  await storeAndReload(page, { 'viewer.landmarks': bad });
  expect(await refusedRows(page)).toEqual([{ key: 'viewer.landmarks', stored: bad, reason: 'the chosen landmark 5 is not one of them' }]);
  await storeAndReload(page, { 'viewer.landmarks': JSON.stringify({ list: [mark], selected: 1 }) });
  await ready(page);
  await expect(page.locator('#settings-refused')).toHaveCount(0);
  expect(await page.evaluate(() => window.SC2App.landmarkState())).toMatchObject({ selected: 1, start: 'stored' });
});

test('negative: with every stored key good there is no panel, and a stored camera reads as stored', async ({ page }) => {
  await open(page);
  const view = { yaw: 0.7, pitch: 0.9, distance: 31, target: [12, -5, 0] };
  await storeAndReload(page, { 'viewer.drawers': GOOD_DRAWERS, 'viewer.camera': JSON.stringify(view) });
  await ready(page);
  await expect(page.locator('#settings-refused')).toHaveCount(0);
  expect(await page.evaluate(() => window.SC2App.cameraStart)).toBe('stored');
  expect((await page.evaluate(() => window.sc2viewer.state())).camera.distance).toBeCloseTo(31, 6);
});

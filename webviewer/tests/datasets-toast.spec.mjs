import { readFile, utimes, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

import { test, expect } from '@playwright/test';

// A dataset whose files changed on disk: the page notices, and a toast
// slides up at the bottom centre of the view asking to reload the data
// (public/js/datasets.js). Yes rebuilds the dataset and reloads the page;
// no hides the toast until the files change again.
// The test edits the fixture dataset fx (scripts/test-fixture.sh) and puts
// it back as it was.

const ROOT = process.env.WEBVIEWER_DATASETS;
const ACTORS = join(ROOT ?? '', 'fx', 'map', 'Base.SC2Data', 'GameData', 'ActorData.xml');
// The change time test-fixture.sh gives every fixture file.
const STAMP = new Date('2026-01-01T00:00:00');

async function open(page, hash = '') {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto('/' + hash);
  await expect.poll(() => errors.join(' | ') || page.evaluate(() => Boolean(window.sc2viewer && window.sc2viewer.ready)), { timeout: 20_000 }).toBe(true);
  return errors;
}

const state = (page) => page.evaluate(() => window.sc2viewer.state());
const idle = (page) => page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 30_000 });
const toast = (page) => page.evaluate(() => window.SC2App.datasetToast());
const check = (page) => page.evaluate(() => window.SC2App.checkDatasets());
const fx = async (request) => (await (await request.get('/api/datasets')).json()).datasets.find((d) => d.id === 'fx');

/** Set the Marine's actor scale in the fixture's map layer; `when`: the file's new change time. */
async function setScale(original, value, when) {
  await writeFile(ACTORS, original.replace('<Scale value="2.000000"/>', `<Scale value="${value}"/>`));
  await utimes(ACTORS, when, when);
}

test('a changed dataset raises the toast; no hides it; yes reloads the data and the page', async ({ page, request }) => {
  test.setTimeout(300_000);
  expect(ROOT, 'WEBVIEWER_DATASETS (set by scripts/test.sh)').toBeTruthy();
  const original = await readFile(ACTORS, 'utf8');
  expect(original).toContain('<Scale value="2.000000"/>');
  try {
    const errors = await open(page);
    await page.evaluate(() => window.sc2viewer.view({ yaw: 0.4, pitch: 0.7, distance: 14, target: [1, 2, 0] }));
    await page.evaluate(() => window.sc2viewer.addUnit('Marine', { x: 1, y: 2, pick: 0.5, dataset: 'fx' }));
    await idle(page);
    expect((await state(page)).items[0].dataScale).toEqual([2, 2, 2]);

    // Negative: nothing changed, no toast. It waits below the bottom edge.
    await check(page);
    expect(await toast(page)).toMatchObject({ up: false, dataset: null });
    await expect(page.locator('#dataset-toast')).toBeHidden();
    const viewport = page.viewportSize();
    const resting = await page.locator('#dataset-toast').evaluate((n) => n.getBoundingClientRect().top);
    expect(resting).toBeGreaterThanOrEqual(viewport.height);
    expect(await page.locator('#dataset-toast').evaluate((n) => getComputedStyle(n).transitionDuration)).toContain('0.25s');

    // The fixture's file changes on disk.
    await setScale(original, '3.000000', new Date('2026-02-02T00:00:00'));
    await expect.poll(async () => (await fx(request)).changed).toBe(true);
    // Negative: the other datasets did not change.
    const others = (await (await request.get('/api/datasets')).json()).datasets.filter((d) => d.id !== 'fx');
    expect(others.map((d) => d.changed)).toEqual([false, false]);

    // The page finds out by itself (it asks every few seconds).
    await expect.poll(async () => (await toast(page)).up, { timeout: 10_000 }).toBe(true);
    expect(await toast(page)).toMatchObject({ dataset: 'fx', text: 'Dataset "Test fixture" changed on disk. Reload the data?' });
    await expect(page.locator('#dataset-toast')).toBeVisible();
    await expect(page.locator('#dataset-toast-yes')).toBeVisible();
    await expect(page.locator('#dataset-toast-no')).toBeVisible();
    // Slid up: at the bottom centre of the part of the view no panel covers.
    await page.waitForTimeout(400);
    const box = await page.locator('#dataset-toast').boundingBox();
    const view = await page.evaluate(() => window.SC2App.visibleRect());
    expect(Math.abs(box.x + box.width / 2 - (view.left + view.right) / 2)).toBeLessThan(2);
    expect(box.y + box.height).toBeLessThanOrEqual(viewport.height - 8);
    expect(box.y + box.height).toBeGreaterThan(viewport.height - 40);
    expect(box.x).toBeGreaterThan(view.left);
    // Negative: asking is not reloading. The instance is as it was.
    expect((await state(page)).items[0].dataScale).toEqual([2, 2, 2]);

    // No: it goes down and stays down for this change.
    await page.click('#dataset-toast-no');
    expect(await toast(page)).toMatchObject({ up: false, dataset: null });
    await check(page);
    expect((await toast(page)).up).toBe(false);
    await expect(page.locator('#dataset-toast')).toBeHidden();
    expect((await fx(request)).changed).toBe(true);

    // The files change again: it asks again.
    await setScale(original, '4.000000', new Date('2026-03-03T00:00:00'));
    await expect.poll(async () => {
      await check(page);
      return (await toast(page)).up;
    }).toBe(true);

    // Yes: the server rebuilds the dataset, then the page reloads with the new data.
    const loaded = page.waitForEvent('load', { timeout: 240_000 });
    await page.click('#dataset-toast-yes');
    expect((await toast(page)).text).toBe('Reloading dataset "Test fixture"…');
    await expect(page.locator('#dataset-toast-yes')).toBeDisabled();
    await loaded;
    await expect.poll(() => page.evaluate(() => Boolean(window.sc2viewer && window.sc2viewer.ready)), { timeout: 20_000 }).toBe(true);
    await idle(page);
    const s = await state(page);
    expect(s.items).toHaveLength(1);
    expect(s.items[0]).toMatchObject({ unit: 'Marine', dataset: 'fx', x: 1, y: 2 });
    expect(s.items[0].dataScale).toEqual([4, 4, 4]);
    // The camera is where it was.
    expect(s.camera.yaw).toBeCloseTo(0.4, 6);
    expect(s.camera.distance).toBeCloseTo(14, 6);
    expect((await fx(request)).changed).toBe(false);
    expect((await (await request.get('/api/unit?id=Marine&dataset=fx')).json()).actorScale).toEqual([4, 4, 4]);
    await check(page);
    expect((await toast(page)).up).toBe(false);
    // Negative: the other datasets kept their data.
    expect((await (await request.get('/api/unit?id=Marine&dataset=stock')).json()).actorScale).toEqual([1, 1, 1]);
    expect(errors).toEqual([]);
  } finally {
    // The fixture as it was, and its catalog with it.
    await writeFile(ACTORS, original);
    await utimes(ACTORS, STAMP, STAMP);
    const response = await request.post('/api/dataset/reload?id=fx', { timeout: 240_000 });
    expect(response.status()).toBe(200);
  }
  expect((await (await request.get('/api/unit?id=Marine&dataset=fx')).json()).actorScale).toEqual([2, 2, 2]);
  expect((await fx(request)).changed).toBe(false);
});

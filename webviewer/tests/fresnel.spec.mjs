import { test, expect } from '@playwright/test';

// The layer fresnel term (psmateriallayer.fx CalcFresnelTerm, WhiteoutFlakes
// M3FresnelTerm): 1 - |N.V| to the exponent, inverted for mode 2, then
// saturate(f * (max - min) + min). Operator 2026-11-23: Diablo, Lord of
// Terror (SpaceDiablo) drew white: its emissive layer (plasmafield1_orange,
// x1.3, emissive multiplier 3.3) has fresnel mode 1, a rim glow, and was
// applied over the whole body.

async function open(page) {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => {
    if (m.text().startsWith('viewer:') || m.type() === 'error') errors.push(m.text());
  });
  await page.goto('/');
  await expect.poll(() => errors.join(' | ') || page.evaluate(() => Boolean(window.sc2viewer && window.sc2viewer.ready)), { timeout: 10_000 }).toBe(true);
  await page.evaluate(() => {
    window.sc2viewer.setGrid(false);
    window.sc2viewer.setParticles(false);
  });
  return errors;
}

const idle = (page) => page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 20_000 });

/** Fresnel layers of one item: material, layer type, mode, exponent, min, max offset. */
const fresnelLayers = (page, id) => page.evaluate((i) => {
  const item = window.SC2App.items.find((x) => x.id === i);
  return item.model.materials[1].flatMap((m) => m.layers.filter((l) => l.active && l.layer && l.layer.fresnelType).map((l) => [m.name, l.type, l.layer.fresnelType, l.layer.fresnelExponent, l.layer.fresnelMin, l.layer.fresnelMaxOffset]));
}, id);

/** Frame statistics with fresnel on and off; also the share of near-white pixels. */
async function onOff(page) {
  return page.evaluate(() => {
    const v = window.sc2viewer;
    v.setFresnel(true);
    const on = v.colorStats();
    const onWhite = v.whiteShare();
    v.setFresnel(false);
    const off = v.colorStats();
    const offWhite = v.whiteShare();
    v.setFresnel(true);
    return { on: { ...on, white: onWhite }, off: { ...off, white: offWhite } };
  });
}

test('Diablo: the emissive rim layer glows at the silhouette only; without the term the body goes white', async ({ page }) => {
  const errors = await open(page);
  const id = await page.evaluate(() => window.sc2viewer.addUnit('SpaceDiablo', { x: 0, y: 0, rot: 0, pick: 0.5, dataset: 'stock' }));
  await idle(page);
  const layers = await fresnelLayers(page, id);
  console.log('fresnel layers', JSON.stringify(layers));
  expect(layers).toContainEqual(['01 - Default', 'emissive', 1, 1, 0, 1]);
  await page.evaluate(() => window.sc2viewer.view({ yaw: -Math.PI / 2, pitch: 0.2, distance: 9, target: [0, 0, 2] }));
  const s = await onOff(page);
  console.log('diablo', JSON.stringify({ on: [s.on.pixels, s.on.brightness.toFixed(1), s.on.white.toFixed(3)], off: [s.off.pixels, s.off.brightness.toFixed(1), s.off.white.toFixed(3)] }));
  expect(s.on.pixels).toBeGreaterThan(1000);
  // Same coverage: the term changes colour, not shape.
  expect(Math.abs(s.on.pixels - s.off.pixels)).toBeLessThan(s.off.pixels * 0.02);
  // Without the term most of the body is near white; with it, little is.
  expect(s.off.white).toBeGreaterThan(0.15);
  expect(s.on.white).toBeLessThan(s.off.white * 0.5);
  expect(s.on.brightness).toBeLessThan(s.off.brightness - 20);
  expect(errors).toEqual([]);
});

test('negative: a model with no fresnel layer draws the same frame with the term on and off', async ({ page }) => {
  const errors = await open(page);
  const id = await page.evaluate(() => window.sc2viewer.addUnit('Marine', { x: 0, y: 0, rot: 0, pick: 0.5, dataset: 'stock' }));
  await idle(page);
  expect(await fresnelLayers(page, id)).toEqual([]);
  await page.evaluate(() => window.sc2viewer.view({ yaw: -Math.PI / 2, pitch: 0.2, distance: 4, target: [0, 0, 0.8] }));
  const s = await onOff(page);
  expect(s.on.pixels).toBeGreaterThan(500);
  expect(s.on).toEqual(s.off);
  expect(errors).toEqual([]);
});

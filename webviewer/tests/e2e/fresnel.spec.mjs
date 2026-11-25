import { test, expect } from '../fixtures.mjs';
import { idle, open } from '../page.mjs';

// The layer fresnel term (psmateriallayer.fx CalcFresnelTerm, WhiteoutFlakes
// M3FresnelTerm): 1 - |N.V| to the exponent, inverted for mode 2, then
// saturate(f * (max - min) + min). Operator 2026-11-23: Diablo, Lord of
// Terror (SpaceDiablo) drew white: its emissive layer (plasmafield1_orange,
// x1.3, emissive multiplier 3.3) has fresnel mode 1, a rim glow, and was
// applied over the whole body. What the glow looks like is an operator
// check (SPEC-VIEWER 14); this test reads the layer values the shader gets.

/** Fresnel layers of one item: material, layer type, mode, exponent, min, max offset. */
const fresnelLayers = (page, id) =>
  page.evaluate((i) => {
    const item = window.SC2App.items.find((x) => x.id === i);
    return item.model.m3.materials[1].flatMap((m) => m.layers.filter((l) => l.active && l.layer && l.layer.fresnelType).map((l) => [m.name, l.type, l.layer.fresnelType, l.layer.fresnelExponent, l.layer.fresnelMin, l.layer.fresnelMaxOffset]));
  }, id);

test('Diablo: the emissive layer carries its fresnel mode, exponent and range', async ({ page }) => {
  const errors = await open(page, { grid: false, particles: false });
  const id = await page.evaluate(() => window.sc2viewer.addUnit('SpaceDiablo', { x: 0, y: 0, rot: 0, pick: 0.5, dataset: 'stock' }));
  await idle(page);
  const layers = await fresnelLayers(page, id);
  console.log('fresnel layers', JSON.stringify(layers));
  expect(layers).toContainEqual(['01 - Default', 'emissive', 1, 1, 0, 1]);
  expect(errors).toEqual([]);
});

test('negative: a model with no fresnel layer has none', async ({ page }) => {
  const errors = await open(page, { grid: false, particles: false });
  const id = await page.evaluate(() => window.sc2viewer.addUnit('Marine', { x: 0, y: 0, rot: 0, pick: 0.5, dataset: 'stock' }));
  await idle(page);
  expect(await fresnelLayers(page, id)).toEqual([]);
  expect(errors).toEqual([]);
});

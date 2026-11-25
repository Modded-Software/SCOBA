import { test, expect } from '../fixtures.mjs';
import { frames, idle, open, state } from '../page.mjs';

// Constant colour layers (gap A5): a layer with flag 0x400 and no texture
// draws its colour, not a sample. The colour is stored b, g, r, a; the rest
// value times the rest rgbMultiply, an all-zero colour and a multiply <= 0
// read as unset (WhiteoutFlakes m3_standard.slang M3LayerValue mode 2,
// m3_surface_table.cpp LayerTint). Ghost material Standard_7 has one: an
// additive emissive, stored (25, 25, 250, 255). What it looks like is an
// operator check (SPEC-VIEWER 14); these tests read the layer the shader gets.

async function drawn(page, id) {
  await page.evaluate((u) => window.scobaeditor.addUnit(u, { x: 0, y: 0 }), id);
  await idle(page);
  await frames(page);
  const item = (await state(page)).items.at(-1);
  expect(item.loaded).toBe(true);
  expect(item.drawn).toBe(true);
  console.log(`${id}: constant layers ` + JSON.stringify(item.constantLayers));
  return item;
}

test('Ghost: the Standard_7 constant emissive is read as red and bound', async ({ page }) => {
  const errors = await open(page);
  const item = await drawn(page, 'Ghost');
  expect(item.constantLayers.length).toBe(1);
  const layer = item.constantLayers[0];
  expect(layer.material).toBe('Standard_7');
  expect(layer.type).toBe('emissive');
  // b, g, r, a = 25, 25, 250, 255 read as r, g, b, a.
  const want = [250 / 255, 25 / 255, 25 / 255, 1];
  layer.color.forEach((c, i) => expect(c).toBeCloseTo(want[i], 4));
  expect(layer.binds).toBeGreaterThan(0);
  // The switch reaches that one layer.
  const off = await page.evaluate((id) => window.scobaeditor.probe('m3', 'setConstantLayers', id, false), item.id);
  expect(off).toBe(1);
  await page.evaluate((id) => window.scobaeditor.probe('m3', 'setConstantLayers', id, true), item.id);
  expect(errors).toEqual([]);
});

test('negative: the Ghost textured layers are not constant', async ({ page }) => {
  const errors = await open(page);
  const item = await drawn(page, 'Ghost');
  const textured = item.uvLayers.filter((l) => l.material !== 'Standard_7');
  // NewGHOST TEXTURE: diffuse, decal, specular, emissive, normal; ghost glow: emissive.
  expect(textured.map((l) => `${l.material}/${l.type}`).sort()).toEqual([
    'NewGHOST TEXTURE/decal', 'NewGHOST TEXTURE/diffuse', 'NewGHOST TEXTURE/emissive',
    'NewGHOST TEXTURE/normal', 'NewGHOST TEXTURE/specular', 'ghost glow/emissive',
  ]);
  expect(item.constantLayers.map((l) => l.material)).toEqual(['Standard_7']);
  // The constant layer wants no texture: every wanted texture loads.
  expect(item.texturesLoaded).toBe(textured.length);
  expect(errors).toEqual([]);
});

test('negative: Marine has no constant colour layer', async ({ page }) => {
  const errors = await open(page);
  const item = await drawn(page, 'Marine');
  expect(item.constantLayers).toEqual([]);
  expect(await page.evaluate((id) => window.scobaeditor.probe('m3', 'setConstantLayers', id, false), item.id)).toBe(0);
  expect(errors).toEqual([]);
});

import { test, expect } from '@playwright/test';

// Constant colour layers (gap A5): a layer with flag 0x400 and no texture
// draws its colour, not a sample. The colour is stored b, g, r, a; the rest
// value times the rest rgbMultiply, an all-zero colour and a multiply <= 0
// read as unset (WhiteoutFlakes m3_standard.slang M3LayerValue mode 2,
// m3_surface_table.cpp LayerTint). Ghost material Standard_7 has one: an
// additive emissive, stored (25, 25, 250, 255).

async function open(page) {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => {
    if (m.text().startsWith('viewer:') || m.type() === 'error') errors.push(m.text());
  });
  await page.goto('/');
  await expect.poll(() => errors.join(' | ') || page.evaluate(() => Boolean(window.sc2viewer && window.sc2viewer.ready)), { timeout: 10_000 }).toBe(true);
  return errors;
}

async function drawn(page, id) {
  await page.evaluate((u) => window.sc2viewer.addUnit(u, { x: 0, y: 0 }), id);
  await page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 15_000 });
  await page.evaluate(() => new Promise((resolve) => setTimeout(resolve, 200)));
  const item = (await page.evaluate(() => window.sc2viewer.state())).items.at(-1);
  expect(item.loaded).toBe(true);
  expect(item.drawn).toBe(true);
  console.log(`${id}: constant layers ` + JSON.stringify(item.constantLayers));
  return item;
}

test('Ghost: the Standard_7 constant emissive is red, bound, and draws pixels', async ({ page }) => {
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

  // What the layer draws: the frame with it off against the frame with it on.
  // One synchronous call, so no animation frame runs between the two renders.
  const { off, on } = await page.evaluate((id) => {
    const v = window.sc2viewer;
    const count = v.setConstantLayers(id, false);
    v.mark();
    v.setConstantLayers(id, true);
    return { off: count, on: v.changedSinceMark() };
  }, item.id);
  console.log(`Ghost constant layer: layers ${off} ${JSON.stringify(on)}`);
  expect(off).toBe(1);
  expect(on.changed).toBeGreaterThan(0);
  // Additive red: the changed pixels gain red, more than green or blue.
  // Standard_7 has no diffuse: the base is black (standard.frag). With the
  // former white base the lit white saturated and this frame changed by 0.
  const [dr, dg, db] = on.delta;
  expect(dr).toBeGreaterThan(0);
  expect(dr).toBeGreaterThan(dg);
  expect(dr).toBeGreaterThan(db);
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
  expect(await page.evaluate((id) => window.sc2viewer.setConstantLayers(id, false), item.id)).toBe(0);
  expect(errors).toEqual([]);
});

import { test, expect } from '../fixtures.mjs';

// Texture coordinates follow the region's own scale and offset (REGN
// version 5: stored * (uvwMult / 16) / 2048 + uvwOffset). Reading every
// region as stored / 2048 tiled the Alarak and Fenix bodies 16 times
// ("smallpox"). Survey: scripts/uv-survey.sh.

async function open(page) {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => {
    if (m.text().startsWith('viewer:') || m.type() === 'error') errors.push(m.text());
  });
  await page.goto('/');
  await expect.poll(() => errors.join(' | ') || page.evaluate(() => Boolean(window.scobaeditor && window.scobaeditor.ready)), { timeout: 10_000 }).toBe(true);
  return errors;
}

async function unitRegions(page, id) {
  await page.evaluate((u) => window.scobaeditor.addUnit(u, { x: 0, y: 0, pick: 0.5 }), id);
  await page.waitForFunction(() => window.scobaeditor.idle(), null, { timeout: 15_000 });
  const item = (await page.evaluate(() => window.scobaeditor.state())).items.at(-1);
  expect(item.loaded).toBe(true);
  return item.regionUv;
}

const show = (regions) => regions.map((r) => `scale ${r.scale.toExponential(3)} offset ${r.offset.toFixed(3)} raw [${r.raw}] -> [${r.range.map((x) => x.toFixed(3))}]`).join('\n');

for (const [id, body] of [
  ['AlarakChampion', 0],
  ['FenixChampion', 1],
]) {
  test(`${id}: the body texture is mapped once, not tiled 16 times`, async ({ page }) => {
    const errors = await open(page);
    const regions = await unitRegions(page, id);
    console.log(id + '\n' + show(regions));
    const r = regions[body];
    // The body region stores its coordinates over the whole int16 range...
    expect(r.raw[1] - r.raw[0]).toBeGreaterThan(60000);
    // ...which the old rule (/ 2048) read as a span of about 32 textures.
    expect((r.raw[1] - r.raw[0]) / 2048).toBeGreaterThan(29);
    // The file's scale brings it to about one texture (two at most, when it
    // spans -1 to 1 on a wrapping layer).
    expect(r.range[1] - r.range[0]).toBeLessThan(2.05);
    for (const region of regions) {
      expect(region.range[0]).toBeGreaterThan(-1.05);
      expect(region.range[1]).toBeLessThan(1.1);
    }
    expect(errors).toEqual([]);
  });
}

test('negative: a model without its own UV scale keeps stored / 2048', async ({ page }) => {
  const errors = await open(page);
  const regions = await unitRegions(page, 'Marine');
  console.log('Marine\n' + show(regions));
  for (const r of regions) {
    expect(r.scale).toBe(1 / 2048);
    expect(r.offset).toBe(0);
  }
  expect(errors).toEqual([]);
});

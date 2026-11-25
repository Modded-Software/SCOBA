import { allowErrors, test, expect } from '../fixtures.mjs';

// The renderer must read vertices with the stride the file has:
// stride x vertex count = vertex bytes. A wrong stride smears every vertex
// after the first into long spikes (seen on the Augustgrad Gate).

async function open(page) {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto('/');
  await expect.poll(() => errors.join(' | ') || page.evaluate(() => Boolean(window.scobaeditor && window.scobaeditor.ready)), { timeout: 10_000 }).toBe(true);
  await page.evaluate(() => window.scobaeditor.setGrid(false));
}

// Units by vertex format, from tools/vertex-survey.mjs (1474 model files).
// Before the fix the library read the wrong stride for 340 of them:
//   KorhalGateEast 0x182027d  colours           real 36, read 32
//   Armory         0x18e007d  3 UV sets         real 40, read 36
//   KerriganGhostLab 0x19e007d 4 UV sets        real 44, read 36
//   VoidThrasher   0x41820261 UV bit 0x40000000 real 40, read 32
//   ShapeShamrock  0x180007d  no UV set         real 28, read 32
// Read right before and after: Marine, Zealot (control cases).
const UNITS = ['KorhalGateEast', 'Armory', 'KerriganGhostLab', 'VoidThrasher', 'ShapeShamrock', 'Marine', 'Zealot'];

for (const unit of UNITS) {
  test(`geometry: ${unit} is read with the file's vertex stride`, async ({ page }) => {
    // Terrain and lens flare materials are not drawn: reported, by design.
    if (unit === 'VoidThrasher') allowErrors(/scobaeditor: Void Thrasher: not drawn: .*material type (4 \(terrain\)|11 \(lens flare\))/);
    await open(page);
    await page.evaluate((id) => window.scobaeditor.addUnit(id, { x: 0, y: 0 }), unit);
    await page.waitForFunction(() => window.scobaeditor.idle());
    const item = (await page.evaluate(() => window.scobaeditor.state())).items[0];
    console.log(unit, JSON.stringify({ stride: item.vertexStride, count: item.vertexCount, bytes: item.vertexBytes }));
    expect(item.vertexCount).toBeGreaterThan(0);
    expect(item.vertexStride * item.vertexCount).toBe(item.vertexBytes);
  });
}

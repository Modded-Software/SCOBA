import { test, expect } from '../fixtures.mjs';

// A format's own test members (SPEC-VIEWER 6.3): reached only as
// scobaeditor.probe(format, name, ...args). Truth: what the M3 probe returns
// for a placed unit, and the errors for a format or a name it does not have.

async function open(page) {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push(m.text());
  });
  await page.goto('/');
  await expect.poll(() => errors.join(' | ') || page.evaluate(() => Boolean(window.scobaeditor && window.scobaeditor.ready)), { timeout: 10_000 }).toBe(true);
  return errors;
}

/** The message a call throws, or null when it returns. */
const thrown = (page, args) => page.evaluate((a) => {
  try {
    window.scobaeditor.probe(...a);
    return null;
  } catch (e) {
    return e.message;
  }
}, args);

test('probe: an M3 probe answers for a placed unit; the old flat names are gone', async ({ page }) => {
  const errors = await open(page);
  const id = await page.evaluate((u) => window.scobaeditor.addUnit(u, { x: 0, y: 0, rot: 0, pick: 0.5, dataset: 'stock' }), 'Probe');
  await page.waitForFunction(() => window.scobaeditor.idle(), null, { timeout: 20_000 });
  const s = await page.evaluate((i) => window.scobaeditor.probe('m3', 'particles', i), id);
  expect(s.emitters.length).toBe(2);
  expect(typeof s.quads).toBe('number');
  // Negative: no probe is a member of scobaeditor itself.
  const flat = await page.evaluate(() => ['particles', 'setParticles', 'billboards', 'alphaTests', 'setAlphaTest', 'setConstantLayers', 'groundLights'].filter((n) => n in window.scobaeditor));
  expect(flat).toEqual([]);
  expect(errors).toEqual([]);
});

test('probe: an unknown format, an unknown name and an inherited name are errors that name them', async ({ page }) => {
  const errors = await open(page);
  expect(await thrown(page, ['mdx', 'particles', 1])).toBe('probe: no format "mdx" has probes');
  expect(await thrown(page, ['m3', 'nothing'])).toBe('probe: format "m3" has no probe "nothing"');
  expect(await thrown(page, ['m3', 'toString'])).toBe('probe: format "m3" has no probe "toString"');
  expect(errors).toEqual([]);
});

import { test, expect } from '../fixtures.mjs';

// Particle materials, measured on the drawn frame: one particle drawn alone
// (sc2viewer.probe('m3', 'particleSamples', ...)), its colour change read at points of its quad.
// - The cut-out (alphaTestThreshold) applies to particles as to meshes
//   (WhiteoutFlakes m3_standard.slang: mask alpha < threshold is discarded).
//   Operator 2026-11-23: Helios debris drew as rectangles.
// - A layer reads the flipbook cell only when its UV source is the particle
//   flipbook (uvSource 6); every other layer reads the whole quad
//   (WhiteoutFlakes m3_surface_table particleFlipbookUv). Operator
//   2026-11-23: the Blimp tank gas drew as soft rectangles (its 2 x 2
//   flipbook cut a quarter of a whole-quad steam mask).

async function open(page) {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => {
    if (m.text().startsWith('viewer:') || m.type() === 'error') errors.push(m.text());
  });
  await page.goto('/');
  await expect.poll(() => errors.join(' | ') || page.evaluate(() => Boolean(window.sc2viewer && window.sc2viewer.ready)), { timeout: 10_000 }).toBe(true);
  await page.evaluate(() => window.sc2viewer.setGrid(false));
  return errors;
}

const idle = (page) => page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 20_000 });

/**
 * Add `unit` at rest, run its emitters `seconds`, pick the live particle of
 * the emitter on `bone` nearest the middle of its life (`near`: nearest the
 * emitter, at least 0.05 s old), and point the
 * camera at it from `widths` quad widths away. Returns the item, emitter
 * index, particle index and the emitter state.
 */
async function oneParticle(page, unit, bone, seconds, near = false, widths = 6) {
  const id = await page.evaluate((u) => window.sc2viewer.addUnit(u, { x: 0, y: 0, rot: 0, pick: 0.5, sequence: -1, dataset: 'stock' }), unit);
  await idle(page);
  await page.evaluate(([i, s]) => window.sc2viewer.probe('m3', 'advanceParticles', i, s, 1 / 60), [id, seconds]);
  const s = await page.evaluate((i) => window.sc2viewer.probe('m3', 'particles', i, true), id);
  const e = s.emitters.find((x) => x.bone === bone);
  expect(e, `emitter on bone ${bone}`).toBeTruthy();
  expect(e.particles.length).toBeGreaterThan(0);
  const score = near ? (p) => Math.hypot(p.position[0] - e.origin[0], p.position[1] - e.origin[1], p.position[2] - e.origin[2]) + (p.age < 0.05 ? 1e9 : 0) : (p) => Math.abs(p.age / p.life - 0.5);
  const k = e.particles.reduce((best, p, n) => (score(p) < score(e.particles[best]) ? n : best), 0);
  const p = e.particles[k];
  const width = Math.hypot(p.quad[9] - p.quad[0], p.quad[10] - p.quad[1], p.quad[11] - p.quad[2]);
  await page.evaluate((v) => window.sc2viewer.view(v), { yaw: -Math.PI / 2, pitch: 0.3, distance: Math.max(widths * width, 0.5), target: p.position });
  return { id, index: e.index, k, emitter: e, width };
}

/** A 5 x 5 grid of quad points, inset from the edges. */
const GRID = [0.1, 0.3, 0.5, 0.7, 0.9].flatMap((u) => [0.1, 0.3, 0.5, 0.7, 0.9].map((v) => [u, v]));

test('Helios debris: the particle cut-out removes the transparent part of the card; off, the whole card draws', async ({ page }) => {
  const errors = await open(page);
  // battlecruiserwarfield.m3: Debris Falling on bone 23, material Standard_24ww
  // (opaque, cut-out 2 / 255, mask metal_debris2 alpha, 2 x 2 flipbook).
  const { id, index, k, emitter } = await oneParticle(page, 'BattlecruiserHelios', 23, 3, true);
  expect(emitter.blendMode).toBe(0);
  const tests = await page.evaluate((i) => window.sc2viewer.probe('m3', 'alphaTests', i), id);
  expect(tests.find((t) => t.material === 'Standard_24ww').alphaTest).toBeCloseTo(2 / 255, 6);
  const on = await page.evaluate(([i, n, q, g]) => window.sc2viewer.probe('m3', 'particleSamples', i, n, q, g), [id, index, k, GRID]);
  await page.evaluate((i) => window.sc2viewer.probe('m3', 'setAlphaTest', i, false), id);
  const off = await page.evaluate(([i, n, g]) => window.sc2viewer.probe('m3', 'particleSamples', i, n, 0, g), [id, index, GRID]);
  await page.evaluate((i) => window.sc2viewer.probe('m3', 'setAlphaTest', i, true), id);
  const drawn = (list) => list.filter((d) => d !== null && d > 0).length;
  console.log('Helios debris samples on', JSON.stringify(on), 'off', JSON.stringify(off));
  expect(on.every((d) => d !== null)).toBe(true);
  // Off: an opaque card covers every point.
  expect(drawn(off)).toBe(GRID.length);
  // On: part of the card is cut, part stays.
  expect(drawn(on)).toBeGreaterThan(0);
  expect(drawn(on)).toBeLessThan(drawn(off));
  // Nothing appears with the test on that is not there with it off.
  expect(on.filter((d, n) => d > 0 && !(off[n] > 0))).toEqual([]);
  expect(errors).toEqual([]);
});

test('Blimp tank steam: its whole-quad mask fades to nothing at the quad corners; the centre draws', async ({ page }) => {
  const errors = await open(page);
  // blimp.m3: steam on bone 28, material "steam" (alpha blend), mask
  // largesmoke1b alpha with uvSource 0, emitter flipbook 2 x 2.
  const { id, index, k, emitter } = await oneParticle(page, 'Blimp', 28, 1.2);
  expect(emitter.blendMode).toBe(1);
  const CORNERS = [[0.03, 0.03], [0.97, 0.03], [0.03, 0.97], [0.97, 0.97]];
  const points = [[0.5, 0.5], ...CORNERS];
  const d = await page.evaluate(([i, n, q, g]) => window.sc2viewer.probe('m3', 'particleSamples', i, n, q, g), [id, index, k, points]);
  console.log('Blimp steam centre and corners', JSON.stringify(d));
  expect(d.every((x) => x !== null)).toBe(true);
  expect(d[0]).toBeGreaterThan(3);
  // The corners: no visible change (a flipbook-cell mask left them at about
  // a third of the centre).
  for (const c of d.slice(1)) expect(c).toBeLessThanOrEqual(2);
  expect(errors).toEqual([]);
});

test('negative: a flipbook layer (uvSource 6) still reads its cell: Helios jet fire changes over the life', async ({ page }) => {
  const errors = await open(page);
  // Star2Part01jetfire02 (bone 25): fireboom1, 8 x 8 flipbook, every layer uvSource 6.
  const { id, index, k } = await oneParticle(page, 'BattlecruiserHelios', 25, 0.2);
  const cells = await page.evaluate(([i, n, q]) => {
    const item = window.SC2App.items.find((x) => x.id === i);
    const mat = item.model.m3.materials[1][item.model.m3.materialMaps[item.instance.m3.particleSystems.find((s) => s.index === n).emitter.materialReferenceIndex].materialIndex];
    return [0, 4, 5].map((l) => mat.layers[l]).filter((l) => l.active).map((l) => l.layer.uvSource);
  }, [id, index, k]);
  expect(cells.length).toBeGreaterThan(0);
  expect(cells.every((u) => u === 6)).toBe(true);
  const d = await page.evaluate(([i, n, q]) => window.sc2viewer.probe('m3', 'particleSamples', i, n, q, [[0.5, 0.5]]), [id, index, k]);
  expect(d[0]).toBeGreaterThan(0);
  expect(errors).toEqual([]);
});

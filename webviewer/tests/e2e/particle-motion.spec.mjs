import { test, expect } from '../fixtures.mjs';

// Which motion an emitter runs (WhiteoutFlakes CanUseGpuMotion): the
// closed form, whose drag floors to 0.01, or the per-step path, whose drag
// is as authored. Sort (flags 0x1), collide terrain, trailing and model
// particles, bit 31, a second-pair force channel (WhiteoutLib forcesFallback), wind, a kill sphere or noise
// move an emitter to the per-step path.
// Operator 2026-11-23: the Zerus Tree spores do not rise. Their emitters
// sort (flags 0x200001), have drag 0 and mass 0.001: the closed form
// stopped them after 0.1 x their speed (about 0.07); stepped, nothing
// slows them.

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

const idle = (page) => page.waitForFunction(() => window.scobaeditor.idle(), null, { timeout: 20_000 });

/** Rise of each particle since its birth, over its age: its mean upward speed. */
const climb = (p) => (p.position[2] - p.born[2]) / p.age;

test('Zerus Tree spores rise at their emission speed: sorted, they take the per-step motion', async ({ page }) => {
  const errors = await open(page);
  const id = await page.evaluate(() => window.scobaeditor.addDoodad('ZerusTree', { x: 0, y: 0, rot: 0, variation: 9, sequence: 0, dataset: 'stock' }));
  await idle(page);
  const stand = await page.evaluate((i) => window.scobaeditor.state().items.find((t) => t.id === i).sequences[0], id);
  await page.evaluate(([i, s]) => window.scobaeditor.probe('m3', 'playParticles', i, s, 6), [id, stand]);
  const st = await page.evaluate((i) => window.scobaeditor.probe('m3', 'particles', i, true), id);
  expect(st.emitters.length).toBe(2);
  for (const e of st.emitters) {
    const old = e.particles.filter((p) => p.age > 1);
    const rises = old.map(climb);
    console.log('spores', JSON.stringify({ bone: e.bone, flags: e.flags, euler: e.euler, drag: e.drag, mass: e.mass, forces: e.forces, forcePair2: e.forcesFallback, live: e.live, old: old.length, rise: rises.map((r) => Number(r.toFixed(3))) }));
    expect(e.flags & 0x1).toBe(1);
    expect(e.drag).toBe(0);
    expect(e.euler).toBe(true);
    expect(old.length).toBeGreaterThan(5);
    // Speed 0.55 to 0.77 along the bone, which points up: each climbs at
    // least 0.3 a second (closed form: under 0.07 in all).
    for (const r of rises) expect(r).toBeGreaterThan(0.3);
  }
  expect(errors).toEqual([]);
});

test('negative: an emitter without those flags keeps the closed form and its drag floor', async ({ page }) => {
  const errors = await open(page);
  const id = await page.evaluate(() => window.scobaeditor.addUnit('Probe', { x: 0, y: 0, rot: 0, pick: 0.5, dataset: 'stock' }));
  await idle(page);
  await page.evaluate((i) => window.scobaeditor.probe('m3', 'playParticles', i, 'Stand', 2), id);
  const st = await page.evaluate((i) => window.scobaeditor.probe('m3', 'particles', i, true), id);
  const closed = st.emitters.filter((e) => !e.euler);
  console.log('probe', JSON.stringify(st.emitters.map((e) => ({ bone: e.bone, flags: e.flags, euler: e.euler, drag: e.drag, forcePair2: e.forcesFallback, wind: e.windMultiplier, kill: e.killSphere, noise: e.noiseAmplitude }))));
  expect(closed.length).toBeGreaterThan(0);
  for (const e of closed) {
    expect(e.flags & 0x10480003).toBe(0);
    expect(e.forcesFallback).toBe(0);
  }
  expect(errors).toEqual([]);
});

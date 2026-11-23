import { test, expect } from '@playwright/test';

// The viewer's ground: a flat invisible plane at world z = 0. Particles
// with collideTerrain (PAR_ flags 0x2) hit it and bounce with the
// emitter's bounce and friction, or rest on it (WhiteoutFlakes
// CollideElement). Operator 2026-11-23: the Helios acid drips fell through
// the floor forever.

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

const idle = (page) => page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 20_000 });

test('Helios acid drips stop at the ground; emitters without collideTerrain pass through', async ({ page }) => {
  const errors = await open(page);
  const id = await page.evaluate(() => window.sc2viewer.addUnit('BattlecruiserHelios', { x: 0, y: 0, rot: 0, pick: 0.5, dataset: 'stock' }));
  await idle(page);
  // 12 s of Stand in 1/60 s steps: drips live 10 s and fall from about z 4.
  await page.evaluate((i) => window.sc2viewer.playParticles(i, 'Stand', 12), id);
  const st = await page.evaluate((i) => window.sc2viewer.particles(i, true), id);
  const drip = st.emitters.find((e) => e.bone === 21);
  console.log('drip', JSON.stringify({ flags: drip.flags, bounce: drip.bounce, friction: drip.friction, live: drip.live, z: drip.particles.map((p) => Number(p.position[2].toFixed(3))), bounces: drip.particles.map((p) => p.bounces), rest: drip.particles.map((p) => p.rest) }));
  expect(drip.flags & 0x2).toBe(2);
  expect(drip.particles.length).toBeGreaterThan(10);
  // None below the ground (the push-out puts them 0.05 above).
  for (const p of drip.particles) expect(p.position[2]).toBeGreaterThanOrEqual(-1e-3);
  // Most have landed: old drips (over 2 s) have touched the ground.
  const old = drip.particles.filter((p) => p.age > 2);
  expect(old.length).toBeGreaterThan(5);
  for (const p of old) expect(p.bounces).toBeGreaterThan(0);
  // Negative: emitters without collideTerrain never touch the ground.
  const free = st.emitters.filter((e) => !(e.flags & 0x2));
  expect(free.length).toBeGreaterThan(0);
  for (const e of free) for (const p of e.particles) expect(p.bounces).toBe(0);
  expect(errors).toEqual([]);
});

test('negative: a colliding particle that has not reached the ground keeps its path from its birth point', async ({ page }) => {
  const errors = await open(page);
  const id = await page.evaluate(() => window.sc2viewer.addUnit('BattlecruiserHelios', { x: 0, y: 0, rot: 0, pick: 0.5, dataset: 'stock' }));
  await idle(page);
  await page.evaluate((i) => window.sc2viewer.playParticles(i, 'Stand', 0.4), id);
  const st = await page.evaluate((i) => window.sc2viewer.particles(i, true), id);
  const drip = st.emitters.find((e) => e.bone === 21);
  expect(drip.particles.length).toBeGreaterThan(0);
  for (const p of drip.particles) {
    expect(p.bounces).toBe(0);
    expect(p.position[2]).toBeGreaterThan(0);
    // The reported birth point is the world start the tails read.
    for (let k = 0; k < 3; k++) expect(p.start[k]).toBeCloseTo(p.born[k], 4);
  }
  expect(errors).toEqual([]);
});

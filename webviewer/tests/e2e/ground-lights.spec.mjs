import { test, expect } from '../fixtures.mjs';
import { idle, open } from '../page.mjs';

// Spot lights (LITE type 2) light the viewer's ground plane, z = 0.
// Operator 2026-11-23: each of the Shadow Battlecruiser's six spotlights
// should cast an ellipse on the ground. This test reads the lights the
// ground shader gets (sc2viewer.probe('m3', 'groundLights')): type, cone,
// range and where each one's axis meets the ground. How the lit patch
// looks is an operator check (SPEC-VIEWER 14).

test('Shadow Battlecruiser: six spot lights, each with a cone and a ground hit', async ({ page }) => {
  const errors = await open(page, { grid: false });
  const id = await page.evaluate(() => window.sc2viewer.addUnit('ShadowBattlecruiser', { x: 0, y: 0, rot: 0, pick: 0.5, dataset: 'stock' }));
  await idle(page);
  await page.evaluate((i) => window.sc2viewer.probe('m3', 'playParticles', i, 'Stand', 0.5), id);
  const lights = await page.evaluate((i) => window.sc2viewer.probe('m3', 'groundLights', i), id);
  console.log('lights', JSON.stringify(lights.map((l) => ({ type: l.type, hit: l.hit && l.hit.map((x) => Number(x.toFixed(2))), far: l.far, hot: l.hotSpot, fall: l.falloff }))));
  const spots = lights.filter((l) => l.type === 2);
  expect(spots.length).toBe(6);
  for (const s of spots) {
    // Its axis points down and meets the ground inside its range.
    expect(s.hit, `bone ${s.bone}`).not.toBe(null);
    expect(s.direction[2], `bone ${s.bone}`).toBeLessThan(0);
    const reach = Math.hypot(s.position[0] - s.hit[0], s.position[1] - s.hit[1], s.position[2]);
    expect(reach, `bone ${s.bone}`).toBeLessThan(s.far);
    // A cone: the hot spot inside the falloff, both under 90 degrees.
    expect(s.falloff).toBeGreaterThan(0);
    expect(s.falloff).toBeLessThan(Math.PI / 2);
    expect(s.hotSpot).toBeLessThanOrEqual(s.falloff);
  }
  // Six lights on six places, not one light six times.
  expect(new Set(spots.map((s) => s.hit.map((v) => v.toFixed(2)).join(','))).size).toBe(6);
  expect(errors).toEqual([]);
});

test('negative: a unit without lights gives the ground none', async ({ page }) => {
  const errors = await open(page, { grid: false });
  const id = await page.evaluate(() => window.sc2viewer.addUnit('Marine', { x: 0, y: 0, rot: 0, pick: 0.5, dataset: 'stock' }));
  await idle(page);
  const lights = await page.evaluate((i) => window.sc2viewer.probe('m3', 'groundLights', i), id);
  expect(lights.filter((l) => l.type === 2)).toEqual([]);
  expect(errors).toEqual([]);
});

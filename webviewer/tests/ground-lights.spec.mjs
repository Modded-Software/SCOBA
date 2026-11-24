import { test, expect } from '@playwright/test';

// Spot lights (LITE type 2) light the viewer's ground plane, z = 0.
// Operator 2026-11-23: each of the Shadow Battlecruiser's six spotlights
// should cast an ellipse on the ground. Truth: the drawn frame with ground
// lights on and off, at world points (sc2viewer.groundPixels), the model's
// meshes left out so the hull covers nothing.

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

/** Sum of |r|, |g|, |b| between the frame with ground lights on (all, or light `only`) and off, at world points. */
async function lightAt(page, points, only = -1) {
  return page.evaluate(([pts, o]) => {
    const v = window.sc2viewer;
    v.probe('m3', 'setGroundLights', true, o);
    const on = v.groundPixels(pts);
    v.probe('m3', 'setGroundLights', false);
    const off = v.groundPixels(pts);
    v.probe('m3', 'setGroundLights', true);
    return on.map((p, n) => p.rgb.reduce((s, c, k) => s + Math.abs(c - off[n].rgb[k]), 0));
  }, [points, only]);
}

test('Shadow Battlecruiser: six spot lights each light an ellipse on the ground; outside the cones nothing changes', async ({ page }) => {
  const errors = await open(page);
  const id = await page.evaluate(() => window.sc2viewer.addUnit('ShadowBattlecruiser', { x: 0, y: 0, rot: 0, pick: 0.5, dataset: 'stock' }));
  await idle(page);
  await page.evaluate((i) => {
    window.sc2viewer.probe('m3', 'setParticles', false);
    window.sc2viewer.probe('m3', 'playParticles', i, 'Stand', 0.5);
    // Leave the meshes out: the ground under the hull is in view.
    const item = window.SC2App.items.find((x) => x.id === i);
    item.model.m3.batches.length = 0;
  }, id);
  await page.evaluate(() => window.sc2viewer.view({ yaw: -Math.PI / 2, pitch: 1.45, distance: 30, target: [0, 0, 0] }));
  const lights = await page.evaluate((i) => window.sc2viewer.probe('m3', 'groundLights', i), id);
  console.log('lights', JSON.stringify(lights.map((l) => ({ hit: l.hit && l.hit.map((x) => Number(x.toFixed(2))), far: l.far, hot: l.hotSpot, fall: l.falloff }))));
  const spots = lights.map((l, index) => ({ ...l, index })).filter((l) => l.type === 2);
  expect(spots.length).toBe(6);
  for (const s of spots) {
    expect(s.hit).not.toBe(null);
    const [lit] = await lightAt(page, [s.hit], s.index);
    expect(lit, `light on bone ${s.bone} at ${s.hit}`).toBeGreaterThan(20);
    // The lit patch, along the tilt (the axis on the ground) and across it,
    // every 0.1 up to 6 units each way: lit only inside the cone and the
    // far range of this light, and at least 60 % of that span lit.
    const along = [s.direction[0], s.direction[1]];
    const n = Math.hypot(along[0], along[1]);
    const a = [along[0] / n, along[1] / n];
    const b = [-a[1], a[0]];
    const steps = Array.from({ length: 121 }, (_, k) => (k - 60) * 0.1);
    const inside = ([x, y]) => {
      const t = [s.position[0] - x, s.position[1] - y, s.position[2]];
      const d = Math.hypot(...t);
      const c = -(t[0] * s.direction[0] + t[1] * s.direction[1] + t[2] * s.direction[2]) / d;
      return d < s.far && c > Math.cos(s.falloff);
    };
    for (const dir of [a, b]) {
      const points = steps.map((t) => [s.hit[0] + dir[0] * t, s.hit[1] + dir[1] * t, 0]);
      const d = await lightAt(page, points, s.index);
      const lit = d.map((x) => x > 2);
      const predicted = points.map(inside);
      console.log('spot', s.bone, dir === a ? 'along' : 'across', 'lit', lit.filter(Boolean).length / 10, 'predicted', predicted.filter(Boolean).length / 10);
      // Never lit outside the cone and range (one sample of slack at each edge).
      lit.forEach((l, k) => {
        if (l) expect(predicted[k] || predicted[k - 1] || predicted[k + 1], `bone ${s.bone} lit at ${steps[k]}`).toBe(true);
      });
      expect(lit.filter(Boolean).length).toBeGreaterThanOrEqual(0.6 * predicted.filter(Boolean).length);
    }
  }
  // Not saturated: with all six on, no point of the lit ground goes near
  // white (operator 2026-11-23: the overlapping spots drew a white blob).
  const grid = [];
  for (let x = -10; x <= 10; x += 0.5) for (let y = -8; y <= 8; y += 0.5) grid.push([x, y, 0]);
  const peak = await page.evaluate((pts) => {
    window.sc2viewer.probe('m3', 'setGroundLights', true);
    return Math.max(...window.sc2viewer.groundPixels(pts).map((p) => Math.max(...p.rgb)));
  }, grid);
  console.log('peak channel', peak);
  expect(peak).toBeLessThan(200);
  // Negative: under the ship's centre and far away, the lights add nothing.
  const off = await lightAt(page, [[0, 0, 0], [12, 12, 0], [-12, 12, 0]]);
  expect(off).toEqual([0, 0, 0]);
  expect(errors).toEqual([]);
});

test('negative: a unit without lights draws the same with ground lights on and off', async ({ page }) => {
  const errors = await open(page);
  const id = await page.evaluate(() => window.sc2viewer.addUnit('Marine', { x: 0, y: 0, rot: 0, pick: 0.5, dataset: 'stock' }));
  await idle(page);
  const lights = await page.evaluate((i) => window.sc2viewer.probe('m3', 'groundLights', i), id);
  expect(lights.filter((l) => l.type === 2)).toEqual([]);
  await page.evaluate(() => window.sc2viewer.view({ yaw: -Math.PI / 2, pitch: 1.2, distance: 8, target: [0, 0, 0] }));
  const d = await lightAt(page, [[0, 0, 0], [1, 0, 0], [0, 1, 0], [-1, -1, 0]]);
  expect(d).toEqual([0, 0, 0, 0]);
  expect(errors).toEqual([]);
});

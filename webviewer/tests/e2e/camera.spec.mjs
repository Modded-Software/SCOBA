import { test, expect } from '../fixtures.mjs';

// Mouse camera controls:
// - left drag holds the ground point under the mouse and pulls the map;
// - middle drag orbits around the ground point under the mouse at press;
// - alt + middle drag turns the view around the eye (mouse-look, R-VIEW-143).
// Each drag's first move is 12 px or more: a fast drag, acting from the press
// point (core/press.ts, R-VIEW-142), so the rates are exact.

const VIEW = { yaw: -Math.PI / 2, pitch: 0.6, distance: 12, target: [0, 0, 0] };
const RATE = 0.004; // radians per pixel

async function open(page) {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto('/');
  await expect.poll(() => errors.join(' | ') || page.evaluate(() => Boolean(window.scobaeditor && window.scobaeditor.ready)), { timeout: 10_000 }).toBe(true);
  await page.evaluate((v) => window.scobaeditor.view(v), VIEW);
  return page.locator('canvas#view').boundingBox();
}

const camera = async (page) => (await page.evaluate(() => window.scobaeditor.state())).camera;
/** The ground point under a canvas pixel (page coordinates in). */
const groundAt = (page, box, x, y) => page.evaluate(([x, y]) => window.scobaeditor.groundUnder(x, y), [x - box.x, y - box.y]);
const eyeOf = (c) => [0, 1, 2].map((i) => c.target[i] + c.distance * [Math.cos(c.pitch) * Math.cos(c.yaw), Math.cos(c.pitch) * Math.sin(c.yaw), Math.sin(c.pitch)][i]);
const gap = (a, b) => Math.hypot(...a.map((v, i) => v - b[i]));

async function drag(page, button, from, to, alt = false) {
  await page.mouse.move(from[0], from[1]);
  if (alt) await page.keyboard.down('Alt');
  await page.mouse.down({ button });
  await page.mouse.move(to[0], to[1], { steps: 4 });
  await page.mouse.up({ button });
  if (alt) await page.keyboard.up('Alt');
}

test('left drag holds the ground under the mouse and pulls the map', async ({ page }) => {
  const box = await open(page);
  const from = [box.x + box.width * 0.4, box.y + box.height * 0.6];
  const to = [box.x + box.width * 0.65, box.y + box.height * 0.45];
  const anchor = await groundAt(page, box, ...from);
  const c0 = await camera(page);
  await drag(page, 'left', from, to);
  const c1 = await camera(page);
  const under = await groundAt(page, box, ...to);
  console.log('anchor', JSON.stringify(anchor), 'now under the mouse', JSON.stringify(under), 'target', JSON.stringify(c1.target));
  // The grabbed point is under the mouse again, within 1% of the view distance.
  expect(gap(anchor, under)).toBeLessThan(0.01 * c0.distance);
  expect(gap(c0.target, c1.target)).toBeGreaterThan(1);
  // Negative: it slides along the ground; no turn, no zoom, no height change.
  expect(c1.yaw).toBeCloseTo(c0.yaw, 9);
  expect(c1.pitch).toBeCloseTo(c0.pitch, 9);
  expect(c1.distance).toBeCloseTo(c0.distance, 9);
  expect(c1.target[2]).toBeCloseTo(c0.target[2], 9);
});

test('middle drag orbits around the ground point under the mouse', async ({ page }) => {
  const box = await open(page);
  // Off the view centre, so the pivot is not the camera target.
  const press = [box.x + box.width * 0.7, box.y + box.height * 0.7];
  const pivot = await groundAt(page, box, ...press);
  const c0 = await camera(page);
  await drag(page, 'middle', press, [press[0] + 100, press[1] - 40]);
  const c1 = await camera(page);
  // The pivot stays on the pixel where the drag started.
  const under = await groundAt(page, box, ...press);
  console.log('pivot', JSON.stringify(pivot), 'under the press point after', JSON.stringify(under));
  expect(gap(pivot, under)).toBeLessThan(0.01 * c0.distance);
  expect(c0.yaw - c1.yaw).toBeCloseTo(100 * RATE, 3);
  expect(c0.pitch - c1.pitch).toBeCloseTo(40 * RATE, 3);
  expect(c1.distance).toBeCloseTo(c0.distance, 6);
  // Negative: it did not turn around the target; the target moved.
  expect(gap(c0.target, c1.target)).toBeGreaterThan(0.2);
});

test('negative: a middle drag that starts on the sky orbits around the target', async ({ page }) => {
  const box = await open(page);
  await page.evaluate(() => window.scobaeditor.view({ pitch: 0.05 }));
  const sky = [box.x + box.width / 2, box.y + 5];
  expect(await groundAt(page, box, ...sky)).toBe(null);
  const c0 = await camera(page);
  await drag(page, 'middle', sky, [sky[0] + 80, sky[1]]);
  const c1 = await camera(page);
  expect(c1.target.map((v) => +v.toFixed(9))).toEqual(c0.target.map((v) => +v.toFixed(9)));
  expect(c0.yaw - c1.yaw).toBeCloseTo(80 * RATE, 3);
});

test('alt + middle drag turns the view around the eye', async ({ page }) => {
  const box = await open(page);
  const centre = [box.x + box.width / 2, box.y + box.height / 2];
  const c0 = await camera(page);
  await drag(page, 'middle', centre, [centre[0] + 100, centre[1] + 30], true);
  const c1 = await camera(page);
  console.log('eye before', JSON.stringify(eyeOf(c0)), 'after', JSON.stringify(eyeOf(c1)));
  // The eye stays; the view turns by the drag.
  expect(gap(eyeOf(c0), eyeOf(c1))).toBeLessThan(1e-6);
  expect(c0.yaw - c1.yaw).toBeCloseTo(100 * RATE, 3);
  expect(c1.pitch - c0.pitch).toBeCloseTo(30 * RATE, 3);
  expect(gap(c0.target, c1.target)).toBeGreaterThan(0.5);
  // Dragging right looks right: the old view centre is now left of centre.
  const old = await page.evaluate((t) => {
    const s = window.scobaeditor.worldToCanvas(t[0], t[1], t[2]);
    return s;
  }, c0.target);
  expect(old[0]).toBeLessThan(box.width / 2 - 50);
});

test('negative: a middle drag without alt moves the eye', async ({ page }) => {
  const box = await open(page);
  const centre = [box.x + box.width / 2, box.y + box.height / 2];
  const c0 = await camera(page);
  await drag(page, 'middle', centre, [centre[0] + 100, centre[1]]);
  expect(gap(eyeOf(c0), eyeOf(await camera(page)))).toBeGreaterThan(0.5);
});

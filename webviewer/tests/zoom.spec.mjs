import { test, expect } from '@playwright/test';

// Wheel zoom: a short glide over a few frames. One notch moves the camera a
// share of its distance: 15% with the eye 10 or more units up, less as the
// eye comes down (never under 12% of that), and a quarter of it with ctrl.

async function open(page) {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto('/');
  await expect.poll(() => errors.join(' | ') || page.evaluate(() => Boolean(window.sc2viewer && window.sc2viewer.ready)), { timeout: 10_000 }).toBe(true);
  const box = await page.locator('canvas#view').boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
}

const camera = async (page) => (await page.evaluate(() => window.sc2viewer.state())).camera;
const settled = (page) => expect.poll(async () => (await camera(page)).zoomGoal, { timeout: 3000 }).toBe(null);
const TARGET = [0, 0, 0];

/** The rule: the share of the distance one notch moves. */
function share(distance, pitch, ctrl = false) {
  const height = TARGET[2] + distance * Math.sin(pitch);
  const s = 0.15 * Math.max(0.12, Math.min(1, height / 10));
  return ctrl ? s * 0.25 : s;
}

/** Start at a distance and pitch, turn the wheel by deltaY, wait; the distance after. */
async function wheelFrom(page, distance, pitch, deltaY, ctrl = false) {
  await page.evaluate(([d, p, t]) => window.sc2viewer.view({ distance: d, pitch: p, target: t }), [distance, pitch, TARGET]);
  if (ctrl) await page.keyboard.down('Control');
  await page.mouse.wheel(0, deltaY);
  if (ctrl) await page.keyboard.up('Control');
  await settled(page);
  return (await camera(page)).distance;
}

test('wheel zoom glides over a few frames, and is done quickly', async ({ page }) => {
  await open(page);
  await page.evaluate((t) => window.sc2viewer.view({ distance: 30, pitch: 0.6, target: t }), TARGET);
  // Record the distance and the time on every frame for a while.
  await page.evaluate(() => {
    window.zoomSamples = [];
    const start = performance.now();
    const sample = (now) => {
      window.zoomSamples.push([now, window.sc2viewer.state().camera.distance]);
      if (now - start < 1000) requestAnimationFrame(sample);
    };
    requestAnimationFrame(sample);
  });
  const wheelAt = await page.evaluate(() => performance.now());
  await page.mouse.wheel(0, 100);
  await settled(page);
  const end = 30 * (1 + share(30, 0.6));
  expect((await camera(page)).distance).toBeCloseTo(end, 3);
  const samples = await page.evaluate(() => window.zoomSamples);
  const between = samples.filter(([, d]) => d > 30.01 && d < end - 0.01);
  let largestStep = 0;
  for (let i = 1; i < samples.length; i++) {
    expect(samples[i][1]).toBeGreaterThanOrEqual(samples[i - 1][1] - 1e-9);
    largestStep = Math.max(largestStep, samples[i][1] - samples[i - 1][1]);
  }
  // Snappy: 95% of the way within 250 ms of the wheel.
  const near = samples.find(([, d]) => d >= 30 + 0.95 * (end - 30));
  const ms = near[0] - wheelAt;
  console.log('frames between', between.length, 'largest step', largestStep.toFixed(3), 'of', (end - 30).toFixed(3), '95% after', ms.toFixed(0), 'ms');
  expect(between.length).toBeGreaterThanOrEqual(2);
  expect(ms).toBeLessThan(250);
  // Negative: no jump, no single frame takes the whole step.
  expect(largestStep).toBeLessThan(0.7 * (end - 30));
});

test('one notch moves less the closer the eye is to the ground', async ({ page }) => {
  await open(page);
  const high = (await wheelFrom(page, 20, 1.2, 100)) / 20 - 1;
  const mid = (await wheelFrom(page, 20, 0.3, 100)) / 20 - 1;
  const low = (await wheelFrom(page, 20, 0.03, 100)) / 20 - 1;
  console.log('one notch out from 20: high', high.toFixed(4), 'mid', mid.toFixed(4), 'low', low.toFixed(4));
  expect(high).toBeCloseTo(share(20, 1.2), 4);
  expect(mid).toBeCloseTo(share(20, 0.3), 4);
  expect(low).toBeCloseTo(share(20, 0.03), 4);
  expect(high).toBeCloseTo(0.15, 4);
  expect(mid).toBeLessThan(high * 0.7);
  expect(low).toBeLessThan(high * 0.15);
  // Far out a notch still covers more ground than near: distance x share.
  const far = (await wheelFrom(page, 60, 0.5, 100)) - 60;
  const near = (await wheelFrom(page, 4, 0.5, 100)) - 4;
  expect(far / near).toBeGreaterThan(30);
});

test('ctrl makes a notch a quarter', async ({ page }) => {
  await open(page);
  const plain = (await wheelFrom(page, 20, 1.2, 100)) / 20 - 1;
  const slow = (await wheelFrom(page, 20, 1.2, 100, true)) / 20 - 1;
  console.log('one notch: plain', plain.toFixed(4), 'ctrl', slow.toFixed(4));
  expect(slow).toBeCloseTo(share(20, 1.2, true), 4);
  expect(slow / plain).toBeCloseTo(0.25, 2);
  // Near the ground ctrl slows the already small step further.
  expect((await wheelFrom(page, 20, 0.03, 100, true)) / 20 - 1).toBeCloseTo(share(20, 0.03, true), 4);
  // Negative: ctrl + wheel does not zoom the page itself.
  expect(await page.evaluate(() => window.visualViewport.scale)).toBe(1);
});

test('wheel up comes closer by the same share; notches add up', async ({ page }) => {
  await open(page);
  expect(await wheelFrom(page, 20, 1.2, -100)).toBeCloseTo(20 / (1 + share(20, 1.2)), 3);
  // Two quick notches: the second builds on the first goal, not on where
  // the glide happens to be.
  await page.evaluate((t) => window.sc2viewer.view({ distance: 20, pitch: 1.2, target: t }), TARGET);
  await page.mouse.wheel(0, 100);
  await page.mouse.wheel(0, 100);
  await settled(page);
  const first = 20 * (1 + share(20, 1.2));
  expect((await camera(page)).distance).toBeCloseTo(first * (1 + share(first, 1.2)), 3);
});

test('negative: setting the view stops a zoom glide', async ({ page }) => {
  await open(page);
  await page.evaluate(() => window.sc2viewer.view({ distance: 10 }));
  await page.mouse.wheel(0, 400);
  await page.evaluate(() => window.sc2viewer.view({ distance: 7 }));
  expect((await camera(page)).zoomGoal).toBe(null);
  // A few frames later the camera is still where it was set.
  await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(() => requestAnimationFrame(done)))));
  expect((await camera(page)).distance).toBe(7);
});

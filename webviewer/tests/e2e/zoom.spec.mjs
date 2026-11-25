import { test, expect } from '../fixtures.mjs';
import { frames, open as openPage, state } from '../page.mjs';

// Wheel zoom in the page: the canvas wheel reaches the zoom, ctrl + wheel
// does not zoom the page, and setting the view stops a glide. The zoom's
// rule (shares, ctrl, the glide on the frame clock, the ground floor):
// tests/unit/zoom.spec.mjs.

async function open(page) {
  await openPage(page);
  const box = await page.locator('canvas#view').boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
}

const camera = async (page) => (await state(page)).camera;
const settled = (page) => expect.poll(async () => (await camera(page)).zoomGoal).toBe(null);

/** The share of the distance one notch moves, the target on the ground (zoom.ts). */
function share(distance, pitch, ctrl = false) {
  const s = 0.15 * Math.max(0.12, Math.min(1, (distance * Math.sin(pitch)) / 10));
  return ctrl ? s * 0.25 : s;
}

test('the canvas wheel zooms by the rule, with ctrl a quarter; ctrl + wheel does not zoom the page', async ({ page }) => {
  await open(page);
  for (const ctrl of [false, true]) {
    await page.evaluate(() => window.sc2viewer.view({ distance: 20, pitch: 1.2, target: [0, 0, 0] }));
    if (ctrl) await page.keyboard.down('Control');
    await page.mouse.wheel(0, 100);
    if (ctrl) await page.keyboard.up('Control');
    await settled(page);
    expect((await camera(page)).distance, `ctrl ${ctrl}`).toBeCloseTo(20 * (1 + share(20, 1.2, ctrl)), 3);
  }
  // Negative: ctrl + wheel does not zoom the page itself.
  expect(await page.evaluate(() => window.visualViewport.scale)).toBe(1);
});

test('negative: setting the view stops a zoom glide', async ({ page }) => {
  await open(page);
  await page.evaluate(() => window.sc2viewer.view({ distance: 10 }));
  await page.mouse.wheel(0, 400);
  await page.evaluate(() => window.sc2viewer.view({ distance: 7 }));
  expect((await camera(page)).zoomGoal).toBe(null);
  // A few frames later the camera is still where it was set.
  await frames(page);
  await frames(page);
  expect((await camera(page)).distance).toBe(7);
});

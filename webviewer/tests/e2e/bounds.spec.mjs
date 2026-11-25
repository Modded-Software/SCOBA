import { test, expect } from '../fixtures.mjs';
import { frames, idle, open, state } from '../page.mjs';

// Culling bounds: a unit stays drawn while any part of it is in view, even
// when its origin is off screen. Bounds come from the M3 file (header and
// sequence boxes) and the rest-pose vertices. Engine state: the item's
// `drawn` flag and what the mouse finds over the canvas (the pick buffer).

const DISTANCE = 10;
const FOV = Math.PI / 4;

/**
 * Look along +y at height z, with the camera target `offset` world units
 * right of where the origin would be at the left edge of the view. Pitch 0,
 * so the left edge at y = 0 is a vertical line at x = target - halfWidth.
 */
async function lookPastLeftEdge(page, offset, z) {
  const aspect = (await state(page)).camera.aspect;
  const halfWidth = DISTANCE * Math.tan(FOV / 2) * aspect;
  await page.evaluate(([x, z, d]) => window.sc2viewer.view({ yaw: -Math.PI / 2, pitch: 0, distance: d, target: [x, 0, z] }), [halfWidth + offset, z, DISTANCE]);
  // `drawn` is set when a frame draws: read it after frames of the new view.
  await frames(page);
  return halfWidth;
}

/** Where on the canvas the mouse finds the item: a grid of points, as fractions of the width. */
const hits = (page, id) =>
  page.evaluate((i) => {
    const r = document.querySelector('#view').getBoundingClientRect();
    const found = [];
    for (let a = 0; a <= 40; a++) {
      for (let b = 1; b < 20; b++) {
        const x = r.left + (r.width * a) / 40;
        const y = r.top + (r.height * b) / 20;
        if (window.SC2App.itemAt(Math.min(x, r.right - 1), y)?.id === i) found.push(a / 40);
      }
    }
    return found;
  }, id);

async function setup(page) {
  await open(page, { grid: false });
  await page.evaluate(() => window.sc2viewer.addUnit('Thor', { x: 0, y: 0, rot: 0, pick: 0.5 }));
  await idle(page);
  const item = (await state(page)).items[0];
  expect(item.loaded).toBe(true);
  // The model has bounds: the sphere is not a point.
  expect(item.boundsRadius).toBeGreaterThan(1);
  expect(item.boundsRadius).toBeLessThan(20);
  return item;
}

test('negative: a unit wholly out of view is culled and not drawn', async ({ page }) => {
  const item = await setup(page);
  const scale = Math.max(...item.dataScale);
  // Past the left frustum plane by more than the whole sphere. The plane is
  // slanted by half the horizontal field of view, so the distance from the
  // origin to it is the offset along x times the cosine of that angle.
  const halfAngle = Math.atan(Math.tan(FOV / 2) * (await state(page)).camera.aspect);
  await lookPastLeftEdge(page, (item.boundsRadius * scale + 1) / Math.cos(halfAngle), 1.5);
  const s = (await state(page)).items[0];
  const at = await hits(page, item.id);
  console.log('wholly out: drawn', s.drawn, 'hits', at.length);
  expect(s.drawn).toBe(false);
  expect(at).toEqual([]);
});

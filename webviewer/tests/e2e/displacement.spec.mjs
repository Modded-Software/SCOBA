import { test, expect } from '../fixtures.mjs';
import { frames, idle, open, state, view } from '../page.mjs';

// Displacement materials (DIS_): drawn after the scene, over a copy of the
// frame, shifted along their normal maps (src/formats/m3/displacement.ts,
// M3ModelInstance.renderDisplacement). Survey: scripts/displacement-survey.sh.
// How the distortion looks is an operator check (SPEC-VIEWER 14); these
// tests count the displacement batches the frame draws.

const VIEW = { yaw: -Math.PI / 2, pitch: 0.35, distance: 7, target: [0, 0, 1.2] };

async function place(page, id) {
  await page.evaluate((u) => window.sc2viewer.addUnit(u, { x: 0, y: 0, pick: 0.5 }), id);
  await idle(page);
  await view(page, VIEW);
  return state(page);
}

/** Displacement batches the next frame draws, with the switch on and off. */
async function drawnBatches(page) {
  const counts = {};
  for (const on of [true, false]) {
    await page.evaluate((o) => window.sc2viewer.setDisplacement(o), on);
    await frames(page);
    counts[on ? 'on' : 'off'] = (await state(page)).displacedBatches;
  }
  await page.evaluate(() => window.sc2viewer.setDisplacement(true));
  return counts;
}

test('A.R.E.S.: its displacement batches are drawn, not reported as undrawn', async ({ page }) => {
  const errors = await open(page);
  const s = await place(page, 'Warbot');
  const item = s.items[0];
  console.log('Warbot undrawn', JSON.stringify(item.undrawn), 'displacement', item.displacementBatches);
  expect(item.loaded).toBe(true);
  expect(item.displacementBatches).toBe(2);
  expect(item.undrawn.filter((u) => /displacement/.test(u))).toEqual([]);
  expect(await drawnBatches(page)).toEqual({ on: 2, off: 0 });
  expect(errors).toEqual([]);
});

test('Archon: its distortion batches are drawn; switched off, none is', async ({ page }) => {
  const errors = await open(page);
  const s = await place(page, 'Archon');
  const item = s.items[0];
  expect(item.displacementBatches).toBeGreaterThan(0);
  expect(item.undrawn.filter((u) => /displacement/.test(u))).toEqual([]);
  expect(await drawnBatches(page)).toEqual({ on: item.displacementBatches, off: 0 });
  expect(errors).toEqual([]);
});

test('negative: a model without displacement draws none', async ({ page }) => {
  const errors = await open(page);
  const s = await place(page, 'Marine');
  expect(s.items[0].displacementBatches).toBe(0);
  expect(await drawnBatches(page)).toEqual({ on: 0, off: 0 });
  expect(errors).toEqual([]);
});

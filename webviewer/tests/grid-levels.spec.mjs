import { test, expect } from '@playwright/test';

// The ground grid at any zoom (operator 2026-11-21: "the visible part of the
// grid scales with the world"; "make 7 hexagons build a bigger hexagon so
// they don't get arbitrarily small"). src/page/core/render/ground.ts: the quad grows with the
// camera distance; shaders/ground.frag: aperture-7 levels, the level per
// pixel such that cells stay at least ground.minPx (24) pixels wide, the
// finer level fading out below that over sqrt(7).

const MIN_PX = 24;
const SQRT7 = Math.sqrt(7);

async function open(page) {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push(m.text());
  });
  await page.goto('/');
  await page.waitForFunction(() => window.sc2viewer && window.sc2viewer.ready);
  return errors;
}

/** Grid lines along rows at shares of the canvas height, with the camera at `distance`. */
const linesAt = (page, distance, shares) => page.evaluate(([d, ks]) => {
  const app = window.SC2App;
  app.view({ target: [0, 0, 0], yaw: -Math.PI / 2, pitch: 0.9, distance: d });
  const h = app.canvas.height;
  return ks.map((k) => app.gridLines(Math.round(h * k)));
}, [distance, shares]);

const gaps = (centres) => centres.slice(1).map((c, i) => c - centres[i]);
const median = (list) => [...list].sort((a, b) => a - b)[list.length >> 1];

test('the grid shows at every zoom, its cells never smaller than the level rule allows', async ({ page }) => {
  const errors = await open(page);
  // Only the part right of the panels counts: the canvas runs under them.
  const left = await page.evaluate(() => window.SC2App.visibleRect().left - window.SC2App.canvas.getBoundingClientRect().left);
  for (const distance of [9, 60, 400, 2000]) {
    const rows = await linesAt(page, distance, [0.5, 0.75, 0.9]);
    for (const [k, row] of rows.entries()) {
      const seen = row.centres.filter((c) => c >= left);
      const g = gaps(seen);
      console.log(`distance ${distance} row ${[0.5, 0.75, 0.9][k]}: ${seen.length} lines, median gap ${g.length ? median(g).toFixed(1) : '-'} px, quad ${row.radius}`);
      // Lines across the view at every zoom.
      expect(seen.length, `distance ${distance}`).toBeGreaterThanOrEqual(3);
      // Never finer than the fading level allows (a little slack for lines
      // crossing the row at an angle and for two levels' lines side by side).
      expect(median(g), `distance ${distance}`).toBeGreaterThanOrEqual(MIN_PX / SQRT7 / 2);
    }
    // The quad grows with the distance.
    expect(rows[0].radius).toBeGreaterThanOrEqual(8 * distance);
  }
  expect(errors).toEqual([]);
});

test('every unit lights the grid around it, past the old 31-unit cap', async ({ page }) => {
  const errors = await open(page);
  const max = await page.evaluate(() => window.SC2App.ground.maxSpots);
  console.log(`spots the shader holds: ${max}`);
  expect(max).toBeGreaterThanOrEqual(64);
  // 48 units in a row along y = 0, 4 apart; the last at x = 188.
  const N = 48;
  for (let i = 0; i < N; i++) await page.evaluate((x) => window.sc2viewer.addUnit('Marine', { x, y: 0, pick: 0.5 }), i * 4);
  await page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 60_000 });
  // Look down on the last unit: the 48th lights the border beside it.
  const lift = async (x, y) => page.evaluate(([px, py]) => {
    // Distance 20 top down: level 0 cells (~40 px), y within about +-8 in view.
    window.SC2App.view({ yaw: -Math.PI / 2, pitch: Math.PI / 2 - 0.01, distance: 20, target: [188, 0, 0] });
    let best = 0;
    for (const dx of [-0.01, -0.005, 0, 0.005, 0.01]) best = Math.max(best, window.sc2viewer.groundPixel(px + dx, py).rgb[1]);
    return best;
  }, [x, y]);
  const nearLast = await lift(188.5, 0);
  // Negative: off the row, the grid stays faint. y = 8 * 0.866: an even hex
  // row, centres on whole x, so x = 188.5 is a border; 6.9 from any unit.
  const offRow = await lift(188.5, 6.928);
  const drawn = await page.evaluate(() => window.SC2App.ground.spotsDrawn);
  console.log(`48 units: spots drawn ${drawn}; border beside the 48th ${nearLast}, off the row ${offRow}`);
  expect(drawn).toBe(N);
  expect(nearLast - 26).toBeGreaterThan(4 * (offRow - 26));
  expect(errors).toEqual([]);
});

test('negative: with one fixed level (the old grid) the far view loses its lines', async ({ page }) => {
  const errors = await open(page);
  const far = (await linesAt(page, 2000, [0.75]))[0];
  // Force level 0 everywhere: cells would need to be under 1e-6 pixels to change level.
  await page.evaluate(() => {
    window.SC2App.ground.minPx = 1e-6;
  });
  const fixed = (await linesAt(page, 2000, [0.75]))[0];
  const g = gaps(fixed.centres);
  console.log(`distance 2000, one level: ${fixed.centres.length} line runs, median gap ${g.length ? median(g).toFixed(1) : '-'}; with levels: ${far.centres.length} lines, median gap ${median(gaps(far.centres)).toFixed(1)}`);
  // Sub-pixel cells: either no clear lines, or runs packed under the rule's least gap.
  expect(fixed.centres.length < 3 || median(g) < MIN_PX / SQRT7 / 2).toBe(true);
  expect(median(gaps(far.centres))).toBeGreaterThanOrEqual(MIN_PX / SQRT7 / 2);
  expect(errors).toEqual([]);
});

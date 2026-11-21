import { test, expect } from '@playwright/test';

// The hex grid ground and the skybox.

/** Open the page; a script error fails at once with its message. */
async function open(page) {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto('/');
  await expect.poll(() => errors.join(' | ') || page.evaluate(() => Boolean(window.sc2viewer && window.sc2viewer.ready)), { timeout: 10_000 }).toBe(true);
}

const state = (page) => page.evaluate(() => window.sc2viewer.state());
const pixels = (page) => page.evaluate(() => window.sc2viewer.pixels());
const pixelAt = (page, x, y) => page.evaluate(([x, y]) => window.sc2viewer.groundPixel(x, y), [x, y]);
/**
 * The brightest (by green) of 5 samples across ±0.01 in x, about ±1 pixel
 * at the top-down view: a one-pixel line may fall between sample points.
 */
async function at(page, x, y) {
  let best = null;
  for (const dx of [-0.01, -0.005, 0, 0.005, 0.01]) {
    const p = await pixelAt(page, x + dx, y);
    if (!best || p.rgb[1] > best.rgb[1]) best = p;
  }
  return best;
}
const BG = [26, 26, 31];
const near = (a, b, step) => a.every((v, i) => Math.abs(v - b[i]) <= step);

/** Look straight down on the origin, so world points map to known pixels. */
const topDown = (page) => page.evaluate(() => window.sc2viewer.view({ yaw: -Math.PI / 2, pitch: Math.PI / 2 - 0.01, distance: 8, target: [0, 0, 0] }));

// Pointy-top hexagons, one unit from side to side: centres at (0, 0), (1, 0),
// (0.5, 0.866); borders through (0.5, 0) and (0.25, 0.433). A square grid
// of the same size would not draw (0.25, 0.433).
const CENTRES = [[0, 0], [1, 0], [0.5, 0.866], [-0.5, -0.866]];
const BORDERS = [[0.5, 0], [-0.5, 0], [0.25, 0.433], [-0.25, -0.433], [0.75, 0.433]];

test('the ground is a green hexagonal grid, on by default', async ({ page }) => {
  await open(page);
  await topDown(page);
  expect((await state(page)).grid).toBe(true);
  await expect(page.locator('#grid-toggle')).toHaveClass(/\bon\b/);
  const borders = [];
  for (const [x, y] of BORDERS) borders.push((await at(page, x, y)).rgb);
  const centres = [];
  for (const [x, y] of CENTRES) centres.push((await at(page, x, y)).rgb);
  console.log('borders', JSON.stringify(borders), 'centres', JSON.stringify(centres));
  for (const [r, g, b] of borders) {
    // Away from units the grid is faint (operator 2026-11-21: "way fainter
    // overall"): green leads and the line shows, but only just. The line
    // before that change was over 20 above the background.
    // Green leads; over the bluish background (26, 26, 31) a faint line keeps
    // little lead on blue (measured: 41 green, 39 blue).
    expect(g).toBeGreaterThan(r + 4);
    expect(g).toBeGreaterThanOrEqual(b + 2);
    expect(g).toBeGreaterThan(BG[1] + 6);
    expect(g).toBeLessThan(BG[1] + 22);
  }
  // Negative: the inside of a cell is a faint fill, not a line.
  for (const [r, g, b] of centres) {
    expect(g).toBeLessThan(BG[1] + 20);
    expect(near([r, g, b], BG, 20)).toBe(true);
  }
});

test('grid lines are thin: about one pixel', async ({ page }) => {
  await open(page);
  await topDown(page);
  // At this view one world unit is about 106 pixels, so 0.03 is ~3 px
  // beside the vertical border at x = 0.5. The old line reached there
  // (measured before: [30, 50, 40] at 0.475).
  const on = (await at(page, 0.5, 0)).rgb;
  const beside = [(await pixelAt(page, 0.53, 0)).rgb, (await pixelAt(page, 0.47, 0)).rgb];
  console.log('on', JSON.stringify(on), 'beside', JSON.stringify(beside));
  // The faint grid (away from units) is 6 or more over the background.
  expect(on[1]).toBeGreaterThan(BG[1] + 6);
  for (const rgb of beside) expect(near(rgb, BG, 12)).toBe(true);
});

/** Points along every side of the hexagons near the origin, corners left out. */
function borderPoints() {
  const points = [];
  const r = 1 / Math.sqrt(3); // centre to corner, for one unit side to side
  for (let j = -3; j <= 3; j++) {
    for (let i = -3; i <= 3; i++) {
      const cx = i + (j % 2 ? 0.5 : 0);
      const cy = j * 0.8660254;
      for (let k = 0; k < 6; k++) {
        const a = Math.PI / 6 + (k * Math.PI) / 3;
        const b = a + Math.PI / 3;
        for (let t = 0.15; t < 0.9; t += 0.1) {
          points.push([cx + r * ((1 - t) * Math.cos(a) + t * Math.cos(b)), cy + r * ((1 - t) * Math.sin(a) + t * Math.sin(b))]);
        }
      }
    }
  }
  return points;
}

// The views of the dashed-line report: the default, a low grazing look and
// a far one. A dashed border has stretches with no line pixel at all.
const SOLID_VIEWS = [
  { yaw: -Math.PI / 2, pitch: 0.5, distance: 9, target: [0, 0, 0] },
  { yaw: -Math.PI / 2 + 0.4, pitch: 0.22, distance: 9, target: [0, 0, 0] },
  { yaw: -Math.PI / 2 - 0.3, pitch: 0.6, distance: 30, target: [0, 0, 0] },
];

test('grid lines are solid: no gaps along the borders, also at a grazing angle', async ({ page }) => {
  await open(page);
  const points = borderPoints();
  for (const view of SOLID_VIEWS) {
    await page.evaluate((v) => window.sc2viewer.view(v), view);
    const peaks = (await page.evaluate((p) => window.sc2viewer.groundPeaks(p, 1), points)).filter(Boolean);
    const lift = peaks.map((p) => p.rgb[1] - BG[1]).sort((a, b) => a - b);
    const median = lift[Math.floor(lift.length / 2)];
    // A gap: a border point with no pixel near it lifted to 40% of a typical one.
    const gaps = lift.filter((g) => g < 0.4 * median).length;
    console.log('view', JSON.stringify(view), 'samples', lift.length, 'median', median, 'min', lift[0], 'p5', lift[Math.floor(lift.length * 0.05)], 'gaps', gaps);
    expect(lift.length).toBeGreaterThan(300);
    // The faint grid: a typical border pixel is 6 or more over the background.
    expect(median).toBeGreaterThan(6);
    expect(gaps / lift.length).toBeLessThan(0.01);
  }
  // Negative: cell insides are not lit like a line.
  await page.evaluate((v) => window.sc2viewer.view(v), SOLID_VIEWS[0]);
  const inside = (await page.evaluate((p) => window.sc2viewer.groundPeaks(p, 0), CENTRES)).filter(Boolean);
  for (const p of inside) expect(p.rgb[1] - BG[1]).toBeLessThan(5);
});

/** Green of the border at (x, 0), the vertical hex side x = k + 0.5. */
const borderGreen = async (page, x) => (await at(page, x, 0)).rgb[1];

test('the grid glows around a unit and fades out with distance', async ({ page }) => {
  await open(page);
  await topDown(page);
  const before = { near: await borderGreen(page, 1.5), far: await borderGreen(page, 4.5) };
  await page.evaluate(() => window.sc2viewer.addUnit('Marine', { x: 0, y: 0, team: 1, pick: 0.5 }));
  await page.waitForFunction(() => window.sc2viewer.idle());
  const after = { near: await borderGreen(page, 1.5), mid: await borderGreen(page, 2.5), far: await borderGreen(page, 4.5) };
  console.log('unit glow', JSON.stringify({ before, after }));
  expect(after.near).toBeGreaterThan(before.near + 25);
  // Near a unit the line stands out: at least four times the lift of the faint grid.
  expect(after.near - BG[1]).toBeGreaterThan(4 * (after.far - BG[1]));
  // It falls off: brighter near than further out.
  expect(after.near).toBeGreaterThan(after.mid);
  // Negative: far from the unit nothing changes.
  expect(Math.abs(after.far - before.far)).toBeLessThanOrEqual(3);
});

test('the grid glows under the mouse, and stops when the mouse leaves', async ({ page }) => {
  await open(page);
  await topDown(page);
  const before = { near: await borderGreen(page, 1.5), far: await borderGreen(page, -2.5) };
  // Move the pointer to the ground point (1.3, 0). Framebuffer rows count from the bottom.
  const spot = await at(page, 1.3, 0);
  const box = await page.locator('canvas#view').boundingBox();
  await page.mouse.move(box.x + spot.px, box.y + box.height - 1 - spot.py);
  const pointer = (await state(page)).pointer;
  expect(pointer[0]).toBeCloseTo(1.3, 1);
  expect(pointer[1]).toBeCloseTo(0, 1);
  const hover = { near: await borderGreen(page, 1.5), far: await borderGreen(page, -2.5) };
  console.log('mouse glow', JSON.stringify({ before, hover }));
  expect(hover.near).toBeGreaterThan(before.near + 25);
  expect(Math.abs(hover.far - before.far)).toBeLessThanOrEqual(3);
  // Negative: over the panel the pointer is off the ground; the glow goes.
  await page.mouse.move(100, 100);
  expect((await state(page)).pointer).toBe(null);
  expect(Math.abs((await borderGreen(page, 1.5)) - before.near)).toBeLessThanOrEqual(3);
});

test('the grid button turns the ground off and on', async ({ page }) => {
  await open(page);
  await topDown(page);
  expect((await pixels(page)).covered).toBeGreaterThan(10000);
  await page.click('#grid-toggle');
  expect((await state(page)).grid).toBe(false);
  await expect(page.locator('#grid-toggle')).not.toHaveClass(/\bon\b/);
  // Negative: with no grid and no units nothing but the background is drawn.
  expect((await pixels(page)).covered).toBe(0);
  await page.click('#grid-toggle');
  expect((await state(page)).grid).toBe(true);
  expect((await pixels(page)).covered).toBeGreaterThan(10000);
});

test('the skybox list holds every skybox file of the game', async ({ request }) => {
  const body = await (await request.get('/api/skyboxes')).json();
  expect(body.total).toBeGreaterThanOrEqual(60);
  expect(body.items).toHaveLength(body.total);
  const ids = body.items.map((s) => s.id);
  expect(new Set(ids).size).toBe(ids.length);
  const aiur = body.items.find((s) => s.id === 'AiurSkybox');
  expect(aiur).toMatchObject({ name: 'Aiur Skybox', model: 'AiurSkybox' });
  expect(aiur.file.toLowerCase()).toMatch(/assets\\skyboxes\\aiurskybox\\aiurskybox\.m3$/);
  // Negative: the map's AiurSkyboxFlipped model names a file that only the
  // map build creates (scripts/skybox_flip.py); with no file it is not listed.
  expect(ids).not.toContain('AiurSkyboxFlipped');
  for (const sky of body.items) expect(sky.file.toLowerCase()).toMatch(/\\assets\\skyboxes\\.+\.m3$/);
  // A listed file is a real M3.
  const file = await request.get('/file?path=' + encodeURIComponent(aiur.file));
  expect((await file.body()).subarray(0, 4).toString('latin1')).toBe('43DM');
  // Search narrows it.
  const char = await (await request.get('/api/skyboxes?q=char')).json();
  expect(char.items.length).toBeGreaterThan(0);
  expect(char.items.every((s) => (s.name + ' ' + s.id).toLowerCase().includes('char'))).toBe(true);
});

test('the sky button opens a dialog; picking a skybox draws it behind everything', async ({ page }) => {
  await open(page);
  await page.click('#grid-toggle'); // grid off: only the sky can cover the background
  expect((await pixels(page)).covered).toBe(0);
  await expect(page.locator('#sky-dialog')).toBeHidden();
  await page.click('#sky-button');
  await expect(page.locator('#sky-dialog')).toBeVisible();
  await expect(page.locator('#sky-dialog .picker-list li').first()).toBeVisible();
  await page.fill('#sky-dialog input[type=search]', 'aiur');
  await page.locator('#sky-dialog .picker-list li[data-id="AiurSkybox"]').click();
  await expect(page.locator('#sky-dialog')).toBeHidden();
  expect((await state(page)).sky).toMatchObject({ id: 'AiurSkybox' });
  await expect(page.locator('#sky-button')).toHaveClass(/\bon\b/);
  await page.waitForFunction(() => window.sc2viewer.idle());
  await page.waitForFunction(() => window.sc2viewer.state().skyLoaded);
  const covered = (await pixels(page)).covered;
  const p = await pixels(page);
  console.log('sky covered', covered, 'of', p.width * p.height);
  expect(covered).toBeGreaterThan(0.5 * p.width * p.height);

  // "none" takes it away again.
  await page.click('#sky-button');
  await page.locator('#sky-dialog .picker-list li[data-id=""]').click();
  expect((await state(page)).sky).toBe(null);
  expect((await pixels(page)).covered).toBe(0);
});

test('escape closes the sky dialog without changing the sky', async ({ page }) => {
  await open(page);
  await page.click('#sky-button');
  await expect(page.locator('#sky-dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.locator('#sky-dialog')).toBeHidden();
  expect((await state(page)).sky).toBe(null);
});

test('a unit stands on the grid, drawn over it', async ({ page }) => {
  await open(page);
  await page.evaluate(() => window.sc2viewer.addUnit('Marine', { x: 0, y: 0, team: 1, pick: 0.5 }));
  await page.waitForFunction(() => window.sc2viewer.idle());
  const withGrid = await page.evaluate(() => window.sc2viewer.colorStats());
  // The marine's middle is the marine, not grid green.
  const middle = await page.evaluate(() => window.sc2viewer.groundPixel(0, 0, 0.9));
  console.log('marine middle', JSON.stringify(middle), 'stats', JSON.stringify(withGrid));
  expect(middle.rgb[1]).toBeLessThan(middle.rgb[0] + 40);
});

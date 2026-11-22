import { test, expect } from '@playwright/test';

// The mouse hit goes by pixel (public/pickbuffer.js, public/js/pick.js
// hitAt): the unit whose solid surface is drawn under the mouse, not a
// cylinder around the unit. The truth here is the drawn frame itself:
// sc2viewer.drawnAt says which pixels are not background, with the grid
// off and the mouse away.

const VIEW = { yaw: -Math.PI / 2, pitch: 0.5, distance: 26, target: [0, 0, 1.5] };
const EDGE = 4; // px: samples this close to the silhouette's edge are left out

async function open(page) {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => {
    if (m.text().startsWith('viewer:') || m.type() === 'error') errors.push(m.text());
  });
  await page.goto('/');
  await expect.poll(() => errors.join(' | ') || page.evaluate(() => Boolean(window.sc2viewer && window.sc2viewer.ready)), { timeout: 10_000 }).toBe(true);
  await page.evaluate((v) => {
    window.sc2viewer.view(v);
    window.sc2viewer.setGrid(false);
  }, VIEW);
  return errors;
}

// The stock data: the map's own data changes the size and height of units.
// No animation (sequence -1): the picture read first is the picture hovered
// seconds later. Animated units: pick.spec.mjs.
async function add(page, unit, x, y, dataset = 'stock') {
  const id = await page.evaluate(([u, ux, uy, d]) => window.sc2viewer.addUnit(u, { x: ux, y: uy, pick: 0.5, dataset: d, sequence: -1 }), [unit, x, y, dataset]);
  await page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 15_000 });
  return id;
}

const onWorld = (page, p) => page.evaluate((q) => window.sc2viewer.screenOf(q), p);
const frames = (page) => page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))));

/** The id under the mouse once it rests at a page pixel. */
async function hoverAt(page, x, y) {
  await page.mouse.move(x, y);
  await frames(page);
  return page.evaluate(() => window.sc2viewer.state().pick.hovered);
}

/** Move the mouse off every unit (a far corner of the view) and wait for no mouse-over. */
async function mouseAway(page) {
  const box = await page.locator('#view').boundingBox();
  await page.mouse.move(box.x + box.width - 3, box.y + box.height - 3);
  await expect.poll(() => page.evaluate(() => window.sc2viewer.state().pick.hovered)).toBe(null);
}

/**
 * Sample a grid of view pixels around the screen point `centre`. Each
 * sample: { x, y, drawn } with drawn true or false; samples whose
 * neighbours EDGE pixels away disagree (the silhouette's edge) and samples
 * not on the bare view (under a panel) are left out.
 */
async function samples(page, centre, halfW, halfH, step) {
  const points = [];
  for (let dy = -halfH; dy <= halfH; dy += step) for (let dx = -halfW; dx <= halfW; dx += step) points.push([Math.round(centre[0] + dx), Math.round(centre[1] + dy)]);
  expect(points.length).toBeLessThanOrEqual(120);
  const onView = await page.evaluate((list) => list.map(([x, y]) => document.elementFromPoint(x, y) === document.getElementById('view')), points);
  const around = points.flatMap(([x, y]) => [[x, y], [x - EDGE, y], [x + EDGE, y], [x, y - EDGE], [x, y + EDGE]]);
  // Two silhouettes: everything drawn, and the solid (unblended) parts alone.
  const [all, solid] = await page.evaluate((list) => {
    const everything = window.sc2viewer.drawnAt(list);
    window.sc2viewer.setSolidOnly(true);
    const solidParts = window.sc2viewer.drawnAt(list);
    window.sc2viewer.setSolidOnly(false);
    return [everything, solidParts];
  }, around);
  const out = [];
  points.forEach(([x, y], i) => {
    const a = all.slice(i * 5, i * 5 + 5);
    const s = solid.slice(i * 5, i * 5 + 5);
    if (!onView[i] || a[0] === null || a.some((d) => d !== a[0]) || s.some((d) => d !== s[0])) return;
    out.push({ x, y, drawn: a[0], solid: s[0] });
  });
  return out;
}

/**
 * Up to `most` pixels of the box drawn by blended parts alone (a glow with
 * nothing solid behind it), each with its four neighbours the same.
 */
async function glowPixels(page, box, most) {
  const points = [];
  for (let y = box.minY; y <= box.maxY; y += 3) for (let x = box.minX; x <= box.maxX; x += 3) points.push([x, y]);
  // Both pictures are of one still frame, so one pixel of margin is enough here.
  const around = points.flatMap(([x, y]) => [[x, y], [x - 1, y], [x + 1, y], [x, y - 1], [x, y + 1]]);
  const [all, solid] = await page.evaluate((list) => {
    const everything = window.sc2viewer.drawnAt(list);
    window.sc2viewer.setSolidOnly(true);
    const solidParts = window.sc2viewer.drawnAt(list);
    window.sc2viewer.setSolidOnly(false);
    return [everything, solidParts];
  }, around);
  return points.filter((p, i) => [0, 1, 2, 3, 4].every((k) => all[i * 5 + k] === true && solid[i * 5 + k] === false)).slice(0, most);
}

// - CommandCenter, Battlecruiser (stock data): large units.
// - Marine of the test dataset `fx`, drawn at twice its size: the picture
//   is wider than the unit's ring, which the old hit (a cylinder of the
//   ring's radius) could not reach.
// - Battlecruiser: its engine glows are blended parts, see-through, no hit.
const CASES = [
  { unit: 'CommandCenter', dataset: 'stock', distance: 26 },
  { unit: 'Battlecruiser', dataset: 'stock', distance: 26, glow: true },
  { unit: 'Marine', dataset: 'fx', distance: 9, beyondRing: true },
];

for (const { unit, dataset, distance, glow: hasGlow, beyondRing } of CASES) {
  // The Marine case stays in the default run (beyond the ring);
  // the two large units are the slow survey.
  test(`mouse-over goes by the drawn picture: ${unit} (${dataset})${unit === 'Marine' ? '' : ' @slow'}`, async ({ page }) => {
    // About 30 mouse moves, each waiting two frames of the software renderer.
    test.setTimeout(60_000);
    const errors = await open(page);
    await page.evaluate((v) => window.sc2viewer.view(v), { ...VIEW, distance });
    const id = await add(page, unit, 0, 0, dataset);
    await mouseAway(page);
    // The grid covers the drawn box (canvas pixels are page pixels here: the
    // view starts at the page's corner, one to one) and a margin around it.
    const view = await page.locator('#view').boundingBox();
    expect([view.x, view.y]).toEqual([0, 0]);
    const box = await page.evaluate(() => window.sc2viewer.pixels());
    console.log(unit, 'drawn box', JSON.stringify([box.minX, box.maxX, box.minY, box.maxY]), 'covered', box.covered);
    expect(box.covered).toBeGreaterThan(2000);
    const halfW = (box.maxX - box.minX) / 2 + 30;
    const halfH = (box.maxY - box.minY) / 2 + 30;
    // An 11 x 11 grid is read from the picture (no mouse, cheap); the mouse
    // then visits a spread of each kind (at most 12 + 12 + every glow-only point).
    const step = Math.max(halfW, halfH) / 5;
    const grid = await samples(page, [(box.minX + box.maxX) / 2, (box.minY + box.maxY) / 2], halfW, halfH, step);
    const spread = (all, n) => (all.length <= n ? all : Array.from({ length: n }, (_, i) => all[Math.floor((i * all.length) / n)]));
    const list = [...spread(grid.filter((s) => s.solid), 12), ...spread(grid.filter((s) => !s.drawn), 12), ...grid.filter((s) => s.drawn && !s.solid)];
    console.log(unit, 'grid', grid.length, 'hovered', list.length);
    const on = list.filter((s) => s.solid);
    const off = list.filter((s) => !s.drawn);
    // Drawn, but only by blended parts (glows): see-through, not a hit.
    const glow = list.filter((s) => s.drawn && !s.solid);
    console.log(unit, 'samples', list.length, 'solid', on.length, 'not drawn', off.length, 'glow only', glow.length);
    // The grid must hold both kinds, or it proves nothing.
    expect(on.length).toBeGreaterThanOrEqual(8);
    expect(off.length).toBeGreaterThanOrEqual(8);
    const wrong = [];
    for (const s of list) {
      const hovered = await hoverAt(page, s.x, s.y);
      if (hovered !== (s.solid ? id : null)) wrong.push({ ...s, hovered });
    }
    // Every solid pixel hovers the unit; no pixel beside it does, and no glow-only pixel.
    expect(wrong).toEqual([]);
    // Solid samples outside the unit's ring on screen: the old hit (a
    // cylinder of the ring's radius) could not reach them.
    const centre = await hoverAt(page, on[Math.floor(on.length / 2)].x, on[Math.floor(on.length / 2)].y);
    expect(centre).toBe(id);
    const radius = (await page.evaluate(() => window.sc2viewer.state())).rings[1].radius;
    const edges = [];
    // The ring's width on screen, at the ground and 3 up (above the units here, where it shows wider).
    for (const p of [[-radius, 0, 0], [radius, 0, 0], [-radius, 0, 3], [radius, 0, 3]]) edges.push((await onWorld(page, p))[0]);
    const beyond = on.filter((s) => s.x < Math.min(...edges) - EDGE || s.x > Math.max(...edges) + EDGE);
    console.log(unit, 'ring radius', radius, 'ring edges px', JSON.stringify(edges.map(Math.round)), 'solid samples beyond the ring', beyond.length);
    if (beyondRing) expect(beyond.length).toBeGreaterThanOrEqual(2);
    // Negative: pixels drawn by a glow alone are not a hit.
    await mouseAway(page);
    const glowOnly = await glowPixels(page, box, 4);
    console.log(unit, 'glow-only pixels tried', JSON.stringify(glowOnly));
    if (hasGlow) expect(glowOnly.length).toBeGreaterThanOrEqual(1);
    for (const [x, y] of glowOnly) expect(await hoverAt(page, x, y), `glow pixel ${x},${y}`).toBe(null);
    expect(errors).toEqual([]);
  });
}

test('a unit in front takes the pixel from the large unit behind it; a click selects by the same pixel', async ({ page }) => {
  const errors = await open(page);
  await page.evaluate((v) => window.sc2viewer.view(v), { ...VIEW, distance: 14 });
  // The side of the building towards the camera: the one lowest on screen.
  const sides = [[0, -2.3], [0, 2.3], [-2.3, 0], [2.3, 0]];
  const feet = [];
  for (const side of sides) feet.push(await onWorld(page, [side[0], side[1], 0]));
  const side = sides[feet.indexOf(feet.reduce((a, b) => (b[1] > a[1] ? b : a)))];
  // Points up a marine standing there, as world points and as pixels.
  const world = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1].map((z) => [side[0], side[1], z]);
  const pixels = [];
  for (const p of world) pixels.push((await onWorld(page, p)).map(Math.round));
  const pictures = () =>
    page.evaluate(([w, px]) => ({ drawn: window.sc2viewer.drawnAt(px), rgb: w.map((p) => window.sc2viewer.groundPixel(p[0], p[1], p[2]).rgb) }), [world, pixels]);
  // Three pictures: the marine alone, the building alone, both.
  const alone = await add(page, 'Marine', side[0], side[1]);
  await mouseAway(page);
  const marineOnly = await pictures();
  await page.evaluate((id) => window.sc2viewer.remove(id), alone);
  const big = await add(page, 'CommandCenter', 0, 0);
  await mouseAway(page);
  const buildingOnly = await pictures();
  const marine = await add(page, 'Marine', side[0], side[1]);
  await mouseAway(page);
  const both = await pictures();
  // A pixel both draw at alone, which shows the marine's colour with both: the marine is in front there.
  const same = (a, b) => a.every((v, i) => Math.abs(v - b[i]) <= 12);
  const table = world.map((p, i) => ({ z: p[2], pixel: pixels[i], marine: marineOnly.drawn[i], building: buildingOnly.drawn[i], marineRgb: marineOnly.rgb[i], buildingRgb: buildingOnly.rgb[i], bothRgb: both.rgb[i] }));
  console.log('front side', JSON.stringify(side), JSON.stringify(table));
  const row = table.find((r) => r.marine && r.building && same(r.bothRgb, r.marineRgb) && !same(r.bothRgb, r.buildingRgb));
  expect(row, 'a pixel where the marine covers the building').toBeTruthy();
  const at = row.pixel;
  expect(await hoverAt(page, at[0], at[1])).toBe(marine);
  await page.mouse.click(at[0], at[1]);
  expect(await page.evaluate(() => window.sc2viewer.state().pick.selected)).toBe(marine);
  // Negative: beside the marine, still on the building, it is the building.
  const beside = [at[0] + 60, at[1] - 40];
  await mouseAway(page);
  const [stillBuilding] = await page.evaluate((p) => window.sc2viewer.drawnAt([p]), beside);
  expect(stillBuilding).toBe(true);
  expect(await hoverAt(page, beside[0], beside[1])).toBe(big);
  await page.mouse.click(beside[0], beside[1]);
  expect(await page.evaluate(() => window.sc2viewer.state().pick.selected)).toBe(big);
  expect(errors).toEqual([]);
});

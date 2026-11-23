import { test, expect } from '@playwright/test';

// Alpha test (cut-out). A standard material with alphaTestThreshold t > 0
// draws only where its alpha-mask layers give alpha >= t / 255; the rest of
// the face is not drawn and takes no mouse hit. Rule: WhiteoutFlakes
// m3_surface_table.cpp (threshold = min(t / 255, 1)) and m3_standard.slang
// (alpha = product of the alpha masks; discard when alpha < threshold).
// The operator's case: the hanging vine and leaf cards of Zerus Large Tree
// drew as dark rectangles.
// The truth is the drawn frame (sc2viewer.drawnAt, grid off, mouse away),
// read with the model's alpha tests on and off (sc2viewer.setAlphaTest).

const VIEW = { yaw: -Math.PI / 2, pitch: 0.25, distance: 24, target: [0, 0, 4] };
const STEP = 6; // px between samples
const NEAR = 2; // px: a sample counts only when its four neighbours this far away agree

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

const frames = (page) => page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))));
const idle = (page) => page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 15_000 });

async function hoverAt(page, x, y) {
  await page.mouse.move(x, y);
  await frames(page);
  return page.evaluate(() => window.sc2viewer.state().pick.hovered);
}

async function mouseAway(page) {
  const box = await page.locator('#view').boundingBox();
  await page.mouse.move(box.x + box.width - 3, box.y + box.height - 3);
  await expect.poll(() => page.evaluate(() => window.sc2viewer.state().pick.hovered)).toBe(null);
}

/**
 * The item's silhouette with its alpha tests on and off, over a grid that
 * covers what it draws with them off. Each sample: { x, y, on, off }; a
 * sample at a silhouette edge (its neighbours disagree in either picture)
 * or under a panel is left out.
 */
async function silhouettes(page, id) {
  await mouseAway(page);
  const box = await page.evaluate((i) => {
    window.sc2viewer.setAlphaTest(i, false);
    const b = window.sc2viewer.pixels();
    window.sc2viewer.setAlphaTest(i, true);
    return b;
  }, id);
  expect(box.covered).toBeGreaterThan(1000);
  const points = [];
  for (let y = box.minY; y <= box.maxY; y += STEP) for (let x = box.minX; x <= box.maxX; x += STEP) points.push([x, y]);
  const around = points.flatMap(([x, y]) => [[x, y], [x - NEAR, y], [x + NEAR, y], [x, y - NEAR], [x, y + NEAR]]);
  const [on, off, onView] = await page.evaluate(([i, list, centres]) => {
    const withTest = window.sc2viewer.drawnAt(list);
    window.sc2viewer.setAlphaTest(i, false);
    const without = window.sc2viewer.drawnAt(list);
    window.sc2viewer.setAlphaTest(i, true);
    const bare = centres.map(([x, y]) => document.elementFromPoint(x, y) === document.getElementById('view'));
    return [withTest, without, bare];
  }, [id, around, points]);
  const out = [];
  points.forEach(([x, y], i) => {
    const a = on.slice(i * 5, i * 5 + 5);
    const b = off.slice(i * 5, i * 5 + 5);
    if (!onView[i] || a[0] === null || a.some((d) => d !== a[0]) || b.some((d) => d !== b[0])) return;
    out.push({ x, y, on: a[0], off: b[0] });
  });
  return out;
}

/** At most `n` of `all`, spread over the list. */
const spread = (all, n) => (all.length <= n ? all : Array.from({ length: n }, (_, i) => all[Math.floor((i * all.length) / n)]));

test('the cut-out of Zerus Large Tree: vine and leaf cards draw only where their alpha mask passes the threshold, and only there take the mouse', async ({ page }) => {
  test.setTimeout(60_000);
  const errors = await open(page);
  const id = await page.evaluate(() => window.sc2viewer.addDoodad('ZerusLargeTree', { x: 0, y: 0, rot: 0, variation: 0, sequence: -1, dataset: 'stock' }));
  await idle(page);
  await frames(page);

  // The thresholds the file holds: vines 150, leaves 200, trunk 0 (no test).
  const tests = await page.evaluate((i) => window.sc2viewer.alphaTests(i), id);
  console.log('alpha tests', JSON.stringify(tests));
  const of = (name) => tests.find((t) => t.material === name).alphaTest;
  expect(of('vinesss')).toBeCloseTo(150 / 255, 4);
  expect(of('Tree A Leaves')).toBeCloseTo(200 / 255, 4);
  expect(of('Starcraft 2 Unit Material_2')).toBe(0);

  const list = await silhouettes(page, id);
  const kept = list.filter((s) => s.on);
  const removed = list.filter((s) => s.off && !s.on);
  const added = list.filter((s) => s.on && !s.off);
  console.log('samples', list.length, 'drawn without the test', list.filter((s) => s.off).length, 'kept', kept.length, 'removed', removed.length, 'added', added.length);
  // The cut-out takes a part of the cards away, and adds nothing.
  expect(added).toEqual([]);
  expect(removed.length).toBeGreaterThanOrEqual(20);
  expect(kept.length).toBeGreaterThanOrEqual(20);

  // The mouse goes by the same picture: a cut-away pixel is no hit, a kept one is.
  const wrong = [];
  for (const s of spread(removed, 8)) {
    const hovered = await hoverAt(page, s.x, s.y);
    if (hovered !== null) wrong.push({ ...s, hovered });
  }
  for (const s of spread(kept, 8)) {
    const hovered = await hoverAt(page, s.x, s.y);
    if (hovered !== id) wrong.push({ ...s, hovered });
  }
  expect(wrong).toEqual([]);

  // Negative: with the test off, a cut-away pixel is a hit again (the hit follows the test).
  await page.evaluate((i) => window.sc2viewer.setAlphaTest(i, false), id);
  const [first] = removed;
  expect(await hoverAt(page, first.x, first.y)).toBe(id);
  await page.evaluate((i) => window.sc2viewer.setAlphaTest(i, true), id);
  expect(errors).toEqual([]);
});

// The operator's case 2026-11-23: Giant Yeti and Ursadon drew with holes in
// the body. Its alpha mask (blastmark4, blue channel) has multiply 10 and
// add 1: mask x 10 + 1 >= 1 everywhere, so nothing is cut (WhiteoutFlakes
// M3LayerValue: rgba * tint + add, before the clamp).
for (const [unit, material] of [['GiantYeti', 'beast'], ['Ursadon', null]]) {
  test(`${unit}: the body's alpha mask has its multiply and add; the body is not cut`, async ({ page }) => {
    const errors = await open(page);
    const id = await page.evaluate((u) => window.sc2viewer.addUnit(u, { x: 0, y: 0, pick: 0.5, sequence: -1, dataset: 'stock' }), unit);
    await idle(page);
    await page.evaluate((v) => window.sc2viewer.view(v), { ...VIEW, distance: 12, target: [0, 0, 1.5] });
    // The body: the batch with the most vertices whose material has a textured alpha mask and a test.
    const body = await page.evaluate(([i, name]) => {
      const item = window.SC2App.items.find((x) => x.id === i);
      const masked = item.model.batches.filter((b) => b.material.alphaTest > 0 && b.material.layers[8].active && !b.material.layers[8].constant && (!name || b.material.name === name));
      masked.sort((a, b) => b.region.elements - a.region.elements);
      const pick = masked[0];
      // Draw only it.
      window.__allBatches = item.model.batches.slice();
      item.model.batches.length = 0;
      item.model.batches.push(pick);
      return { material: pick.material.name, alphaTest: pick.material.alphaTest };
    }, [id, material]);
    await frames(page);
    const list = await silhouettes(page, id);
    const ma = await page.evaluate((i) => {
      const item = window.SC2App.items.find((x) => x.id === i);
      const m = item.model.batches[0].material;
      return { mask: Array.from(m.layers[8].lastMultiplyAdd), diffuse: Array.from(m.layers[0].lastMultiplyAdd) };
    }, id);
    const removed = list.filter((s) => s.off && !s.on);
    console.log(unit, JSON.stringify(body), 'multiplyAdd', JSON.stringify(ma), 'samples', list.length, 'drawn', list.filter((s) => s.on).length, 'removed', removed.length);
    expect(body.alphaTest).toBeGreaterThan(0);
    // The file's values (m3addon: brightMult 10, midtoneOffset 1 on the Yeti body).
    if (unit === 'GiantYeti') expect(ma.mask).toEqual([10, 1]);
    // Negative: other layers keep (1, 0).
    expect(ma.diffuse).toEqual([1, 0]);
    expect(list.filter((s) => s.on).length).toBeGreaterThan(50);
    expect(removed).toEqual([]);
    await page.evaluate((i) => {
      const item = window.SC2App.items.find((x) => x.id === i);
      item.model.batches.length = 0;
      item.model.batches.push(...window.__allBatches);
    }, id);
    expect(errors).toEqual([]);
  });
}

test('negative: a model with no alpha test draws the same with the test on or off', async ({ page }) => {
  const errors = await open(page);
  const id = await page.evaluate(() => window.sc2viewer.addUnit('Marine', { x: 0, y: 0, pick: 0.5, sequence: -1, dataset: 'stock' }));
  await idle(page);
  await page.evaluate((v) => window.sc2viewer.view(v), { ...VIEW, distance: 6, target: [0, 0, 1] });
  await frames(page);
  const tests = await page.evaluate((i) => window.sc2viewer.alphaTests(i), id);
  console.log('Marine alpha tests', JSON.stringify(tests));
  expect(tests.length).toBeGreaterThan(0);
  expect(tests.every((t) => t.alphaTest === 0)).toBe(true);
  expect(await page.evaluate((i) => window.sc2viewer.setAlphaTest(i, true), id)).toBe(0);
  const list = await silhouettes(page, id);
  expect(list.filter((s) => s.on).length).toBeGreaterThan(20);
  expect(list.filter((s) => s.on !== s.off)).toEqual([]);
  expect(errors).toEqual([]);
});

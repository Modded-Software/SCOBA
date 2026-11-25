import { test, expect } from '../fixtures.mjs';
import { frames, idle, open as openPage, view } from '../page.mjs';

// Alpha test (cut-out). A standard material with alphaTestThreshold t > 0
// draws only where its alpha-mask layers give alpha >= t / 255; the rest of
// the face is not drawn and takes no mouse hit. Rule: WhiteoutFlakes
// m3_surface_table.cpp (threshold = min(t / 255, 1)) and m3_standard.slang
// (alpha = product of the alpha masks; discard when alpha < threshold).
// The operator's case: the hanging vine and leaf cards of Zerus Large Tree
// drew as dark rectangles.
// The truth here is the mouse hit (the pick buffer, SCOBAEdit.itemAt), read
// with the model's alpha tests on and off (scobaeditor.probe('m3', 'setAlphaTest', ...)).
// What the cards look like is an operator check (SPEC-VIEWER 14).

const VIEW = { yaw: -Math.PI / 2, pitch: 0.25, distance: 24, target: [0, 0, 4] };
const SAMPLES = 16; // per side of the item's screen box

async function open(page) {
  const errors = await openPage(page, { grid: false });
  await view(page, VIEW);
  return errors;
}

/** The item's box on the page: its rest-pose vertex box, placed, through the camera. */
const screenBox = (page, id) =>
  page.evaluate((i) => {
    const item = window.scobaeditor.state().items.find((x) => x.id === i);
    const [lo, hi] = item.vertexBox;
    const s = item.engineScale;
    const p = item.location;
    const corners = [];
    for (const x of [lo[0], hi[0]]) for (const y of [lo[1], hi[1]]) for (const z of [lo[2], hi[2]]) corners.push(window.scobaeditor.screenOf([p[0] + x * s[0], p[1] + y * s[1], p[2] + z * s[2]]));
    const xs = corners.filter(Boolean).map((c) => c[0]);
    const ys = corners.filter(Boolean).map((c) => c[1]);
    return { minX: Math.min(...xs), maxX: Math.max(...xs), minY: Math.min(...ys), maxY: Math.max(...ys) };
  }, id);

/**
 * The mouse hit over a grid of the item's screen box, with its alpha tests
 * on and off. Each sample: { x, y, on, off } (true: the item is hit). A
 * sample under a panel is left out.
 */
async function hits(page, id) {
  const box = await screenBox(page, id);
  return page.evaluate(
    ([i, b, n]) => {
      const points = [];
      for (let k = 0; k < n; k++) for (let j = 0; j < n; j++) points.push([b.minX + ((j + 0.5) * (b.maxX - b.minX)) / n, b.minY + ((k + 0.5) * (b.maxY - b.minY)) / n]);
      const view = document.getElementById('view');
      const shown = points.filter(([x, y]) => document.elementFromPoint(x, y) === view);
      const at = () => shown.map(([x, y]) => window.SCOBAEdit.itemAt(x, y)?.id === i);
      const on = at();
      window.scobaeditor.probe('m3', 'setAlphaTest', i, false);
      const off = at();
      window.scobaeditor.probe('m3', 'setAlphaTest', i, true);
      return shown.map(([x, y], k) => ({ x, y, on: on[k], off: off[k] }));
    },
    [id, box, SAMPLES],
  );
}

async function hoverAt(page, x, y) {
  await page.mouse.move(x, y);
  await frames(page);
  return page.evaluate(() => window.scobaeditor.state().pick.hovered);
}

test('the cut-out of Zerus Large Tree: vine and leaf cards take the mouse only where their alpha mask passes the threshold', async ({ page }) => {
  const errors = await open(page);
  const id = await page.evaluate(() => window.scobaeditor.addDoodad('ZerusLargeTree', { x: 0, y: 0, rot: 0, variation: 0, sequence: -1, dataset: 'stock' }));
  await idle(page);
  await frames(page);

  // The thresholds the file holds: vines 150, leaves 200, trunk 0 (no test).
  const tests = await page.evaluate((i) => window.scobaeditor.probe('m3', 'alphaTests', i), id);
  console.log('alpha tests', JSON.stringify(tests));
  const of = (name) => tests.find((t) => t.material === name).alphaTest;
  expect(of('vinesss')).toBeCloseTo(150 / 255, 4);
  expect(of('Tree A Leaves')).toBeCloseTo(200 / 255, 4);
  expect(of('Starcraft 2 Unit Material_2')).toBe(0);

  const list = await hits(page, id);
  const kept = list.filter((s) => s.on);
  const removed = list.filter((s) => s.off && !s.on);
  const added = list.filter((s) => s.on && !s.off);
  console.log('samples', list.length, 'hit without the test', list.filter((s) => s.off).length, 'kept', kept.length, 'removed', removed.length, 'added', added.length);
  // The cut-out takes a part of the cards away, and adds nothing.
  expect(added).toEqual([]);
  expect(removed.length).toBeGreaterThanOrEqual(5);
  expect(kept.length).toBeGreaterThanOrEqual(5);

  // The real mouse agrees: a cut-away point is no hit, a kept one is.
  expect(await hoverAt(page, removed[0].x, removed[0].y)).toBe(null);
  expect(await hoverAt(page, kept[0].x, kept[0].y)).toBe(id);
  // Negative: with the test off, a cut-away point is a hit again (the hit follows the test).
  await page.evaluate((i) => window.scobaeditor.probe('m3', 'setAlphaTest', i, false), id);
  await page.mouse.move(5, 5);
  expect(await hoverAt(page, removed[0].x, removed[0].y)).toBe(id);
  await page.evaluate((i) => window.scobaeditor.probe('m3', 'setAlphaTest', i, true), id);
  expect(errors).toEqual([]);
});

// The operator's case 2026-11-23: Giant Yeti and Ursadon drew with holes in
// the body. Its alpha mask (blastmark4, blue channel) has multiply 10 and
// add 1: mask x 10 + 1 >= 1 everywhere, so nothing is cut (WhiteoutFlakes
// M3LayerValue: rgba * tint + add, before the clamp).
for (const [unit, material] of [['GiantYeti', 'beast'], ['Ursadon', null]]) {
  test(`${unit}: the body's alpha mask has its multiply and add; the body is not cut`, async ({ page }) => {
    const errors = await open(page);
    const id = await page.evaluate((u) => window.scobaeditor.addUnit(u, { x: 0, y: 0, pick: 0.5, sequence: -1, dataset: 'stock' }), unit);
    await idle(page);
    await view(page, { ...VIEW, distance: 12, target: [0, 0, 1.5] });
    // The body: the batch with the most vertices whose material has a textured alpha mask and a test. Only it is drawn.
    const body = await page.evaluate(([i, name]) => {
      const item = window.SCOBAEdit.items.find((x) => x.id === i);
      const masked = item.model.m3.batches.filter((b) => b.material.alphaTest > 0 && b.material.layers[8].active && !b.material.layers[8].constant && (!name || b.material.name === name));
      masked.sort((a, b) => b.region.elements - a.region.elements);
      const pick = masked[0];
      item.model.m3.batches.length = 0;
      item.model.m3.batches.push(pick);
      return { material: pick.material.name, alphaTest: pick.material.alphaTest };
    }, [id, material]);
    await frames(page);
    const list = await hits(page, id);
    const ma = await page.evaluate((i) => {
      const item = window.SCOBAEdit.items.find((x) => x.id === i);
      const m = item.model.m3.batches[0].material;
      return { mask: Array.from(m.layers[8].lastMultiplyAdd), diffuse: Array.from(m.layers[0].lastMultiplyAdd) };
    }, id);
    const removed = list.filter((s) => s.off && !s.on);
    console.log(unit, JSON.stringify(body), 'multiplyAdd', JSON.stringify(ma), 'samples', list.length, 'hit', list.filter((s) => s.on).length, 'removed', removed.length);
    expect(body.alphaTest).toBeGreaterThan(0);
    // The file's values (m3addon: brightMult 10, midtoneOffset 1 on the Yeti body).
    if (unit === 'GiantYeti') expect(ma.mask).toEqual([10, 1]);
    // Negative: other layers keep (1, 0).
    expect(ma.diffuse).toEqual([1, 0]);
    expect(list.filter((s) => s.on).length).toBeGreaterThan(20);
    expect(removed).toEqual([]);
    expect(errors).toEqual([]);
  });
}

test('negative: a model with no alpha test takes the mouse the same with the test on or off', async ({ page }) => {
  const errors = await open(page);
  const id = await page.evaluate(() => window.scobaeditor.addUnit('Marine', { x: 0, y: 0, pick: 0.5, sequence: -1, dataset: 'stock' }));
  await idle(page);
  await view(page, { ...VIEW, distance: 6, target: [0, 0, 1] });
  await frames(page);
  const tests = await page.evaluate((i) => window.scobaeditor.probe('m3', 'alphaTests', i), id);
  console.log('Marine alpha tests', JSON.stringify(tests));
  expect(tests.length).toBeGreaterThan(0);
  expect(tests.every((t) => t.alphaTest === 0)).toBe(true);
  expect(await page.evaluate((i) => window.scobaeditor.probe('m3', 'setAlphaTest', i, true), id)).toBe(0);
  const list = await hits(page, id);
  expect(list.filter((s) => s.on).length).toBeGreaterThan(20);
  expect(list.filter((s) => s.on !== s.off)).toEqual([]);
  expect(errors).toEqual([]);
});

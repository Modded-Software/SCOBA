import { test, expect } from '../fixtures.mjs';
import { add as addGhost } from '../ghost.mjs';
import { frames, idle, open as openPage, state as viewState, view } from '../page.mjs';

// The triangle under the mouse in edges mode (R-VIEW-153, features/edges,
// core/render/triangleglow.ts):
// - the triangle of a unit showing edges under the mouse is the hover; it
//   glows and gets the glass shimmer pass;
// - the one the mouse left keeps a glow that fades out over 0.5 s;
// - no hover on a unit without edges, beyond the range, or once the edges
//   are switched off.
// Engine state: the picked triangle, checked by drawing it alone at the
// mouse pixel; the triangles and shimmer passes drawn in the last frame;
// the strengths over time. How the glow and the glass look is an operator
// check (SPEC-VIEWER 14).

const VIEW = { yaw: -Math.PI / 2, pitch: 0.5, distance: 6, target: [0, 0, 0.5] };
const EMPTY = [1000, 80];

const open = (page) => openPage(page, { grid: false });
const edges = async (page) => {
  await frames(page);
  return (await viewState(page)).edges;
};
const select = (page, ids) => page.evaluate((list) => window.SCOBAEdit.setSelection(list), ids);
const covers = (page, id, triangle, [x, y]) => page.evaluate(([i, t, px, py]) => window.scobaeditor.edgesCovers(i, t, px, py), [id, triangle, x, y]);
const pixelOf = (page, id) => page.evaluate((i) => window.scobaeditor.itemPixel(i), id);

/** A Marine standing still, the camera on it. */
async function place(page, x = 0) {
  const id = await page.evaluate((at) => window.scobaeditor.addUnit('Marine', { x: at, y: 0, pick: 0.5, sequence: -1 }), x);
  await idle(page);
  await view(page, VIEW);
  await page.mouse.move(...EMPTY);
  return id;
}

/** Switch the edges of `ids` on (they were off). */
async function edgesOn(page, ids) {
  await select(page, ids);
  await page.keyboard.press('Control+/');
  await expect.poll(async () => (await edges(page)).on.sort()).toEqual([...ids].sort());
}

/** Hover a pixel; the edges state once a frame has drawn with the mouse there. */
async function hoverAt(page, at) {
  await page.mouse.move(at[0], at[1]);
  return edges(page);
}

/** A pixel near `from` on unit `id` whose hovered triangle is not `triangle`. */
async function otherTriangle(page, id, from, triangle) {
  for (const [dx, dy] of [[0, -14], [0, 14], [-8, 0], [8, 0], [0, -26], [0, 26], [-5, -8], [5, 8]]) {
    const at = [from[0] + dx, from[1] + dy];
    const now = await hoverAt(page, at);
    if (now.hover && now.hover.item === id && now.hover.triangle !== triangle) return { at, now };
  }
  throw new Error(`no other triangle of item ${id} near ${from}`);
}

test('the triangle under the mouse glows and shimmers; it is the one drawn at the mouse pixel', async ({ page }) => {
  const errors = await open(page);
  const marine = await place(page);
  await edgesOn(page, [marine]);
  const at = await pixelOf(page, marine);
  const now = await hoverAt(page, at);
  console.log('hover', JSON.stringify({ at, hover: now.hover, glow: now.glow, shimmer: now.shimmer, stencil: now.stencil }));
  expect(now.stencil).toBe(true);
  expect(now.hover).toMatchObject({ item: marine });
  expect(now.glow).toBe(1);
  expect(now.shimmer).toBe(1);
  expect(now.fading).toEqual([]);
  // The engine draws that triangle, alone, at the mouse pixel; negative: not at an empty one.
  expect(await covers(page, marine, now.hover.triangle, at)).toBe(true);
  expect(await covers(page, marine, now.hover.triangle, EMPTY)).toBe(false);

  // Another triangle: it is the hover now, the first one fades; one shimmer pass, two glows.
  const next = await otherTriangle(page, marine, at, now.hover.triangle);
  expect(await covers(page, marine, next.now.hover.triangle, next.at)).toBe(true);
  expect(next.now.shimmer).toBe(1);
  expect(next.now.fading.map((f) => f.triangle)).toContain(now.hover.triangle);
  expect(next.now.glow).toBe(1 + next.now.fading.length);
  expect(errors).toEqual([]);
});

test('the triangle the mouse left fades out over 0.5 s; while it fades it does not shimmer', async ({ page }) => {
  const errors = await open(page);
  const marine = await place(page);
  await edgesOn(page, [marine]);
  const before = await hoverAt(page, await pixelOf(page, marine));
  const hovered = before.hover;
  expect(hovered).not.toBeNull();
  expect(before.fadeMs).toBe(500);

  await page.mouse.move(...EMPTY);
  // In the page: each frame's strength of that triangle, until it is gone.
  const trace = await page.evaluate(
    (spot) =>
      new Promise((resolve) => {
        const start = performance.now();
        const rows = [];
        const step = () => {
          const s = window.scobaeditor.state().edges;
          const f = s.fading.find((one) => one.item === spot.item && one.triangle === spot.triangle);
          rows.push({ t: performance.now() - start, strength: f ? f.strength : null, hover: s.hover, glow: s.glow, shimmer: s.shimmer });
          if ((!f && rows.length > 1) || performance.now() - start > 2000) resolve(rows);
          else requestAnimationFrame(step);
        };
        requestAnimationFrame(step);
      }),
    hovered,
  );
  const live = trace.filter((r) => r.strength !== null);
  const gone = trace.find((r) => r.strength === null && r.t > 0);
  console.log('fade', JSON.stringify({ rows: trace.length, first: live[0], last: live[live.length - 1], gone }));
  expect(live.length).toBeGreaterThan(3);
  // Gone between 0.35 s and 0.8 s after the leave; still there at 0.3 s.
  expect(gone.t).toBeGreaterThan(350);
  expect(gone.t).toBeLessThan(800);
  expect(live.some((r) => r.t > 300)).toBe(true);
  // Weaker frame by frame, from the full strength down.
  for (let i = 1; i < live.length; i++) expect(live[i].strength).toBeLessThanOrEqual(live[i - 1].strength);
  expect(live[0].strength).toBeLessThanOrEqual(before.full);
  // Part way: some frame between a fifth and four fifths of the full strength.
  expect(live.some((r) => r.strength > before.full * 0.2 && r.strength < before.full * 0.8)).toBe(true);
  // Negative: no hover, so no shimmer, while it fades; it is drawn (one glow).
  for (const r of live) expect(r).toMatchObject({ hover: null, shimmer: 0 });
  expect(live.filter((r) => r.glow === 1).length).toBeGreaterThan(0);
  expect(await edges(page)).toMatchObject({ hover: null, fading: [], glow: 0, shimmer: 0 });
  expect(errors).toEqual([]);
});

test('negative: no hover on a unit without edges, beyond the range, or once the edges are off', async ({ page }) => {
  const errors = await open(page);
  const left = await place(page, -1);
  const right = await place(page, 1);
  // Edges off everywhere: the mouse is on the unit, no triangle.
  const onRight = await pixelOf(page, right);
  let now = await hoverAt(page, onRight);
  expect((await viewState(page)).pick.hovered).toBe(right);
  expect(now).toMatchObject({ hover: null, glow: 0, shimmer: 0 });

  // Edges on the left one only: the right one under the mouse has none.
  await edgesOn(page, [left]);
  now = await hoverAt(page, onRight);
  expect((await viewState(page)).pick.hovered).toBe(right);
  expect(now).toMatchObject({ hover: null, glow: 0, shimmer: 0 });
  const onLeft = await pixelOf(page, left);
  now = await hoverAt(page, onLeft);
  expect(now.hover).toMatchObject({ item: left });

  // Edges off while hovered: no hover and nothing fading at once.
  await page.keyboard.press('Control+/');
  now = await edges(page);
  expect(now).toMatchObject({ on: [], hover: null, fading: [], glow: 0, shimmer: 0 });

  expect(errors).toEqual([]);
});

test('negative: beyond the range, the mouse on the unit has no hover; inside it, it does', async ({ page }) => {
  const errors = await open(page);
  // A large unit, so it still has pixels beyond the range.
  const ultra = await page.evaluate(() => window.scobaeditor.addUnit('Ultralisk', { x: 0, y: 0, pick: 0.5, sequence: -1 }));
  await idle(page);
  await view(page, { ...VIEW, target: [0, 0, 1.5] });
  await edgesOn(page, [ultra]);
  const range = (await edges(page)).range;
  for (const [distance, inside] of [[range * 1.08, false], [range * 0.92, true]]) {
    await page.evaluate((d) => window.scobaeditor.view({ distance: d }), distance);
    await page.mouse.move(...EMPTY);
    await frames(page);
    const at = await pixelOf(page, ultra);
    expect(at, `a pixel of the unit at ${distance}`).not.toBeNull();
    const now = await hoverAt(page, at);
    console.log('range', JSON.stringify({ distance, hovered: (await viewState(page)).pick.hovered, hover: now.hover, far: now.far }));
    expect((await viewState(page)).pick.hovered).toBe(ultra);
    if (inside) {
      expect(now.far).toEqual([]);
      expect(now.hover).toMatchObject({ item: ultra });
    } else {
      expect(now.far).toEqual([ultra]);
      expect(now).toMatchObject({ hover: null, glow: 0, shimmer: 0 });
    }
  }
  expect(errors).toEqual([]);
});

test('Ghost: a nod model has the hover, and the triangle is the one at the mouse pixel', async ({ page }) => {
  const errors = await open(page);
  const crate = await addGhost(page, '3D/Models/crate.nod');
  await idle(page);
  await page.evaluate(() => window.scobaeditor.view('front'));
  await page.mouse.move(...EMPTY);
  await edgesOn(page, [crate]);
  const at = await pixelOf(page, crate);
  const now = await hoverAt(page, at);
  console.log('crate hover', JSON.stringify(now.hover));
  expect(now.hover).toMatchObject({ item: crate });
  expect(now).toMatchObject({ glow: 1, shimmer: 1 });
  expect(await covers(page, crate, now.hover.triangle, at)).toBe(true);
  expect(errors).toEqual([]);
});

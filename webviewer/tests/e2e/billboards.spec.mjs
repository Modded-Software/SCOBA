import { test, expect } from '../fixtures.mjs';

// M3 billboards (BBSC): bones that turn to the camera each frame, such as
// light cones and lens flares. Rules: WhiteoutFlakes io/m3/m3_billboard.cpp
// (CBBSolver::ApplyBillboard); layout: m3addon structures.xml BBSC.
// Truth: the bone world matrices the renderer skins with, read for two
// camera views at one animation time (scobaeditor.probe('m3', 'billboards', ...)).

async function open(page) {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push(m.text());
  });
  await page.goto('/');
  await expect.poll(() => errors.join(' | ') || page.evaluate(() => Boolean(window.scobaeditor && window.scobaeditor.ready)), { timeout: 10_000 }).toBe(true);
  await page.evaluate(() => window.scobaeditor.setGrid(false));
  return errors;
}

const idle = (page) => page.waitForFunction(() => window.scobaeditor.idle(), null, { timeout: 20_000 });
const unit = async (page, id) => {
  const item = await page.evaluate((u) => window.scobaeditor.addUnit(u, { x: 0, y: 0, rot: 0, pick: 0.5, dataset: 'stock' }), id);
  await idle(page);
  return item;
};

/** Two views at one animation time: the bones are posed again with no time step after each camera move. */
const twoViews = (page, id) => page.evaluate((i) => {
  const v = window.scobaeditor;
  const item = window.SCOBAEdit.items.find((x) => x.id === i);
  const read = (yaw) => {
    v.view({ yaw, pitch: 0.5, distance: 60, target: [0, 0, 1] });
    item.instance.m3.skeleton.update(0);
    return v.probe('m3', 'billboards', i);
  };
  return [read(0), read(Math.PI / 2)];
}, id);

const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
/** A bone's axes in the camera's frame (right, up, forward). */
function inCamera(view, axes) {
  const right = cross(view.forward, view.up);
  return axes.map((a) => [dot(a, right), dot(a, view.up), dot(a, view.forward)]);
}
const largest = (a, b) => Math.max(...a.flatMap((row, r) => row.map((x, c) => Math.abs(x - b[r][c]))));

for (const name of ['Archon', 'Sentry']) test(`${name}: BBSC records are read; free billboards keep their pose to the camera when it orbits, and turn in the world`, async ({ page }) => {
  const errors = await open(page);
  const id = await unit(page, name);
  const [a, b] = await twoViews(page, id);
  console.log(name, 'BBSC', JSON.stringify(a.records.map((r) => [r.bone, r.name, r.type, r.lookAt])), 'billboarded', b.billboarded);
  expect(a.sequence).not.toBe(-1);
  // The camera frame the solver uses: forward points from the eye at the target (0, 0, 1).
  const toTarget = [-a.eye[0], -a.eye[1], 1 - a.eye[2]];
  expect(dot(a.forward, toTarget) / Math.hypot(...toTarget)).toBeGreaterThan(0.999);
  expect(a.records.length).toBeGreaterThan(0);
  expect(b.billboarded).toBeGreaterThan(0);
  const free = a.records.map((r, k) => [r, b.records[k]]).filter(([r]) => r.type === 6);
  expect(free.length).toBeGreaterThan(0);
  const rows = free.map(([r, s]) => ({ bone: r.bone, lookAt: r.lookAt, camera: +largest(inCamera(a, r.axes), inCamera(b, s.axes)).toFixed(3), world: +largest(r.axes, s.axes).toFixed(3) }));
  console.log('free billboards: largest axis change, in the camera frame and in the world', JSON.stringify(rows));
  // Seen from the camera they stay put (look-at bones within the parallax of a 60 unit orbit).
  expect(rows.filter((x) => x.camera > (x.lookAt ? 0.05 : 0.01))).toEqual([]);
  // Negative: in the world they turned with the camera (a quarter turn of yaw).
  expect(rows.filter((x) => x.world < 0.5)).toEqual([]);
  expect(errors).toEqual([]);
});

test('negative: a model without BBSC records turns no bone, and its bones keep their world pose when the camera orbits', async ({ page }) => {
  const errors = await open(page);
  const id = await unit(page, 'Marine');
  const [a, b] = await twoViews(page, id);
  expect(a.records).toEqual([]);
  expect(b.billboarded).toBe(0);
  const axes = await page.evaluate((i) => {
    const item = window.SCOBAEdit.items.find((x) => x.id === i);
    const read = (yaw) => {
      window.scobaeditor.view({ yaw, pitch: 0.5, distance: 60, target: [0, 0, 1] });
      item.instance.m3.skeleton.update(0);
      return Array.from(item.instance.m3.skeleton.nodes[1].worldMatrix);
    };
    return [read(0), read(Math.PI / 2)];
  }, id);
  expect(Math.max(...axes[0].map((x, k) => Math.abs(x - axes[1][k])))).toBeLessThan(1e-5);
  expect(errors).toEqual([]);
});

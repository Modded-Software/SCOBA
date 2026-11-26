import { test, expect } from '../fixtures.mjs';
import { source } from './source.mjs';

// Wheel zoom (src/page/core/zoom.ts), without a browser, on a frame clock the
// test steps. One notch moves the camera a share of its distance: 15% with
// the eye 10 or more units up, less as the eye comes down (never under 12% of
// that), and a quarter of it with ctrl. The zoom starts from the ground point
// on the view line, so it depends on the eye height only, and the eye stays
// 0.3 or more over the ground. That the canvas wheel reaches it, and that
// setting the view stops a glide: tests/e2e/zoom.spec.mjs.

const ZOOM_TIME = 35; // ms, zoom.ts
const FRAME = 16;

/** The rule: the share of the distance one notch moves, the target on the ground. */
function share(distance, pitch, ctrl = false) {
  const s = 0.15 * Math.max(0.12, Math.min(1, (distance * Math.sin(pitch)) / 10));
  return ctrl ? s * 0.25 : s;
}

const eyeOf = (c) => [
  c.target[0] + c.distance * Math.cos(c.pitch) * Math.cos(c.yaw),
  c.target[1] + c.distance * Math.cos(c.pitch) * Math.sin(c.yaw),
  c.target[2] + c.distance * Math.sin(c.pitch),
];

/** A camera, its zoom, and a frame clock: `frame(dt)` runs the waiting frame `dt` ms on. */
async function rig(camera) {
  const { createZoom } = await source('src/page/core/zoom.ts');
  let now = 1000;
  let waiting = null;
  Object.defineProperty(globalThis, 'performance', { value: { now: () => now }, configurable: true, writable: true });
  globalThis.requestAnimationFrame = (step) => {
    waiting = step;
    return 1;
  };
  globalThis.cancelAnimationFrame = () => {
    waiting = null;
  };
  const cam = { yaw: -Math.PI / 2, ...camera };
  // Sensitivity 1: the rates as written (R-VIEW-150 scales them in the page).
  const zoom = createZoom(cam, { eye: () => eyeOf(cam), applyCamera() {}, sensitivity: () => 1 });
  const frame = (dt = FRAME) => {
    now += dt;
    const step = waiting;
    waiting = null;
    if (step) step(now);
    return cam.distance;
  };
  /** Wheel by deltaY, then run frames until the glide ends; the distance. */
  const wheel = (deltaY, { ctrl = false, deltaMode = 0 } = {}) => {
    let prevented = false;
    zoom.wheel({ deltaY, deltaMode, ctrlKey: ctrl, preventDefault: () => (prevented = true) });
    expect(prevented, 'the page itself does not zoom').toBe(true);
  };
  const settle = () => {
    for (let i = 0; i < 1000 && zoom.goal() !== null; i++) frame();
    expect(zoom.goal()).toBeNull();
    return cam.distance;
  };
  return { cam, zoom, frame, wheel, settle };
}

/** From distance and pitch (target on the ground), one wheel turn; the distance after. */
async function wheelFrom(distance, pitch, deltaY, options) {
  const r = await rig({ distance, pitch, target: [0, 0, 0] });
  r.wheel(deltaY, options);
  return r.settle();
}

test('the glide follows the frame clock: each frame takes exp(-dt / 35 ms) of the way left, and ends on the goal', async () => {
  const r = await rig({ distance: 30, pitch: 0.6, target: [0, 0, 0] });
  r.wheel(100);
  const goal = r.zoom.goal();
  expect(goal).toBeCloseTo(30 * (1 + share(30, 0.6)), 6);
  // Frames of uneven length: a slow frame is a longer step, not a slower glide.
  let last = 30;
  for (const dt of [16, 16, 40, 8, 16]) {
    const before = Math.log(goal) - Math.log(last);
    const now = r.frame(dt);
    const after = Math.log(goal) - Math.log(now);
    expect(Math.log(after / before), `dt ${dt}`).toBeCloseTo(-dt / ZOOM_TIME, 6);
    // Negative: no frame takes the whole step.
    expect(now).toBeLessThan(goal);
    last = now;
  }
  expect(r.settle()).toBe(goal);
});

test('one notch moves less the closer the eye is to the ground; far out it covers more ground', async () => {
  const high = (await wheelFrom(20, 1.2, 100)) / 20 - 1;
  const mid = (await wheelFrom(20, 0.3, 100)) / 20 - 1;
  const low = (await wheelFrom(20, 0.03, 100)) / 20 - 1;
  expect(high).toBeCloseTo(share(20, 1.2), 6);
  expect(mid).toBeCloseTo(share(20, 0.3), 6);
  expect(low).toBeCloseTo(share(20, 0.03), 6);
  expect(high).toBeCloseTo(0.15, 6);
  expect(mid).toBeLessThan(high * 0.7);
  expect(low).toBeLessThan(high * 0.15);
  const far = (await wheelFrom(60, 0.5, 100)) - 60;
  const near = (await wheelFrom(4, 0.5, 100)) - 4;
  expect(far / near).toBeGreaterThan(30);
});

test('ctrl makes a notch a quarter, near the ground too; lines and pages count as pixels', async () => {
  const plain = (await wheelFrom(20, 1.2, 100)) / 20 - 1;
  const slow = (await wheelFrom(20, 1.2, 100, { ctrl: true })) / 20 - 1;
  expect(slow).toBeCloseTo(share(20, 1.2, true), 6);
  expect(slow / plain).toBeCloseTo(0.25, 6);
  expect((await wheelFrom(20, 0.03, 100, { ctrl: true })) / 20 - 1).toBeCloseTo(share(20, 0.03, true), 6);
  // deltaMode 1: lines of 33 px. 3 lines are 99 px, about one notch.
  const lines = (await wheelFrom(20, 1.2, 3, { deltaMode: 1 })) / 20;
  expect(Math.log(lines)).toBeCloseTo(Math.log(1 + share(20, 1.2)) * 0.99, 6);
});

test('wheel up comes closer by the same share; notches add up on the goal, not on the glide', async () => {
  expect(await wheelFrom(20, 1.2, -100)).toBeCloseTo(20 / (1 + share(20, 1.2)), 6);
  const r = await rig({ distance: 20, pitch: 1.2, target: [0, 0, 0] });
  r.wheel(100);
  r.frame();
  r.wheel(100);
  const first = 20 * (1 + share(20, 1.2));
  expect(r.settle()).toBeCloseTo(first * (1 + share(first, 1.2)), 6);
});

test('zoom is absolute: the same eye gives the same step, wherever pan or look left the target', async () => {
  const pitch = 0.6;
  const height = 12;
  const expected = height * (1 + share(height / Math.sin(pitch), pitch));
  const after = [];
  // One eye 12 over the ground; three targets on its view line: on the ground, 5 above, 5 below.
  for (const tz of [0, 5, -5]) {
    const r = await rig({ yaw: 0, pitch, distance: (height - tz) / Math.sin(pitch), target: [-(height - tz) / Math.tan(pitch) + height / Math.tan(pitch), 0, tz] });
    expect(eyeOf(r.cam)[2]).toBeCloseTo(height, 9);
    r.wheel(100);
    r.settle();
    const eye = eyeOf(r.cam);
    expect(eye[2], `tz ${tz}`).toBeCloseTo(expected, 6);
    expect(r.cam.target[2], 'the target was moved to the ground').toBeCloseTo(0, 9);
    after.push(eye[0]);
  }
  for (const x of after) expect(x).toBeCloseTo(after[0], 6);
});

test('negative: zooming in never takes the eye under the ground, also with the target below it', async () => {
  for (const tz of [0, -5]) {
    const r = await rig({ yaw: 0, pitch: 0.8, distance: 20, target: [0, 0, tz] });
    for (let i = 0; i < 40; i++) r.wheel(-1000);
    r.settle();
    // Two floors: eye height 0.3, and distance 0.5 to the ground target.
    const eye = eyeOf(r.cam);
    expect(eye[2]).toBeGreaterThanOrEqual(0.3 - 1e-9);
    expect(eye[2]).toBeCloseTo(Math.max(0.3, 0.5 * Math.sin(0.8)), 6);
  }
});

test('negative: stop ends a glide where it is; no later frame moves the camera', async () => {
  const r = await rig({ distance: 10, pitch: 0.6, target: [0, 0, 0] });
  r.wheel(400);
  r.frame();
  r.zoom.stop();
  expect(r.zoom.goal()).toBeNull();
  const at = r.cam.distance;
  r.frame();
  r.frame();
  expect(r.cam.distance).toBe(at);
});

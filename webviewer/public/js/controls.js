// Mouse controls:
// - left drag: grab the ground and pull it ("left click scrolls the map");
//   ctrl + left with a unit selected turns that unit instead (pick.js);
//   a left or right click without a drag is handled by pick.js;
// - middle drag: orbit around the ground point under the mouse;
// - ctrl + middle drag: mouse-look, turning around the camera itself;
// - right drag: pan in the view plane;
// - wheel: zoom, smooth; smaller steps near the ground, smaller with ctrl.
// Tracks the ground point under the mouse for the grid glow.
'use strict';

(() => {
  const app = window.SC2App;
  const { canvas, camera } = app;

  const ROTATE_RATE = 0.004; // radians per pixel of middle drag
  const PAN_RATE = 0.0006; // camera distances per pixel of right drag
  const PITCH_LIMIT = Math.PI / 2 - 0.01;
  const BUTTON = { left: 0, middle: 1, right: 2 };

  canvas.addEventListener('mousemove', (e) => {
    app.pointer = app.eventGround(e);
  });
  canvas.addEventListener('mouseleave', () => {
    app.pointer = null;
  });

  // ---- vector helpers ----

  const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
  const add = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
  const scale = (a, k) => [a[0] * k, a[1] * k, a[2] * k];
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];

  /** Rotate v by `angle` around the unit axis (Rodrigues). */
  function rotate(v, axis, angle) {
    const c = Math.cos(angle);
    const s = Math.sin(angle);
    return add(add(scale(v, c), scale(cross(axis, v), s)), scale(axis, dot(axis, v) * (1 - c)));
  }

  /** From eye to camera unit direction (eye = target + distance * dir). */
  const direction = (yaw, pitch) => [Math.cos(pitch) * Math.cos(yaw), Math.cos(pitch) * Math.sin(yaw), Math.sin(pitch)];

  /** Set yaw, pitch, distance and target from an eye and a target point. */
  function placeCamera(eye, target) {
    const d = sub(eye, target);
    const length = Math.hypot(d[0], d[1], d[2]);
    camera.distance = length;
    camera.pitch = Math.asin(Math.max(-1, Math.min(1, d[2] / length)));
    camera.yaw = Math.atan2(d[1], d[0]);
    camera.target = target;
  }

  /** The pitch change that keeps the pitch inside the poles. */
  const clampPitch = (dpitch) => Math.max(-PITCH_LIMIT, Math.min(PITCH_LIMIT, camera.pitch + dpitch)) - camera.pitch;

  /**
   * Orbit: move the whole camera rigidly around `pivot`, by dyaw around the
   * vertical and dpitch around the camera's right axis. A rigid move around
   * a point keeps that point on the same pixel.
   */
  function orbit(pivot, dyaw, dpitch) {
    dpitch = clampPitch(dpitch);
    let eye = sub(app.eye(), pivot);
    let target = sub(camera.target, pivot);
    eye = rotate(eye, [0, 0, 1], dyaw);
    target = rotate(target, [0, 0, 1], dyaw);
    const yaw = camera.yaw + dyaw;
    const right = [-Math.sin(yaw), Math.cos(yaw), 0];
    // Around the right axis a positive angle lowers the eye: negate it.
    eye = rotate(eye, right, -dpitch);
    target = rotate(target, right, -dpitch);
    placeCamera(add(eye, pivot), add(target, pivot));
  }

  /** Mouse-look: the eye stays, the view turns. */
  function look(dyaw, dpitch) {
    const eye = app.eye();
    camera.yaw += dyaw;
    camera.pitch += clampPitch(dpitch);
    camera.target = sub(eye, scale(direction(camera.yaw, camera.pitch), camera.distance));
  }

  /** Grab: move the camera along the ground so `anchor` is under the mouse. */
  function grab(anchor, e) {
    const now = app.eventGround(e);
    // Above the horizon there is no ground to hold: wait for it.
    if (!now) return;
    camera.target = [camera.target[0] + anchor[0] - now[0], camera.target[1] + anchor[1] - now[1], camera.target[2]];
  }

  function pan(dx, dy) {
    const k = camera.distance * PAN_RATE;
    const { yaw, pitch } = camera;
    const right = [-Math.sin(yaw), Math.cos(yaw), 0];
    const up = [-Math.sin(pitch) * Math.cos(yaw), -Math.sin(pitch) * Math.sin(yaw), Math.cos(pitch)];
    for (let i = 0; i < 3; i++) camera.target[i] += (-dx * right[i] + dy * up[i]) * k;
  }

  // ---- drags ----

  /** The drag in progress: { mode, x, y, anchor, pivot }, or null. */
  let drag = null;
  canvas.addEventListener('contextmenu', (e) => e.preventDefault());
  // Middle click must not paste or start autoscroll.
  canvas.addEventListener('auxclick', (e) => e.preventDefault());
  canvas.addEventListener('mousedown', (e) => {
    e.preventDefault();
    const ground = app.eventGround(e);
    const at = { x: e.clientX, y: e.clientY };
    // Ctrl + left with a unit selected turns that unit (pick.js).
    if (e.button === BUTTON.left && e.ctrlKey && app.hasSelection()) {
      drag = { mode: 'face', ...at };
      app.faceSelected(e);
    } else if (e.button === BUTTON.left) drag = { mode: 'grab', ...at, anchor: ground };
    else if (e.button === BUTTON.middle && e.ctrlKey) drag = { mode: 'look', ...at };
    // Off the ground (sky under the mouse) the orbit turns around the target.
    else if (e.button === BUTTON.middle) drag = { mode: 'orbit', ...at, pivot: ground ? [ground[0], ground[1], 0] : [...camera.target] };
    else if (e.button === BUTTON.right) drag = { mode: 'pan', ...at };
    if (drag) stopZoom();
  });
  window.addEventListener('mouseup', () => {
    drag = null;
  });
  window.addEventListener('mousemove', (e) => {
    if (!drag) return;
    const dx = e.clientX - drag.x;
    const dy = e.clientY - drag.y;
    drag.x = e.clientX;
    drag.y = e.clientY;
    if (drag.mode === 'face') {
      app.faceSelected(e);
      return;
    }
    if (drag.mode === 'grab') {
      // Pressed on the sky: the first ground point reached becomes the anchor.
      if (!drag.anchor) drag.anchor = app.eventGround(e);
      else grab(drag.anchor, e);
    } else if (drag.mode === 'orbit') orbit(drag.pivot, -dx * ROTATE_RATE, dy * ROTATE_RATE);
    else if (drag.mode === 'look') look(-dx * ROTATE_RATE, dy * ROTATE_RATE);
    else pan(dx, dy);
    app.applyCamera();
  });

  // ---- wheel zoom ----

  // One wheel notch (deltaY 100) moves the camera a share of its distance:
  // 15% with the eye high up, less as it comes down to the ground (down to
  // 1.8% at 1.2 units and below). Ctrl makes every step a quarter.
  const NOTCH_SHARE = 0.15;
  const HIGH = 10; // eye height from which a notch is the full share
  const LOW_SHARE = 0.12; // the least part of the full share, near the ground
  const CTRL_SHARE = 0.25;
  const ZOOM_TIME = 35; // ms: time constant of the glide to the zoom goal
  const MIN_DISTANCE = 0.5;
  const MAX_DISTANCE = 2000;
  // deltaMode: 0 pixels, 1 lines, 2 pages. Lines and pages in pixels.
  const DELTA_UNIT = [1, 33, 400];

  /** The share of the distance one notch moves, for a camera at `distance`. */
  function notchShare(distance, ctrl) {
    const height = camera.target[2] + distance * Math.sin(camera.pitch);
    const share = NOTCH_SHARE * Math.max(LOW_SHARE, Math.min(1, height / HIGH));
    return ctrl ? share * CTRL_SHARE : share;
  }

  /** The distance the camera glides to, or null when it is not zooming. */
  let zoomGoal = null;
  let zoomTime = 0;
  let zoomFrame = 0;

  function stopZoom() {
    cancelAnimationFrame(zoomFrame);
    zoomGoal = null;
  }

  function zoomStep(now) {
    const dt = Math.max(0, now - zoomTime);
    zoomTime = now;
    // Glide in log space, so each frame moves the same share of the way at
    // any distance.
    const k = 1 - Math.exp(-dt / ZOOM_TIME);
    const from = Math.log(camera.distance);
    const to = Math.log(zoomGoal);
    if (Math.abs(to - from) < 1e-4) {
      camera.distance = zoomGoal;
      zoomGoal = null;
    } else {
      camera.distance = Math.exp(from + (to - from) * k);
      zoomFrame = requestAnimationFrame(zoomStep);
    }
    app.applyCamera();
  }

  canvas.addEventListener(
    'wheel',
    (e) => {
      // Also keeps ctrl + wheel from zooming the page.
      e.preventDefault();
      const notches = (e.deltaY * (DELTA_UNIT[e.deltaMode] ?? 1)) / 100;
      const start = zoomGoal ?? camera.distance;
      const gliding = zoomGoal !== null;
      const step = Math.log(1 + notchShare(start, e.ctrlKey)) * notches;
      zoomGoal = Math.min(MAX_DISTANCE, Math.max(MIN_DISTANCE, start * Math.exp(step)));
      if (!gliding) {
        zoomTime = performance.now();
        zoomFrame = requestAnimationFrame(zoomStep);
      }
    },
    { passive: false },
  );

  /** The zoom goal while the camera glides to it, or null. */
  app.zoomGoal = () => zoomGoal;
  /** What one wheel notch would move now, as a share of the distance. */
  app.notchShare = (ctrl = false) => notchShare(camera.distance, ctrl);

  /** Set the camera: any of yaw, pitch, distance, target. Stops a zoom glide. */
  app.view = (next) => {
    stopZoom();
    Object.assign(camera, next);
    if (next.target) camera.target = [...next.target];
    app.applyCamera();
  };
})();

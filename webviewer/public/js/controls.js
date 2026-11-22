// Mouse controls:
// - left drag: grab the ground and pull it ("left click scrolls the map");
//   ctrl + left with a unit selected turns that unit instead (pick.js);
//   alt + left on a unit drags the unit over the ground instead, the point
//   of the unit pressed staying under the mouse ("drag unit"); on a
//   selected unit every selected unit moves along by the same step;
//   alt + left off any unit draws the select rectangle instead (select.js);
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

  /** The drag in progress: { mode, x, y, anchor, pivot, item, z, offset }, or null. */
  let drag = null;
  // Releasing Alt must not open the browser's menu bar (Firefox).
  window.addEventListener('keyup', (e) => {
    if (e.key === 'Alt') e.preventDefault();
  });
  canvas.addEventListener('contextmenu', (e) => e.preventDefault());
  // Middle click must not paste or start autoscroll.
  canvas.addEventListener('auxclick', (e) => e.preventDefault());
  canvas.addEventListener('mousedown', (e) => {
    e.preventDefault();
    const ground = app.eventGround(e);
    const at = { x: e.clientX, y: e.clientY };
    // Alt + left on a unit: drag the unit. The point of the unit pressed
    // stays under the mouse: the mouse ray is cut with the level plane
    // through that point, and the unit keeps its offset from it.
    const hit = e.button === BUTTON.left && e.altKey ? app.hitAt(e.clientX, e.clientY) : null;
    if (hit) {
      const p = hit.point;
      // On a selected unit the others selected come along, each keeping its
      // offset from the one pressed.
      const ids = app.selectedIds();
      const others = ids.includes(hit.item.id) ? app.items.filter((i) => i !== hit.item && ids.includes(i.id)).map((i) => ({ item: i, dx: i.x - hit.item.x, dy: i.y - hit.item.y })) : [];
      drag = { mode: 'move', ...at, item: hit.item, others, z: p[2], offset: [hit.item.x - p[0], hit.item.y - p[1]] };
    } else if (e.button === BUTTON.left && e.altKey) {
      // Alt + left on the ground or the sky: the select rectangle (select.js).
      drag = { mode: 'rect', ...at };
      app.startSelectRect(e);
    } else if (e.button === BUTTON.left && e.ctrlKey && app.hasSelection()) {
      // Ctrl + left with a unit selected turns that unit (pick.js).
      drag = { mode: 'face', ...at };
      app.faceSelected(e);
    } else if (e.button === BUTTON.left) drag = { mode: 'grab', ...at, anchor: ground };
    else if (e.button === BUTTON.middle && e.ctrlKey) drag = { mode: 'look', ...at };
    // Off the ground (sky under the mouse) the orbit turns around the target.
    else if (e.button === BUTTON.middle) drag = { mode: 'orbit', ...at, pivot: ground ? [ground[0], ground[1], 0] : [...camera.target] };
    else if (e.button === BUTTON.right) drag = { mode: 'pan', ...at };
    if (drag) stopZoom();
  });
  window.addEventListener('mouseup', (e) => {
    // A moved unit goes into the URL once, on release.
    if (drag && drag.mode === 'move') app.saveHash();
    if (drag && drag.mode === 'rect') app.endSelectRect(e);
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
    if (drag.mode === 'rect') {
      app.moveSelectRect(e);
      return;
    }
    if (drag.mode === 'move') {
      // The ray above the plane's horizon: the unit waits where it is.
      const now = app.planeAt(e.clientX, e.clientY, drag.z);
      if (!now) return;
      const x = now[0] + drag.offset[0];
      const y = now[1] + drag.offset[1];
      app.setPosition(drag.item, x, y);
      for (const o of drag.others) app.setPosition(o.item, x + o.dx, y + o.dy);
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
  // The zoom works from the eye's height above the ground (z = 0): when a
  // zoom starts, the target is moved to where the view line meets the
  // ground, the eye staying put, so the distance is the eye height over
  // sin(pitch) whatever pan, orbit or mouse-look did to the target. The eye
  // never comes closer than MIN_HEIGHT to the ground.
  const NOTCH_SHARE = 0.15;
  const MIN_HEIGHT = 0.3;
  // Below this pitch the view line meets the ground too far away (or not at
  // all, looking up): the target stays, only the height floor holds.
  const MIN_SIN = 0.01;
  const HIGH = 10; // eye height from which a notch is the full share
  const LOW_SHARE = 0.12; // the least part of the full share, near the ground
  const CTRL_SHARE = 0.25;
  const ZOOM_TIME = 35; // ms: time constant of the glide to the zoom goal
  const MIN_DISTANCE = 0.5;
  const MAX_DISTANCE = 2000;
  // deltaMode: 0 pixels, 1 lines, 2 pages. Lines and pages in pixels.
  const DELTA_UNIT = [1, 33, 400];

  /**
   * Put the target on the ground along the view line, the eye staying put.
   * False when the view line does not meet the ground in front of the eye.
   */
  function targetToGround() {
    const s = Math.sin(camera.pitch);
    const eye = app.eye();
    if (s < MIN_SIN || eye[2] <= 0) return false;
    const t = eye[2] / s;
    const dir = direction(camera.yaw, camera.pitch);
    camera.target = [eye[0] - dir[0] * t, eye[1] - dir[1] * t, 0];
    camera.distance = t;
    return true;
  }

  /** The nearest the camera may come along its view line: the eye MIN_HEIGHT over the ground. */
  function nearest() {
    const s = Math.sin(camera.pitch);
    // Eye height = target z + distance * s; looking flat or up, distance does not lower it.
    if (s <= 0) return MIN_DISTANCE;
    return Math.max(MIN_DISTANCE, (MIN_HEIGHT - camera.target[2]) / s);
  }

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
      const gliding = zoomGoal !== null;
      // A glide already started from the ground; a new zoom anchors first.
      if (!gliding) {
        targetToGround();
        app.applyCamera();
      }
      const start = zoomGoal ?? camera.distance;
      const step = Math.log(1 + notchShare(start, e.ctrlKey)) * notches;
      zoomGoal = Math.min(MAX_DISTANCE, Math.max(nearest(), start * Math.exp(step)));
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

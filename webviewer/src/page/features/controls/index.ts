// Mouse controls:
// - left drag: grab the ground and pull it ("left click scrolls the map");
//   ctrl + left with a unit selected turns that unit instead (features/pick);
//   alt + left on a unit drags the unit over the ground instead, the point
//   of the unit pressed staying under the mouse ("drag unit"); on a
//   selected unit every selected unit moves along by the same step;
//   alt + left off any unit draws the select rectangle instead (features/select);
//   a left or right click without a drag is handled by features/pick;
// - middle drag: orbit around the ground point under the mouse;
// - ctrl + middle drag: mouse-look, turning around the camera itself;
// - right drag: pan in the view plane;
// - wheel: zoom (zoom.ts).
// Tracks the ground point under the mouse for the grid glow.

import { app, type ControlsApi, type CoreApi, type Item, type Vec2, type Vec3 } from '../../core/app';
import { add, cross, dot, scale, sub } from '../../core/camera';
import { createZoom, direction } from './zoom';

const ROTATE_RATE = 0.004; // radians per pixel of middle drag
const PAN_RATE = 0.0006; // camera distances per pixel of right drag
const PITCH_LIMIT = Math.PI / 2 - 0.01;
const BUTTON = { left: 0, middle: 1, right: 2 };

/** Rotate v by `angle` around the unit axis (Rodrigues). */
function rotate(v: Vec3, axis: Vec3, angle: number): Vec3 {
  const c = Math.cos(angle);
  const s = Math.sin(angle);
  return add(add(scale(v, c), scale(cross(axis, v), s)), scale(axis, dot(axis, v) * (1 - c)));
}

interface At {
  x: number;
  y: number;
}

/** The drag in progress. */
type Drag =
  | (At & { mode: 'move'; item: Item; others: { item: Item; dx: number; dy: number }[]; z: number; offset: Vec2 })
  | (At & { mode: 'rect' | 'face' | 'look' | 'pan' })
  | (At & { mode: 'grab'; anchor: Vec2 | null })
  | (At & { mode: 'orbit'; pivot: Vec3 });

export function installControls(core: CoreApi): ControlsApi {
  const { canvas, camera } = core;

  canvas.addEventListener('mousemove', (e) => {
    app().pointer = app().eventGround(e);
  });
  canvas.addEventListener('mouseleave', () => {
    app().pointer = null;
  });

  /** Set yaw, pitch, distance and target from an eye and a target point. */
  function placeCamera(eye: Vec3, target: Vec3): void {
    const d = sub(eye, target);
    const length = Math.hypot(d[0], d[1], d[2]);
    camera.distance = length;
    camera.pitch = Math.asin(Math.max(-1, Math.min(1, d[2] / length)));
    camera.yaw = Math.atan2(d[1], d[0]);
    camera.target = target;
  }

  /** The pitch change that keeps the pitch inside the poles. */
  const clampPitch = (dpitch: number): number => Math.max(-PITCH_LIMIT, Math.min(PITCH_LIMIT, camera.pitch + dpitch)) - camera.pitch;

  /**
   * Orbit: move the whole camera rigidly around `pivot`, by dyaw around the
   * vertical and dpitch around the camera's right axis. A rigid move around
   * a point keeps that point on the same pixel.
   */
  function orbit(pivot: Vec3, dyaw: number, dpitchWanted: number): void {
    const dpitch = clampPitch(dpitchWanted);
    let eye = sub(app().eye(), pivot);
    let target = sub(camera.target, pivot);
    eye = rotate(eye, [0, 0, 1], dyaw);
    target = rotate(target, [0, 0, 1], dyaw);
    const yaw = camera.yaw + dyaw;
    const right: Vec3 = [-Math.sin(yaw), Math.cos(yaw), 0];
    // Around the right axis a positive angle lowers the eye: negate it.
    eye = rotate(eye, right, -dpitch);
    target = rotate(target, right, -dpitch);
    placeCamera(add(eye, pivot), add(target, pivot));
  }

  /** Mouse-look: the eye stays, the view turns. */
  function look(dyaw: number, dpitch: number): void {
    const eye = app().eye();
    camera.yaw += dyaw;
    camera.pitch += clampPitch(dpitch);
    camera.target = sub(eye, scale(direction(camera.yaw, camera.pitch), camera.distance));
  }

  /** Grab: move the camera along the ground so `anchor` is under the mouse. */
  function grab(anchor: Vec2, e: MouseEvent): void {
    const now = app().eventGround(e);
    // Above the horizon there is no ground to hold: wait for it.
    if (!now) return;
    camera.target = [camera.target[0] + anchor[0] - now[0], camera.target[1] + anchor[1] - now[1], camera.target[2]];
  }

  function pan(dx: number, dy: number): void {
    const k = camera.distance * PAN_RATE;
    const { yaw, pitch } = camera;
    const right: Vec3 = [-Math.sin(yaw), Math.cos(yaw), 0];
    const up: Vec3 = [-Math.sin(pitch) * Math.cos(yaw), -Math.sin(pitch) * Math.sin(yaw), Math.cos(pitch)];
    const t = camera.target;
    camera.target = [t[0] + (-dx * right[0] + dy * up[0]) * k, t[1] + (-dx * right[1] + dy * up[1]) * k, t[2] + (-dx * right[2] + dy * up[2]) * k];
  }

  const zoom = createZoom(camera);

  // ---- drags ----

  let drag: Drag | null = null;
  // Releasing Alt must not open the browser's menu bar (Firefox).
  window.addEventListener('keyup', (e) => {
    if (e.key === 'Alt') e.preventDefault();
  });
  canvas.addEventListener('contextmenu', (e) => e.preventDefault());
  // Middle click must not paste or start autoscroll.
  canvas.addEventListener('auxclick', (e) => e.preventDefault());
  canvas.addEventListener('mousedown', (e) => {
    e.preventDefault();
    const a = app();
    const ground = a.eventGround(e);
    const at = { x: e.clientX, y: e.clientY };
    // Alt + left on a unit: drag the unit. The point of the unit pressed
    // stays under the mouse: the mouse ray is cut with the level plane
    // through that point, and the unit keeps its offset from it.
    const hit = e.button === BUTTON.left && e.altKey ? a.hitAt(e.clientX, e.clientY) : null;
    if (hit) {
      const p = hit.point;
      const pressed = hit.item;
      // On a selected unit the others selected come along, each keeping its
      // offset from the one pressed.
      const ids = a.selectedIds();
      const others = ids.includes(pressed.id) ? a.items.filter((i) => i !== pressed && ids.includes(i.id)).map((i) => ({ item: i, dx: i.x - pressed.x, dy: i.y - pressed.y })) : [];
      drag = { mode: 'move', ...at, item: pressed, others, z: p[2], offset: [pressed.x - p[0], pressed.y - p[1]] };
    } else if (e.button === BUTTON.left && e.altKey) {
      // Alt + left on the ground or the sky: the select rectangle (features/select).
      drag = { mode: 'rect', ...at };
      a.startSelectRect(e);
    } else if (e.button === BUTTON.left && e.ctrlKey && a.hasSelection()) {
      // Ctrl + left with a unit selected turns that unit (features/pick).
      drag = { mode: 'face', ...at };
      a.faceSelected(e);
    } else if (e.button === BUTTON.left) drag = { mode: 'grab', ...at, anchor: ground };
    else if (e.button === BUTTON.middle && e.ctrlKey) drag = { mode: 'look', ...at };
    // Off the ground (sky under the mouse) the orbit turns around the target.
    else if (e.button === BUTTON.middle) drag = { mode: 'orbit', ...at, pivot: ground ? [ground[0], ground[1], 0] : [...camera.target] };
    else if (e.button === BUTTON.right) drag = { mode: 'pan', ...at };
    if (drag) zoom.stop();
  });
  window.addEventListener('mouseup', (e) => {
    // A moved unit goes into the URL once, on release.
    if (drag && drag.mode === 'move') app().saveScene();
    if (drag && drag.mode === 'rect') app().endSelectRect(e);
    drag = null;
  });
  window.addEventListener('mousemove', (e) => {
    if (!drag) return;
    const a = app();
    const dx = e.clientX - drag.x;
    const dy = e.clientY - drag.y;
    drag.x = e.clientX;
    drag.y = e.clientY;
    if (drag.mode === 'face') {
      a.faceSelected(e);
      return;
    }
    if (drag.mode === 'rect') {
      a.moveSelectRect(e);
      return;
    }
    if (drag.mode === 'move') {
      // The ray above the plane's horizon: the unit waits where it is.
      const now = a.planeAt(e.clientX, e.clientY, drag.z);
      if (!now) return;
      const x = now[0] + drag.offset[0];
      const y = now[1] + drag.offset[1];
      a.setPosition(drag.item, x, y);
      for (const o of drag.others) a.setPosition(o.item, x + o.dx, y + o.dy);
      return;
    }
    if (drag.mode === 'grab') {
      // Pressed on the sky: the first ground point reached becomes the anchor.
      if (!drag.anchor) drag.anchor = a.eventGround(e);
      else grab(drag.anchor, e);
    } else if (drag.mode === 'orbit') orbit(drag.pivot, -dx * ROTATE_RATE, dy * ROTATE_RATE);
    else if (drag.mode === 'look') look(-dx * ROTATE_RATE, dy * ROTATE_RATE);
    else pan(dx, dy);
    a.applyCamera();
  });

  canvas.addEventListener('wheel', (e) => zoom.wheel(e), { passive: false });

  return {
    /** The zoom goal while the camera glides to it, or null. */
    zoomGoal: () => zoom.goal(),
    /** What one wheel notch would move now, as a share of the distance. */
    notchShare: (ctrl = false) => zoom.notchShare(camera.distance, ctrl),
    /** Set the camera: any of yaw, pitch, distance, target. Stops a zoom glide. */
    view: (next) => {
      zoom.stop();
      Object.assign(camera, next);
      if (next.target) camera.target = [...next.target];
      app().applyCamera();
    },
  };
}

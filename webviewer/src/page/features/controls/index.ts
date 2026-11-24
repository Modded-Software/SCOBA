// Mouse controls:
// - left drag: grab the ground and pull it ("left click scrolls the map");
//   ctrl + left with units selected turns them to face the mouse instead;
//   alt + left on a unit drags the unit over the ground instead, the point
//   of the unit pressed staying under the mouse ("drag unit"); on a
//   selected unit every selected unit moves along by the same step;
//   alt + left off any unit draws the select rectangle instead (features/select
//   has its own listeners; here the press only keeps the camera still);
//   a left or right click without a drag is handled by features/pick;
// - middle drag: orbit around the ground point under the mouse;
// - ctrl + middle drag: mouse-look, turning around the camera itself;
// - right drag: pan in the view plane;
// - wheel: zoom (core/zoom.ts, the camera service).
// The camera itself is the camera service (core/view.ts).

import type { Feature } from '../../core/context';
import type { Item, Vec2, Vec3 } from '../../core/types';
import { add, cross, dot, scale, sub } from '../../core/camera';
import { direction } from '../../core/zoom';

const ROTATE_RATE = 0.004; // radians per pixel of middle drag
const PAN_RATE = 0.0006; // camera distances per pixel of right drag
const PITCH_LIMIT = Math.PI / 2 - 0.01;
const BUTTON = { left: 0, middle: 1, right: 2 };
const MODEL_FRONT_OFFSET = 90; // degrees: rotation 0 faces -y, see rotationFacing

/**
 * The rotation that makes a model face `angle` (degrees, from +x towards
 * +y). At rotation 0 a model faces -y (operator 2026-11-21: facing the
 * mouse came out 90 degrees clockwise of it). Kept in (-180, 180].
 */
function rotationFacing(angle: number): number {
  const rot = angle + MODEL_FRONT_OFFSET;
  return rot > 180 ? rot - 360 : rot <= -180 ? rot + 360 : rot;
}

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

export const controlsFeature: Feature = {
  id: 'controls',
  install({ render, camera: view, scene, selection, events }) {
    const { canvas } = render;
    const { camera } = view;
    const { items } = scene;

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
      let eye = sub(view.eye(), pivot);
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
      const eye = view.eye();
      camera.yaw += dyaw;
      camera.pitch += clampPitch(dpitch);
      camera.target = sub(eye, scale(direction(camera.yaw, camera.pitch), camera.distance));
    }

    /** Grab: move the camera along the ground so `anchor` is under the mouse. */
    function grab(anchor: Vec2, e: MouseEvent): void {
      const now = view.eventGround(e);
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

    /** Turn the selected units to face the ground point under a mouse event. */
    function faceSelected(e: MouseEvent): void {
      const point = view.eventGround(e);
      if (!point) return;
      for (const id of selection.selectedIds()) {
        const item = items.find((i) => i.id === id);
        if (!item) continue;
        const dx = point[0] - item.x;
        const dy = point[1] - item.y;
        if (Math.hypot(dx, dy) < 1e-3) continue;
        scene.setRotation(item, rotationFacing((Math.atan2(dy, dx) * 180) / Math.PI));
      }
    }

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
      const ground = view.eventGround(e);
      const at = { x: e.clientX, y: e.clientY };
      // Alt + left on a unit: drag the unit. The point of the unit pressed
      // stays under the mouse: the mouse ray is cut with the level plane
      // through that point, and the unit keeps its offset from it.
      const hit = e.button === BUTTON.left && e.altKey ? selection.hitAt(e.clientX, e.clientY) : null;
      if (hit) {
        const p = hit.point;
        const pressed = hit.item;
        // On a selected unit the others selected come along, each keeping its
        // offset from the one pressed.
        const ids = selection.selectedIds();
        const others = ids.includes(pressed.id) ? items.filter((i) => i !== pressed && ids.includes(i.id)).map((i) => ({ item: i, dx: i.x - pressed.x, dy: i.y - pressed.y })) : [];
        drag = { mode: 'move', ...at, item: pressed, others, z: p[2], offset: [pressed.x - p[0], pressed.y - p[1]] };
      } else if (e.button === BUTTON.left && e.altKey) {
        // Alt + left on the ground or the sky: the select rectangle (features/select draws it).
        drag = { mode: 'rect', ...at };
      } else if (e.button === BUTTON.left && e.ctrlKey && selection.hasSelection()) {
        // Ctrl + left with units selected turns them.
        drag = { mode: 'face', ...at };
        faceSelected(e);
      } else if (e.button === BUTTON.left) drag = { mode: 'grab', ...at, anchor: ground };
      else if (e.button === BUTTON.middle && e.ctrlKey) drag = { mode: 'look', ...at };
      // Off the ground (sky under the mouse) the orbit turns around the target.
      else if (e.button === BUTTON.middle) drag = { mode: 'orbit', ...at, pivot: ground ? [ground[0], ground[1], 0] : [...camera.target] };
      else if (e.button === BUTTON.right) drag = { mode: 'pan', ...at };
      if (drag) view.stopGlide();
    });
    window.addEventListener('mouseup', (e) => {
      // A moved unit goes into the URL once, on release.
      if (drag && drag.mode === 'move') events.emit('scene-edited', { what: 'move' });
      drag = null;
    });
    window.addEventListener('mousemove', (e) => {
      if (!drag) return;
      const dx = e.clientX - drag.x;
      const dy = e.clientY - drag.y;
      drag.x = e.clientX;
      drag.y = e.clientY;
      if (drag.mode === 'face') {
        faceSelected(e);
        return;
      }
      // The select rectangle: features/select draws it; the camera stays.
      if (drag.mode === 'rect') return;
      if (drag.mode === 'move') {
        // The ray above the plane's horizon: the unit waits where it is.
        const now = selection.planeAt(e.clientX, e.clientY, drag.z);
        if (!now) return;
        const x = now[0] + drag.offset[0];
        const y = now[1] + drag.offset[1];
        scene.setPosition(drag.item, x, y);
        for (const o of drag.others) scene.setPosition(o.item, x + o.dx, y + o.dy);
        return;
      }
      if (drag.mode === 'grab') {
        // Pressed on the sky: the first ground point reached becomes the anchor.
        if (!drag.anchor) drag.anchor = view.eventGround(e);
        else grab(drag.anchor, e);
      } else if (drag.mode === 'orbit') orbit(drag.pivot, -dx * ROTATE_RATE, dy * ROTATE_RATE);
      else if (drag.mode === 'look') look(-dx * ROTATE_RATE, dy * ROTATE_RATE);
      else pan(dx, dy);
      view.applyCamera();
    });

    canvas.addEventListener('wheel', (e) => view.wheel(e), { passive: false });
  },
};

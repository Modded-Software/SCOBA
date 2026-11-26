// Mouse controls:
// - left drag: grab the ground and pull it ("left click scrolls the map");
//   ctrl + left with units selected turns them to face the mouse instead;
//   alt + left on a unit drags the unit over the ground instead, the point
//   of the unit pressed staying under the mouse ("drag unit"); on a
//   selected unit every selected unit moves along by the same step;
//   alt + left off any unit draws the select rectangle instead (features/select
//   has its own listeners; here the press only keeps the camera still);
//   a left or right click without a drag is handled by features/pick;
// - a press is a drag only after 2 px and 150 ms, or 12 px at once (core/press.ts, R-VIEW-142);
// - middle drag: orbit around the ground point under the mouse;
// - with a unit under the mouse (hover outline) at the press, its centre
//   takes the ground point's place: the orbit turns around it and a left
//   drag holds the level plane through it (R-VIEW-149);
// - alt + middle drag: mouse-look, turning around the camera itself;
// - right drag: pan in the view plane;
// - ctrl held during a left, middle or right camera drag: a quarter of the
//   movement, for precision (ctrl + left with units selected turns them);
// - the mouse sensitivity (stored setting mouse.sensitivity, 0.6 when none
//   is stored) scales every camera drag; Ctrl's quarter comes on top of it.
//   A unit move, a turn and the select rectangle follow the pointer exactly
//   (R-VIEW-150);
// - wheel: zoom (core/zoom.ts, the camera service).
// Those are the default bindings and rates. Every button, modifier and rate
// above is the input map's (core/input.ts, R-VIEW-154), read at each press;
// the controls window (panel.ts) changes them.
// - the cancel key (Escape) during a unit move or turn puts the units back
//   where they were at the press and ends the drag;
// - the page losing the focus ends any drag, as a release would.
// The camera itself is the camera service (core/view.ts).

import type { Feature } from '../../core/context';
import type { Item, Vec2, Vec3 } from '../../core/types';
import { add, cross, dot, scale, sub } from '../../core/camera';
import { restBox } from '../../core/geometry';
import { direction } from '../../core/zoom';
import { dragsAt, pressAt, type Press } from '../../core/press';
import { settings } from '../../core/settings';
import { held, keyIs, mouseMatches, pressAction, resolveInput, type InputMap, type Rates } from '../../core/input';
import { createControlsPanel } from './panel';

const PITCH_LIMIT = Math.PI / 2 - 0.01;
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

/** The drag in progress. `x`, `y`: the last place it acted from; where it became a drag, then the last move. */
/** `rates`: the input map's, read at the press; `before`: the units a move or turn changes, as they were at the press. */
type Drag = { press: Press; sensitivity: number; rates: Readonly<Rates>; before: { item: Item; x: number; y: number; rot: number }[] } & (
  | (At & { mode: 'move'; item: Item; others: { item: Item; dx: number; dy: number }[]; z: number; offset: Vec2 })
  | (At & { mode: 'rect' | 'face' | 'look' | 'pan' })
  | (At & { mode: 'grab'; anchor: Vec2 | null; z: number })
  | (At & { mode: 'orbit'; pivot: Vec3 })
);

export const controlsFeature: Feature = {
  id: 'controls',
  install(context) {
    const { render, camera: view, scene, selection, events, store } = context;
    const { canvas } = render;
    const { camera } = view;
    const { items } = scene;
    const inputMap = (): InputMap => resolveInput(store.read(settings.input));
    createControlsPanel(context);
    /** For the tests: the last grab or orbit press, the unit it centred on (R-VIEW-149) and the orbit pivot. */
    let lastPress: { mode: 'grab' | 'orbit'; unit: number | null; pivot: Vec3 | null } | null = null;
    context.testApi.viewer({ lastPress: () => lastPress });

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

    /** The point of the level plane at height z under a page pixel: the ground at z = 0, else the plane through a unit's centre (R-VIEW-149). */
    function heldAt(clientX: number, clientY: number, z: number): Vec2 | null {
      if (z !== 0) return selection.planeAt(clientX, clientY, z);
      const box = canvas.getBoundingClientRect();
      return view.groundAt(clientX - box.left, clientY - box.top);
    }

    /**
     * The centre of a press (R-VIEW-149): the middle of the rest-pose vertex box of
     * the instance with the hover outline (core/geometry.ts restBox, as the row
     * focus), else null (the ground point is used).
     */
    function unitCentre(): Vec3 | null {
      const item = selection.hovered();
      return item ? restBox(item).centre : null;
    }

    /** Grab: move the camera along the plane at `z` so `anchor` is under the mouse. */
    function grab(anchor: Vec2, z: number, e: MouseEvent): void {
      const now = heldAt(e.clientX, e.clientY, z);
      // Above the horizon there is no plane to hold: wait for it.
      if (!now) return;
      camera.target = [camera.target[0] + anchor[0] - now[0], camera.target[1] + anchor[1] - now[1], camera.target[2]];
    }

    /** Grab by a share `k` of the plane at `z` the pointer crossed from (x0, y0) to (x1, y1) (page pixels). */
    function preciseGrab(x0: number, y0: number, x1: number, y1: number, z: number, k: number): void {
      const before = heldAt(x0, y0, z);
      const now = heldAt(x1, y1, z);
      if (!before || !now) return;
      const t = camera.target;
      camera.target = [t[0] - (now[0] - before[0]) * k, t[1] - (now[1] - before[1]) * k, t[2]];
    }

    function pan(dx: number, dy: number, rate: number): void {
      const k = camera.distance * rate;
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
      const map = inputMap();
      const ground = view.eventGround(e);
      // The unit under the pointer, the ray cut with it: tested only for a press that can move one.
      const hit = mouseMatches(map.mouse.move, e) ? selection.hitAt(e.clientX, e.clientY) : null;
      const mode = pressAction(map, e, { onUnit: hit !== null, selected: selection.hasSelection() });
      // A click until core/press.ts says it is a drag (R-VIEW-142).
      const at = { x: e.clientX, y: e.clientY, press: pressAt(e, map.rates), sensitivity: store.read(settings.mouseSensitivity), rates: map.rates, before: [] };
      const kept = (list: readonly Item[]): Drag['before'] => list.map((item) => ({ item, x: item.x, y: item.y, rot: item.rot }));
      if (mode === 'move' && hit) {
        // The point of the unit pressed stays under the mouse: the mouse ray is
        // cut with the level plane through that point, and the unit keeps its offset from it.
        const p = hit.point;
        const pressed = hit.item;
        // On a selected unit the others selected come along, each keeping its
        // offset from the one pressed.
        const ids = selection.selectedIds();
        const along = ids.includes(pressed.id) ? items.filter((i) => i !== pressed && ids.includes(i.id)) : [];
        const others = along.map((i) => ({ item: i, dx: i.x - pressed.x, dy: i.y - pressed.y }));
        drag = { mode: 'move', ...at, before: kept([pressed, ...along]), item: pressed, others, z: p[2], offset: [pressed.x - p[0], pressed.y - p[1]] };
      } else if (mode === 'rect') {
        // Off any unit: the select rectangle (features/select draws it).
        drag = { mode: 'rect', ...at };
      } else if (mode === 'face') {
        const ids = selection.selectedIds();
        drag = { mode: 'face', ...at, before: kept(items.filter((i) => ids.includes(i.id))) };
        faceSelected(e);
      } else if (mode === 'grab') {
        // A unit under the mouse: its centre's plane is held; else the ground (R-VIEW-149).
        const centre = unitCentre();
        drag = centre ? { mode: 'grab', ...at, anchor: heldAt(e.clientX, e.clientY, centre[2]), z: centre[2] } : { mode: 'grab', ...at, anchor: ground, z: 0 };
      } else if (mode === 'look') drag = { mode: 'look', ...at };
      // Around the unit under the mouse; else the ground point; off the ground (sky) around the target.
      else if (mode === 'orbit') {
        const centre = unitCentre();
        const pivot: Vec3 = centre ?? (ground ? [ground[0], ground[1], 0] : [...camera.target]);
        lastPress = { mode, unit: centre ? (selection.hovered()?.id ?? null) : null, pivot };
        drag = { mode: 'orbit', ...at, pivot };
      }
      if (mode === 'grab') lastPress = { mode, unit: drag?.mode === 'grab' && drag.z !== 0 ? (selection.hovered()?.id ?? null) : null, pivot: null };
      else if (mode === 'pan') drag = { mode: 'pan', ...at };
      if (drag) view.stopGlide();
    });
    /** A press became a drag at `e`: take the pointer's place now as its start. */
    function begin(d: Drag, e: MouseEvent): void {
      d.x = e.clientX;
      d.y = e.clientY;
      if (d.mode === 'grab') d.anchor = heldAt(e.clientX, e.clientY, d.z);
      else if (d.mode === 'move') {
        // The unit keeps its place; the pointer holds it at the offset it has now.
        const now = selection.planeAt(e.clientX, e.clientY, d.z);
        if (now) d.offset = [d.item.x - now[0], d.item.y - now[1]];
      }
    }
    /** The drag ends: a moved unit goes into the URL once, on release. */
    function end(): void {
      if (drag && drag.mode === 'move') events.emit('scene-edited', { what: 'move' });
      drag = null;
    }
    window.addEventListener('mouseup', end);
    // A release outside the page is not seen: the page losing the focus ends the drag.
    window.addEventListener('blur', end);
    window.addEventListener('keydown', (e) => {
      // The drag's own modifiers are held (Alt for a move): the cancel key matches with any held.
      if (!drag || (drag.mode !== 'move' && drag.mode !== 'face') || !keyIs(inputMap().keys.cancel, e)) return;
      e.preventDefault();
      // The units go back to where they were at the press; nothing was edited.
      for (const b of drag.before) {
        scene.setPosition(b.item, b.x, b.y);
        scene.setRotation(b.item, b.rot);
      }
      drag = null;
    });
    window.addEventListener('mousemove', (e) => {
      if (!drag) return;
      // Ctrl + left with a selection is a hold: it turns from the press on.
      // Every other press waits until it is a drag.
      if (drag.mode !== 'face') {
        const was = drag.press.dragging;
        if (!dragsAt(drag.press, e)) return;
        // A slow drag starts here: it holds what is under the pointer now, so
        // nothing jumps by the travel of the hold. A fast one acts from the
        // press point: the travel is short and is the drag (R-VIEW-142).
        if (!was && !drag.press.fast) {
          begin(drag, e);
          return;
        }
      }
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
      // The mouse sensitivity (R-VIEW-150), read at the press; the precision modifier held: its share of that on top (R-VIEW-143). It is read on every move.
      const { rates } = drag;
      const k = drag.sensitivity * (held(e, rates.precise) ? rates.preciseShare : 1);
      const sx = rates.invertOrbitX ? -1 : 1;
      const sy = rates.invertOrbitY ? -1 : 1;
      const sp = rates.invertPan ? -1 : 1;
      if (drag.mode === 'grab') {
        if (k !== 1) {
          // The ground under the pointer moves a quarter of the way: the anchor is
          // let go, and taken again (without a jump) when Ctrl is released.
          preciseGrab(e.clientX - dx, e.clientY - dy, e.clientX, e.clientY, drag.z, k);
          drag.anchor = null;
        } else if (!drag.anchor) drag.anchor = heldAt(e.clientX, e.clientY, drag.z);
        // Pressed on the sky: the first ground point reached becomes the anchor.
        else grab(drag.anchor, drag.z, e);
      } else if (drag.mode === 'orbit') orbit(drag.pivot, -dx * rates.orbit * k * sx, dy * rates.orbit * k * sy);
      else if (drag.mode === 'look') look(-dx * rates.orbit * k * sx, dy * rates.orbit * k * sy);
      else pan(dx * k * sp, dy * k * sp, rates.pan);
      view.applyCamera();
    });

    canvas.addEventListener('wheel', (e) => view.wheel(e), { passive: false });
  },
};

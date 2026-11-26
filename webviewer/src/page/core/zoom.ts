// Wheel zoom, smooth; smaller steps near the ground, smaller with ctrl.
//
// One wheel notch (deltaY 100) moves the camera a share of its distance:
// 15% with the eye high up, less as it comes down to the ground (down to
// 1.8% at 1.2 units and below). Ctrl makes every step a quarter. The mouse
// sensitivity (0.6 when none is stored, R-VIEW-150) scales every step.
// The zoom works from the eye's height above the ground (z = 0): when a
// zoom starts, the target is moved to where the view line meets the
// ground, the eye staying put, so the distance is the eye height over
// sin(pitch) whatever pan, orbit or mouse-look did to the target. The eye
// never comes closer than MIN_HEIGHT to the ground.
// Two flags of the input map (core/input.ts, R-VIEW-154), read at each
// wheel event, both off when nothing is stored:
// - invertZoom: the wheel the other way round;
// - zoomToPointer: the ground point under the pointer stays under it. The
//   target, on the ground, moves towards that point by the share the
//   distance changes: target = point + (target - point) * new / old. With
//   the pointer on the sky, or the view line not meeting the ground, the
//   zoom is along the view line as without the flag.

import type { CameraState, Vec2, Vec3 } from './types';

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

/** From eye to camera unit direction (eye = target + distance * dir). */
export const direction = (yaw: number, pitch: number): Vec3 => [Math.cos(pitch) * Math.cos(yaw), Math.cos(pitch) * Math.sin(yaw), Math.sin(pitch)];

export interface Zoom {
  wheel(e: WheelEvent): void;
  stop(): void;
  /** The distance the camera glides to, or null when it is not zooming. */
  goal(): number | null;
  /** The share of the distance one notch moves, for a camera at `distance`. */
  notchShare(distance: number, ctrl: boolean): number;
}

export interface ZoomRig {
  eye(): Vec3;
  applyCamera(): void;
  sensitivity(): number;
  /** The ground point under the pointer of a wheel event, or null on the sky. */
  pointerGround(e: WheelEvent): Vec2 | null;
  /** The wheel flags of the input map, as stored now. */
  flags(): { invertZoom: boolean; zoomToPointer: boolean };
}

export function createZoom(camera: CameraState, rig: ZoomRig): Zoom {
  /**
   * Put the target on the ground along the view line, the eye staying put.
   * False when the view line does not meet the ground in front of the eye.
   */
  function targetToGround(): boolean {
    const s = Math.sin(camera.pitch);
    const eye = rig.eye();
    if (s < MIN_SIN || eye[2] <= 0) return false;
    const t = eye[2] / s;
    const dir = direction(camera.yaw, camera.pitch);
    camera.target = [eye[0] - dir[0] * t, eye[1] - dir[1] * t, 0];
    camera.distance = t;
    return true;
  }

  /** The nearest the camera may come along its view line: the eye MIN_HEIGHT over the ground. */
  function nearest(): number {
    const s = Math.sin(camera.pitch);
    // Eye height = target z + distance * s; looking flat or up, distance does not lower it.
    if (s <= 0) return MIN_DISTANCE;
    return Math.max(MIN_DISTANCE, (MIN_HEIGHT - camera.target[2]) / s);
  }

  function notchShare(distance: number, ctrl: boolean): number {
    const height = camera.target[2] + distance * Math.sin(camera.pitch);
    const share = NOTCH_SHARE * Math.max(LOW_SHARE, Math.min(1, height / HIGH));
    return ctrl ? share * CTRL_SHARE : share;
  }

  let zoomGoal: number | null = null;
  let zoomTime = 0;
  let zoomFrame = 0;
  /** Whether the glide started with the target on the ground. */
  let grounded = false;
  /** zoomToPointer: the ground point the glide keeps under the pointer. */
  let anchor: Vec2 | null = null;

  function stop(): void {
    cancelAnimationFrame(zoomFrame);
    zoomGoal = null;
    anchor = null;
  }

  /** Set the distance; with an anchor, move the target so the anchor stays on its pixel. */
  function setDistance(next: number): void {
    const share = next / camera.distance;
    camera.distance = next;
    if (!anchor) return;
    const t = camera.target;
    camera.target = [anchor[0] + (t[0] - anchor[0]) * share, anchor[1] + (t[1] - anchor[1]) * share, t[2]];
  }

  function zoomStep(now: number): void {
    if (zoomGoal === null) return;
    const dt = Math.max(0, now - zoomTime);
    zoomTime = now;
    // Glide in log space, so each frame moves the same share of the way at
    // any distance.
    const k = 1 - Math.exp(-dt / ZOOM_TIME);
    const from = Math.log(camera.distance);
    const to = Math.log(zoomGoal);
    if (Math.abs(to - from) < 1e-4) {
      setDistance(zoomGoal);
      zoomGoal = null;
      anchor = null;
    } else {
      setDistance(Math.exp(from + (to - from) * k));
      zoomFrame = requestAnimationFrame(zoomStep);
    }
    rig.applyCamera();
  }

  function wheel(e: WheelEvent): void {
    // Also keeps ctrl + wheel from zooming the page.
    e.preventDefault();
    const flags = rig.flags();
    const notches = ((e.deltaY * (DELTA_UNIT[e.deltaMode] ?? 1)) / 100) * (flags.invertZoom ? -1 : 1);
    const gliding = zoomGoal !== null;
    // A glide already started from the ground; a new zoom anchors first.
    if (!gliding) {
      grounded = targetToGround();
      rig.applyCamera();
    }
    // The point under the pointer now, mid-glide too: the pointer may have moved.
    anchor = flags.zoomToPointer && grounded ? rig.pointerGround(e) : null;
    const start = zoomGoal ?? camera.distance;
    // The mouse sensitivity scales each step too (R-VIEW-150).
    const step = Math.log(1 + notchShare(start, e.ctrlKey) * rig.sensitivity()) * notches;
    zoomGoal = Math.min(MAX_DISTANCE, Math.max(nearest(), start * Math.exp(step)));
    if (!gliding) {
      zoomTime = performance.now();
      zoomFrame = requestAnimationFrame(zoomStep);
    }
  }

  return { wheel, stop, goal: () => zoomGoal, notchShare };
}

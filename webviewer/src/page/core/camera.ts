// The camera: its state (kept in localStorage), the eye, the projection,
// and rays between page pixels and the world.

import type Scene from '@renderer/viewer/scene';
import type { CameraState, Ray, Vec2, Vec3 } from './types';
import { readSetting, settings, writeSetting, type Restore } from './settings';

export const UP: Vec3 = [0, 0, 1];
export const FOV = Math.PI / 4;

// The camera is a setting (core/settings.ts), so a reload shows the same view.

export const sub = (a: Vec3, b: Vec3): Vec3 => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
export const add = (a: Vec3, b: Vec3): Vec3 => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
export const scale = (a: Vec3, k: number): Vec3 => [a[0] * k, a[1] * k, a[2] * k];
export const dot = (a: Vec3, b: Vec3): number => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
export const cross = (a: Vec3, b: Vec3): Vec3 => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const unit3 = (v: Vec3): Vec3 => {
  const length = Math.hypot(v[0], v[1], v[2]);
  return [v[0] / length, v[1] / length, v[2] / length];
};

export interface CameraRig {
  camera: CameraState;
  cameraRestore: string;
  eye(): Vec3;
  applyCamera(): void;
  resize(): void;
  rayAt(px: number, py: number): Ray;
  screenOf(point: Vec3): Vec2 | null;
  groundAt(px: number, py: number): Vec2 | null;
  eventGround(e: MouseEvent): Vec2 | null;
}

/** The camera of the unit scene and the sky scene, drawn on `canvas`. */
export function createCamera(canvas: HTMLCanvasElement, scene: Scene, skyScene: Scene): CameraRig {
  const camera: CameraState = { yaw: -Math.PI / 2, pitch: 0.5, distance: 9, target: [0, 0, 0.8] };

  /** How the stored camera loaded (core/settings.ts). */
  const stored = readSetting(settings.camera);
  const cameraRestore: Restore = stored.restore;
  if (stored.value) Object.assign(camera, stored.value);

  function saveCamera(): void {
    writeSetting(settings.camera, { yaw: camera.yaw, pitch: camera.pitch, distance: camera.distance, target: [...camera.target] });
  }

  function eye(): Vec3 {
    const { yaw, pitch, distance, target } = camera;
    return [
      target[0] + distance * Math.cos(pitch) * Math.cos(yaw),
      target[1] + distance * Math.cos(pitch) * Math.sin(yaw),
      target[2] + distance * Math.sin(pitch),
    ];
  }

  /**
   * The unit scene's projection. Near and far follow the camera distance,
   * so a far view keeps the ground and the units in front of the far plane
   * (and the depth range stays the same ratio, 1 to 20000).
   */
  function project(): void {
    const near = Math.max(0.1, camera.distance * 0.01);
    const far = Math.max(2000, camera.distance * 200);
    scene.camera.perspective(FOV, canvas.width / canvas.height, near, far);
  }

  function applyCamera(): void {
    const from = eye();
    project();
    scene.camera.moveToAndFace(from, camera.target, UP);
    // The sky turns with the camera but never comes closer.
    skyScene.camera.moveToAndFace([0, 0, 0], sub(camera.target, from), UP);
    saveCamera();
  }

  function resize(): void {
    const width = Math.max(1, Math.floor(canvas.clientWidth));
    const height = Math.max(1, Math.floor(canvas.clientHeight));
    if (canvas.width === width && canvas.height === height) return;
    canvas.width = width;
    canvas.height = height;
    for (const s of [scene, skyScene]) {
      s.viewport[2] = width;
      s.viewport[3] = height;
    }
    // SC2 models are a few units tall, so the near plane is close (project).
    project();
    // Skyboxes are large models around the origin.
    skyScene.camera.perspective(FOV, width / height, 1, 100000);
  }

  /** The camera's eye and its forward, right and up axes. */
  function basis(): { from: Vec3; forward: Vec3; right: Vec3; up: Vec3; tan: number; aspect: number } {
    const from = eye();
    const forward = unit3(sub(camera.target, from));
    const right = unit3(cross(forward, UP));
    const up = cross(right, forward);
    return { from, forward, right, up, tan: Math.tan(FOV / 2), aspect: canvas.clientWidth / canvas.clientHeight };
  }

  /** The ray through a canvas pixel (from the top left, in CSS pixels). */
  function rayAt(px: number, py: number): Ray {
    const { from, forward, right, up, tan, aspect } = basis();
    const nx = ((2 * px) / canvas.clientWidth - 1) * tan * aspect;
    const ny = (1 - (2 * py) / canvas.clientHeight) * tan;
    return { from, dir: add(add(forward, scale(right, nx)), scale(up, ny)) };
  }

  /** The page pixel [clientX, clientY] a world point lands on, or null behind the camera. The inverse of rayAt. */
  function screenOf(point: Vec3): Vec2 | null {
    const { from, forward, right, up, tan, aspect } = basis();
    const d = sub(point, from);
    const depth = dot(d, forward);
    if (depth <= 0) return null;
    const nx = dot(d, right) / depth;
    const ny = dot(d, up) / depth;
    const box = canvas.getBoundingClientRect();
    return [box.left + ((nx / (tan * aspect) + 1) * canvas.clientWidth) / 2, box.top + ((1 - ny / tan) * canvas.clientHeight) / 2];
  }

  /** The ground point (z = 0) under a canvas pixel, or null when the pixel shows sky. */
  function groundAt(px: number, py: number): Vec2 | null {
    const { from, dir } = rayAt(px, py);
    if (dir[2] >= -1e-6) return null;
    const t = -from[2] / dir[2];
    if (t <= 0) return null;
    return [from[0] + dir[0] * t, from[1] + dir[1] * t];
  }

  /** The ground point under a mouse or drag event, or null. */
  function eventGround(e: MouseEvent): Vec2 | null {
    const box = canvas.getBoundingClientRect();
    return groundAt(e.clientX - box.left, e.clientY - box.top);
  }

  return { camera, cameraRestore, eye, applyCamera, resize, rayAt, screenOf, groundAt, eventGround };
}

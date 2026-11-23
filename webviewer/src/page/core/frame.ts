// Drawing, the grid glow and the frame loop (the old js/main.js, without
// the startup, which is page/main.ts). The scene is kept by features/scenes.

import type { Spot } from './render/ground';
import { app, type CoreApi, type FrameApi } from './app';

const GLOW = 2.5; // how far the glow reaches past a unit's radius, or from the mouse

export function installFrame(core: CoreApi): FrameApi & { start(): void } {
  const { viewer, scene, skyScene, canvas, camera, items, ground, BACKGROUND } = core;

  /**
   * Grid glow spots: under the mouse and under each unit, [x, y, radius,
   * hd]. hd is 1 for a model with a 2048 texture or larger (features/hd isHd): its glow is blue.
   */
  function glowSpots(): Spot[] {
    const a = app();
    const spots: Spot[] = a.pointer ? [[a.pointer[0], a.pointer[1], GLOW, 0]] : [];
    for (const item of items) spots.push([item.x, item.y, (item.unit ? item.unit.radius : 0.5) + GLOW, a.isHd(item) ? 1 : 0]);
    return spots;
  }

  /** One frame: background, sky (and its displacement), ground, units (and theirs), mouse-over outline. */
  function draw(dt: number): void {
    const a = app();
    const gl = viewer.gl;
    viewer.update(dt);
    a.endOneShots();
    a.updatePick();
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.scissor(0, 0, canvas.width, canvas.height);
    gl.depthMask(true);
    gl.clearColor(BACKGROUND[0], BACKGROUND[1], BACKGROUND[2], 1);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    a.displacedBatches = 0;
    if (a.sky && a.sky.instance) {
      skyScene.render();
      a.displacedBatches += a.displacement.draw(skyScene, canvas.width, canvas.height);
      // The sky is behind everything: forget its depth.
      gl.depthMask(true);
      gl.clear(gl.DEPTH_BUFFER_BIT);
    }
    ground.draw(scene.camera, camera.target, glowSpots(), camera.distance);
    scene.render();
    a.displacedBatches += a.displacement.draw(scene, canvas.width, canvas.height);
    // The mouse-over outline, when the hovered unit is drawn this frame.
    const hovered = a.hoveredItem();
    if (hovered && scene.instances.includes(hovered.instance)) a.outline.draw(hovered.instance, canvas.width, canvas.height);
  }

  /** Draw displacement materials or not (tests compare the two). */
  function setDisplacement(on: boolean): void {
    app().displacement.enabled = Boolean(on);
  }

  // ---- frame loop ----

  // Animations advance by the real time since the last frame, so they play
  // at the data's speed on any screen refresh rate. A long gap (hidden tab)
  // counts as at most MAX_STEP.
  const MAX_STEP = 100; // ms
  let lastTime: number | null = null;
  function frame(now: number): void {
    const dt = lastTime === null ? 0 : Math.min(now - lastTime, MAX_STEP);
    lastTime = now;
    app().resize();
    draw(dt);
    requestAnimationFrame(frame);
  }

  function start(): void {
    requestAnimationFrame(frame);
  }

  return { displacedBatches: 0, draw, setDisplacement, start };
}

// Drawing, the grid glow and the frame loop (the startup is
// page/main.ts). With the host it makes the render
// service (core/context.ts RenderHost).

import type { GameRegistry, RenderHost, SceneService, SelectionService, CameraService } from './context';
import type { EventBus, ViewerEvents } from './bus';
import type { Host } from './host';
import type { Spot } from './render/ground';

const GLOW = 2.5; // how far the glow reaches past a unit's radius, or from the mouse

export interface FrameDeps {
  readonly host: Host;
  readonly camera: CameraService;
  readonly scene: SceneService;
  readonly selection: SelectionService;
  readonly games: GameRegistry;
  readonly events: EventBus<ViewerEvents>;
}

export function createFrame({ host, camera: view, scene: items, selection, games, events }: FrameDeps): RenderHost & { start(): void } {
  const { viewer, scene, skyScene, canvas, ground, outline, postPasses, BACKGROUND } = host;
  const { camera } = view;
  let displaced = 0;

  /** Every post pass after one scene: how many parts they drew. */
  function afterScene(drawn: typeof scene): number {
    return postPasses.reduce((n, pass) => n + (pass.enabled ? pass.draw(drawn, canvas.width, canvas.height) : 0), 0);
  }

  /**
   * Grid glow spots: under the mouse and under each unit, [x, y, radius,
   * class]. The class is the game's rule (glowOf): 0 the standard glow, 1
   * the second (SC2: blue, a model with a 2048 texture or larger).
   */
  function glowSpots(): Spot[] {
    const pointer = view.pointer();
    const spots: Spot[] = pointer ? [[pointer[0], pointer[1], GLOW, 0]] : [];
    for (const item of items.items) spots.push([item.x, item.y, (item.placement.radius ?? 0.5) + GLOW, games.partsOf(item.game).glowOf(item)]);
    return spots;
  }

  /** One frame: background, sky (and its displacement), ground, units (and theirs), what draws over them, mouse-over outline. */
  function draw(dt: number): void {
    const gl = viewer.gl;
    viewer.update(dt);
    items.endOneShots();
    // What is under the mouse, the highlight and the rings (features/pick).
    events.emit('frame', { dt });
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.scissor(0, 0, canvas.width, canvas.height);
    gl.depthMask(true);
    gl.clearColor(BACKGROUND[0], BACKGROUND[1], BACKGROUND[2], 1);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    displaced = 0;
    const sky = items.sky();
    if (sky && sky.instance) {
      skyScene.render();
      displaced += afterScene(skyScene);
      // The sky is behind everything: forget its depth.
      gl.depthMask(true);
      gl.clear(gl.DEPTH_BUFFER_BIT);
    }
    ground.draw(scene.camera, camera.target, glowSpots(), camera.distance);
    scene.render();
    displaced += afterScene(scene);
    // Over the units, with their depth: the edges (features/edges).
    events.emit('scene-drawn', { width: canvas.width, height: canvas.height });
    // The mouse-over outline, when the hovered unit is drawn this frame.
    const hovered = selection.hovered();
    if (hovered && hovered.instance.drawn) outline.draw(hovered.instance, canvas.width, canvas.height);
  }

  function setPostPass(id: string, on: boolean): void {
    const pass = postPasses.find((p) => p.id === id);
    if (!pass) throw new Error(`no post pass ${id}`);
    pass.enabled = Boolean(on);
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
    host.resize();
    draw(dt);
    requestAnimationFrame(frame);
  }

  return {
    ...host,
    draw,
    setPostPass,
    displacedBatches: () => displaced,
    start: () => {
      requestAnimationFrame(frame);
    },
  };
}

// SC2 unit viewer, core: the renderer, the scenes, shared state, the camera
// and small helpers. Builds window.SC2App, which the other modules in js/
// extend. Renders with mdx-m3-viewer (global ModelViewer).
'use strict';

(() => {
  const { viewer: lib } = ModelViewer;
  const $ = (id) => document.getElementById(id);
  const canvas = $('view');
  const statusLine = $('status');

  const BACKGROUND = [26 / 255, 26 / 255, 31 / 255];
  const UP = [0, 0, 1];
  const FOV = Math.PI / 4;

  const viewer = new lib.ModelViewer(canvas, { alpha: false, antialias: true });
  viewer.addHandler(lib.handlers.m3);
  viewer.addHandler(lib.handlers.dds);
  viewer.addHandler(lib.handlers.tga);
  // The library reports failures as events. Show them; never drop them.
  viewer.on('error', (e) => {
    console.warn('viewer:', e.error, e.fetchUrl || '', e.reason || '');
    setStatus(`${e.error} ${e.fetchUrl ? decodeURIComponent(e.fetchUrl) : ''}`);
  });
  // Two scenes: the sky, drawn first around a camera at the origin, and the
  // units. draw() clears once, so neither scene clears (alpha = true).
  const skyScene = viewer.addScene();
  skyScene.alpha = true;
  const scene = viewer.addScene();
  scene.alpha = true;
  scene.color.set(BACKGROUND);
  // A far light above and in front of the default camera, a bit to the right.
  scene.lightPosition.set([3000, -6000, 8000]);
  skyScene.lightPosition.set([3000, -6000, 8000]);

  const camera = { yaw: -Math.PI / 2, pitch: 0.5, distance: 9, target: [0, 0, 0.8] };

  function setStatus(text) {
    statusLine.textContent = text;
  }

  /**
   * End of the line for a failed user action (add, drop, pick a sky): the
   * action already put the message in the status line; this also logs it.
   */
  function reportFailure(error) {
    console.warn('sc2viewer:', error);
    setStatus(error.message);
  }

  /** Say so when a loaded model has parts the renderer cannot draw. */
  function reportUndrawn(name, model) {
    if (!model.undrawnBatches.length) return;
    console.warn(`sc2viewer: ${name}: not drawn: ${model.undrawnBatches.join('; ')}`);
    setStatus(`${name}: ${model.undrawnBatches.length} part(s) not drawn (${model.undrawnBatches[0]})`);
  }

  async function getJson(url) {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`${response.status} ${url}`);
    return response.json();
  }

  function el(tag, props = {}, children = []) {
    const node = Object.assign(document.createElement(tag), props);
    node.append(...children);
    return node;
  }

  /** A unit icon, or an empty box when the unit has none. */
  function iconNode(name) {
    return name ? el('img', { className: 'icon', src: '/icon/' + name, alt: '', draggable: false }) : el('span', { className: 'icon none' });
  }

  const shown = (value) => String(Math.round(value * 1000) / 1000);

  // ---- camera ----

  function eye() {
    const { yaw, pitch, distance, target } = camera;
    return [
      target[0] + distance * Math.cos(pitch) * Math.cos(yaw),
      target[1] + distance * Math.cos(pitch) * Math.sin(yaw),
      target[2] + distance * Math.sin(pitch),
    ];
  }

  function applyCamera() {
    const from = eye();
    scene.camera.moveToAndFace(from, camera.target, UP);
    // The sky turns with the camera but never comes closer.
    skyScene.camera.moveToAndFace([0, 0, 0], [camera.target[0] - from[0], camera.target[1] - from[1], camera.target[2] - from[2]], UP);
  }

  function resize() {
    const width = Math.max(1, Math.floor(canvas.clientWidth));
    const height = Math.max(1, Math.floor(canvas.clientHeight));
    if (canvas.width === width && canvas.height === height) return;
    canvas.width = width;
    canvas.height = height;
    for (const s of [scene, skyScene]) {
      s.viewport[2] = width;
      s.viewport[3] = height;
    }
    // SC2 models are a few units tall, so the near plane is close.
    scene.camera.perspective(FOV, width / height, 0.1, 2000);
    // Skyboxes are large models around the origin.
    skyScene.camera.perspective(FOV, width / height, 1, 100000);
  }

  const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  const unit3 = (v) => {
    const length = Math.hypot(v[0], v[1], v[2]);
    return [v[0] / length, v[1] / length, v[2] / length];
  };

  /** The camera's eye and its forward, right and up axes. */
  function basis() {
    const from = eye();
    const forward = unit3([camera.target[0] - from[0], camera.target[1] - from[1], camera.target[2] - from[2]]);
    const right = unit3(cross(forward, UP));
    const up = cross(right, forward);
    return { from, forward, right, up, tan: Math.tan(FOV / 2), aspect: canvas.clientWidth / canvas.clientHeight };
  }

  /** The ray through a canvas pixel (from the top left, in CSS pixels): { from, dir }. */
  function rayAt(px, py) {
    const { from, forward, right, up, tan, aspect } = basis();
    const nx = ((2 * px) / canvas.clientWidth - 1) * tan * aspect;
    const ny = (1 - (2 * py) / canvas.clientHeight) * tan;
    return { from, dir: [0, 1, 2].map((i) => forward[i] + right[i] * nx + up[i] * ny) };
  }

  /** The page pixel [clientX, clientY] a world point lands on, or null behind the camera. The inverse of rayAt. */
  function screenOf(point) {
    const { from, forward, right, up, tan, aspect } = basis();
    const d = [0, 1, 2].map((i) => point[i] - from[i]);
    const depth = d[0] * forward[0] + d[1] * forward[1] + d[2] * forward[2];
    if (depth <= 0) return null;
    const nx = (d[0] * right[0] + d[1] * right[1] + d[2] * right[2]) / depth;
    const ny = (d[0] * up[0] + d[1] * up[1] + d[2] * up[2]) / depth;
    const box = canvas.getBoundingClientRect();
    return [box.left + ((nx / (tan * aspect) + 1) * canvas.clientWidth) / 2, box.top + ((1 - ny / tan) * canvas.clientHeight) / 2];
  }

  /** The ground point (z = 0) under a canvas pixel, or null when the pixel shows sky. */
  function groundAt(px, py) {
    const { from, dir } = rayAt(px, py);
    if (dir[2] >= -1e-6) return null;
    const t = -from[2] / dir[2];
    if (t <= 0) return null;
    return [from[0] + dir[0] * t, from[1] + dir[1] * t];
  }

  /** The ground point under a mouse or drag event, or null. */
  function eventGround(e) {
    const box = canvas.getBoundingClientRect();
    return groundAt(e.clientX - box.left, e.clientY - box.top);
  }

  // ---- what the unit data does to the look ----

  /** The data scale of a unit: actor scale x model scale x creation scale. `pick` chooses inside the model's range. */
  function dataScale(unit, pick) {
    if (!unit) return [1, 1, 1];
    return [0, 1, 2].map((i) => unit.actorScale[i] * (unit.modelScaleMin[i] + (unit.modelScaleMax[i] - unit.modelScaleMin[i]) * pick) * unit.eventScale[i]);
  }

  /**
   * How fast the current animation plays. The model's speed always counts.
   * A walk also runs faster or slower with the unit's speed: it is made for
   * the actor's WalkAnimMoveSpeed.
   */
  function playRate(item) {
    const unit = item.unit;
    if (!unit) return 1;
    let rate = unit.animSpeed * unit.timeScale;
    const sequence = item.model.sequences[item.sequence];
    if (sequence && /^walk/i.test(sequence.name) && unit.speed > 0 && unit.walkAnimMoveSpeed > 0) rate *= unit.speed / unit.walkAnimMoveSpeed;
    return rate;
  }

  /** The index of the stand animation, or the first one, or none. */
  function defaultSequence(model) {
    if (!model.sequences.length) return -1;
    const stand = model.sequences.findIndex((s) => /^stand/i.test(s.name));
    return stand >= 0 ? stand : 0;
  }

  window.SC2App = {
    // renderer
    lib,
    viewer,
    scene,
    skyScene,
    ground: SC2Ground.create(viewer),
    outline: SC2Outline.create(viewer),
    displacement: SC2Displacement.create(viewer),
    canvas,
    // constants
    BACKGROUND,
    TEAMS: 14, // team colours the renderer knows
    // shared state, changed by the modules
    camera,
    /** Items in the scene, in the order they were added. */
    items: [],
    /** Model and unit loads in flight. */
    pending: 0,
    /** The ground point under the mouse, or null when it is off the ground. */
    pointer: null,
    // helpers
    $,
    setStatus,
    reportFailure,
    reportUndrawn,
    getJson,
    el,
    iconNode,
    shown,
    // A model path is fetched as-is. Anything a model asks for (textures) is
    // an in-model path, resolved by the server.
    modelUrl: (path) => '/file?path=' + encodeURIComponent(path),
    pathSolver: (src) => (typeof src === 'string' && !src.startsWith('/') ? '/asset?path=' + encodeURIComponent(src) : src),
    eye,
    applyCamera,
    resize,
    groundAt,
    eventGround,
    rayAt,
    screenOf,
    dataScale,
    playRate,
    defaultSequence,
  };
})();

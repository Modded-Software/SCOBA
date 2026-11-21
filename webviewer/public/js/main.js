// Drawing, the grid glow, the scene in the URL, and startup. Loaded last.
'use strict';

(() => {
  const app = window.SC2App;
  const { viewer, scene, skyScene, canvas, camera, items, ground, BACKGROUND } = app;

  const GLOW = 2.5; // how far the glow reaches past a unit's radius, or from the mouse

  /** Grid glow spots: under the mouse and under each unit. */
  function glowSpots() {
    const spots = app.pointer ? [[app.pointer[0], app.pointer[1], GLOW]] : [];
    for (const item of items) spots.push([item.x, item.y, (item.unit ? item.unit.radius : 0.5) + GLOW]);
    return spots;
  }

  /** One frame: background, sky (and its displacement), ground, units (and theirs), mouse-over outline. */
  function draw(dt) {
    const gl = viewer.gl;
    viewer.update(dt);
    app.endOneShots();
    app.updatePick();
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.scissor(0, 0, canvas.width, canvas.height);
    gl.depthMask(true);
    gl.clearColor(BACKGROUND[0], BACKGROUND[1], BACKGROUND[2], 1);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    // Displacement batches drawn this frame, sky and units (for the tests).
    app.displacedBatches = 0;
    if (app.sky && app.sky.instance) {
      skyScene.render();
      app.displacedBatches += app.displacement.draw(skyScene, canvas.width, canvas.height);
      // The sky is behind everything: forget its depth.
      gl.depthMask(true);
      gl.clear(gl.DEPTH_BUFFER_BIT);
    }
    ground.draw(scene.camera, camera.target, glowSpots());
    scene.render();
    app.displacedBatches += app.displacement.draw(scene, canvas.width, canvas.height);
    // The mouse-over outline, when the hovered unit is drawn this frame.
    const hovered = app.hoveredItem();
    if (hovered && scene.instances.includes(hovered.instance)) app.outline.draw(hovered.instance, canvas.width, canvas.height);
  }
  app.draw = draw;
  /** Draw displacement materials or not (tests compare the two). */
  app.setDisplacement = (on) => {
    app.displacement.enabled = Boolean(on);
  };

  // ---- URL state ----

  app.saveHash = () => {
    const data = items.map((i) => ({ ...(i.unit ? { u: i.unit.id } : { p: i.path }), x: i.x, y: i.y, r: i.rot, s: i.scale, q: i.sequence, t: i.team, k: i.pick }));
    history.replaceState(null, '', data.length ? '#' + encodeURIComponent(JSON.stringify(data)) : location.pathname);
  };

  async function loadHash() {
    if (location.hash.length < 2) return;
    let data;
    try {
      data = JSON.parse(decodeURIComponent(location.hash.slice(1)));
    } catch (error) {
      app.setStatus('bad scene in URL: ' + error.message);
      return;
    }
    if (!Array.isArray(data)) return;
    for (const entry of data) {
      const options = { x: entry.x, y: entry.y, rot: entry.r, scale: entry.s, sequence: entry.q, team: entry.t, pick: entry.k };
      // One after another, so the order is kept.
      if (entry.u) await app.addUnit(entry.u, options).catch(app.reportFailure);
      else if (entry.p) await app.add(entry.p, options).catch(app.reportFailure);
    }
  }

  // ---- frame loop and startup ----

  // Animations advance by the real time since the last frame, so they play
  // at the data's speed on any screen refresh rate. A long gap (hidden tab)
  // counts as at most MAX_STEP.
  const MAX_STEP = 100; // ms
  let lastTime = null;
  function frame(now) {
    const dt = lastTime === null ? 0 : Math.min(now - lastTime, MAX_STEP);
    lastTime = now;
    app.resize();
    draw(dt);
    requestAnimationFrame(frame);
  }

  const api = ['add', 'addUnit', 'remove', 'clear', 'restart', 'state', 'pixels', 'colorStats', 'mark', 'changedSinceMark', 'idle', 'view', 'groundPixel', 'groundPeaks', 'worldToCanvas', 'setGrid', 'setSky', 'screenOf', 'itemScreen', 'pickState', 'setDisplacement'];
  window.sc2viewer = { ready: false, groundUnder: app.groundAt };
  for (const name of api) {
    if (typeof app[name] !== 'function') throw new Error('sc2viewer: module did not define ' + name);
    window.sc2viewer[name] = app[name];
  }

  app.resize();
  app.applyCamera();
  requestAnimationFrame(frame);
  Promise.all([app.setupUnits(), loadHash(), ground.ready, app.outline.ready])
    .catch((error) => app.setStatus(error.message))
    .finally(() => {
      window.sc2viewer.ready = true;
    });
})();

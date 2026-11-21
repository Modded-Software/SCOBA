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

  /** One frame: background, sky, ground, units. */
  function draw(dt) {
    const gl = viewer.gl;
    viewer.update(dt);
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.scissor(0, 0, canvas.width, canvas.height);
    gl.depthMask(true);
    gl.clearColor(BACKGROUND[0], BACKGROUND[1], BACKGROUND[2], 1);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    if (app.sky && app.sky.instance) {
      skyScene.render();
      // The sky is behind everything: forget its depth.
      gl.depthMask(true);
      gl.clear(gl.DEPTH_BUFFER_BIT);
    }
    ground.draw(scene.camera, camera.target, glowSpots());
    scene.render();
  }
  app.draw = draw;

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

  function frame() {
    app.resize();
    draw(1000 / 60);
    requestAnimationFrame(frame);
  }

  const api = ['add', 'addUnit', 'remove', 'clear', 'restart', 'state', 'pixels', 'colorStats', 'mark', 'changedSinceMark', 'idle', 'view', 'groundPixel', 'setGrid', 'setSky'];
  window.sc2viewer = { ready: false, groundUnder: app.groundAt };
  for (const name of api) {
    if (typeof app[name] !== 'function') throw new Error('sc2viewer: module did not define ' + name);
    window.sc2viewer[name] = app[name];
  }

  app.resize();
  app.applyCamera();
  requestAnimationFrame(frame);
  Promise.all([app.setupUnits(), loadHash(), ground.ready])
    .catch((error) => app.setStatus(error.message))
    .finally(() => {
      window.sc2viewer.ready = true;
    });
})();

// Mouse controls: left drag turns the camera, right drag pans, the wheel
// zooms. Tracks the ground point under the mouse for the grid glow.
'use strict';

(() => {
  const app = window.SC2App;
  const { canvas, camera } = app;

  const ROTATE_RATE = 0.004; // radians per pixel of left drag
  const PAN_RATE = 0.0006; // camera distances per pixel of right drag

  canvas.addEventListener('mousemove', (e) => {
    app.pointer = app.eventGround(e);
  });
  canvas.addEventListener('mouseleave', () => {
    app.pointer = null;
  });

  let drag = null;
  canvas.addEventListener('contextmenu', (e) => e.preventDefault());
  canvas.addEventListener('mousedown', (e) => {
    drag = { button: e.button, x: e.clientX, y: e.clientY };
    e.preventDefault();
  });
  window.addEventListener('mouseup', () => {
    drag = null;
  });
  window.addEventListener('mousemove', (e) => {
    if (!drag) return;
    const dx = e.clientX - drag.x;
    const dy = e.clientY - drag.y;
    drag.x = e.clientX;
    drag.y = e.clientY;
    if (drag.button === 0) {
      const limit = Math.PI / 2 - 0.01;
      camera.yaw -= dx * ROTATE_RATE;
      camera.pitch = Math.min(limit, Math.max(-limit, camera.pitch + dy * ROTATE_RATE));
    } else {
      const k = camera.distance * PAN_RATE;
      const { yaw, pitch } = camera;
      const right = [-Math.sin(yaw), Math.cos(yaw), 0];
      const up = [-Math.sin(pitch) * Math.cos(yaw), -Math.sin(pitch) * Math.sin(yaw), Math.cos(pitch)];
      for (let i = 0; i < 3; i++) camera.target[i] += (-dx * right[i] + dy * up[i]) * k;
    }
    app.applyCamera();
  });
  canvas.addEventListener(
    'wheel',
    (e) => {
      e.preventDefault();
      camera.distance = Math.min(2000, Math.max(0.5, camera.distance * Math.exp(e.deltaY * 0.001)));
      app.applyCamera();
    },
    { passive: false },
  );

  /** Set the camera: any of yaw, pitch, distance, target. */
  app.view = (next) => {
    Object.assign(camera, next);
    if (next.target) camera.target = [...next.target];
    app.applyCamera();
  };
})();

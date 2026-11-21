// Landmarks: named camera views to jump back to (the view tools select).
// "origin" (looking at 0, 0, 0) is always there. "add all" adds one per run,
// framing its new block and named after the unit list filters.
'use strict';

(() => {
  const app = window.SC2App;
  const { camera, el } = app;
  const select = app.$('landmarks');

  const ORIGIN = { name: 'origin (0, 0, 0)', target: [0, 0, 0], yaw: -Math.PI / 2, pitch: 0.5, distance: 9 };
  const PAD = 0.04; // share of the visible area kept free around a framed box
  const MIN_DISTANCE = 1;
  const MAX_DISTANCE = 2000; // controls.js

  const list = [];
  let nextId = 0;

  function render(selectedId) {
    select.replaceChildren(...list.map((l) => el('option', { value: String(l.id), textContent: l.name })));
    if (selectedId !== undefined) select.value = String(selectedId);
  }

  /** Add a landmark ({ name, target, yaw, pitch, distance }); a taken name gets " (2)", " (3)"... Returns its id. */
  function addLandmark(view) {
    let name = view.name;
    for (let n = 2; list.some((l) => l.name === name); n++) name = `${view.name} (${n})`;
    const landmark = { id: nextId++, name, target: [...view.target], yaw: view.yaw, pitch: view.pitch, distance: view.distance };
    list.push(landmark);
    render(landmark.id);
    return landmark.id;
  }

  function goToLandmark(id) {
    const l = list.find((x) => x.id === id);
    if (!l) throw new Error(`no landmark ${id}`);
    app.view({ target: [...l.target], yaw: l.yaw, pitch: l.pitch, distance: l.distance });
    select.value = String(id);
  }

  select.addEventListener('change', () => goToLandmark(Number(select.value)));

  /** The part of the canvas no panel covers, in page pixels. */
  function visibleRect() {
    const canvas = app.canvas.getBoundingClientRect();
    const side = app.$('side').getBoundingClientRect();
    return { left: Math.max(canvas.left, side.right), right: canvas.right, top: canvas.top, bottom: canvas.bottom };
  }

  /** Whether every point lands inside the rect, PAD kept free. */
  function fits(points, r) {
    const px = (r.right - r.left) * PAD;
    const py = (r.bottom - r.top) * PAD;
    return points.every((p) => {
      const s = app.screenOf(p);
      return s && s[0] >= r.left + px && s[0] <= r.right - px && s[1] >= r.top + py && s[1] <= r.bottom - py;
    });
  }

  /** The least distance (binary search) at which the points fit; the camera is left there. */
  function fitDistance(points, r) {
    let low = MIN_DISTANCE;
    let high = MAX_DISTANCE;
    app.view({ distance: high });
    if (!fits(points, r)) return high;
    for (let i = 0; i < 50; i++) {
      const mid = (low + high) / 2;
      app.view({ distance: mid });
      if (fits(points, r)) high = mid;
      else low = mid;
    }
    app.view({ distance: high });
    return high;
  }

  /**
   * Point the camera at a ground box { x0, x1, y0, y1, z } (z: the height to
   * keep in view), at the current yaw and pitch, and back off until the box
   * fits the uncovered part of the canvas. Returns the view.
   */
  function frameBox(box) {
    const centre = [(box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2, 0];
    const points = [];
    for (const x of [box.x0, box.x1]) for (const y of [box.y0, box.y1]) for (const z of [0, box.z || 0]) points.push([x, y, z]);
    const r = visibleRect();
    app.view({ target: centre });
    fitDistance(points, r);
    // The panel covers the left: move the target so the box centre lands
    // in the middle of the uncovered part, then fit again.
    const canvas = app.canvas.getBoundingClientRect();
    const under = app.groundAt((r.left + r.right) / 2 - canvas.left, (r.top + r.bottom) / 2 - canvas.top);
    if (under) {
      app.view({ target: [camera.target[0] + centre[0] - under[0], camera.target[1] + centre[1] - under[1], 0] });
      fitDistance(points, r);
    }
    return { target: [...camera.target], yaw: camera.yaw, pitch: camera.pitch, distance: camera.distance };
  }

  // Kinds as a plural noun; any other kind takes an "s".
  const PLURAL = { Hero: 'Heroes', Other: 'Other Units', Unit: 'Units' };

  /**
   * A human readable name for the unit list filters, read like a phrase:
   * race, family, kind (plural), then the search, e.g. 'Terran Campaign
   * Units', 'Zerg Melee Units "drone"', 'Structures (no family)'.
   */
  function filterName(query) {
    const words = [];
    if (query.race) words.push(query.race);
    if (query.family) words.push(query.family);
    words.push(query.kind ? PLURAL[query.kind] ?? `${query.kind}s` : 'Units');
    if (!query.race && !query.family && !query.kind && !query.q && query.family !== '') words.unshift('All');
    if (query.family === '') words.push('(no family)');
    if (query.q) words.push(`"${query.q}"`);
    return words.join(' ');
  }

  addLandmark(ORIGIN);

  Object.assign(app, {
    addLandmark,
    goToLandmark,
    frameBox,
    filterName,
    visibleRect,
    landmarks: () => list.map((l) => ({ ...l, target: [...l.target] })),
  });
})();

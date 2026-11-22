// Landmarks: named camera views to jump back to (the view tools drop-down).
// - "origin" (looking at 0, 0, 0) is always there and cannot be deleted.
// - The pin button saves the current view as a landmark, after asking a name.
// - "add all" adds one per run, framing its new block and named after the
//   list filters.
// - Each landmark of the list has a trash button; it asks before deleting.
// - The landmarks and the one chosen are kept in localStorage.
'use strict';

(() => {
  const app = window.SC2App;
  const { camera, el } = app;
  const button = app.$('landmarks-button');
  const pinButton = app.$('landmark-pin');
  const listNode = app.$('landmarks-list');

  const ORIGIN_ID = 0;
  const ORIGIN = { id: ORIGIN_ID, name: 'origin (0, 0, 0)', target: [0, 0, 0], yaw: -Math.PI / 2, pitch: 0.5, distance: 9 };
  const PAD = 0.04; // share of the visible area kept free around a framed box
  const MIN_DISTANCE = 1;
  const MAX_DISTANCE = 2000; // controls.js
  const KEY = 'sc2viewer.landmarks';
  const TRASH = '<svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true"><path fill="currentColor" d="M6 1h4l1 1h3v2H2V2h3zM3 5h10l-1 10H4zm3 2v6h1V7zm3 0v6h1V7z"/></svg>';

  const list = [ORIGIN];
  let nextId = ORIGIN_ID + 1;
  /** The landmark chosen last, or null. */
  let selected = null;
  /** 'none' (nothing stored), 'restored', or 'refused: <why>'. */
  let restore = 'none';

  const finite = (n) => typeof n === 'number' && Number.isFinite(n);

  /** A stored landmark, checked. */
  function parseLandmark(l) {
    if (!l || !Number.isInteger(l.id) || l.id <= ORIGIN_ID || typeof l.name !== 'string' || !l.name) throw new Error('not a landmark');
    if (![l.yaw, l.pitch, l.distance].every(finite) || !Array.isArray(l.target) || l.target.length !== 3 || !l.target.every(finite)) throw new Error(`"${l.name}" is not a view`);
    if (l.distance <= 0) throw new Error(`"${l.name}" has distance ${l.distance}`);
    return { id: l.id, name: l.name, target: [...l.target], yaw: l.yaw, pitch: l.pitch, distance: l.distance };
  }

  function load() {
    const text = localStorage.getItem(KEY);
    if (text === null) return;
    try {
      const stored = JSON.parse(text);
      if (!stored || !Array.isArray(stored.list)) throw new Error('no landmark list');
      const parsed = stored.list.map(parseLandmark);
      if (new Set(parsed.map((l) => l.id)).size !== parsed.length) throw new Error('an id is used twice');
      list.push(...parsed);
      nextId = Math.max(ORIGIN_ID, ...parsed.map((l) => l.id)) + 1;
      selected = list.some((l) => l.id === stored.selected) ? stored.selected : null;
      restore = 'restored';
    } catch (error) {
      restore = `refused: ${error.message}`;
      console.warn(`sc2viewer: stored landmarks ${restore}`);
    }
  }

  function save() {
    localStorage.setItem(KEY, JSON.stringify({ list: list.filter((l) => l.id !== ORIGIN_ID), selected }));
  }

  // ---- the drop-down list ----

  const dropdown = new SC2Components.Dropdown({ root: app.$('landmarks'), button, list: listNode });
  const closeList = () => dropdown.close();

  function render() {
    const chosen = list.find((l) => l.id === selected);
    button.textContent = chosen ? chosen.name : 'landmarks';
    listNode.replaceChildren(
      ...list.map((l) => {
        const go = el('button', { className: 'go', textContent: l.name, title: 'go to this view' });
        go.addEventListener('click', () => {
          goToLandmark(l.id);
          closeList();
        });
        const row = el('li', {}, [go]);
        row.dataset.id = String(l.id);
        row.classList.toggle('selected', l.id === selected);
        if (l.id !== ORIGIN_ID) {
          const trash = el('button', { className: 'trash', title: `delete "${l.name}"`, innerHTML: TRASH });
          trash.addEventListener('click', () => {
            closeList();
            askDelete(l).catch(app.reportFailure);
          });
          row.append(trash);
        }
        return row;
      }),
    );
  }


  /** Add a landmark ({ name, target, yaw, pitch, distance }); a taken name gets " (2)", " (3)"... It becomes the chosen one. Returns its id. */
  function addLandmark(view) {
    let name = view.name;
    for (let n = 2; list.some((l) => l.name === name); n++) name = `${view.name} (${n})`;
    const landmark = { id: nextId++, name, target: [...view.target], yaw: view.yaw, pitch: view.pitch, distance: view.distance };
    list.push(landmark);
    selected = landmark.id;
    save();
    render();
    return landmark.id;
  }

  function goToLandmark(id) {
    const l = list.find((x) => x.id === id);
    if (!l) throw new Error(`no landmark ${id}`);
    app.view({ target: [...l.target], yaw: l.yaw, pitch: l.pitch, distance: l.distance });
    selected = id;
    save();
    render();
  }

  /** Delete a landmark. The camera stays; a deleted chosen one leaves none chosen. */
  function removeLandmark(id) {
    if (id === ORIGIN_ID) throw new Error('the origin landmark cannot be deleted');
    const at = list.findIndex((l) => l.id === id);
    if (at < 0) throw new Error(`no landmark ${id}`);
    list.splice(at, 1);
    if (selected === id) selected = null;
    save();
    render();
  }

  // ---- dialogs: name a new landmark, confirm a delete ----

  const question = el('div', { className: 'question' });
  const deleteDialog = new SC2Components.ConfirmDialog({ id: 'landmark-delete-dialog', title: 'delete landmark', yesText: 'delete', content: [question] });

  async function askDelete(landmark) {
    question.textContent = `Delete the landmark "${landmark.name}"?`;
    const asking = deleteDialog.ask();
    deleteDialog.no.focus();
    if (await asking) removeLandmark(landmark.id);
  }

  const nameBox = el('input', { id: 'landmark-name', type: 'text', autocomplete: 'off', spellcheck: false, maxLength: 60 });
  const nameDialog = new SC2Components.ConfirmDialog({ id: 'landmark-name-dialog', title: 'new landmark: this view', yesText: 'save', content: [nameBox] });
  nameDialog.yes.id = 'landmark-save';
  nameDialog.no.id = 'landmark-cancel';
  const nameOk = () => nameBox.value.trim().length > 0;
  nameBox.addEventListener('input', () => {
    nameDialog.yes.disabled = !nameOk();
  });
  nameBox.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && nameOk()) nameDialog.settle(true);
  });

  /** The pin button: ask a name, then keep the view as it was when the button was pressed. */
  async function pin() {
    const view = { target: [...camera.target], yaw: camera.yaw, pitch: camera.pitch, distance: camera.distance };
    let n = 1;
    while (list.some((l) => l.name === `landmark ${n}`)) n++;
    nameBox.value = `landmark ${n}`;
    nameDialog.yes.disabled = false;
    const asking = nameDialog.ask();
    nameBox.focus();
    nameBox.select();
    if (await asking) addLandmark({ name: nameBox.value.trim(), ...view });
  }
  pinButton.addEventListener('click', () => {
    closeList();
    pin().catch(app.reportFailure);
  });

  // The part of the canvas no open panel covers: app.visibleRect (core.js).
  const visibleRect = () => app.visibleRect();

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

  load();
  render();

  Object.assign(app, {
    addLandmark,
    goToLandmark,
    removeLandmark,
    /** For the tests: the landmarks, the chosen one, and how the stored ones loaded. */
    landmarkState: () => ({ list: list.map((l) => ({ ...l, target: [...l.target] })), selected, restore }),
    frameBox,
    filterName,
    landmarks: () => list.map((l) => ({ ...l, target: [...l.target] })),
  });
})();

// Drag a unit or a doodad from its list into the view. While dragged, a
// preview (the ghost) stands on the ground under the pointer; a drop adds
// the unit or doodad there, looking as the preview did.
'use strict';

(() => {
  const app = window.SC2App;
  const { canvas, scene, viewer } = app;

  // One drag type per kind of record; the data is the record's id.
  const DRAG_TYPES = { unit: 'application/x-sc2-unit', doodad: 'application/x-sc2-doodad' };

  /** While a record is dragged: { kind, id, unit, instance, pick, variation, rot, at }; otherwise null. */
  let ghost = null;

  /** Load the dragged record's model, hidden until the drag is over the ground. */
  async function startGhost(kind, id) {
    endGhost();
    const mine = { kind, id, unit: null, instance: null, pick: Math.random(), variation: null, rot: 0, at: null };
    ghost = mine;
    app.pending++;
    try {
      const unit = await app.record(kind, id);
      // A skybox unit is not placed (a drop sets it as the sky): no preview.
      if (unit.skybox) return;
      // A doodad's variation and angle are chosen now, so the drop matches the preview.
      if (kind === 'doodad') Object.assign(mine, app.doodadPlacement(unit));
      const file = kind === 'doodad' ? unit.files[mine.variation] : unit.file;
      const model = await viewer.load(app.modelUrl(file, unit.dataset), app.pathSolver(unit.dataset));
      if (ghost !== mine) return; // the drag ended meanwhile
      if (!model) throw new Error('cannot load ' + file);
      const instance = model.addInstance();
      const sequence = app.defaultSequence(model);
      instance.setSequence(sequence);
      instance.setSequenceLoopMode(2);
      instance.timeScale = app.playRate({ unit, model, sequence });
      instance.setScale(app.dataScale(unit, mine.pick));
      const half = (mine.rot * Math.PI) / 360;
      instance.setRotation([0, 0, Math.sin(half), Math.cos(half)]);
      instance.setTeamColor(0);
      instance.hide();
      scene.addInstance(instance);
      Object.assign(mine, { unit, instance });
      placeGhost();
    } catch (error) {
      app.setStatus(error.message, { failure: true });
      throw error;
    } finally {
      app.pending--;
    }
  }

  /** Show the preview at its ground point, or hide it when it has none. */
  function placeGhost() {
    if (!ghost || !ghost.instance) return;
    if (!ghost.at) {
      ghost.instance.hide();
      return;
    }
    ghost.instance.setLocation([ghost.at[0], ghost.at[1], app.baseHeight(ghost.unit)]);
    ghost.instance.show();
  }

  function endGhost() {
    if (ghost && ghost.instance) ghost.instance.detach();
    ghost = null;
  }

  /** dragstart on a list row: `kind` is 'unit' or 'doodad'. */
  function startDrag(e, record, kind = 'unit') {
    e.dataTransfer.setData(DRAG_TYPES[kind], record.id);
    e.dataTransfer.setData('text/plain', record.name);
    e.dataTransfer.effectAllowed = 'copy';
    startGhost(kind, record.id).catch(app.reportFailure);
  }

  // Drop a unit or doodad on the view: it lands on the ground under the pointer.
  /** The kind of record a drag carries ('unit', 'doodad'), or null for any other drag. */
  function carried(e) {
    if (!e.dataTransfer) return null;
    const types = [...e.dataTransfer.types];
    return Object.keys(DRAG_TYPES).find((kind) => types.includes(DRAG_TYPES[kind])) ?? null;
  }
  canvas.addEventListener('dragover', (e) => {
    if (!carried(e)) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
    canvas.classList.add('drop');
    app.pointer = app.eventGround(e);
    if (ghost) {
      ghost.at = app.pointer;
      placeGhost();
    }
  });
  canvas.addEventListener('dragleave', () => {
    canvas.classList.remove('drop');
    app.pointer = null;
    if (ghost) {
      ghost.at = null;
      placeGhost();
    }
  });
  canvas.addEventListener('drop', (e) => {
    canvas.classList.remove('drop');
    const kind = carried(e);
    if (!kind) return;
    e.preventDefault();
    // The preview's choices, when it got as far as making them.
    const seen = ghost && ghost.unit ? ghost : null;
    const pick = ghost ? ghost.pick : undefined;
    endGhost();
    const point = app.eventGround(e);
    if (!point) {
      app.setStatus('drop it on the ground, not above the horizon');
      return;
    }
    const id = e.dataTransfer.getData(DRAG_TYPES[kind]);
    // The same scale pick as the preview (and a doodad's variation and
    // angle), so it looks as it did.
    if (kind === 'doodad') {
      const placement = seen ? { variation: seen.variation, rot: seen.rot } : {};
      app.addDoodad(id, { x: point[0], y: point[1], pick, ...placement }).catch(app.reportFailure);
    } else app.addUnit(id, { x: point[0], y: point[1], pick }).catch(app.reportFailure);
  });

  /** The drag preview, for the tests: null when nothing is dragged. */
  function ghostState() {
    if (!ghost) return null;
    return {
      kind: ghost.kind,
      unit: ghost.id,
      variation: ghost.variation,
      rot: ghost.rot,
      loaded: Boolean(ghost.instance),
      shown: Boolean(ghost.instance && ghost.instance.rendered),
      location: ghost.instance ? Array.from(ghost.instance.localLocation) : null,
    };
  }

  Object.assign(app, { startDrag, endGhost, ghostState });
})();

// Drag a unit from the list into the view. While dragged, a preview (the
// ghost) stands on the ground under the pointer; a drop adds the unit there.
'use strict';

(() => {
  const app = window.SC2App;
  const { canvas, scene, viewer } = app;

  const DRAG_TYPE = 'application/x-sc2-unit';

  /** While a unit is dragged: { id, unit, instance, pick, at }; otherwise null. */
  let ghost = null;

  /** Load the dragged unit's model, hidden until the drag is over the ground. */
  async function startGhost(id) {
    endGhost();
    const mine = { id, unit: null, instance: null, pick: Math.random(), at: null };
    ghost = mine;
    app.pending++;
    try {
      const unit = await app.getJson('/api/unit?id=' + encodeURIComponent(id));
      // A skybox unit is not placed (a drop sets it as the sky): no preview.
      if (unit.skybox) return;
      const model = await viewer.load(app.modelUrl(unit.file), app.pathSolver);
      if (ghost !== mine) return; // the drag ended meanwhile
      if (!model) throw new Error('cannot load ' + unit.file);
      const instance = model.addInstance();
      const sequence = app.defaultSequence(model);
      instance.setSequence(sequence);
      instance.setSequenceLoopMode(2);
      instance.timeScale = app.playRate({ unit, model, sequence });
      instance.setScale(app.dataScale(unit, mine.pick));
      instance.setTeamColor(0);
      instance.hide();
      scene.addInstance(instance);
      Object.assign(mine, { unit, instance });
      placeGhost();
    } catch (error) {
      app.setStatus(error.message);
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
    ghost.instance.setLocation([ghost.at[0], ghost.at[1], ghost.unit.height]);
    ghost.instance.show();
  }

  function endGhost() {
    if (ghost && ghost.instance) ghost.instance.detach();
    ghost = null;
  }

  /** dragstart on a unit row. */
  function startDrag(e, unit) {
    e.dataTransfer.setData(DRAG_TYPE, unit.id);
    e.dataTransfer.setData('text/plain', unit.name);
    e.dataTransfer.effectAllowed = 'copy';
    startGhost(unit.id).catch(app.reportFailure);
  }

  // Drop a unit on the view: it lands on the ground under the pointer.
  const carriesUnit = (e) => e.dataTransfer && [...e.dataTransfer.types].includes(DRAG_TYPE);
  canvas.addEventListener('dragover', (e) => {
    if (!carriesUnit(e)) return;
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
    if (!carriesUnit(e)) return;
    e.preventDefault();
    const pick = ghost ? ghost.pick : undefined;
    endGhost();
    const point = app.eventGround(e);
    if (!point) {
      app.setStatus('drop it on the ground, not above the horizon');
      return;
    }
    // The same scale pick as the preview, so the unit looks as it did.
    app.addUnit(e.dataTransfer.getData(DRAG_TYPE), { x: point[0], y: point[1], pick }).catch(app.reportFailure);
  });

  /** The drag preview, for the tests: null when nothing is dragged. */
  function ghostState() {
    if (!ghost) return null;
    return {
      unit: ghost.id,
      loaded: Boolean(ghost.instance),
      shown: Boolean(ghost.instance && ghost.instance.rendered),
      location: ghost.instance ? Array.from(ghost.instance.localLocation) : null,
    };
  }

  Object.assign(app, { startDrag, endGhost, ghostState });
})();

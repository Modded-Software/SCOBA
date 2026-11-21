// Scene items: add, remove, clear, and the scene list in the side panel.
'use strict';

(() => {
  const app = window.SC2App;
  const { viewer, scene, items, el, shown, TEAMS } = app;
  const sceneList = app.$('scene');

  const REACH = 1.25; // half the room a model with no unit data takes in a row
  let nextId = 1;

  function applyTransform(item) {
    const half = (item.rot * Math.PI) / 360;
    item.instance.setLocation([item.x, item.y, item.unit ? item.unit.height : 0]);
    item.instance.setRotation([0, 0, Math.sin(half), Math.cos(half)]);
    item.instance.setScale(item.dataScale.map((v) => v * item.scale));
  }

  /** Play the item's own (idle) animation, looping. Ends a one-shot. */
  function applySequence(item) {
    item.oneShot = null;
    item.instance.setSequence(item.sequence);
    item.instance.setSequenceLoopMode(2);
    item.instance.timeScale = app.playRate(item);
  }

  /** Play one animation once; then the item goes back to its own (see endOneShots). */
  function playOnce(item, sequence) {
    item.oneShot = sequence;
    item.instance.setSequence(sequence);
    item.instance.setSequenceLoopMode(1); // never loop
    item.instance.timeScale = app.playRate({ unit: item.unit, model: item.model, sequence });
  }

  /** Make an animation the item's own: it loops; the list row and the URL show it. */
  function loopSequence(item, sequence) {
    item.sequence = sequence;
    applySequence(item);
    const select = sceneList.querySelector(`li[data-id="${item.id}"] select.anim`);
    if (select) select.value = String(sequence);
    app.saveHash();
  }

  /** After each update: items whose one-shot has ended go back to their own animation. */
  function endOneShots() {
    for (const item of items) if (item.oneShot !== null && item.instance.sequenceEnded) applySequence(item);
  }

  function applyLook(item) {
    item.instance.setTeamColor(item.team);
    const tint = item.unit && item.unit.tint;
    item.instance.setVertexColor(tint ? [tint[0], tint[1], tint[2], 1] : [1, 1, 1, 1]);
  }

  const reach = (unit) => (unit ? Math.max(REACH, unit.radius + 0.5) : REACH);

  /** Where the next one goes: in a row, clear of the rightmost one. */
  function nextX(unit) {
    return items.length ? Math.max(...items.map((item) => item.x + reach(item.unit))) + reach(unit) : 0;
  }

  /** Add a model file, or a unit when `options.unit` is a unit record. */
  async function add(path, options = {}) {
    app.pending++;
    app.setStatus('loading ' + (options.unit ? options.unit.name : path));
    try {
      const model = await viewer.load(app.modelUrl(path), app.pathSolver);
      if (!model) throw new Error('cannot load ' + path);
      const unit = options.unit || null;
      const pick = options.pick ?? Math.random();
      const item = {
        id: nextId++,
        path,
        unit,
        model,
        instance: model.addInstance(),
        x: options.x ?? nextX(unit),
        y: options.y ?? 0,
        rot: options.rot ?? 0,
        scale: options.scale ?? 1,
        sequence: options.sequence ?? app.defaultSequence(model),
        team: options.team ?? 0,
        pick,
        dataScale: app.dataScale(unit, pick),
        oneShot: null, // the animation played once from the menu, or null
      };
      if (item.sequence < -1 || item.sequence >= model.sequences.length) item.sequence = -1;
      if (!(item.team >= 0 && item.team < TEAMS)) item.team = 0;
      applyTransform(item);
      applySequence(item);
      applyLook(item);
      scene.addInstance(item.instance);
      items.push(item);
      renderList();
      app.saveHash();
      app.setStatus('');
      app.reportUndrawn(unit ? unit.name : path, model);
      return item.id;
    } catch (error) {
      app.setStatus(error.message);
      throw error;
    } finally {
      app.pending--;
    }
  }

  /** Add a unit by id, with everything its data says about its look. */
  async function addUnit(id, options = {}) {
    app.pending++;
    try {
      const unit = await app.getJson('/api/unit?id=' + encodeURIComponent(id));
      return await add(unit.file, { ...options, unit });
    } catch (error) {
      app.setStatus(error.message);
      throw error;
    } finally {
      app.pending--;
    }
  }

  function remove(id) {
    const at = items.findIndex((item) => item.id === id);
    if (at < 0) return;
    items[at].instance.detach();
    items.splice(at, 1);
    app.forget(id);
    renderList();
    app.saveHash();
  }

  function clear() {
    for (const item of items) item.instance.detach();
    items.length = 0;
    app.forget(null);
    renderList();
    app.saveHash();
  }

  /** Start every animation again from its first frame. */
  function restart() {
    for (const item of items) applySequence(item);
  }

  // ---- scene list ----

  function numberInput(item, field, step) {
    const input = el('input', { type: 'number', className: field, step: String(step), value: shown(item[field]) });
    input.addEventListener('change', () => {
      const value = Number.parseFloat(input.value);
      if (!Number.isFinite(value) || (field === 'scale' && value <= 0)) {
        input.value = shown(item[field]);
        return;
      }
      item[field] = value;
      applyTransform(item);
      app.saveHash();
    });
    return el('label', {}, [field, input]);
  }

  function listRow(item) {
    const name = item.unit ? item.unit.name : item.path.split('\\').pop();
    const removeButton = el('button', { className: 'remove', textContent: 'x', title: 'remove' });
    removeButton.addEventListener('click', () => remove(item.id));
    const anim = el('select', { className: 'anim' }, [
      el('option', { value: '-1', textContent: '(none)' }),
      ...item.model.sequences.map((s, i) => el('option', { value: String(i), textContent: s.name })),
    ]);
    anim.value = String(item.sequence);
    anim.addEventListener('change', () => {
      item.sequence = Number.parseInt(anim.value, 10);
      applySequence(item);
      app.saveHash();
    });
    const team = el(
      'select',
      { className: 'team', title: 'team colour' },
      Array.from({ length: TEAMS }, (_, i) => el('option', { value: String(i), textContent: 'team ' + (i + 1) })),
    );
    team.value = String(item.team);
    team.addEventListener('change', () => {
      item.team = Number.parseInt(team.value, 10);
      applyLook(item);
      app.saveHash();
    });
    const head = [el('span', { className: 'name', textContent: name, title: item.unit ? `${item.unit.id}  ${item.path}` : item.path }), removeButton];
    if (item.unit) head.unshift(app.iconNode(item.unit.icon));
    const row = el('li', {}, [
      el('div', { className: 'head' }, head),
      el('div', { className: 'row' }, [anim, team]),
      el('div', { className: 'row' }, [numberInput(item, 'x', 0.5), numberInput(item, 'y', 0.5), numberInput(item, 'rot', 15), numberInput(item, 'scale', 0.1)]),
    ]);
    row.dataset.id = String(item.id);
    if (item.unit) row.dataset.unit = item.unit.id;
    return row;
  }

  function renderList() {
    sceneList.replaceChildren(...items.map(listRow));
  }

  app.$('clear').addEventListener('click', clear);

  /** Turn an item to `rot` degrees and show it in its list row. */
  function setRotation(item, rot) {
    item.rot = rot;
    applyTransform(item);
    const input = sceneList.querySelector(`li[data-id="${item.id}"] input.rot`);
    if (input) input.value = shown(rot);
  }

  Object.assign(app, { add, addUnit, remove, clear, restart, playOnce, loopSequence, endOneShots, setRotation });
})();

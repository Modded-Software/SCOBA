// Scene items (units, doodads, bare model files): add, remove, clear, and
// the scene list in the instances panel, where the selected item's row is
// marked. An item's `unit` is its data record: a unit's, or a doodad's
// (`unit.doodad` true), or null for a bare model file. An item's `dataset`
// is where that record and the model's textures come from (datasets.js).
'use strict';

(() => {
  const app = window.SC2App;
  const { viewer, scene, items, el, shown, TEAMS } = app;
  const sceneList = app.$('scene');

  const REACH = 1.25; // half the room a model with no unit data takes in a row
  let nextId = 1;

  function applyTransform(item) {
    const half = (item.rot * Math.PI) / 360;
    item.instance.setLocation([item.x, item.y, app.baseHeight(item.unit)]);
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

  /**
   * Add a model file, or a unit when `options.unit` is a unit record.
   * `options.dataset`: where its textures (and the record) come from;
   * the current dataset when not given.
   */
  async function add(path, options = {}) {
    app.pending++;
    app.setStatus('loading ' + (options.unit ? options.unit.name : path));
    try {
      const dataset = app.requireDataset(options.dataset ?? app.dataset());
      const model = await viewer.load(app.modelUrl(path, dataset), app.pathSolver(dataset));
      if (!model) throw new Error('cannot load ' + path);
      const unit = options.unit || null;
      const pick = options.pick ?? Math.random();
      const item = {
        id: nextId++,
        path,
        dataset,
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
        // Which of a doodad's model variations this is; null for a unit or a bare model.
        variation: unit && unit.doodad ? options.variation : null,
        dataScale: app.dataScale(unit, pick),
        oneShot: null, // the animation played once from the menu, or null
        // The HD texture set, where the model has one (hd.js); hdLayers: how many layers have both.
        hd: options.hd ?? true,
        hdLayers: 0,
        largestTexture: 0,
      };
      if (item.sequence < -1 || item.sequence >= model.sequences.length) item.sequence = -1;
      if (!(item.team >= 0 && item.team < TEAMS)) item.team = 0;
      applyTransform(item);
      applySequence(item);
      applyLook(item);
      await app.applyHd(item);
      scene.addInstance(item.instance);
      items.push(item);
      renderList();
      app.saveHash();
      app.setStatus('');
      app.reportUndrawn(unit ? unit.name : path, model);
      return item.id;
    } catch (error) {
      app.setStatus(error.message, { failure: true });
      throw error;
    } finally {
      app.pending--;
    }
  }

  /**
   * Add a unit by id, with everything its data says about its look. A unit
   * whose model is a skybox (server markSkyboxUnits) becomes the sky
   * instead; it is not placed, and the result is null.
   */
  async function addUnit(id, options = {}) {
    app.pending++;
    try {
      const dataset = app.requireDataset(options.dataset ?? app.dataset());
      const unit = await app.record('unit', id, dataset);
      if (unit.skybox) {
        await app.setSky({ id: unit.id, name: unit.name, file: unit.file });
        app.setStatus(`${unit.name} is a skybox: set as the sky`);
        return null;
      }
      return await add(unit.file, { ...options, unit, dataset });
    } catch (error) {
      app.setStatus(error.message, { failure: true });
      throw error;
    } finally {
      app.pending--;
    }
  }

  /** A whole variation number inside the doodad's range, or null when `value` is not one. */
  function validVariation(doodad, value) {
    return Number.isInteger(value) && value >= 0 && value < doodad.variations ? value : null;
  }

  /**
   * What the map editor decides when it places a doodad: which model
   * variation, and the angle. The angle is random unless the doodad's data
   * forbids it (EditorFlags NoAutoRotate, or CanRotate off). Given options win.
   */
  function doodadPlacement(doodad, options = {}) {
    const variation = validVariation(doodad, options.variation) ?? Math.floor(Math.random() * doodad.variations);
    const rot = options.rot ?? (doodad.autoRotate ? Math.floor(Math.random() * 360) : 0);
    return { variation, rot };
  }

  /**
   * Add a doodad by id: one of its model variations, at its data scale
   * (random inside RandomScaleRange by `options.pick`), turned as the
   * editor would turn it.
   */
  async function addDoodad(id, options = {}) {
    app.pending++;
    try {
      const dataset = app.requireDataset(options.dataset ?? app.dataset());
      const doodad = await app.record('doodad', id, dataset);
      const placement = doodadPlacement(doodad, options);
      return await add(doodad.files[placement.variation], { ...options, ...placement, unit: doodad, dataset });
    } catch (error) {
      app.setStatus(error.message, { failure: true });
      throw error;
    } finally {
      app.pending--;
    }
  }

  /**
   * Give a placed item another model file, record, dataset or variation
   * (`next`: any of path, unit, dataset, variation). Its id, place, angle,
   * own scale, team and scale pick stay; the data scale follows the record.
   * It keeps playing its animation when the new model has one of that name.
   */
  async function swapModel(item, next) {
    app.pending++;
    try {
      const { path = item.path, unit = item.unit, dataset = item.dataset, variation = item.variation } = next;
      const model = await viewer.load(app.modelUrl(path, dataset), app.pathSolver(dataset));
      if (!model) throw new Error('cannot load ' + path);
      // Removed while the model loaded: nothing to swap.
      if (!items.includes(item)) return;
      const playing = item.sequence >= 0 ? item.model.sequences[item.sequence].name : null;
      const same = playing === null ? -1 : model.sequences.findIndex((s) => s.name === playing);
      item.instance.detach();
      Object.assign(item, { path, unit, dataset, variation, model, instance: model.addInstance(), sequence: same >= 0 ? same : app.defaultSequence(model), dataScale: app.dataScale(unit, item.pick) });
      applyTransform(item);
      applySequence(item);
      applyLook(item);
      await app.applyHd(item);
      scene.addInstance(item.instance);
      renderList();
      app.saveHash();
      app.reportUndrawn(unit ? unit.name : path, model);
    } catch (error) {
      app.setStatus(error.message, { failure: true });
      throw error;
    } finally {
      app.pending--;
    }
  }

  /** Swap a placed doodad to another of its model variations; place, angle and scale stay. */
  async function setVariation(item, variation) {
    const doodad = item.unit;
    if (!doodad || !doodad.doodad) throw new Error(`item ${item.id} is not a doodad`);
    if (validVariation(doodad, variation) === null) throw new Error(`${doodad.id} has no variation ${variation}`);
    return swapModel(item, { path: doodad.files[variation], variation });
  }

  /**
   * Take a placed item's data, model and textures from another dataset. A
   * doodad keeps its variation when the other dataset has it. A unit or
   * doodad the other dataset does not have stays as it is (an error).
   */
  async function setItemDataset(item, dataset) {
    app.pending++;
    try {
      app.requireDataset(dataset);
      // A bare model file: the same file, its textures from the other dataset.
      if (!item.unit) return await swapModel(item, { dataset });
      const isDoodad = Boolean(item.unit.doodad);
      const unit = await app.record(isDoodad ? 'doodad' : 'unit', item.unit.id, dataset);
      if (!isDoodad) return await swapModel(item, { path: unit.file, unit, dataset });
      const variation = validVariation(unit, item.variation) ?? 0;
      return await swapModel(item, { path: unit.files[variation], unit, dataset, variation });
    } catch (error) {
      app.setStatus(error.message, { failure: true });
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

  /** Remove the items `ids` in one go: one list rebuild, one URL update. */
  function removeMany(ids) {
    const gone = items.filter((item) => ids.includes(item.id));
    if (!gone.length) return 0;
    for (const item of gone) {
      item.instance.detach();
      items.splice(items.indexOf(item), 1);
      app.forget(item.id);
    }
    renderList();
    app.saveHash();
    return gone.length;
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
    const removeButton = el('button', { className: 'remove', textContent: '×', title: 'remove' });
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
    const isDoodad = Boolean(item.unit && item.unit.doodad);
    if (item.unit && !isDoodad) head.unshift(app.iconNode(item.unit.icon, item.dataset));
    // A doodad has model variations in place of a team colour.
    const controls = [anim];
    if (!isDoodad) controls.push(team);
    else if (item.unit.variations > 1) {
      const variation = el(
        'select',
        { className: 'variation', title: 'model variation' },
        Array.from({ length: item.unit.variations }, (_, i) => el('option', { value: String(i), textContent: `variation ${i + 1} of ${item.unit.variations}` })),
      );
      variation.value = String(item.variation);
      variation.addEventListener('change', () => setVariation(item, Number.parseInt(variation.value, 10)).catch(app.reportFailure));
      controls.push(variation);
    }
    // Where the item's data and textures come from; another choice swaps them.
    const all = app.datasets();
    if (all.length > 1) {
      const source = el('select', { className: 'dataset', title: 'dataset: where this instance\'s data and textures come from' }, all.map((d) => el('option', { value: d.id, textContent: d.label })));
      source.value = item.dataset;
      source.addEventListener('change', () =>
        setItemDataset(item, source.value).catch((error) => {
          app.reportFailure(error);
          // It stays as it was: show that.
          source.value = item.dataset;
        }),
      );
      controls.push(source);
    }
    const row = el('li', {}, [
      el('div', { className: 'head' }, head),
      el('div', { className: 'row' }, controls),
      el('div', { className: 'row' }, [numberInput(item, 'x', 0.5), numberInput(item, 'y', 0.5), numberInput(item, 'rot', 15), numberInput(item, 'scale', 0.1)]),
    ]);
    row.dataset.id = String(item.id);
    if (item.unit) row.dataset[isDoodad ? 'doodad' : 'unit'] = item.unit.id;
    // What the instance search matches: the name, the unit or doodad id, the model file.
    row.dataset.search = [name, item.unit ? item.unit.id : '', item.path].join(' ').toLowerCase();
    // A click on the row's name selects the unit in the view (pick.js).
    // With shift it adds the unit to the selection or takes it out.
    row.querySelector('.head').addEventListener('click', (e) => {
      if (e.target === removeButton) return;
      if (e.shiftKey) app.toggleSelected(item.id);
      else app.select(item.id);
    });
    // A double-click opens the texture window on the unit's textures (textures.js).
    row.querySelector('.head').addEventListener('dblclick', (e) => {
      if (e.target !== removeButton) app.openTexturesOf(item).catch(app.reportFailure);
    });
    return row;
  }

  /** Mark the rows of the selected items (a Set of ids) and scroll the row of `last` (null: none) into view. */
  function markSelected(ids, last) {
    for (const row of sceneList.children) row.classList.toggle('selected', ids.has(Number(row.dataset.id)));
    const row = last === null ? null : sceneList.querySelector(`li[data-id="${last}"]`);
    if (row) row.scrollIntoView({ block: 'nearest' });
  }

  /**
   * The instance search: rows whose name, id or model file hold the text
   * stay, the others hide. Only the list changes: the instances stay in the
   * view and in the selection.
   */
  const instanceSearch = app.$('instance-search');
  function filterList() {
    const query = instanceSearch.value.trim().toLowerCase();
    let shown = 0;
    for (const row of sceneList.children) {
      row.hidden = Boolean(query) && !row.dataset.search.includes(query);
      if (!row.hidden) shown++;
    }
    const count = app.$('instance-count');
    if (!items.length) count.textContent = '';
    else count.textContent = query ? `(${shown} of ${items.length})` : `(${items.length})`;
  }
  instanceSearch.addEventListener('input', filterList);

  function renderList() {
    sceneList.replaceChildren(...items.map(listRow));
    filterList();
    markSelected(new Set(app.selectedIds()), app.selectedId());
  }

  app.$('clear').addEventListener('click', clear);

  /** Turn an item to `rot` degrees and show it in its list row. */
  function setRotation(item, rot) {
    item.rot = rot;
    applyTransform(item);
    const input = sceneList.querySelector(`li[data-id="${item.id}"] input.rot`);
    if (input) input.value = shown(rot);
  }

  /** Move an item to ground point (x, y) and show it in its list row. */
  function setPosition(item, x, y) {
    item.x = x;
    item.y = y;
    applyTransform(item);
    for (const field of ['x', 'y']) {
      const input = sceneList.querySelector(`li[data-id="${item.id}"] input.${field}`);
      if (input) input.value = shown(item[field]);
    }
  }

  Object.assign(app, { add, addUnit, addDoodad, doodadPlacement, setVariation, setItemDataset, remove, removeMany, clear, restart, playOnce, loopSequence, endOneShots, setRotation, setPosition, markSelected });
})();

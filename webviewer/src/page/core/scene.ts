// Scene items (units, doodads, bare model files): add, remove, clear,
// swap. An item's `unit` is its data record: a unit's, or a doodad's
// (`unit.doodad` true), or null for a bare model file. An item's `dataset`
// is where that record and the model's textures come from (core/datasets.ts).
// The scene list is page/ui/instances.ts.

import type { DoodadRecord, PlacedRecord } from '../../shared/records';
import { app, type AddOptions, type CoreApi, type DoodadPlacement, type Item, type SceneApi } from './app';
import { loadM3 } from './library';

const REACH = 1.25; // half the room a model with no unit data takes in a row

/** A whole variation number inside the doodad's range, or null when `value` is not one. */
function validVariation(doodad: DoodadRecord, value: unknown): number | null {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0 && value < doodad.variations ? value : null;
}

/** What swapModel may change. */
interface Swap {
  path?: string;
  unit?: PlacedRecord | null;
  dataset?: string;
  variation?: number | null;
}

/** A doodad's model file of one variation. */
function variationFile(doodad: DoodadRecord, variation: number): string {
  const file = doodad.files[variation];
  if (file === undefined) throw new Error(`${doodad.id} has no variation ${variation}`);
  return file;
}

export function installScene(core: CoreApi): SceneApi {
  const { viewer, scene, items, TEAMS } = core;
  let nextId = 1;

  function applyTransform(item: Item): void {
    const half = (item.rot * Math.PI) / 360;
    item.instance.setLocation([item.x, item.y, app().baseHeight(item.unit)]);
    item.instance.setRotation([0, 0, Math.sin(half), Math.cos(half)]);
    item.instance.setScale(item.dataScale.map((v) => v * item.scale));
  }

  /** Play the item's own (idle) animation, looping. Ends a one-shot. */
  function applySequence(item: Item): void {
    item.oneShot = null;
    item.instance.setSequence(item.sequence);
    item.instance.setSequenceLoopMode(2);
    item.instance.timeScale = app().playRate(item);
  }

  /** Play one animation once; then the item goes back to its own (see endOneShots). */
  function playOnce(item: Item, sequence: number): void {
    item.oneShot = sequence;
    item.instance.setSequence(sequence);
    item.instance.setSequenceLoopMode(1); // never loop
    item.instance.timeScale = app().playRate({ unit: item.unit, model: item.model, sequence });
  }

  /** Make an animation the item's own: it loops; the list row and the URL show it. */
  function loopSequence(item: Item, sequence: number): void {
    item.sequence = sequence;
    applySequence(item);
    app().showItemField(item, 'sequence');
    app().saveScene();
  }

  /** After each update: items whose one-shot has ended go back to their own animation. */
  function endOneShots(): void {
    for (const item of items) if (item.oneShot !== null && item.instance.sequenceEnded) applySequence(item);
  }

  function applyLook(item: Item): void {
    item.instance.setTeamColor(item.team);
    const tint = item.unit && item.unit.tint;
    item.instance.setVertexColor(tint ? [tint[0], tint[1], tint[2], 1] : [1, 1, 1, 1]);
  }

  const reach = (unit: PlacedRecord | null): number => (unit ? Math.max(REACH, unit.radius + 0.5) : REACH);

  /** Where the next one goes: in a row, clear of the rightmost one. */
  function nextX(unit: PlacedRecord | null): number {
    return items.length ? Math.max(...items.map((item) => item.x + reach(item.unit))) + reach(unit) : 0;
  }

  /** The model of a file in a dataset; an error when it does not load. */
  async function loadModel(path: string, dataset: string): Promise<NonNullable<Awaited<ReturnType<typeof loadM3>>>> {
    const model = await loadM3(viewer, app().modelUrl(path, dataset), app().pathSolver(dataset));
    if (!model) throw new Error('cannot load ' + path);
    return model;
  }

  /**
   * Add a model file, or a unit when `options.unit` is a unit record.
   * `options.dataset`: where its textures (and the record) come from;
   * the current dataset when not given.
   */
  async function add(path: string, options: AddOptions = {}): Promise<number> {
    const a = app();
    a.pending++;
    a.setStatus('loading ' + (options.unit ? options.unit.name : path));
    try {
      const dataset = a.requireDataset(options.dataset ?? a.dataset());
      const model = await loadModel(path, dataset);
      const unit = options.unit || null;
      const pick = options.pick ?? Math.random();
      const item: Item = {
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
        sequence: options.sequence ?? a.defaultSequence(model),
        team: options.team ?? 0,
        pick,
        variation: unit && unit.doodad ? (options.variation ?? null) : null,
        dataScale: a.dataScale(unit, pick),
        oneShot: null,
        hd: options.hd ?? true,
        hdLayers: 0,
        largestTexture: 0,
      };
      if (item.sequence < -1 || item.sequence >= model.sequences.length) item.sequence = -1;
      if (!(item.team >= 0 && item.team < TEAMS)) item.team = 0;
      applyTransform(item);
      applySequence(item);
      applyLook(item);
      await a.applyHd(item);
      scene.addInstance(item.instance);
      items.push(item);
      a.renderList();
      a.saveScene();
      a.setStatus('');
      a.reportUndrawn(unit ? unit.name : path, model);
      return item.id;
    } catch (error) {
      a.setStatus(error instanceof Error ? error.message : String(error), { failure: true });
      throw error;
    } finally {
      a.pending--;
    }
  }

  /** Run a load with the pending count up and its failure on the status line. */
  async function loading<T>(work: () => Promise<T>): Promise<T> {
    const a = app();
    a.pending++;
    try {
      return await work();
    } catch (error) {
      a.setStatus(error instanceof Error ? error.message : String(error), { failure: true });
      throw error;
    } finally {
      a.pending--;
    }
  }

  /**
   * Add a unit by id, with everything its data says about its look. A unit
   * whose model is a skybox (games/sc2/server/skyboxes.ts) becomes the sky
   * instead; it is not placed, and the result is null.
   */
  function addUnit(id: string, options: AddOptions = {}): Promise<number | null> {
    return loading(async () => {
      const a = app();
      const dataset = a.requireDataset(options.dataset ?? a.dataset());
      const unit = await a.record('unit', id, dataset);
      if (unit.skybox) {
        await a.setSky({ id: unit.id, name: unit.name, file: unit.file });
        a.setStatus(`${unit.name} is a skybox: set as the sky`);
        return null;
      }
      return await add(unit.file, { ...options, unit, dataset });
    });
  }

  /**
   * What the map editor decides when it places a doodad: which model
   * variation, and the angle. The angle is random unless the doodad's data
   * forbids it (EditorFlags NoAutoRotate, or CanRotate off). Given options win.
   */
  function doodadPlacement(doodad: DoodadRecord, options: AddOptions = {}): DoodadPlacement {
    const variation = validVariation(doodad, options.variation) ?? Math.floor(Math.random() * doodad.variations);
    const rot = options.rot ?? (doodad.autoRotate ? Math.floor(Math.random() * 360) : 0);
    return { variation, rot };
  }

  /**
   * Add a doodad by id: one of its model variations, at its data scale
   * (random inside RandomScaleRange by `options.pick`), turned as the
   * editor would turn it.
   */
  function addDoodad(id: string, options: AddOptions = {}): Promise<number> {
    return loading(async () => {
      const a = app();
      const dataset = a.requireDataset(options.dataset ?? a.dataset());
      const doodad = await a.record('doodad', id, dataset);
      const placement = doodadPlacement(doodad, options);
      return await add(variationFile(doodad, placement.variation), { ...options, ...placement, unit: doodad, dataset });
    });
  }

  /**
   * Give a placed item another model file, record, dataset or variation.
   * Its id, place, angle, own scale, team and scale pick stay; the data
   * scale follows the record. It keeps playing its animation when the new
   * model has one of that name.
   */
  function swapModel(item: Item, next: Swap): Promise<void> {
    return loading(async () => {
      const a = app();
      const { path = item.path, unit = item.unit, dataset = item.dataset, variation = item.variation } = next;
      const model = await loadModel(path, dataset);
      // Removed while the model loaded: nothing to swap.
      if (!items.includes(item)) return;
      const playing = item.sequence >= 0 ? (item.model.sequences[item.sequence]?.name ?? null) : null;
      const same = playing === null ? -1 : model.sequences.findIndex((s) => s.name === playing);
      item.instance.detach();
      Object.assign(item, { path, unit, dataset, variation, model, instance: model.addInstance(), sequence: same >= 0 ? same : a.defaultSequence(model), dataScale: a.dataScale(unit, item.pick) });
      applyTransform(item);
      applySequence(item);
      applyLook(item);
      await a.applyHd(item);
      scene.addInstance(item.instance);
      a.renderList();
      a.saveScene();
      a.reportUndrawn(unit ? unit.name : path, model);
    });
  }

  /** Swap a placed doodad to another of its model variations; place, angle and scale stay. */
  async function setVariation(item: Item, variation: number): Promise<void> {
    const doodad = item.unit;
    if (!doodad || !doodad.doodad) throw new Error(`item ${item.id} is not a doodad`);
    if (validVariation(doodad, variation) === null) throw new Error(`${doodad.id} has no variation ${variation}`);
    return swapModel(item, { path: variationFile(doodad, variation), variation });
  }

  /**
   * Take a placed item's data, model and textures from another dataset. A
   * doodad keeps its variation when the other dataset has it. A unit or
   * doodad the other dataset does not have stays as it is (an error).
   */
  function setItemDataset(item: Item, dataset: string): Promise<void> {
    return loading(async () => {
      const a = app();
      a.requireDataset(dataset);
      // A bare model file: the same file, its textures from the other dataset.
      const own = item.unit;
      if (!own) return await swapModel(item, { dataset });
      if (!own.doodad) {
        const unit = await a.record('unit', own.id, dataset);
        return await swapModel(item, { path: unit.file, unit, dataset });
      }
      const doodad = await a.record('doodad', own.id, dataset);
      const variation = validVariation(doodad, item.variation) ?? 0;
      return await swapModel(item, { path: variationFile(doodad, variation), unit: doodad, dataset, variation });
    });
  }

  function remove(id: number): void {
    const at = items.findIndex((item) => item.id === id);
    const item = items[at];
    if (!item) return;
    item.instance.detach();
    items.splice(at, 1);
    app().forget(id);
    app().renderList();
    app().saveScene();
  }

  /** Remove the items `ids` in one go: one list rebuild, one scene write. */
  function removeMany(ids: readonly number[]): number {
    const gone = items.filter((item) => ids.includes(item.id));
    if (!gone.length) return 0;
    for (const item of gone) {
      item.instance.detach();
      items.splice(items.indexOf(item), 1);
      app().forget(item.id);
    }
    app().renderList();
    app().saveScene();
    return gone.length;
  }

  function clear(): void {
    for (const item of items) item.instance.detach();
    items.length = 0;
    app().forget(null);
    app().renderList();
    app().saveScene();
  }

  /** Start every animation again from its first frame. */
  function restart(): void {
    for (const item of items) applySequence(item);
  }

  /** Turn an item to `rot` degrees and show it in its list row. */
  function setRotation(item: Item, rot: number): void {
    item.rot = rot;
    applyTransform(item);
    app().showItemField(item, 'rot');
  }

  /** Move an item to ground point (x, y) and show it in its list row. */
  function setPosition(item: Item, x: number, y: number): void {
    item.x = x;
    item.y = y;
    applyTransform(item);
    app().showItemField(item, 'x');
    app().showItemField(item, 'y');
  }

  return {
    add,
    addUnit,
    addDoodad,
    doodadPlacement,
    setVariation,
    setItemDataset,
    remove,
    removeMany,
    clear,
    restart,
    playOnce,
    loopSequence,
    endOneShots,
    setRotation,
    setPosition,
    applyTransform,
    applySequence,
    applyLook,
  };
}

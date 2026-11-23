// Drag a unit or a doodad from its list into the view. While dragged, a
// preview (the ghost) stands on the ground under the pointer; a drop adds
// the unit or doodad there, looking as the preview did.

import type { PlacedRecord } from '../../../shared/records';
import { app, type AddOptions, type CoreApi, type DragApi, type Vec2 } from '../../core/app';
import { loadM3, type M3ModelInstance } from '../../core/library';

type Kind = 'unit' | 'doodad';

// One drag type per kind of record; the data is the record's id.
const DRAG_TYPES: Record<Kind, string> = { unit: 'application/x-sc2-unit', doodad: 'application/x-sc2-doodad' };
const KINDS: readonly Kind[] = ['unit', 'doodad'];

interface Ghost {
  kind: Kind;
  id: string;
  unit: PlacedRecord | null;
  instance: M3ModelInstance | null;
  pick: number;
  variation: number | null;
  rot: number;
  at: Vec2 | null;
}

export function installDrag(core: CoreApi): DragApi {
  const { canvas, scene, viewer } = core;

  /** While a record is dragged: its preview; otherwise null. */
  let ghost: Ghost | null = null;

  /** Load the dragged record's model, hidden until the drag is over the ground. */
  async function startGhost(kind: Kind, id: string): Promise<void> {
    endGhost();
    const mine: Ghost = { kind, id, unit: null, instance: null, pick: Math.random(), variation: null, rot: 0, at: null };
    ghost = mine;
    const a = app();
    a.pending++;
    try {
      const unit = await a.record(kind, id);
      // A skybox unit is not placed (a drop sets it as the sky): no preview.
      if (!unit.doodad && unit.skybox) return;
      // A doodad's variation and angle are chosen now, so the drop matches the preview.
      let file = unit.file;
      if (unit.doodad) {
        Object.assign(mine, a.doodadPlacement(unit));
        file = unit.files[mine.variation ?? 0] ?? unit.file;
      }
      const model = await loadM3(viewer, a.modelUrl(file, unit.dataset), a.pathSolver(unit.dataset));
      if (ghost !== mine) return; // the drag ended meanwhile
      if (!model) throw new Error('cannot load ' + file);
      const instance = model.addInstance();
      const sequence = a.defaultSequence(model);
      instance.setSequence(sequence);
      instance.setSequenceLoopMode(2);
      instance.timeScale = a.playRate({ unit, model, sequence });
      instance.setScale(a.dataScale(unit, mine.pick));
      const half = (mine.rot * Math.PI) / 360;
      instance.setRotation([0, 0, Math.sin(half), Math.cos(half)]);
      instance.setTeamColor(0);
      instance.hide();
      scene.addInstance(instance);
      Object.assign(mine, { unit, instance });
      placeGhost();
    } catch (error) {
      a.setStatus(error instanceof Error ? error.message : String(error), { failure: true });
      throw error;
    } finally {
      a.pending--;
    }
  }

  /** Show the preview at its ground point, or hide it when it has none. */
  function placeGhost(): void {
    if (!ghost || !ghost.instance) return;
    if (!ghost.at) {
      ghost.instance.hide();
      return;
    }
    ghost.instance.setLocation([ghost.at[0], ghost.at[1], app().baseHeight(ghost.unit)]);
    ghost.instance.show();
  }

  function endGhost(): void {
    if (ghost && ghost.instance) ghost.instance.detach();
    ghost = null;
  }

  /** dragstart on a list row. */
  function startDrag(e: DragEvent, record: { id: string; name: string }, kind: Kind = 'unit'): void {
    if (e.dataTransfer) {
      e.dataTransfer.setData(DRAG_TYPES[kind], record.id);
      e.dataTransfer.setData('text/plain', record.name);
      e.dataTransfer.effectAllowed = 'copy';
    }
    startGhost(kind, record.id).catch(app().reportFailure);
  }

  // Drop a unit or doodad on the view: it lands on the ground under the pointer.
  /** The kind of record a drag carries, or null for any other drag. */
  function carried(e: DragEvent): Kind | null {
    if (!e.dataTransfer) return null;
    const types = [...e.dataTransfer.types];
    return KINDS.find((kind) => types.includes(DRAG_TYPES[kind])) ?? null;
  }
  canvas.addEventListener('dragover', (e) => {
    if (!carried(e)) return;
    e.preventDefault();
    if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy';
    canvas.classList.add('drop');
    const a = app();
    a.pointer = a.eventGround(e);
    if (ghost) {
      ghost.at = a.pointer;
      placeGhost();
    }
  });
  canvas.addEventListener('dragleave', () => {
    canvas.classList.remove('drop');
    app().pointer = null;
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
    const a = app();
    // The preview's choices, when it got as far as making them.
    const seen = ghost && ghost.unit ? ghost : null;
    const pick = ghost ? ghost.pick : undefined;
    endGhost();
    const point = a.eventGround(e);
    if (!point) {
      a.setStatus('drop it on the ground, not above the horizon');
      return;
    }
    const id = e.dataTransfer ? e.dataTransfer.getData(DRAG_TYPES[kind]) : '';
    // The same scale pick as the preview (and a doodad's variation and
    // angle), so it looks as it did.
    const options: AddOptions = { x: point[0], y: point[1] };
    if (pick !== undefined) options.pick = pick;
    if (kind === 'doodad') {
      if (seen) Object.assign(options, { variation: seen.variation, rot: seen.rot });
      a.addDoodad(id, options).catch(a.reportFailure);
    } else a.addUnit(id, options).catch(a.reportFailure);
  });

  /** The drag preview, for the tests: null when nothing is dragged. */
  function ghostState(): ReturnType<DragApi['ghostState']> {
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

  return { startDrag, endGhost, ghostState };
}

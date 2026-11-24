// Drag a record from its gallery list into the view. While dragged, a
// preview (the ghost) stands on the ground under the pointer; a drop adds
// the record there, looking as the preview did. The gallery rows call it
// through ui.setRowDrag.

import type { AddOptions, GhostState, Vec2 } from '../../core/types';
import type { Feature } from '../../core/context';
import type { GameCategory, Placement, ViewerInstance } from '../../core/plugin';

interface Ghost {
  category: GameCategory;
  id: string;
  /** The game's placement, once the record is read: its variant and angle are what a drop keeps. */
  placement: Placement | null;
  instance: ViewerInstance | null;
  pick: number;
  at: Vec2 | null;
}

export const dragFeature: Feature = {
  id: 'drag',
  install({ render, scene: items, games, api, camera, status, ui, testApi }) {
    const { canvas, scene } = render;
    // The gallery game at call time: the game tabs change it.
    const game = games.plugin;

    // One drag type per record category; the data is the record's id.
    const dragType = (category: GameCategory): string => `application/x-${game().id}-${category.noun}`;

    /** While a record is dragged: its preview; otherwise null. */
    let ghost: Ghost | null = null;

    /** Load the dragged record's model, hidden until the drag is over the ground. */
    async function startGhost(category: GameCategory, id: string): Promise<void> {
      endGhost();
      const mine: Ghost = { category, id, placement: null, instance: null, pick: Math.random(), at: null };
      ghost = mine;
      status.pending++;
      try {
        const record = await api.record(category.id, id);
        // The variant and angle are chosen now, so the drop matches the preview.
        const placement = game().place(category.id, record, { pick: mine.pick });
        // A backdrop is not placed (a drop sets it as the sky): no preview.
        if (placement.asBackdrop) return;
        mine.placement = placement;
        const model = await render.loadModel(api.modelUrl(placement.file, record.dataset), api.pathSolver(record.dataset));
        if (ghost !== mine) return; // the drag ended meanwhile
        if (!model) throw new Error('cannot load ' + placement.file);
        const instance = model.addInstance();
        const sequence = game().restSequence(instance.sequences);
        instance.setSequence(sequence);
        instance.setLoop(true);
        instance.timeScale = game().playRate(record, instance.sequences[sequence]);
        instance.setScale(placement.scale);
        const half = (placement.rot * Math.PI) / 360;
        instance.setRotation([0, 0, Math.sin(half), Math.cos(half)]);
        const { teamColor } = render.formatOf(model).capabilities(instance);
        if (teamColor) teamColor.set(0);
        instance.hide();
        instance.attach(scene);
        mine.instance = instance;
        placeGhost();
      } catch (error) {
        status.setStatus(error instanceof Error ? error.message : String(error), { failure: true });
        throw error;
      } finally {
        status.pending--;
      }
    }

    /** Show the preview at its ground point, or hide it when it has none. */
    function placeGhost(): void {
      if (!ghost || !ghost.instance || !ghost.placement) return;
      if (!ghost.at) {
        ghost.instance.hide();
        return;
      }
      ghost.instance.setLocation([ghost.at[0], ghost.at[1], ghost.placement.height]);
      ghost.instance.show();
    }

    function endGhost(): void {
      if (ghost && ghost.instance) ghost.instance.detach();
      ghost = null;
    }

    /** dragstart on a list row: `noun` names the record's category ("unit"). */
    function startDrag(e: DragEvent, record: { id: string; name: string }, noun: string): void {
      const category = games.categoryOf(noun);
      if (e.dataTransfer) {
        e.dataTransfer.setData(dragType(category), record.id);
        e.dataTransfer.setData('text/plain', record.name);
        e.dataTransfer.effectAllowed = 'copy';
      }
      startGhost(category, record.id).catch(status.reportFailure);
    }

    // Drop a record on the view: it lands on the ground under the pointer.
    /** The category a drag carries, or null for any other drag. */
    function carried(e: DragEvent): GameCategory | null {
      if (!e.dataTransfer) return null;
      const types = [...e.dataTransfer.types];
      return game().categories.find((category) => types.includes(dragType(category))) ?? null;
    }
    canvas.addEventListener('dragover', (e) => {
      if (!carried(e)) return;
      e.preventDefault();
      if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy';
      canvas.classList.add('drop');
      camera.setPointer(camera.eventGround(e));
      if (ghost) {
        ghost.at = camera.pointer();
        placeGhost();
      }
    });
    canvas.addEventListener('dragleave', () => {
      canvas.classList.remove('drop');
      camera.setPointer(null);
      if (ghost) {
        ghost.at = null;
        placeGhost();
      }
    });
    canvas.addEventListener('drop', (e) => {
      canvas.classList.remove('drop');
      const category = carried(e);
      if (!category) return;
      e.preventDefault();
      // The preview's choices, when it got as far as making them.
      const seen = ghost && ghost.placement ? ghost.placement : null;
      const pick = ghost ? ghost.pick : undefined;
      endGhost();
      const point = camera.eventGround(e);
      if (!point) {
        status.setStatus('drop it on the ground, not above the horizon');
        return;
      }
      const id = e.dataTransfer ? e.dataTransfer.getData(dragType(category)) : '';
      // The same scale pick as the preview, and its variant and angle, so it looks as it did.
      const options: AddOptions = { x: point[0], y: point[1] };
      if (pick !== undefined) options.pick = pick;
      if (seen) Object.assign(options, { variant: seen.variant, rot: seen.rot });
      items.addRecord(category.id, id, options).catch(status.reportFailure);
    });

    /** The drag preview, for the tests: null when nothing is dragged. */
    function ghostState(): GhostState | null {
      if (!ghost) return null;
      return {
        kind: ghost.category.noun,
        unit: ghost.id,
        variation: ghost.placement ? ghost.placement.variant : null,
        rot: ghost.placement ? ghost.placement.rot : 0,
        loaded: Boolean(ghost.instance),
        shown: Boolean(ghost.instance && ghost.instance.shown),
        location: ghost.instance ? Array.from(ghost.instance.location) : null,
      };
    }

    ui.setRowDrag({ start: startDrag, end: endGhost });
    testApi.statePart('ghost', ghostState);
  },
};

// Copy, cut and paste of the selected instances:
// - Ctrl+C copies the selected instances: its game, what each is (a record of a
//   category and its variant, or model file), its dataset, place, angle, scale,
//   animation, team, scale pick and the game's options (SC2: the HD choice);
// - Ctrl+X copies them and removes them;
// - Ctrl+V adds the copies. The group keeps its shape; its centre goes to
//   the ground point under the mouse, or, with the mouse off the view, to
//   where it was copied from. The pasted ones become the selection. The copy
//   stays, so each Ctrl+V adds the group again.
// A text field being edited keeps its own Ctrl+C, Ctrl+X and Ctrl+V.
// The copy lives in the page, not the system clipboard.

import type { Feature } from '../../core/context';
import type { Item, Vec2 } from '../../core/types';

interface Entry {
  game: string;
  /** The record's category; null: a model file, `id` its path. */
  category: string | null;
  id: string;
  dataset: string;
  variant: number | null;
  x: number;
  y: number;
  rot: number;
  scale: number;
  sequence: number;
  team: number;
  pick: number;
  /** The game's settings of the item (SC2: hd). */
  options: Record<string, unknown>;
}

function entryOf(item: Item): Entry {
  const own = item.source;
  return {
    game: item.game,
    category: own ? own.category : null,
    id: own ? own.record.id : item.path,
    dataset: item.dataset,
    variant: item.placement.variant,
    x: item.x,
    y: item.y,
    rot: item.rot,
    scale: item.scale,
    sequence: item.sequence,
    team: item.team,
    pick: item.placement.pick,
    options: { ...item.options },
  };
}

const plural = (n: number): string => `${n} instance${n === 1 ? '' : 's'}`;

export const clipboardFeature: Feature = {
  id: 'clipboard',
  install({ scene, selection, camera, status, testApi }) {
    const { items } = scene;

    /** The copied instances, in the scene's order; empty before the first copy. */
    let copied: Entry[] = [];

    /** The selected items, in the scene's order. */
    function chosen(): Item[] {
      const ids = new Set(selection.selectedIds());
      return items.filter((item) => ids.has(item.id));
    }

    /** Copy the selected instances. Their count, 0 when none is selected. */
    function copy(): number {
      const list = chosen();
      if (!list.length) return 0;
      copied = list.map(entryOf);
      return copied.length;
    }

    /** Copy the selected instances and remove them. Their count. */
    function cut(): number {
      const count = copy();
      if (count) scene.removeMany(chosen().map((item) => item.id));
      return count;
    }

    /** Add the copies, centred on `at` or where they were. The new ids. */
    async function paste(at: Vec2 | null = null): Promise<number[]> {
      if (!copied.length) return [];
      const cx = copied.reduce((s, e) => s + e.x, 0) / copied.length;
      const cy = copied.reduce((s, e) => s + e.y, 0) / copied.length;
      const dx = at ? at[0] - cx : 0;
      const dy = at ? at[1] - cy : 0;
      const ids: number[] = [];
      // One after another, so the order is kept.
      for (const e of copied) {
        const options = { x: e.x + dx, y: e.y + dy, rot: e.rot, scale: e.scale, sequence: e.sequence, team: e.team, pick: e.pick, options: e.options, game: e.game, dataset: e.dataset };
        let id: number | null | void = null;
        if (e.category !== null) id = await scene.addRecord(e.category, e.id, { ...options, variant: e.variant }).catch(status.reportFailure);
        else id = await scene.add(e.id, options).catch(status.reportFailure);
        if (typeof id === 'number') ids.push(id);
      }
      selection.setSelection(ids);
      return ids;
    }

    window.addEventListener('keydown', (e) => {
      if (!(e.ctrlKey || e.metaKey) || e.altKey || e.shiftKey) return;
      const key = e.key.toLowerCase();
      if (!['c', 'x', 'v'].includes(key) || selection.editingText(e.target)) return;
      e.preventDefault();
      if (key === 'v') {
        if (!copied.length) {
          status.setStatus('nothing copied: select instances, then Ctrl+C or Ctrl+X before Ctrl+V');
          return;
        }
        const ground = camera.pointer();
        paste(ground ? [ground[0], ground[1]] : null).then((ids) => status.setStatus(`pasted ${plural(ids.length)}`), status.reportFailure);
        return;
      }
      const count = key === 'c' ? copy() : cut();
      if (count) status.setStatus(`${key === 'c' ? 'copied' : 'cut'} ${plural(count)}`);
    });

    testApi.app({
      copySelected: copy,
      cutSelected: cut,
      pasteCopied: paste,
      // For the tests: how many instances the copy holds.
      copiedCount: () => copied.length,
    });
  },
};

// Copy, cut and paste of the selected instances:
// - Ctrl+C copies the selected instances: what each is (unit, doodad and
//   its variation, or model file), its dataset, place, angle, scale,
//   animation, team, scale pick and HD choice;
// - Ctrl+X copies them and removes them;
// - Ctrl+V adds the copies. The group keeps its shape; its centre goes to
//   the ground point under the mouse, or, with the mouse off the view, to
//   where it was copied from. The pasted ones become the selection. The copy
//   stays, so each Ctrl+V adds the group again.
// A text field being edited keeps its own Ctrl+C, Ctrl+X and Ctrl+V.
// The copy lives in the page, not the system clipboard.

import { app, type ClipboardApi, type CoreApi, type Item, type Vec2 } from '../../core/app';

interface Entry {
  kind: 'path' | 'doodad' | 'unit';
  id: string;
  dataset: string;
  variation: number | null;
  x: number;
  y: number;
  rot: number;
  scale: number;
  sequence: number;
  team: number;
  pick: number;
  hd: boolean;
}

function entryOf(item: Item): Entry {
  const unit = item.unit;
  return {
    kind: !unit ? 'path' : unit.doodad ? 'doodad' : 'unit',
    id: unit ? unit.id : item.path,
    dataset: item.dataset,
    variation: item.variation,
    x: item.x,
    y: item.y,
    rot: item.rot,
    scale: item.scale,
    sequence: item.sequence,
    team: item.team,
    pick: item.pick,
    hd: item.hd,
  };
}

const plural = (n: number): string => `${n} instance${n === 1 ? '' : 's'}`;

export function installClipboard(core: CoreApi): ClipboardApi {
  const { items } = core;

  /** The copied instances, in the scene's order; empty before the first copy. */
  let copied: Entry[] = [];

  /** The selected items, in the scene's order. */
  function chosen(): Item[] {
    const ids = new Set(app().selectedIds());
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
    if (count) app().removeMany(chosen().map((item) => item.id));
    return count;
  }

  /** Add the copies, centred on `at` or where they were. The new ids. */
  async function paste(at: Vec2 | null = null): Promise<number[]> {
    if (!copied.length) return [];
    const a = app();
    const cx = copied.reduce((s, e) => s + e.x, 0) / copied.length;
    const cy = copied.reduce((s, e) => s + e.y, 0) / copied.length;
    const dx = at ? at[0] - cx : 0;
    const dy = at ? at[1] - cy : 0;
    const ids: number[] = [];
    // One after another, so the order is kept.
    for (const e of copied) {
      const options = { x: e.x + dx, y: e.y + dy, rot: e.rot, scale: e.scale, sequence: e.sequence, team: e.team, pick: e.pick, hd: e.hd, dataset: e.dataset };
      let id: number | null | void = null;
      if (e.kind === 'unit') id = await a.addUnit(e.id, options).catch(a.reportFailure);
      else if (e.kind === 'doodad') id = await a.addDoodad(e.id, { ...options, variation: e.variation }).catch(a.reportFailure);
      else id = await a.add(e.id, options).catch(a.reportFailure);
      if (typeof id === 'number') ids.push(id);
    }
    a.setSelection(ids);
    return ids;
  }

  window.addEventListener('keydown', (e) => {
    if (!(e.ctrlKey || e.metaKey) || e.altKey || e.shiftKey) return;
    const key = e.key.toLowerCase();
    if (!['c', 'x', 'v'].includes(key) || app().editingText(e.target)) return;
    e.preventDefault();
    if (key === 'v') {
      if (!copied.length) {
        app().setStatus('nothing copied: select instances, then Ctrl+C or Ctrl+X before Ctrl+V');
        return;
      }
      const ground = app().pointer;
      paste(ground ? [ground[0], ground[1]] : null).then((ids) => app().setStatus(`pasted ${plural(ids.length)}`), app().reportFailure);
      return;
    }
    const count = key === 'c' ? copy() : cut();
    if (count) app().setStatus(`${key === 'c' ? 'copied' : 'cut'} ${plural(count)}`);
  });

  return {
    copySelected: copy,
    cutSelected: cut,
    pasteCopied: paste,
    /** For the tests: how many instances the copy holds. */
    copiedCount: () => copied.length,
  };
}

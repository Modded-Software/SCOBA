// "add all": adds one instance of every unit the unit list shows (search,
// race, kind and family filters), after a dialog asks to confirm the count.
// The doodads tab has its own button: every doodad its list shows (SOURCES).
// Skybox units (a backdrop model, games/sc2/server/skyboxes.ts) are left out, and
// the dialog names them.
// The new units are laid out on the ground by size (layout.ts); on a map
// with units already, the block goes next to them.
// The camera then frames the new block, kept as a landmark (features/landmarks)
// named after the list filters.

import type { DoodadSummary, Page, UnitSummary } from '../../../shared/records';
import { app, type AddAllApi, type AddAllRun, type DoodadQuery, type Item, type UnitQuery } from '../../core/app';
import { byId, make, messageOf } from '../../core/dom';
import { ConfirmDialog } from '../../ui/components/dialog';
import { arrange } from './layout';

const PAGE = 500; // the server's largest page
const LOADERS = 6; // models loading at once

/**
 * A doodad list's landmark name, read like a phrase: terrain set, type,
 * "Doodads", then the search, e.g. 'Char Environment Doodads "rock"'.
 */
function doodadFilterName(query: DoodadQuery): string {
  const words = [];
  if (query.tileset) words.push(query.tileset);
  if (query.type) words.push(query.type);
  words.push('Doodads');
  if (!query.tileset && !query.type && !query.q) words.unshift('All');
  if (query.q) words.push(`"${query.q}"`);
  return words.join(' ');
}

/** A listed record, as both lists give it. */
type Listed = UnitSummary | DoodadSummary;

/**
 * What "add all" works on, per gallery tab: the list's query and API,
 * how one record is added, the landmark name, and which records are left
 * out (with the word for them).
 */
interface Source {
  query(): UnitQuery | DoodadQuery;
  /** The category its list is. */
  category: string;
  add(id: string): Promise<number | null>;
  noun: string;
  name(): string;
  left(record: Listed): boolean;
  leftNoun: string;
}

function sourceOf(kind: string): Source | null {
  if (kind === 'unit') {
    const query = app().unitQuery();
    return { query: () => query, category: 'units', add: (id) => app().addUnit(id), noun: 'unit', name: () => app().filterName(query), left: (r) => 'skybox' in r && Boolean(r.skybox), leftNoun: 'skybox unit' };
  }
  if (kind === 'doodad') {
    const query = app().doodadQuery();
    return { query: () => query, category: 'doodads', add: (id) => app().addDoodad(id), noun: 'doodad', name: () => doodadFilterName(query), left: () => false, leftNoun: '' };
  }
  return null;
}

/** Every record the list shows, all pages. */
async function listedRecords(source: Source, query: UnitQuery | DoodadQuery): Promise<Listed[]> {
  const units: Listed[] = [];
  let total = Infinity;
  while (units.length < total) {
    const page = await app().getJson<Page<Listed>>(app().records(source.category, { ...query, offset: String(units.length), limit: String(PAGE) }));
    total = page.total;
    if (!page.items.length) break;
    units.push(...page.items);
  }
  if (units.length !== total) throw new Error(`add all: the list changed while it was read (${units.length} of ${total})`);
  return units;
}

export function installAddAll(): AddAllApi {
  const button = byId('add-all');

  /** What the last run did, for the tests and the status line. */
  const run: AddAllRun = { asked: 0, added: 0, failed: [], running: false, layout: [], landmark: null, skipped: [] };

  // ---- confirm dialog ----

  const question = make('div', { className: 'question' });
  const confirm = new ConfirmDialog({ id: 'add-all-dialog', title: 'add all', yesText: 'add', content: [question] });

  function ask(text: string): Promise<boolean> {
    question.textContent = text;
    const asking = confirm.ask();
    confirm.yes.focus();
    return asking;
  }

  /** `kind`: 'unit' (the units tab) or 'doodad' (the doodads tab). */
  async function addAll(kind = 'unit'): Promise<void> {
    if (run.running) return;
    // The filters as the list showed them: the query, and the landmark's name.
    const source = sourceOf(kind);
    if (!source) throw new Error(`add all: unknown kind ${kind}`);
    const query = source.query();
    const name = source.name();
    const listed = await listedRecords(source, query);
    // Skybox units are backdrops, not units to stand on the map: left out, and said so.
    const skipped = listed.filter(source.left);
    const ids = listed.filter((record) => !source.left(record)).map((record) => record.id);
    const skippedText = skipped.length ? ` ${skipped.length} ${source.leftNoun}${skipped.length === 1 ? ' is' : 's are'} left out: ${skipped.map((unit) => unit.id).join(', ')}.` : '';
    if (!ids.length) {
      app().setStatus(listed.length ? `add all: only ${source.leftNoun}s in the list.${skippedText}` : 'add all: the list is empty');
      return;
    }
    const sure = await ask(`Are you sure you want to add ${ids.length} ${source.noun}${ids.length === 1 ? '' : 's'} to the map?${skippedText}`);
    if (!sure) return;
    Object.assign(run, { asked: ids.length, added: 0, failed: [], running: true, layout: [], landmark: null, skipped: skipped.map((unit) => unit.id) });
    // The units already on the map: the new block goes next to them.
    const before = new Set(app().items.map((item) => item.id));
    const made: (number | null)[] = [];
    let next = 0;
    const worker = async (): Promise<void> => {
      while (next < ids.length) {
        const id = ids[next++] ?? '';
        try {
          made.push(await source.add(id));
          run.added++;
        } catch (error) {
          run.failed.push(`${id}: ${messageOf(error)}`);
        }
        app().setStatus(`add all: ${run.added + run.failed.length} of ${ids.length}`);
      }
    };
    try {
      await Promise.all(Array.from({ length: LOADERS }, worker));
      const items = made.map((id) => app().items.find((item) => item.id === id)).filter((item): item is Item => Boolean(item));
      run.layout = arrange(items, app().items.filter((item) => before.has(item.id)));
      // Look at the new block and keep the view as a landmark.
      if (run.layout.length) {
        const box = {
          x0: Math.min(...run.layout.map((l) => l.x - l.cell / 2)),
          x1: Math.max(...run.layout.map((l) => l.x + l.cell / 2)),
          y0: Math.min(...run.layout.map((l) => l.y - l.cell / 2)),
          y1: Math.max(...run.layout.map((l) => l.y + l.cell / 2)),
        };
        run.landmark = app().addLandmark({ name, ...app().frameBox(box) });
      }
      app().setStatus(run.failed.length ? `add all: ${run.added} added, ${run.failed.length} failed: ${run.failed.join('; ')}` : `add all: ${run.added} added`);
      for (const line of run.failed) console.warn('add all failed: ' + line);
    } finally {
      run.running = false;
    }
  }

  button.addEventListener('click', () => addAll('unit').catch(app().reportFailure));
  byId('doodad-add-all').addEventListener('click', () => addAll('doodad').catch(app().reportFailure));

  return {
    addAll,
    arrangeBySize: arrange,
    addAllState: () => ({ ...run, failed: [...run.failed], skipped: [...run.skipped], layout: run.layout.map((l) => ({ ...l })), dialogOpen: confirm.dialog.isOpen, question: question.textContent }),
  };
}

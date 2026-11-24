// "add all": adds one instance of every record a gallery list shows (its
// search and filters, ui/gallery), after a dialog asks to confirm the count.
// Each category with `addAll` has the button (ui.addGalleryTool). Records the server marks as
// not placeable (SC2: skybox units, a backdrop model) are not added, and
// the dialog names them.
// The new items are laid out on the ground by size (layout.ts); on a map
// with items already, the block goes next to them.
// The camera then frames the new block, kept as a landmark (core/landmarks.ts)
// named after the list filters (the game's listName).

import type { RecordSummary } from '../../../shared/protocol';
import type { Page } from '../../../shared/records';
import type { ApiClient, Feature } from '../../core/context';
import type { AddAllRun, Item } from '../../core/types';
import { make, messageOf } from '../../core/dom';
import { ConfirmDialog } from '../../ui/components/dialog';
import { arrange } from './layout';

const PAGE = 500; // the server's largest page
const LOADERS = 6; // models loading at once

/** Every record the list shows, all pages. */
async function listedRecords(api: ApiClient, category: string, query: Record<string, string>): Promise<RecordSummary[]> {
  const units: RecordSummary[] = [];
  let total = Infinity;
  while (units.length < total) {
    const page = await api.getJson<Page<RecordSummary>>(api.records(category, { ...query, offset: String(units.length), limit: String(PAGE) }));
    total = page.total;
    if (!page.items.length) break;
    units.push(...page.items);
  }
  if (units.length !== total) throw new Error(`add all: the list changed while it was read (${units.length} of ${total})`);
  return units;
}

export const addAllFeature: Feature = {
  id: 'add-all',
  install({ api, games, scene, camera, status, ui, events, testApi }) {
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

    /** `kind`: a category noun of the game (the first category's when not given: SC2 'unit'). */
    async function addAll(kind = games.plugin().categories[0]?.noun ?? ''): Promise<void> {
      if (run.running) return;
      const category = games.categoryOf(kind).id;
      // The filters as the list showed them: the query, and the landmark's name.
      const query = ui.galleryQuery(category);
      const name = games.plugin().listName(category, query);
      const listed = await listedRecords(api, category, query);
      // What the server marks as not placeable (SC2 skybox units: backdrops, not units to stand on the map), said so.
      const skipped = listed.filter((record) => !record.placeable);
      const ids = listed.filter((record) => record.placeable).map((record) => record.id);
      const leftNoun = skipped[0]?.notPlaceableAs ?? `unplaceable ${kind}`;
      const skippedText = skipped.length ? ` ${skipped.length} ${leftNoun}${skipped.length === 1 ? ' is' : 's are'} left out: ${skipped.map((unit) => unit.id).join(', ')}.` : '';
      if (!ids.length) {
        status.setStatus(listed.length ? `add all: only ${leftNoun}s in the list.${skippedText}` : 'add all: the list is empty');
        return;
      }
      const sure = await ask(`Are you sure you want to add ${ids.length} ${kind}${ids.length === 1 ? '' : 's'} to the map?${skippedText}`);
      if (!sure) return;
      Object.assign(run, { asked: ids.length, added: 0, failed: [], running: true, layout: [], landmark: null, skipped: skipped.map((unit) => unit.id) });
      // The units already on the map: the new block goes next to them.
      const before = new Set(scene.items.map((item) => item.id));
      const made: (number | null)[] = [];
      let next = 0;
      const worker = async (): Promise<void> => {
        while (next < ids.length) {
          const id = ids[next++] ?? '';
          try {
            made.push(await scene.addRecord(category, id));
            run.added++;
          } catch (error) {
            run.failed.push(`${id}: ${messageOf(error)}`);
          }
          status.setStatus(`add all: ${run.added + run.failed.length} of ${ids.length}`);
        }
      };
      try {
        await Promise.all(Array.from({ length: LOADERS }, worker));
        const items = made.map((id) => scene.items.find((item) => item.id === id)).filter((item): item is Item => Boolean(item));
        run.layout = arrange(scene, items, scene.items.filter((item) => before.has(item.id)));
        events.emit('scene-edited', { what: 'add all' });
        // Look at the new block and keep the view as a landmark.
        if (run.layout.length) {
          const box = {
            x0: Math.min(...run.layout.map((l) => l.x - l.cell / 2)),
            x1: Math.max(...run.layout.map((l) => l.x + l.cell / 2)),
            y0: Math.min(...run.layout.map((l) => l.y - l.cell / 2)),
            y1: Math.max(...run.layout.map((l) => l.y + l.cell / 2)),
          };
          run.landmark = camera.addLandmark({ name, ...camera.frameBox(box) });
        }
        status.setStatus(run.failed.length ? `add all: ${run.added} added, ${run.failed.length} failed: ${run.failed.join('; ')}` : `add all: ${run.added} added`);
        for (const line of run.failed) console.warn('add all failed: ' + line);

      } finally {
        run.running = false;
      }
    }

    ui.addGalleryTool({
      id: 'add-all',
      label: 'add all',
      title: (category) => `add every ${category.noun} of the list to the scene`,
      when: (category) => category.addAll,
      run: (category) => addAll(category.noun),
    });
    testApi.app({
      addAll,
      addAllState: () => ({ ...run, failed: [...run.failed], skipped: [...run.skipped], layout: run.layout.map((l) => ({ ...l })), dialogOpen: confirm.dialog.isOpen, question: question.textContent }),
    });
  },
};

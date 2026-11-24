// The gallery: one tab and one pane per category of the current dataset,
// built from what the server sends (/api/<game>/categories, SPEC-VIEWER
// 10.1). No game has gallery code of its own (R-VIEW-25): the rows, the
// filters and the preview card come from the categories, the record rows
// and the game's describe. Built again when the dataset changes; the tab
// shown stays when the new dataset has it. The scene list is ui/instances.ts.

import type { GalleryTool, RowDrag, UiService } from '../../core/context';
import type { EventBus, ViewerEvents } from '../../core/bus';
import { byId, make } from '../../core/dom';
import { buildPane, type Pane, type PaneDeps } from './pane';

export type GalleryApi = Pick<UiService, 'galleryQuery' | 'addGalleryTool' | 'setRowDrag'>;

export type GalleryDeps = Omit<PaneDeps, 'tools' | 'drag'> & { readonly events: EventBus<ViewerEvents> };

export function installGallery(deps: GalleryDeps): GalleryApi {
  const tools: GalleryTool[] = [];
  let drag: RowDrag | null = null;
  const tabs = byId('tabs');
  const panel = byId('gallery');
  const panes = new Map<string, Pane>();
  let shown: string | null = null;
  /** Counts the builds, so a slow categories answer for an earlier dataset is dropped. */
  let build = 0;

  function showTab(id: string): void {
    shown = id;
    for (const [other, pane] of panes) {
      byId('tab-' + other).classList.toggle('on', other === id);
      pane.node.hidden = other !== id;
    }
  }

  async function setupGallery(): Promise<void> {
    const mine = ++build;
    const categories = await deps.api.categories();
    if (mine !== build) return;
    // The search text stays over a rebuild; the filters start at "any" (their values are the new dataset's).
    const searches = new Map([...panes].map(([id, pane]) => [id, pane.query()['q'] ?? '']));
    for (const pane of panes.values()) pane.node.remove();
    panes.clear();
    const buttons = categories.map((category) => {
      const button = make('button', { id: 'tab-' + category.id, textContent: category.label });
      button.addEventListener('click', () => showTab(category.id));
      return button;
    });
    tabs.replaceChildren(...buttons);
    for (const category of categories) {
      const pane = buildPane({ ...deps, tools, drag }, category, searches.get(category.id) ?? '');
      panes.set(category.id, pane);
      panel.append(pane.node);
    }
    const first = categories[0];
    if (first) showTab(shown !== null && panes.has(shown) ? shown : first.id);
    await Promise.all([...panes.values()].map((pane) => pane.relist()));
  }

  // Built at startup, and again for each dataset (and game) change.
  deps.events.on('startup', ({ wait }) => wait(setupGallery()));
  deps.events.on('dataset-changed', () => {
    setupGallery().catch(deps.status.reportFailure);
  });

  function galleryQuery(category: string): Record<string, string> {
    const pane = panes.get(category);
    if (!pane) throw new Error(`gallery: no category "${category}"`);
    return pane.query();
  }

  return {
    galleryQuery,
    addGalleryTool(tool) {
      if (tools.some((t) => t.id === tool.id)) throw new Error(`gallery: two tools "${tool.id}"`);
      tools.push(tool);
    },
    setRowDrag(next) {
      if (drag) throw new Error('gallery: the row drag is set already');
      drag = next;
    },
  };
}

// Gallery panel, doodads tab: the doodad browser with its search, its type
// and terrain set filters, and the preview card. A doodad is a prop the map
// editor places (CActorDoodad): trees, rocks, wreckage, cliff dressing.
// Adding one is core/scene.ts addDoodad; "add all" is features/addall.

import type { DoodadRecord, DoodadSummary, Page } from '../../../shared/records';
import { app, type CoreApi, type DatasetsApi, type DoodadQuery } from '../../core/app';
import { byId, byIdAs, make, rows } from '../../core/dom';
import { PagedList } from '../components/pagedlist';
import { range } from './units';

/** "8 variations", "editor only": what the list says under a doodad's name. */
function notes(doodad: DoodadSummary | DoodadRecord): string {
  const out = [doodad.type, doodad.id];
  if (doodad.variations > 1) out.push(`${doodad.variations} variations`);
  if (doodad.editorOnly) out.push('editor only');
  if (doodad.inMap) out.push('in map');
  return out.join(' · ');
}

export function installDoodads(core: CoreApi & Pick<DatasetsApi, 'onDatasetChange'>): { setupDoodads(): Promise<void>; doodadQuery(): DoodadQuery } {
  const { shown } = core;
  const box = byIdAs('doodad-search', HTMLInputElement);
  const list = byId('doodads');
  const count = byId('doodad-count');
  const typeSelect = byIdAs('doodad-type', HTMLSelectElement);
  const tilesetSelect = byIdAs('doodad-tileset', HTMLSelectElement);
  const preview = byId('doodad-preview');
  const filter = { type: '', tileset: '' };
  let selected: string | null = null;

  /** The doodad search query of the list as shown. */
  const doodadQuery = (): DoodadQuery => ({ q: box.value.trim(), type: filter.type, tileset: filter.tileset });

  function row(doodad: DoodadSummary): HTMLLIElement {
    const node = make('li', { draggable: true, title: 'click to preview, double-click for its textures, drag into the view to place' }, [
      make('div', { className: 'name', textContent: doodad.name }),
      make('div', { className: 'sub', textContent: notes(doodad) }),
    ]);
    node.dataset.id = doodad.id;
    node.classList.toggle('selected', doodad.id === selected);
    node.addEventListener('click', () => select(doodad.id).catch((error: unknown) => app().reportFailure(error)));
    node.addEventListener('dblclick', () => app().openTexturesFor('doodad', doodad.id).catch(app().reportFailure));
    node.addEventListener('dragstart', (e) => app().startDrag(e, doodad, 'doodad'));
    node.addEventListener('dragend', () => app().endGhost());
    return node;
  }

  // The list loads a page at a time as it scrolls.
  const pages = new PagedList<DoodadSummary>({
    list,
    pageSize: 60,
    fetchPage: (offset, limit) => app().getJson<Page<DoodadSummary>>(app().records('doodads', { ...doodadQuery(), offset: String(offset), limit: String(limit) })),
    renderItem: row,
    onTotal: (total) => {
      count.textContent = `${total} doodads`;
    },
    onError: (error) => app().reportFailure(error),
  });
  const relist = (): void => {
    pages.reset().catch((error: unknown) => app().reportFailure(error));
  };

  /** Show one doodad's data in the preview card. */
  async function select(id: string): Promise<void> {
    selected = id;
    for (const node of rows(list)) node.classList.toggle('selected', node.dataset.id === id);
    const a = app();
    const doodad = await a.record('doodad', id);
    if (selected !== id) return; // another doodad was selected meanwhile
    const facts = [notes(doodad), `scale ${range(shown, a.dataScale(doodad, 0)[0], a.dataScale(doodad, 1)[0])} · ${doodad.autoRotate ? 'random angle' : 'fixed angle'}`];
    const rate = doodad.animSpeed * doodad.timeScale;
    if (Math.abs(rate - 1) > 1e-6) facts.push(`anim ×${shown(rate)}`);
    if (doodad.footprint) facts.push(`footprint ${doodad.footprint}`);
    if (doodad.tilesets.length) facts.push(`terrain sets: ${doodad.tilesets.join(', ')}`);
    if (doodad.tint) facts.push(`tint ${doodad.tint.map(shown).join(', ')}`);
    if (doodad.editorOnly) facts.push(`draws nothing in game; shown: editor model ${String(doodad.editorModel)}`);
    const addButton = make('button', { id: 'doodad-preview-add', textContent: 'add to scene' });
    addButton.addEventListener('click', () => app().addDoodad(doodad.id).catch(app().reportFailure));
    preview.replaceChildren(
      make('div', { className: 'top' }, [make('div', { className: 'name', textContent: doodad.name }), addButton]),
      make('div', { className: 'facts' }, facts.map((text) => make('div', { textContent: text, title: text }))),
    );
  }

  /** Fill the filters with what the current dataset has; both start at "any". */
  async function fillFilters(): Promise<void> {
    const facets = await app().facets();
    Object.assign(filter, { type: '', tileset: '' });
    typeSelect.replaceChildren(make('option', { value: '', textContent: 'any type' }), ...facets.doodadTypes.map((type) => make('option', { value: type, textContent: type.toLowerCase() })));
    tilesetSelect.replaceChildren(make('option', { value: '', textContent: 'any terrain' }), ...[...facets.tilesets].sort().map((set) => make('option', { value: set, textContent: set })));
  }
  typeSelect.addEventListener('change', () => {
    filter.type = typeSelect.value;
    relist();
  });
  tilesetSelect.addEventListener('change', () => {
    filter.tileset = tilesetSelect.value;
    relist();
  });
  box.addEventListener('input', relist);

  /** Fill the filters, then the first page of doodads. Again when the current dataset changes. */
  const setupDoodads = (): Promise<void> => fillFilters().then(() => pages.reset());
  core.onDatasetChange(() => {
    selected = null;
    preview.replaceChildren();
    setupDoodads().catch((error: unknown) => app().reportFailure(error));
  });
  return { setupDoodads, doodadQuery };
}

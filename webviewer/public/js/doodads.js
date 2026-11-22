// Gallery panel, doodads tab: the doodad browser with its search, its type
// and terrain set filters, and the preview card. A doodad is a prop the map
// editor places (CActorDoodad): trees, rocks, wreckage, cliff dressing.
// Adding one is scene.js addDoodad; "add all" is addall.js.
'use strict';

(() => {
  const app = window.SC2App;
  const { $, el, shown } = app;

  const box = $('doodad-search');
  const list = $('doodads');
  const count = $('doodad-count');
  const typeSelect = $('doodad-type');
  const tilesetSelect = $('doodad-tileset');
  const preview = $('doodad-preview');
  const filter = { type: '', tileset: '' };
  let selected = null;

  /** The doodad search query of the list as shown. */
  const doodadQuery = () => ({ q: box.value.trim(), type: filter.type, tileset: filter.tileset });

  /** "8 variations", "editor only": what the list says under a doodad's name. */
  function notes(doodad) {
    const out = [doodad.type, doodad.id];
    if (doodad.variations > 1) out.push(`${doodad.variations} variations`);
    if (doodad.editorOnly) out.push('editor only');
    if (doodad.inMap) out.push('in map');
    return out.join(' · ');
  }

  function row(doodad) {
    const node = el('li', { draggable: true, title: 'click to preview, double-click for its textures, drag into the view to place' }, [
      el('div', { className: 'name', textContent: doodad.name }),
      el('div', { className: 'sub', textContent: notes(doodad) }),
    ]);
    node.dataset.id = doodad.id;
    node.classList.toggle('selected', doodad.id === selected);
    node.addEventListener('click', () => select(doodad.id).catch((error) => app.reportFailure(error)));
    node.addEventListener('dblclick', () => app.openTexturesFor('doodad', doodad.id).catch(app.reportFailure));
    node.addEventListener('dragstart', (e) => app.startDrag(e, doodad, 'doodad'));
    node.addEventListener('dragend', () => app.endGhost());
    return node;
  }

  // The list loads a page at a time as it scrolls.
  const pages = new SC2Components.PagedList({
    list,
    pageSize: 60,
    fetchPage: (offset, limit) => app.getJson(app.api('/api/doodads', { ...doodadQuery(), offset: String(offset), limit: String(limit) })),
    renderItem: row,
    onTotal: (total) => {
      count.textContent = `${total} doodads`;
    },
    onError: (error) => app.reportFailure(error),
  });
  const relist = () => pages.reset().catch((error) => app.reportFailure(error));

  const range = (low, high) => (Math.abs(high - low) < 1e-6 ? shown(low) : `${shown(low)} to ${shown(high)}`);

  /** Show one doodad's data in the preview card. */
  async function select(id) {
    selected = id;
    for (const node of list.children) node.classList.toggle('selected', node.dataset.id === id);
    const doodad = await app.record('doodad', id);
    if (selected !== id) return; // another doodad was selected meanwhile
    const facts = [
      notes(doodad),
      `scale ${range(app.dataScale(doodad, 0)[0], app.dataScale(doodad, 1)[0])} · ${doodad.autoRotate ? 'random angle' : 'fixed angle'}`,
    ];
    const rate = doodad.animSpeed * doodad.timeScale;
    if (Math.abs(rate - 1) > 1e-6) facts.push(`anim ×${shown(rate)}`);
    if (doodad.footprint) facts.push(`footprint ${doodad.footprint}`);
    if (doodad.tilesets.length) facts.push(`terrain sets: ${doodad.tilesets.join(', ')}`);
    if (doodad.tint) facts.push(`tint ${doodad.tint.map(shown).join(', ')}`);
    if (doodad.editorOnly) facts.push(`draws nothing in game; shown: editor model ${doodad.editorModel}`);
    const addButton = el('button', { id: 'doodad-preview-add', textContent: 'add to scene' });
    addButton.addEventListener('click', () => app.addDoodad(doodad.id).catch(app.reportFailure));
    preview.replaceChildren(
      el('div', { className: 'top' }, [el('div', { className: 'name', textContent: doodad.name }), addButton]),
      el('div', { className: 'facts' }, facts.map((text) => el('div', { textContent: text, title: text }))),
    );
  }

  /** Fill the filters with what the current dataset has; both start at "any". */
  async function fillFilters() {
    const facets = await app.getJson(app.api('/api/facets'));
    Object.assign(filter, { type: '', tileset: '' });
    typeSelect.replaceChildren(el('option', { value: '', textContent: 'any type' }), ...facets.doodadTypes.map((type) => el('option', { value: type, textContent: type.toLowerCase() })));
    tilesetSelect.replaceChildren(el('option', { value: '', textContent: 'any terrain' }), ...[...facets.tilesets].sort().map((set) => el('option', { value: set, textContent: set })));
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
  app.setupDoodads = () => fillFilters().then(() => pages.reset());
  app.onDatasetChange(() => {
    selected = null;
    preview.replaceChildren();
    app.setupDoodads().catch((error) => app.reportFailure(error));
  });
  app.doodadQuery = doodadQuery;
})();

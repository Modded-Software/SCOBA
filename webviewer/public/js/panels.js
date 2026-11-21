// Gallery panel: the tabs, the model file search, and the unit browser with
// its filters and preview card. The scene list is the instances panel (scene.js).
'use strict';

(() => {
  const app = window.SC2App;
  const { $, el, shown } = app;

  // ---- tabs ----

  function showTab(name) {
    for (const tab of ['units', 'models']) {
      $('tab-' + tab).classList.toggle('on', tab === name);
      $('pane-' + tab).hidden = tab !== name;
    }
  }
  $('tab-units').addEventListener('click', () => showTab('units'));
  $('tab-models').addEventListener('click', () => showTab('models'));

  // ---- model files tab ----

  const searchBox = $('search');
  const resultList = $('results');
  let searchSeq = 0;
  async function search() {
    const seq = ++searchSeq;
    const query = searchBox.value.trim();
    if (!query) {
      resultList.replaceChildren();
      return;
    }
    const body = await app.getJson('/api/models?limit=60&q=' + encodeURIComponent(query));
    if (seq !== searchSeq) return; // a newer search is on its way
    resultList.replaceChildren(
      ...body.items.map((path) => {
        const button = el('button', { textContent: path, title: path });
        button.dataset.path = path;
        button.addEventListener('click', () => app.add(path).catch(app.reportFailure));
        return el('li', {}, [button]);
      }),
    );
  }
  searchBox.addEventListener('input', () => search().catch((error) => app.setStatus(error.message)));

  // ---- units tab ----

  const unitBox = $('unit-search');
  const unitList = $('units');
  const unitCount = $('unit-count');
  const raceBar = $('races');
  const kindSelect = $('kind');
  const familySelect = $('family');
  const preview = $('preview');
  // family null: any family; '' : units with no family.
  const filter = { race: '', kind: '', family: null };

  /** The unit search query of the list as shown: q, race, kind and, when set, family. */
  function unitQuery() {
    const query = { q: unitBox.value.trim(), race: filter.race, kind: filter.kind };
    if (filter.family !== null) query.family = filter.family;
    return query;
  }
  let selected = null;

  function unitRow(unit) {
    const row = el('li', { draggable: true, title: 'click to preview, drag into the view to place' }, [
      app.iconNode(unit.icon),
      el('div', { className: 'text' }, [
        el('div', { className: 'name', textContent: unit.name }),
        el('div', { className: 'sub', textContent: `${unit.race} · ${unit.kind} · ${unit.id}${unit.skybox ? ' · skybox' : ''}` }),
      ]),
    ]);
    row.dataset.id = unit.id;
    row.classList.toggle('selected', unit.id === selected);
    row.addEventListener('click', () => select(unit.id).catch((error) => app.setStatus(error.message)));
    row.addEventListener('dblclick', () => app.addUnit(unit.id).catch(app.reportFailure));
    row.addEventListener('dragstart', (e) => app.startDrag(e, unit));
    row.addEventListener('dragend', () => app.endGhost());
    return row;
  }

  // The list loads a page at a time as it scrolls.
  const unitPages = new SC2Components.LazyList({
    list: unitList,
    pageSize: 60,
    fetchPage: (offset, limit) =>
      app.getJson('/api/units?' + new URLSearchParams({ ...unitQuery(), offset: String(offset), limit: String(limit) })),
    renderItem: unitRow,
    onTotal: (total) => {
      unitCount.textContent = `${total} units`;
    },
    onError: (error) => app.setStatus(error.message),
  });
  const listUnits = () => unitPages.reset();
  const relist = () => listUnits().catch((error) => app.setStatus(error.message));

  const range = (low, high) => (Math.abs(high - low) < 1e-6 ? shown(low) : `${shown(low)} to ${shown(high)}`);

  async function select(id) {
    selected = id;
    for (const row of unitList.children) row.classList.toggle('selected', row.dataset.id === id);
    const unit = await app.getJson('/api/unit?id=' + encodeURIComponent(id));
    if (selected !== id) return; // another unit was selected meanwhile
    const low = app.dataScale(unit, 0)[0];
    const high = app.dataScale(unit, 1)[0];
    const facts = [`${unit.race} · ${unit.kind}${unit.family ? ' · ' + unit.family : ''}${unit.inMap ? ' · in map' : ''}`, `id ${unit.id}`, `scale ${range(low, high)}`];
    const rate = unit.animSpeed * unit.timeScale;
    const speeds = [];
    if (Math.abs(rate - 1) > 1e-6) speeds.push(`anim ×${shown(rate)}`);
    if (unit.speed > 0 && unit.walkAnimMoveSpeed > 0) speeds.push(`walk ×${shown((rate * unit.speed) / unit.walkAnimMoveSpeed)}`);
    if (speeds.length) facts.push(speeds.join(' · '));
    if (unit.height) facts.push(`height ${shown(unit.height)}`);
    if (unit.tint) facts.push(`tint ${unit.tint.map(shown).join(', ')}`);
    const picture = unit.portrait || unit.icon;
    const addButton = el('button', { id: 'preview-add', textContent: 'add to scene' });
    addButton.addEventListener('click', () => app.addUnit(unit.id).catch(app.reportFailure));
    preview.replaceChildren(
      picture ? el('img', { className: 'portrait', src: '/icon/' + picture, alt: unit.name }) : el('span', { className: 'portrait' }),
      // Name and add on one line; the facts scroll inside the fixed-height card.
      el('div', { className: 'body' }, [
        el('div', { className: 'top' }, [el('div', { className: 'name', textContent: unit.name }), addButton]),
        el('div', { className: 'facts' }, facts.map((text) => el('div', { textContent: text, title: text }))),
      ]),
    );
  }

  async function setupFilters() {
    const facets = await app.getJson('/api/facets');
    const raceButton = (value, label) => {
      const button = el('button', { textContent: label });
      button.dataset.race = value;
      button.classList.toggle('on', value === filter.race);
      button.addEventListener('click', () => {
        filter.race = value;
        for (const other of raceBar.children) other.classList.toggle('on', other === button);
        relist();
      });
      return button;
    };
    raceBar.replaceChildren(raceButton('', 'all'), ...facets.races.map((race) => raceButton(race, race.toLowerCase())));
    kindSelect.replaceChildren(el('option', { value: '', textContent: 'any kind' }), ...facets.kinds.map((kind) => el('option', { value: kind, textContent: kind.toLowerCase() })));
    kindSelect.addEventListener('change', () => {
      filter.kind = kindSelect.value;
      relist();
    });
    // Family (ObjectFamily): Melee is the ladder and multiplayer data.
    // Option values carry a prefix so "any" and "no family" ('') differ.
    familySelect.replaceChildren(
      el('option', { value: 'any', textContent: 'any family' }),
      ...facets.families.map((family) => el('option', { value: 'is:' + family, textContent: family ? family.toLowerCase() : '(no family)' })),
    );
    familySelect.addEventListener('change', () => {
      filter.family = familySelect.value === 'any' ? null : familySelect.value.slice(3);
      relist();
    });
  }
  unitBox.addEventListener('input', relist);

  /** Fill the filters, then the first page of units. */
  app.setupUnits = () => setupFilters().then(listUnits);
  app.unitQuery = unitQuery;
})();

// Gallery panel: the tabs, the model file search, and the unit browser with
// its filters and preview card. The scene list is the instances panel (ui/instances.ts).

import type { Page, UnitSummary } from '../../../shared/records';
import { app, type CoreApi, type DatasetsApi, type UnitQuery } from '../../core/app';
import { byId, byIdAs, make, rows } from '../../core/dom';
import { PagedList } from '../components/pagedlist';

const TABS = ['units', 'doodads', 'models'];

/** "1.2" or "1.2 to 1.5". */
export const range = (shown: (v: number) => string, low: number, high: number): string => (Math.abs(high - low) < 1e-6 ? shown(low) : `${shown(low)} to ${shown(high)}`);

export function installUnits(core: CoreApi & Pick<DatasetsApi, 'onDatasetChange'>): { setupUnits(): Promise<void>; unitQuery(): UnitQuery } {
  const { shown } = core;

  // ---- tabs ----

  function showTab(name: string): void {
    for (const tab of TABS) {
      byId('tab-' + tab).classList.toggle('on', tab === name);
      byId('pane-' + tab).hidden = tab !== name;
    }
  }
  for (const tab of TABS) byId('tab-' + tab).addEventListener('click', () => showTab(tab));

  // ---- model files tab ----

  const searchBox = byIdAs('search', HTMLInputElement);
  const resultList = byId('results');
  let searchSeq = 0;
  async function search(): Promise<void> {
    const seq = ++searchSeq;
    const query = searchBox.value.trim();
    if (!query) {
      resultList.replaceChildren();
      return;
    }
    const body = await app().getJson<Page<string>>(app().records('models', { limit: '60', q: query }));
    if (seq !== searchSeq) return; // a newer search is on its way
    resultList.replaceChildren(
      ...body.items.map((path) => {
        const button = make('button', { textContent: path, title: path });
        button.dataset.path = path;
        button.addEventListener('click', () => app().add(path).catch(app().reportFailure));
        return make('li', {}, [button]);
      }),
    );
  }
  searchBox.addEventListener('input', () => search().catch((error: unknown) => app().reportFailure(error)));

  // ---- units tab ----

  const unitBox = byIdAs('unit-search', HTMLInputElement);
  const unitList = byId('units');
  const unitCount = byId('unit-count');
  const raceBar = byId('races');
  const kindSelect = byIdAs('kind', HTMLSelectElement);
  const familySelect = byIdAs('family', HTMLSelectElement);
  const preview = byId('preview');
  // family null: any family; '' : units with no family.
  const filter: { race: string; kind: string; family: string | null } = { race: '', kind: '', family: null };

  /** The unit search query of the list as shown: q, race, kind and, when set, family. */
  function unitQuery(): UnitQuery {
    const query: UnitQuery = { q: unitBox.value.trim(), race: filter.race, kind: filter.kind };
    if (filter.family !== null) query.family = filter.family;
    return query;
  }
  let selected: string | null = null;

  function unitRow(unit: UnitSummary): HTMLLIElement {
    const row = make('li', { draggable: true, title: 'click to preview, double-click for its textures, drag into the view to place' }, [
      app().iconNode(unit.icon),
      // (The list is the current dataset's, and so is the icon.)
      make('div', { className: 'text' }, [
        make('div', { className: 'name', textContent: unit.name }),
        make('div', { className: 'sub', textContent: `${unit.race} · ${unit.kind} · ${unit.id}${unit.skybox ? ' · skybox' : ''}` }),
      ]),
    ]);
    row.dataset.id = unit.id;
    row.classList.toggle('selected', unit.id === selected);
    row.addEventListener('click', () => select(unit.id).catch((error: unknown) => app().reportFailure(error)));
    row.addEventListener('dblclick', () => app().openTexturesFor('unit', unit.id).catch(app().reportFailure));
    row.addEventListener('dragstart', (e) => app().startDrag(e, unit));
    row.addEventListener('dragend', () => app().endGhost());
    return row;
  }

  // The list loads a page at a time as it scrolls.
  const unitPages = new PagedList<UnitSummary>({
    list: unitList,
    pageSize: 60,
    fetchPage: (offset, limit) => app().getJson<Page<UnitSummary>>(app().records('units', { ...unitQuery(), offset: String(offset), limit: String(limit) })),
    renderItem: unitRow,
    onTotal: (total) => {
      unitCount.textContent = `${total} units`;
    },
    onError: (error) => app().reportFailure(error),
  });
  const listUnits = (): Promise<void> => unitPages.reset();
  const relist = (): void => {
    listUnits().catch((error: unknown) => app().reportFailure(error));
  };

  async function select(id: string): Promise<void> {
    selected = id;
    for (const row of rows(unitList)) row.classList.toggle('selected', row.dataset.id === id);
    const a = app();
    const unit = await a.record('unit', id);
    if (selected !== id) return; // another unit was selected meanwhile
    const low = a.dataScale(unit, 0)[0];
    const high = a.dataScale(unit, 1)[0];
    const facts = [`${unit.race} · ${unit.kind}${unit.family ? ' · ' + unit.family : ''}${unit.inMap ? ' · in map' : ''}`, `id ${unit.id}`, `scale ${range(shown, low, high)}`];
    const rate = unit.animSpeed * unit.timeScale;
    const speeds = [];
    if (Math.abs(rate - 1) > 1e-6) speeds.push(`anim ×${shown(rate)}`);
    if (unit.speed > 0 && unit.walkAnimMoveSpeed !== null && unit.walkAnimMoveSpeed > 0) speeds.push(`walk ×${shown((rate * unit.speed) / unit.walkAnimMoveSpeed)}`);
    if (speeds.length) facts.push(speeds.join(' · '));
    if (unit.height) facts.push(`height ${shown(unit.height)}`);
    if (unit.tint) facts.push(`tint ${unit.tint.map(shown).join(', ')}`);
    const picture = unit.portrait || unit.icon;
    const addButton = make('button', { id: 'preview-add', textContent: 'add to scene' });
    addButton.addEventListener('click', () => app().addUnit(unit.id).catch(app().reportFailure));
    preview.replaceChildren(
      picture ? make('img', { className: 'portrait', src: a.iconUrl(picture, unit.dataset), alt: unit.name }) : make('span', { className: 'portrait' }),
      // Name and add on one line; the facts scroll inside the fixed-height card.
      make('div', { className: 'body' }, [
        make('div', { className: 'top' }, [make('div', { className: 'name', textContent: unit.name }), addButton]),
        make('div', { className: 'facts' }, facts.map((text) => make('div', { textContent: text, title: text }))),
      ]),
    );
  }

  /** Fill the filters with what the current dataset has; every filter starts at "any". */
  async function fillFilters(): Promise<void> {
    const facets = await app().facets();
    Object.assign(filter, { race: '', kind: '', family: null });
    const raceButton = (value: string, label: string): HTMLButtonElement => {
      const button = make('button', { textContent: label });
      button.dataset.race = value;
      button.classList.toggle('on', value === filter.race);
      button.addEventListener('click', () => {
        filter.race = value;
        for (const other of rows(raceBar)) other.classList.toggle('on', other === button);
        relist();
      });
      return button;
    };
    raceBar.replaceChildren(raceButton('', 'all'), ...facets.races.map((race) => raceButton(race, race.toLowerCase())));
    kindSelect.replaceChildren(make('option', { value: '', textContent: 'any kind' }), ...facets.kinds.map((kind) => make('option', { value: kind, textContent: kind.toLowerCase() })));
    // Family (ObjectFamily): Melee is the ladder and multiplayer data.
    // Option values carry a prefix so "any" and "no family" ('') differ.
    familySelect.replaceChildren(
      make('option', { value: 'any', textContent: 'any family' }),
      ...facets.families.map((family) => make('option', { value: 'is:' + family, textContent: family ? family.toLowerCase() : '(no family)' })),
    );
  }
  kindSelect.addEventListener('change', () => {
    filter.kind = kindSelect.value;
    relist();
  });
  familySelect.addEventListener('change', () => {
    filter.family = familySelect.value === 'any' ? null : familySelect.value.slice(3);
    relist();
  });
  unitBox.addEventListener('input', relist);

  /** Fill the filters, then the first page of units. Again when the current dataset changes. */
  const setupUnits = (): Promise<void> => fillFilters().then(listUnits);
  core.onDatasetChange(() => {
    selected = null;
    preview.replaceChildren();
    setupUnits().catch((error: unknown) => app().reportFailure(error));
  });
  return { setupUnits, unitQuery };
}

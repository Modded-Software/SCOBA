// The scene list in the instances panel: one row per item, where the
// selected items' rows are marked; the instance search; the clear button.

import { app, type CoreApi, type InstancesApi, type Item } from '../core/app';
import { byId, byIdAs, find, make, rows } from '../core/dom';
import { ConfirmDialog } from './components/dialog';

type NumberField = 'x' | 'y' | 'rot' | 'scale';

export function installInstances(core: CoreApi): InstancesApi {
  const { items, shown, TEAMS } = core;
  const sceneList = byId('scene');

  function numberInput(item: Item, field: NumberField, step: number): HTMLLabelElement {
    const input = make('input', { type: 'number', className: field, step: String(step), value: shown(item[field]) });
    input.addEventListener('change', () => {
      const value = Number.parseFloat(input.value);
      if (!Number.isFinite(value) || (field === 'scale' && value <= 0)) {
        input.value = shown(item[field]);
        return;
      }
      item[field] = value;
      app().applyTransform(item);
      app().saveScene();
    });
    return make('label', {}, [field, input]);
  }

  const option = (value: string, text: string): HTMLOptionElement => make('option', { value, textContent: text });

  function listRow(item: Item): HTMLLIElement {
    const unit = item.unit;
    const name = unit ? unit.name : (item.path.split('\\').pop() ?? item.path);
    const removeButton = make('button', { className: 'remove', textContent: '×', title: 'remove' });
    removeButton.addEventListener('click', () => app().remove(item.id));
    const anim = make('select', { className: 'anim' }, [option('-1', '(none)'), ...item.model.sequences.map((s, i) => option(String(i), s.name))]);
    anim.value = String(item.sequence);
    anim.addEventListener('change', () => {
      item.sequence = Number.parseInt(anim.value, 10);
      app().applySequence(item);
      app().saveScene();
    });
    const team = make(
      'select',
      { className: 'team', title: 'team colour' },
      Array.from({ length: TEAMS }, (_, i) => option(String(i), 'team ' + (i + 1))),
    );
    team.value = String(item.team);
    team.addEventListener('change', () => {
      item.team = Number.parseInt(team.value, 10);
      app().applyLook(item);
      app().saveScene();
    });
    const head: HTMLElement[] = [make('span', { className: 'name', textContent: name, title: unit ? `${unit.id}  ${item.path}` : item.path }), removeButton];
    if (unit && !unit.doodad) head.unshift(app().iconNode(unit.icon, item.dataset));
    // A doodad has model variations in place of a team colour.
    const controls: HTMLElement[] = [anim];
    if (!unit || !unit.doodad) controls.push(team);
    else if (unit.variations > 1) {
      const count = unit.variations;
      const variation = make(
        'select',
        { className: 'variation', title: 'model variation' },
        Array.from({ length: count }, (_, i) => option(String(i), `variation ${i + 1} of ${count}`)),
      );
      variation.value = String(item.variation);
      variation.addEventListener('change', () => app().setVariation(item, Number.parseInt(variation.value, 10)).catch(app().reportFailure));
      controls.push(variation);
    }
    // Where the item's data and textures come from; another choice swaps them.
    const all = app().datasets();
    if (all.length > 1) {
      const source = make('select', { className: 'dataset', title: "dataset: where this instance's data and textures come from" }, all.map((d) => option(d.id, d.label)));
      source.value = item.dataset;
      source.addEventListener('change', () =>
        app()
          .setItemDataset(item, source.value)
          .catch((error: unknown) => {
            app().reportFailure(error);
            // It stays as it was: show that.
            source.value = item.dataset;
          }),
      );
      controls.push(source);
    }
    const headNode = make('div', { className: 'head' }, head);
    const row = make('li', {}, [
      headNode,
      make('div', { className: 'row' }, controls),
      make('div', { className: 'row' }, [numberInput(item, 'x', 0.5), numberInput(item, 'y', 0.5), numberInput(item, 'rot', 15), numberInput(item, 'scale', 0.1)]),
    ]);
    row.dataset.id = String(item.id);
    if (unit) row.dataset[unit.doodad ? 'doodad' : 'unit'] = unit.id;
    // What the instance search matches: the name, the unit or doodad id, the model file.
    row.dataset.search = [name, unit ? unit.id : '', item.path].join(' ').toLowerCase();
    // A click on the row's name selects the unit in the view (features/pick).
    // With shift it adds the unit to the selection or takes it out.
    // With ctrl it selects the unit and points the camera at it.
    headNode.addEventListener('click', (e) => {
      if (e.target === removeButton) return;
      if (e.shiftKey) app().toggleSelected(item.id);
      else app().select(item.id);
      if (e.ctrlKey && !e.shiftKey) app().focusItem(item);
    });
    // A double-click opens the texture window on the unit's textures (features/textures).
    headNode.addEventListener('dblclick', (e) => {
      if (e.target !== removeButton) app().openTexturesOf(item).catch(app().reportFailure);
    });
    return row;
  }

  /** Mark the rows of the selected items and scroll the row of `last` (null: none) into view. */
  function markSelected(ids: ReadonlySet<number>, last: number | null): void {
    for (const row of rows(sceneList)) row.classList.toggle('selected', ids.has(Number(row.dataset.id)));
    const row = last === null ? null : find(sceneList, `li[data-id="${last}"]`, HTMLElement);
    if (row) row.scrollIntoView({ block: 'nearest' });
  }

  /**
   * The instance search: rows whose name, id or model file hold the text
   * stay, the others hide. Only the list changes: the instances stay in the
   * view and in the selection.
   */
  const instanceSearch = byIdAs('instance-search', HTMLInputElement);
  function filterList(): void {
    const query = instanceSearch.value.trim().toLowerCase();
    let count = 0;
    for (const row of rows(sceneList)) {
      row.hidden = Boolean(query) && !(row.dataset.search ?? '').includes(query);
      if (!row.hidden) count++;
    }
    const label = byId('instance-count');
    if (!items.length) label.textContent = '';
    else label.textContent = query ? `(${count} of ${items.length})` : `(${items.length})`;
  }
  instanceSearch.addEventListener('input', filterList);

  function renderList(): void {
    sceneList.replaceChildren(...items.map(listRow));
    filterList();
    markSelected(new Set(app().selectedIds()), app().selectedId());
  }

  /** Show an item's field in its list row. */
  function showItemField(item: Item, field: 'sequence' | 'rot' | 'x' | 'y'): void {
    if (field === 'sequence') {
      const select = find(sceneList, `li[data-id="${item.id}"] select.anim`, HTMLSelectElement);
      if (select) select.value = String(item.sequence);
      return;
    }
    const input = find(sceneList, `li[data-id="${item.id}"] input.${field}`, HTMLInputElement);
    if (input) input.value = shown(item[field]);
  }

  // The clear button asks first (operator 2026-11-22); with no instance it does nothing.
  const clearQuestion = make('div', { className: 'question' });
  const clearDialog = new ConfirmDialog({ id: 'clear-dialog', title: 'remove all', yesText: 'remove all', content: [clearQuestion] });
  byId('clear').addEventListener('click', () => {
    void (async () => {
      if (!items.length) return;
      clearQuestion.textContent = `Remove all ${items.length} instance${items.length === 1 ? '' : 's'} from the scene?`;
      const asking = clearDialog.ask();
      // A stray Enter must not remove everything.
      clearDialog.no.focus();
      if (await asking) app().clear();
    })();
  });

  return { renderList, markSelected, showItemField };
}

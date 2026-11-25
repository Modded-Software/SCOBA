// The scene list in the instances panel: one row per item, where the
// selected items' rows are marked; the instance search; the clear button.
// It follows the scene and the selection through their events.

import type { Item } from '../core/types';
import type { ApiClient, CameraService, GameRegistry, SceneService, SelectionService, StatusService, UiService } from '../core/context';
import type { EventBus, ItemField, ViewerEvents } from '../core/bus';
import { byId, byIdAs, find, make, rows } from '../core/dom';
import { ConfirmDialog } from './components/dialog';
import { stepNumber, stepSelect } from './components/stepper';

type NumberField = 'x' | 'y' | 'rot' | 'scale';

export interface InstancesDeps {
  readonly scene: SceneService;
  readonly selection: SelectionService;
  readonly games: GameRegistry;
  readonly api: ApiClient;
  readonly camera: CameraService;
  readonly status: StatusService;
  readonly events: EventBus<ViewerEvents>;
  readonly iconNode: UiService['iconNode'];
}

/** A number as the list shows it: three decimals at most. */
const shown = (value: number): string => String(Math.round(value * 1000) / 1000);

export function installInstances({ scene, selection, games, api, camera, status, events, iconNode }: InstancesDeps): void {
  const { items } = scene;
  const edited = (what: string): void => events.emit('scene-edited', { what });
  const sceneList = byId('scene');

  function numberInput(item: Item, field: NumberField, step: number): HTMLLabelElement {
    const input = stepNumber(make('input', { type: 'number', className: field, step: String(step), value: shown(item[field]) }));
    input.addEventListener('change', () => {
      const value = Number.parseFloat(input.value);
      if (!Number.isFinite(value) || (field === 'scale' && value <= 0)) {
        input.value = shown(item[field]);
        return;
      }
      item[field] = value;
      scene.applyTransform(item);
      edited('row');
    });
    return make('label', {}, [field, input]);
  }

  const option = (value: string, text: string): HTMLOptionElement => make('option', { value, textContent: text });

  function listRow(item: Item): HTMLLIElement {
    const record = item.source ? item.source.record : null;
    const { placement } = item;
    const name = record ? record.name : (item.path.split('\\').pop() ?? item.path);
    const removeButton = make('button', { className: 'remove danger', textContent: '×', title: 'Remove Instance' });
    removeButton.addEventListener('click', () => scene.remove(item.id));
    const anim = stepSelect(make('select', { className: 'anim' }, [option('-1', '(none)'), ...item.instance.sequences.map((s, i) => option(String(i), s.name))]));
    anim.value = String(item.sequence);
    anim.addEventListener('change', () => {
      item.sequence = Number.parseInt(anim.value, 10);
      scene.applySequence(item);
      edited('row');
    });
    // Team colours the instance's format knows (SPEC-VIEWER 6.2); none: no control.
    const teams = item.capabilities.teamColor ? item.capabilities.teamColor.count : 0;
    const team = stepSelect(
      make(
        'select',
        { className: 'team', title: 'team colour' },
        Array.from({ length: teams }, (_, i) => option(String(i), 'team ' + (i + 1))),
      ),
    );
    team.value = String(item.team);
    team.addEventListener('change', () => {
      item.team = Number.parseInt(team.value, 10);
      scene.applyLook(item);
      edited('row');
    });
    const head: HTMLElement[] = [make('span', { className: 'name', textContent: name, title: record ? `${record.id}  ${item.path}` : item.path }), removeButton];
    if (placement.icon) head.unshift(iconNode(placement.icon.name, item.dataset, item.game));
    // A record without a team colour (an SC2 doodad) has its model variants in its place.
    const controls: HTMLElement[] = [anim];
    if (placement.team) {
      if (teams > 0) controls.push(team);
    } else if (placement.variants > 1) {
      const count = placement.variants;
      const variation = stepSelect(
        make(
          'select',
          { className: 'variation', title: 'model variation' },
          Array.from({ length: count }, (_, i) => option(String(i), `variation ${i + 1} of ${count}`)),
        ),
      );
      variation.value = String(placement.variant);
      variation.addEventListener('change', () => scene.setVariation(item, Number.parseInt(variation.value, 10)).catch(status.reportFailure));
      controls.push(variation);
    }
    // Where the item's data and textures come from; another choice swaps them.
    const all = api.datasets(item.game);
    if (all.length > 1) {
      const source = stepSelect(make('select', { className: 'dataset', title: "dataset: where this instance's data and textures come from" }, all.map((d) => option(d.id, d.label))));
      source.value = item.dataset;
      source.addEventListener('change', () =>
        scene
          .setItemDataset(item, source.value)
          .catch((error: unknown) => {
            status.reportFailure(error);
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
    // data-<noun>: the record's id ("data-unit", "data-doodad").
    const noun = games.nounOf(item);
    if (record && noun) row.dataset[noun] = record.id;
    // What the instance search matches: the name, the record id, the model file.
    row.dataset.search = [name, record ? record.id : '', item.path].join(' ').toLowerCase();
    // A click on the row's name selects the unit in the view (features/pick).
    // With shift it adds the unit to the selection or takes it out.
    // With ctrl it selects the unit and points the camera at it.
    headNode.addEventListener('click', (e) => {
      if (e.target === removeButton) return;
      if (e.shiftKey) selection.toggleSelected(item.id);
      else selection.select(item.id);
      if (e.ctrlKey && !e.shiftKey) camera.focusItem(item);
    });
    // A double-click opens what the game shows for the item (SC2: the texture window).
    headNode.addEventListener('dblclick', (e) => {
      if (e.target !== removeButton) games.partsOf(item.game).openItem(item).catch(status.reportFailure);
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
    markSelected(new Set(selection.selectedIds()), selection.selectedId());
  }

  /** Show an item's field in its list row. */
  function showItemField(item: Item, field: ItemField): void {
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
  const clearDialog = new ConfirmDialog({ id: 'clear-dialog', title: 'Remove All Instances', yesText: 'Remove All Instances', content: [clearQuestion], danger: true });
  byId('clear').addEventListener('click', () => {
    void (async () => {
      if (!items.length) return;
      clearQuestion.textContent = `Remove all ${items.length} instance${items.length === 1 ? '' : 's'} from the scene?`;
      const asking = clearDialog.ask();
      // A stray Enter must not remove everything.
      clearDialog.no.focus();
      if (await asking) scene.clear();
    })();
  });

  events.on('item-added', renderList);
  events.on('items-removed', renderList);
  events.on('item-swapped', renderList);
  events.on('item-changed', ({ item, field }) => showItemField(item, field));
  events.on('selection-changed', ({ ids, last }) => markSelected(ids, last));
}

// One category pane of the gallery, built from its CategoryInfo (SPEC-VIEWER
// 10.1): the search, the filters the game declares (buttons or a select),
// the count, "add all" when the category has it, the list that loads a page
// at a time, and the preview card. Ids: search-<c>, filter-<c>-<f>,
// count-<c>, <tool>-<c> (ui.addGalleryTool: add-all-<c>), <c> (the list),
// preview-<c>, preview-add-<c>.
// A 'files' category lists model file paths: a click adds the file.

import type { CategoryInfo, FilterInfo, RecordSummary } from '../../../shared/protocol';
import type { Page } from '../../../shared/records';
import type { ApiClient, GalleryTool, GameRegistry, RowDrag, SceneService, StatusService, UiService } from '../../core/context';
import { make, rows } from '../../core/dom';
import { PagedList } from '../components/pagedlist';
import { stepSelect } from '../components/stepper';

const PAGE_SIZE = 60;
/** The value of a select's "any" option when '' is one of the filter's values (SC2 "no family"). */
const ANY = 'any';
const IS = 'is:';

export interface Pane {
  readonly node: HTMLElement;
  /** The query as shown: `q` and each filter that is set. */
  query(): Record<string, string>;
  /** Load the first page again. */
  relist(): Promise<void>;
}

/** A filter's control: buttons or a select. `chosen` is null for "any". */
function filterControl(category: CategoryInfo, filter: FilterInfo, choose: (value: string | null) => void): HTMLElement {
  const id = `filter-${category.id}-${filter.id}`;
  if (filter.kind === 'buttons') {
    const bar = make('div', { id, className: 'filter-buttons', title: filter.label });
    const button = (value: string, label: string): HTMLButtonElement => {
      const node = make('button', { textContent: label });
      node.dataset[filter.id] = value;
      node.classList.toggle('on', value === '');
      node.addEventListener('click', () => {
        for (const other of rows(bar)) other.classList.toggle('on', other === node);
        choose(value === '' ? null : value);
      });
      return node;
    };
    bar.append(button('', 'all'), ...filter.values.map((v) => button(v.value, v.label)));
    return bar;
  }
  // '' among the values: the options carry a prefix, so "any" and '' differ.
  const prefixed = filter.values.some((v) => v.value === '');
  const select = stepSelect(make('select', { id, className: 'filter', title: filter.label }));
  select.append(make('option', { value: prefixed ? ANY : '', textContent: `any ${filter.label}` }), ...filter.values.map((v) => make('option', { value: prefixed ? IS + v.value : v.value, textContent: v.label })));
  select.addEventListener('change', () => {
    const value = select.value;
    if (prefixed) choose(value === ANY ? null : value.slice(IS.length));
    else choose(value === '' ? null : value);
  });
  return select;
}

/** `text`: the search to start with (kept over a dataset change). */
/** What a pane needs; the tools and the row drag are read when the pane is built. */
export interface PaneDeps {
  readonly scene: SceneService;
  readonly games: GameRegistry;
  readonly api: ApiClient;
  readonly status: StatusService;
  readonly iconNode: UiService['iconNode'];
  readonly tools: readonly GalleryTool[];
  readonly drag: RowDrag | null;
}

export function buildPane(deps: PaneDeps, category: CategoryInfo, text: string): Pane {
  const { scene, games, api, status, iconNode } = deps;
  const c = category.id;
  const files = category.rows === 'files';
  const search = make('input', { id: `search-${c}`, type: 'search', value: text, placeholder: files ? `search ${category.label}` : `search ${category.label} by name or id`, autocomplete: 'off', spellcheck: false });
  const list = make('ul', { id: c, className: files ? 'rows files' : 'rows records' });
  const count = make('span', { id: `count-${c}`, className: 'count' });
  const preview = make('div', { id: `preview-${c}`, className: 'preview' });
  const chosen = new Map<string, string>();
  let selected: string | null = null;

  function query(): Record<string, string> {
    const out: Record<string, string> = { q: search.value.trim() };
    for (const [key, value] of chosen) out[key] = value;
    return out;
  }

  const relistNow = (): void => {
    pages.reset().catch(status.reportFailure);
  };

  const buttons: HTMLElement[] = [];
  const tools: HTMLElement[] = [];
  for (const filter of category.filters) {
    const control = filterControl(category, filter, (value) => {
      if (value === null) chosen.delete(filter.id);
      else chosen.set(filter.id, value);
      relistNow();
    });
    (filter.kind === 'buttons' ? buttons : tools).push(control);
  }
  tools.push(count);
  for (const tool of deps.tools) {
    if (!tool.when(category)) continue;
    const button = make('button', { id: `${tool.id}-${c}`, className: tool.id, textContent: tool.label, title: tool.title(category) });
    button.addEventListener('click', () => tool.run(category).catch(status.reportFailure));
    tools.push(button);
  }

  function fileRow(path: string): HTMLLIElement {
    const button = make('button', { textContent: path, title: path });
    button.dataset.path = path;
    button.addEventListener('click', () => scene.add(path).catch(status.reportFailure));
    return make('li', {}, [button]);
  }

  function recordRow(record: RecordSummary): HTMLLIElement {
    const text = make('div', { className: 'text' }, [make('div', { className: 'name', textContent: record.name }), make('div', { className: 'sub', textContent: record.sub })]);
    // (The list is the current dataset's, and so is the icon.)
    const row = make('li', { draggable: true, title: 'click to preview, double-click for what the game shows, drag into the view to place' }, category.icons ? [iconNode(record.icon), text] : [text]);
    row.dataset.id = record.id;
    row.classList.toggle('selected', record.id === selected);
    row.addEventListener('click', () => select(record.id).catch(status.reportFailure));
    row.addEventListener('dblclick', () => games.partsOf(games.game()).openRecord(c, record.id).catch(status.reportFailure));
    const { drag } = deps;
    if (drag) {
      row.addEventListener('dragstart', (e) => drag.start(e, record, category.noun));
      row.addEventListener('dragend', () => drag.end());
    }
    return row;
  }

  const fetchFiles = async (offset: number, limit: number): Promise<Page<string>> => {
    const q = search.value.trim();
    // No search, no list: a game's model files are many.
    if (!q) return { total: 0, items: [] };
    return api.getJson<Page<string>>(api.records(c, { q, offset: String(offset), limit: String(limit) }));
  };
  const fetchRecords = (offset: number, limit: number): Promise<Page<RecordSummary>> => api.getJson<Page<RecordSummary>>(api.records(c, { ...query(), offset: String(offset), limit: String(limit) }));
  const onTotal = (total: number): void => {
    count.textContent = `${total} ${category.label}`;
  };
  const onError = (error: unknown): void => status.reportFailure(error);
  const pages: { reset(): Promise<void> } = files
    ? new PagedList<string>({ list, pageSize: PAGE_SIZE, fetchPage: fetchFiles, renderItem: fileRow, onTotal, onError })
    : new PagedList<RecordSummary>({ list, pageSize: PAGE_SIZE, fetchPage: fetchRecords, renderItem: recordRow, onTotal, onError });

  /** Show one record's preview card: the game's lines, and "add to scene". */
  async function select(id: string): Promise<void> {
    selected = id;
    for (const row of rows(list)) row.classList.toggle('selected', row.dataset.id === id);
    const record = await api.record(c, id);
    if (selected !== id) return; // another record was selected meanwhile
    const card = games.plugin().describe(c, record);
    const addButton = make('button', { id: `preview-add-${c}`, className: 'preview-add', textContent: 'add to scene' });
    addButton.addEventListener('click', () => scene.addRecord(c, record.id).catch(status.reportFailure));
    const picture = card.picture ? make('img', { className: 'portrait', src: api.iconUrl(card.picture, record.dataset), alt: card.name }) : make('span', { className: 'portrait' });
    // Name and add on one line; the facts scroll inside the fixed-height card.
    const body = make('div', { className: 'body' }, [
      make('div', { className: 'top' }, [make('div', { className: 'name', textContent: card.name }), addButton]),
      make('div', { className: 'facts' }, card.facts.map((line) => make('div', { textContent: line, title: line }))),
    ]);
    preview.replaceChildren(...(category.icons ? [picture, body] : [body]));
  }

  search.addEventListener('input', relistNow);
  const parts: HTMLElement[] = [search, ...buttons];
  if (tools.length > 1 || !files) parts.push(make('div', { className: 'tools' }, tools));
  parts.push(list);
  if (!files) parts.push(preview);
  const node = make('section', { id: `pane-${c}`, className: 'pane' }, parts);
  return { node, query, relist: () => pages.reset() };
}

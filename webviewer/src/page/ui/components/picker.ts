// A dialog to pick one item: a search box over a paged list. The first row
// can be a fixed "none" choice.

import { Dialog } from './dialog';
import { make } from '../../core/dom';
import { PagedList, type Page } from './pagedlist';

/** How a row shows an item. */
export interface Described {
  id: string;
  name: string;
  sub: string;
}

export interface PickerOptions<T> {
  id: string;
  title: string;
  fetchPage: (query: string, offset: number, limit: number) => Promise<Page<T>>;
  describe: (item: T) => Described;
  onPick: (item: T | null) => void;
  /** Label of the "none" row, or null for no such row. */
  none?: string | null;
  /** Grey hint text in the search box. */
  hint?: string;
}

export class Picker<T> {
  readonly dialog: Dialog;
  readonly search: HTMLInputElement;
  readonly count: HTMLDivElement;
  readonly list: PagedList<T>;
  /** The id of the picked row; null for none. */
  selected: string | null = null;
  private readonly describe: (item: T) => Described;
  private readonly onPick: (item: T | null) => void;
  private readonly none: string | null;

  constructor({ id, title, fetchPage, describe, onPick, none = null, hint = 'search' }: PickerOptions<T>) {
    this.dialog = new Dialog({ id, title });
    this.describe = describe;
    this.onPick = onPick;
    this.none = none;
    this.search = make('input', { type: 'search', placeholder: hint, autocomplete: 'off', spellcheck: false });
    this.count = make('div', { className: 'sub' });
    const list = make('ul', { className: 'picker-list rows' });
    this.dialog.body.append(this.search, this.count, list);
    this.list = new PagedList<T>({
      list,
      fetchPage: (offset, limit) => fetchPage(this.search.value.trim(), offset, limit),
      renderItem: (item) => this.row(item),
      onTotal: (total) => {
        this.count.textContent = `${total} found`;
      },
    });
    this.search.addEventListener('input', () => {
      this.reload().catch((error: unknown) => {
        console.warn('sc2viewer: picker search failed:', error);
        this.count.textContent = 'search failed';
      });
    });
  }

  private row(item: T | null): HTMLLIElement {
    const { id, name, sub } = item === null ? { id: '', name: this.none ?? '', sub: '' } : this.describe(item);
    const li = make('li', {}, [make('div', { textContent: name })]);
    li.dataset.id = id;
    if (sub) li.append(make('div', { className: 'sub', textContent: sub }));
    li.classList.toggle('selected', id === (this.selected ?? ''));
    li.addEventListener('click', () => this.pick(item, id));
    return li;
  }

  async reload(): Promise<void> {
    await this.list.reset();
    if (this.none !== null && !this.search.value.trim()) {
      this.list.list.prepend(this.row(null));
    }
  }

  private pick(item: T | null, id: string): void {
    this.selected = id || null;
    this.dialog.close();
    this.onPick(item);
  }

  async open(): Promise<void> {
    this.search.value = '';
    this.dialog.open();
    await this.reload();
    this.search.focus();
  }
}

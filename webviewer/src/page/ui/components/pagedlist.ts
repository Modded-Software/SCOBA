// A list that loads one page at a time and the next when its end scrolls
// into reach. A hidden list waits with the next page until it is shown.

/** One page of a list the server serves. */
export interface Page<T> {
  total: number;
  items: T[];
}

export interface PagedListOptions<T> {
  /** The <ul>; it is the scroll box. */
  list: HTMLElement;
  fetchPage: (offset: number, limit: number) => Promise<Page<T>>;
  renderItem: (item: T) => HTMLElement;
  /** Items per request (default 60). */
  pageSize?: number;
  /** After the first page of each reset. */
  onTotal?: (total: number) => void;
  onError?: (error: unknown) => void;
}

export class PagedList<T> {
  readonly list: HTMLElement;
  readonly pageSize: number;
  total = 0;
  loaded = 0;
  done = false;
  private generation = 0;
  private loading: Promise<void> | null = null;
  private readonly fetchPage: PagedListOptions<T>['fetchPage'];
  private readonly renderItem: PagedListOptions<T>['renderItem'];
  private readonly onTotal: (total: number) => void;
  private readonly onError: (error: unknown) => void;

  constructor({ list, fetchPage, renderItem, pageSize = 60, onTotal = () => {}, onError = (error: unknown) => console.warn('scobaeditor: list page failed:', error) }: PagedListOptions<T>) {
    this.list = list;
    this.fetchPage = fetchPage;
    this.renderItem = renderItem;
    this.pageSize = pageSize;
    this.onTotal = onTotal;
    this.onError = onError;
    list.addEventListener('scroll', () => this.fill());
    // Shown (its tab chosen) or resized: the box may need more rows now.
    new ResizeObserver(() => this.fill()).observe(list);
  }

  /** Drop every row and load the first page again. */
  reset(): Promise<void> {
    this.generation++;
    this.loading = null;
    this.total = 0;
    this.loaded = 0;
    this.done = false;
    this.list.replaceChildren();
    this.list.scrollTop = 0;
    return this.more();
  }

  /** Load the next page, unless one is loading or the list is complete. */
  more(): Promise<void> {
    if (this.loading) return this.loading;
    if (this.done) return Promise.resolve();
    const generation = this.generation;
    const offset = this.loaded;
    this.loading = this.fetchPage(offset, this.pageSize)
      .then((body) => {
        if (generation !== this.generation) return; // reset meanwhile
        this.total = body.total;
        this.list.append(...body.items.map((item) => this.renderItem(item)));
        this.loaded = offset + body.items.length;
        this.done = this.loaded >= body.total || body.items.length === 0;
        if (offset === 0) this.onTotal(body.total);
      })
      .catch((error: unknown) => {
        if (generation === this.generation) this.onError(error);
      })
      .finally(() => {
        if (generation !== this.generation) return;
        this.loading = null;
        // The list may still not fill its box, or the user scrolled on.
        this.fill();
      });
    return this.loading;
  }

  /** Load more when the end of the list is within one box height. A hidden list (no box) loads no more than its first page. */
  fill(): void {
    const list = this.list;
    if (this.done || this.loading || list.clientHeight === 0) return;
    if (list.scrollTop + list.clientHeight >= list.scrollHeight - list.clientHeight) this.more().catch((error: unknown) => this.onError(error));
  }
}

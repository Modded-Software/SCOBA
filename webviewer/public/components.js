// Reusable page components: a list that loads as it scrolls, and a modal
// dialog. Plain DOM, no framework. Exposed as window.SC2Components.
'use strict';

(() => {
  /**
   * A list that loads one page at a time and the next when its end scrolls
   * into reach.
   *
   * options:
   *   list        the <ul> (it is the scroll box)
   *   fetchPage   (offset, limit) => Promise<{ total, items }>
   *   renderItem  (item) => <li>
   *   pageSize    items per request (default 60)
   *   onTotal     (total) => void, after the first page of each reset
   *   onError     (error) => void
   */
  class LazyList {
    constructor({ list, fetchPage, renderItem, pageSize = 60, onTotal = () => {}, onError = () => {} }) {
      Object.assign(this, { list, fetchPage, renderItem, pageSize, onTotal, onError });
      this.total = 0;
      this.loaded = 0;
      this.generation = 0;
      this.loading = null;
      list.addEventListener('scroll', () => this.fill());
    }

    /** Drop every row and load the first page again. */
    reset() {
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
    more() {
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
        .catch((error) => {
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

    /** Load more when the end of the list is within one box height. */
    fill() {
      const list = this.list;
      if (this.done || this.loading) return;
      if (list.scrollTop + list.clientHeight >= list.scrollHeight - list.clientHeight) this.more();
    }
  }

  /**
   * A modal dialog with a title, a body and a close button. Escape, the
   * close button and a click outside the box close it.
   */
  class Dialog {
    constructor({ id, title }) {
      this.node = document.createElement('dialog');
      this.node.id = id;
      this.node.className = 'dialog';
      const head = document.createElement('div');
      head.className = 'dialog-head';
      const heading = document.createElement('span');
      heading.textContent = title;
      const close = document.createElement('button');
      close.className = 'dialog-close';
      close.textContent = 'x';
      close.title = 'close';
      close.addEventListener('click', () => this.close());
      head.append(heading, close);
      this.body = document.createElement('div');
      this.body.className = 'dialog-body';
      this.node.append(head, this.body);
      this.node.addEventListener('click', (e) => {
        if (e.target === this.node) this.close(); // the backdrop
      });
      document.body.append(this.node);
    }

    open() {
      if (!this.node.open) this.node.showModal();
    }

    close() {
      if (this.node.open) this.node.close();
    }

    get isOpen() {
      return this.node.open;
    }
  }

  /**
   * A dialog to pick one item: a search box over a paged list. The first row
   * can be a fixed "none" choice.
   *
   * options:
   *   id, title     of the dialog
   *   fetchPage     (query, offset, limit) => Promise<{ total, items }>
   *   describe      (item) => { id, name, sub }
   *   onPick        (item | null) => void
   *   none          label of the "none" row, or null for no such row
   *   hint          grey hint text in the search box
   */
  class Picker {
    constructor({ id, title, fetchPage, describe, onPick, none = null, hint = 'search' }) {
      this.dialog = new Dialog({ id, title });
      this.describe = describe;
      this.onPick = onPick;
      this.none = none;
      this.selected = null;
      this.search = document.createElement('input');
      this.search.type = 'search';
      this.search.placeholder = hint;
      this.search.autocomplete = 'off';
      this.search.spellcheck = false;
      this.count = document.createElement('div');
      this.count.className = 'sub';
      const list = document.createElement('ul');
      list.className = 'picker-list';
      this.dialog.body.append(this.search, this.count, list);
      this.list = new LazyList({
        list,
        fetchPage: (offset, limit) => fetchPage(this.search.value.trim(), offset, limit),
        renderItem: (item) => this.row(item),
        onTotal: (total) => {
          this.count.textContent = `${total} found`;
        },
      });
      this.search.addEventListener('input', () => this.reload());
    }

    row(item) {
      const { id, name, sub } = item === null ? { id: '', name: this.none, sub: '' } : this.describe(item);
      const li = document.createElement('li');
      li.dataset.id = id;
      const title = document.createElement('div');
      title.textContent = name;
      li.append(title);
      if (sub) {
        const small = document.createElement('div');
        small.className = 'sub';
        small.textContent = sub;
        li.append(small);
      }
      li.classList.toggle('selected', id === (this.selected ?? ''));
      li.addEventListener('click', () => this.pick(item, id));
      return li;
    }

    async reload() {
      await this.list.reset();
      if (this.none !== null && !this.search.value.trim()) {
        this.list.list.prepend(this.row(null));
      }
    }

    pick(item, id) {
      this.selected = id || null;
      this.dialog.close();
      this.onPick(item);
    }

    async open() {
      this.search.value = '';
      this.dialog.open();
      await this.reload();
      this.search.focus();
    }
  }

  window.SC2Components = { LazyList, Dialog, Picker };
})();

// Reusable page components: a list that loads as it scrolls, a modal dialog,
// a picker and a confirm dialog built on it, a toast, a drop-down, and a
// floating window. Plain DOM, no framework. Exposed as window.SC2Components.
// Their look is in theme.css.
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
  class PagedList {
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
      close.textContent = '×';
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
      list.className = 'picker-list rows';
      this.dialog.body.append(this.search, this.count, list);
      this.list = new PagedList({
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

  function make(tag, props = {}, children = []) {
    const node = Object.assign(document.createElement(tag), props);
    node.append(...children);
    return node;
  }

  /**
   * A small dialog with a question and two answer buttons. `ask()` opens it
   * and resolves true (yes) or false (no, Escape, the x, the backdrop).
   *
   * options:
   *   id        of the dialog, "<name>-dialog"; the buttons are "<name>-yes" and "<name>-no"
   *   title     of the dialog
   *   yesText   label of the yes button
   *   content   nodes above the buttons
   */
  class ConfirmDialog {
    constructor({ id, title, yesText, noText = 'cancel', content = [] }) {
      const name = id.replace(/-dialog$/, '');
      this.dialog = new Dialog({ id, title });
      this.dialog.node.classList.add('confirm-dialog');
      this.yes = make('button', { id: `${name}-yes`, className: 'primary', textContent: yesText });
      this.no = make('button', { id: `${name}-no`, textContent: noText });
      this.dialog.body.append(...content, make('div', { className: 'answers' }, [this.no, this.yes]));
      this.answer = null;
      this.yes.addEventListener('click', () => this.settle(true));
      this.no.addEventListener('click', () => this.settle(false));
      this.dialog.node.addEventListener('close', () => this.settle(false));
    }

    settle(value) {
      const done = this.answer;
      this.answer = null;
      this.dialog.close();
      if (done) done(value);
    }

    ask() {
      return new Promise((resolve) => {
        this.answer = resolve;
        this.dialog.open();
      });
    }
  }

  /**
   * A note that slides up from below the bottom edge: a text and buttons.
   * `show(text, centre)` puts it up, centred on the page x `centre`.
   */
  class Toast {
    /** `place`: 'bottom' (default) slides up from the bottom edge, 'top' down from the top edge. */
    constructor({ id, place = 'bottom', role = 'alertdialog' }) {
      if (place !== 'bottom' && place !== 'top') throw new Error(`Toast: place "${place}" is not bottom or top`);
      this.text = make('span', { className: 'text' });
      this.node = make('div', { id, className: `toast ${place}`, role }, [this.text]);
      document.body.append(this.node);
    }

    addButton(id, label) {
      const button = make('button', { id, textContent: label });
      this.node.append(button);
      return button;
    }

    show(text, centre) {
      this.text.textContent = text;
      this.node.style.left = `${centre}px`;
      this.node.classList.add('up');
    }

    hide() {
      this.node.classList.remove('up');
    }

    get isUp() {
      return this.node.classList.contains('up');
    }
  }

  /**
   * A button that opens a list below it. Escape and a press outside `root`
   * close it.
   */
  class Dropdown {
    constructor({ root, button, list }) {
      Object.assign(this, { root, button, list });
      root.classList.add('dropdown');
      list.classList.add('dropdown-list');
      button.addEventListener('click', () => {
        list.hidden = !list.hidden;
      });
      window.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') this.close();
      });
      window.addEventListener('mousedown', (e) => {
        if (!root.contains(e.target)) this.close();
      });
    }

    close() {
      this.list.hidden = true;
    }
  }

  /**
   * A window that floats over the page: a title bar to move it by, a close
   * button, and a body. Hidden until open(). It is not modal. Escape closes
   * it. Its bottom right corner resizes it.
   */
  class FloatingWindow {
    static KEEP = 80; // pixels of the title bar that stay on the page

    constructor({ id, title }) {
      this.title = make('span', { className: 'window-title', textContent: title });
      const close = make('button', { className: 'window-close', textContent: '×', title: 'close (Esc)' });
      this.head = make('div', { className: 'window-head' }, [this.title, close]);
      this.body = make('div', { className: 'window-body' });
      this.node = make('div', { id, className: 'window', hidden: true }, [this.head, this.body]);
      document.body.append(this.node);
      close.addEventListener('click', () => this.close());
      window.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') this.close();
      });
      window.addEventListener('resize', () => {
        if (this.isOpen) this.moveTo(this.node.offsetLeft, this.node.offsetTop);
      });
      let grab = null; // where in the window the pointer holds it
      this.head.addEventListener('pointerdown', (e) => {
        if (e.button !== 0 || e.target === close) return;
        e.preventDefault();
        grab = { x: e.clientX - this.node.offsetLeft, y: e.clientY - this.node.offsetTop };
        this.head.setPointerCapture(e.pointerId);
        // A frame in the body would take the pointer when it passes over it.
        this.node.classList.add('dragging');
      });
      this.head.addEventListener('pointermove', (e) => {
        if (grab) this.moveTo(e.clientX - grab.x, e.clientY - grab.y);
      });
      for (const name of ['pointerup', 'pointercancel']) {
        this.head.addEventListener(name, () => {
          grab = null;
          this.node.classList.remove('dragging');
        });
      }
    }

    /** Move the top left corner to (left, top), as far as the title bar stays reachable. */
    moveTo(left, top) {
      const keep = FloatingWindow.KEEP;
      const x = Math.min(Math.max(left, keep - this.node.offsetWidth), innerWidth - keep);
      const y = Math.min(Math.max(top, 0), innerHeight - this.head.offsetHeight);
      this.node.style.left = `${x}px`;
      this.node.style.top = `${y}px`;
    }

    /** Show the window. `place` ({ left, top, width, height }) is used the first time only: later it opens where it was left. */
    open(place) {
      if (this.isOpen) return;
      this.node.hidden = false;
      if (!this.placed) {
        this.node.style.width = `${place.width}px`;
        this.node.style.height = `${place.height}px`;
        this.moveTo(place.left, place.top);
        this.placed = true;
      }
    }

    close() {
      this.node.hidden = true;
    }

    get isOpen() {
      return !this.node.hidden;
    }
  }

  window.SC2Components = { PagedList, Dialog, Picker, ConfirmDialog, Toast, Dropdown, FloatingWindow };
})();

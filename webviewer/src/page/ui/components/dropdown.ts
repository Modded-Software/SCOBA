// A button that opens a list below it. Escape and a press outside `root`
// close it.

export interface DropdownOptions {
  root: HTMLElement;
  button: HTMLElement;
  list: HTMLElement;
}

export class Dropdown {
  readonly root: HTMLElement;
  readonly button: HTMLElement;
  readonly list: HTMLElement;

  constructor({ root, button, list }: DropdownOptions) {
    this.root = root;
    this.button = button;
    this.list = list;
    root.classList.add('dropdown');
    list.classList.add('dropdown-list');
    button.addEventListener('click', () => {
      list.hidden = !list.hidden;
    });
    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') this.close();
    });
    window.addEventListener('mousedown', (e) => {
      if (!(e.target instanceof Node) || !root.contains(e.target)) this.close();
    });
  }

  close(): void {
    this.list.hidden = true;
  }
}

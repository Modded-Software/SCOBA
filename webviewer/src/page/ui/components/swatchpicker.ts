// A drop-down of choices that each show a colour box before their name:
// the team colour of an instance row (ui/instances.ts). It is a list
// drop-down (dropdown.ts), since a native select cannot show a colour box
// in its entries. The button shows the chosen entry's box and name. The
// wheel over it and Up/Down on it step through the entries (stepper.ts).
// The list is placed fixed under the button, so a scrolling panel does not
// cut it off; a scroll anywhere but in the list closes it.

import { make } from '../../core/dom';
import { Dropdown } from './dropdown';

export interface Swatch {
  readonly value: string;
  readonly label: string;
  /** 0 to 255 per channel. */
  readonly color: readonly [number, number, number];
}

export interface SwatchPicker {
  readonly node: HTMLElement;
  readonly value: string;
  set(value: string): void;
}

function box(c: readonly [number, number, number]): HTMLElement {
  const node = make('span', { className: 'swatch' });
  node.style.background = `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
  return node;
}

/** The open picker's drop-down: any scroll on the page but in its own list closes it. */
let opened: Dropdown | null = null;
window.addEventListener(
  'scroll',
  (e) => {
    if (opened?.isOpen && !(e.target instanceof Node && opened.list.contains(e.target))) opened.close();
  },
  { capture: true, passive: true },
);

export function swatchPicker({ className, title, choices, value, onChange }: { className: string; title: string; choices: readonly Swatch[]; value: string; onChange: (value: string) => void }): SwatchPicker {
  const button = make('button', { type: 'button', className: 'swatch-button', title });
  // Entries are divs: the picker sits in list rows (#scene li), whose count must not change.
  const list = make('div', { className: 'swatch-list', hidden: true });
  const node = make('div', { className: `swatch-picker ${className}` }, [button, list]);
  let current = value;

  function show(): void {
    const at = choices.findIndex((c) => c.value === current);
    const chosen = choices[at];
    if (!chosen) throw new Error(`${title}: no choice "${current}"`);
    button.replaceChildren(box(chosen.color), make('span', { className: 'swatch-label', textContent: chosen.label }));
    node.dataset['value'] = current;
    for (const entry of list.children) entry.classList.toggle('selected', entry instanceof HTMLElement && entry.dataset['value'] === current);
  }

  function choose(index: number): void {
    const c = choices[index];
    if (!c) return;
    current = c.value;
    show();
    onChange(current);
  }

  const dropdown = new Dropdown({
    root: node,
    button,
    list,
    steps: { current: () => choices.findIndex((c) => c.value === current), count: () => choices.length, usable: () => true, choose },
    // Closed, the list goes back into the picker.
    onClose: () => node.append(list),
  });
  list.append(
    ...choices.map((c, i) => {
      const entry = make('div', { className: 'swatch-entry' }, [box(c.color), make('span', { className: 'swatch-label', textContent: c.label })]);
      entry.dataset['value'] = c.value;
      entry.addEventListener('click', () => {
        choose(i);
        dropdown.close();
      });
      return entry;
    }),
  );
  // Open, the list lives on the page body, fixed under the button: inside the
  // drawer it would be cut off (overflow), and the drawer's backdrop filter
  // would make "fixed" relative to the drawer, not the window. Closed, it goes back.
  button.addEventListener('click', () => {
    if (!dropdown.isOpen) return;
    opened = dropdown;
    const r = button.getBoundingClientRect();
    document.body.append(list);
    Object.assign(list.style, { position: 'fixed', left: `${r.left}px`, top: `${r.bottom + 4}px`, right: 'auto', minWidth: `${r.width}px` });
    // Past the window's bottom: open upwards.
    const height = list.getBoundingClientRect().height;
    if (r.bottom + 4 + height > window.innerHeight) list.style.top = `${Math.max(4, r.top - 4 - height)}px`;
  });

  show();
  return {
    node,
    get value() {
      return current;
    },
    set(next) {
      current = next;
      show();
    },
  };
}

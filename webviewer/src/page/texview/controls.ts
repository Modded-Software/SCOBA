// The controls of the texture page (SPEC-VIEWER 17.3): the search box, the
// buttons of the bar and the keys. main.ts hands over what they act on.

import type { ImageView } from './imageview';

export interface ControlParts {
  $(id: string): HTMLElement;
  search: HTMLInputElement;
  image: ImageView;
  /** The search text changed: trimmed, in lower case. */
  searched(text: string): void;
  /** Show the entry one before (-1) or after (1) the one shown, among those listed. */
  step(by: number): void;
}

/** Bind the search box, the buttons and the keys of the page. */
export function bindControls({ $, search, image, searched, step }: ControlParts): void {
  const toggle = (name: 'tile' | 'smooth'): void => {
    $(name).classList.toggle('on', image.toggle(name));
  };
  search.addEventListener('input', () => searched(search.value.trim().toLowerCase()));
  $('previous').addEventListener('click', () => step(-1));
  $('next').addEventListener('click', () => step(1));
  $('fit').addEventListener('click', image.fit);
  $('actual').addEventListener('click', image.actual);
  for (const name of ['tile', 'smooth'] as const) $(name).addEventListener('click', () => toggle(name));
  window.addEventListener('keydown', (event) => {
    if (event.target === search) {
      if (event.key === 'Escape') search.blur();
      if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return;
    }
    if (event.target instanceof HTMLSelectElement || event.ctrlKey || event.metaKey || event.altKey) return;
    if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
      event.preventDefault();
      step(-1);
    }
    if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
      event.preventDefault();
      step(1);
    }
    if (event.key === 'f') image.fit();
    if (event.key === '1') image.actual();
    if (event.key === 't') toggle('tile');
    if (event.key === 's') toggle('smooth');
    if (event.key === '/') {
      event.preventDefault();
      search.focus();
      search.select();
    }
  });
}

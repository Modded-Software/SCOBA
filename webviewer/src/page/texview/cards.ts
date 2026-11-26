// The details of the chosen texture in the texture window (SPEC-VIEWER
// 17.3): what it is, who uses it, why it cannot be upscaled, its bake, and
// the game's own facts. "used by" has one user per line, in a box of a fixed
// height that scrolls (R-VIEW-134). The tiles beside it are core/tiles.ts,
// the same as the skin editor's (R-VIEW-132).

import { namedByLines, type TextureState } from '../../shared/textures';

const element = <K extends keyof HTMLElementTagNameMap>(tag: K, className = '', text?: string): HTMLElementTagNameMap[K] => {
  const made = document.createElement(tag);
  if (className) made.className = className;
  if (text !== undefined) made.textContent = text;
  return made;
};

/** A box of lines, one per line, that scrolls inside; its hover holds them all. */
function lineBox(className: string, lines: readonly string[]): HTMLElement {
  const box = element('dd', className);
  box.title = lines.join('\n');
  box.append(...lines.map((line) => element('div', '', line)));
  return box;
}

/** "used by": one user per line, fixed height, scrolls (R-VIEW-134). */
const usedBy = (users: readonly string[]): HTMLElement => lineBox('used-by', users);

/** The details block: a heading with the size, then name and value pairs. */
export function detailsOf(size: readonly number[], format: string, facts: readonly (readonly [string, string])[], state: TextureState | null): HTMLElement {
  const made = element('div', 'details');
  const head = element('h3', '', 'Details');
  head.append(element('small', '', size.join('x')));
  const table = element('dl');
  const add = (name: string, value: string | HTMLElement, className = ''): void => {
    table.append(element('dt', className, name), typeof value === 'string' ? element('dd', className, value) : value);
  };
  add('format', format);
  if (state) {
    add('kind', state.kind);
    if (state.users.length) add('used by', usedBy(state.users));
    // Who names a variant of it, the bakes first (R-VIEW-161). Nobody: no row.
    const named = namedByLines(state);
    if (named.length) add('named by', lineBox('named-by', named));
    if (state.reason) add('cannot be upscaled', state.reason);
    if (state.bake) add('baked', `${state.bake}${state.packaged?.held ? ', packaged' : ''}`);
  }
  // The game's own facts may be long (a Ghost material and its shader): two lines each, label then value.
  for (const [name, value] of facts) add(name, value, 'fact');
  made.append(head, table);
  // Nobody asked for it by name yet: what it may ask for shows once the pipeline has read it (the judge route).
  if (state && !state.judged) made.append(element('div', 'unread', 'reading what can be made of it'));
  return made;
}

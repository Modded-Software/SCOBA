// DOM helpers for the page. The look is in theme.css and style.css.

/** A new element with properties set and children appended. */
export function make<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  props: Partial<HTMLElementTagNameMap[K]> = {},
  children: readonly (Node | string)[] = [],
): HTMLElementTagNameMap[K] {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children);
  return node;
}

/** The element of index.html with this id. A missing one is an error in the page. */
export function byId(id: string): HTMLElement {
  const node = document.getElementById(id);
  if (node === null) throw new Error(`page: no element #${id}`);
  return node;
}

/** The same, of a given element class (an input, a select, a canvas). */
export function byIdAs<T extends HTMLElement>(id: string, type: abstract new () => T): T {
  const node = byId(id);
  if (!(node instanceof type)) throw new Error(`page: #${id} is a ${node.tagName.toLowerCase()}, not a ${type.name}`);
  return node;
}

/** The elements of a list node, each an HTMLElement. */
export function rows(list: Element): HTMLElement[] {
  return [...list.children].filter((child): child is HTMLElement => child instanceof HTMLElement);
}

/** An element under `root`, of a given class; null when there is none. */
export function find<T extends Element>(root: ParentNode, selector: string, type: abstract new () => T): T | null {
  const node = root.querySelector(selector);
  return node instanceof type ? node : null;
}

/** The message of a thrown value. */
export function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

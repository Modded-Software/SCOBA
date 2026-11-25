// The list filter of the texture window (SPEC-VIEWER 17.3): a category, a
// plane and search words. main.ts owns the entries; this decides which
// pass and draws the chips of one field.

/** All of a field: no choice made. */
export const ALL = '';

export interface Filter {
  category: string;
  plane: string;
  text: string;
}

/** What the filter reads of one entry. */
export interface Filtered {
  plane: string;
  texture: string;
}

export interface FilterPage<T extends Filtered> {
  filter: Filter;
  entries(): readonly T[];
  categoryOf(item: T): string;
  usersOf(item: T): readonly string[];
  render(): void;
  element(tag: 'button' | 'span', className: string, text?: string): HTMLElement;
}

/** Whether an entry passes the filter; `skip` leaves one field out (its own chips count past it). */
export function passes<T extends Filtered>(page: FilterPage<T>, item: T, skip = ''): boolean {
  const { filter } = page;
  if (skip !== 'category' && filter.category !== ALL && page.categoryOf(item) !== filter.category) return false;
  if (skip !== 'plane' && filter.plane !== ALL && item.plane !== filter.plane) return false;
  if (filter.text) {
    const hay = `${item.texture} ${item.plane} ${page.categoryOf(item)} ${page.usersOf(item).join(' ')}`.toLowerCase();
    return filter.text.split(/\s+/).every((word) => hay.includes(word));
  }
  return true;
}

/** The chips of one field, each with the count that passes the other fields. */
export function chips<T extends Filtered>(page: FilterPage<T>, holder: HTMLElement, field: 'category' | 'plane', valueOf: (item: T) => string): void {
  const { filter } = page;
  const counts = new Map<string, number>();
  let total = 0;
  for (const item of page.entries()) {
    counts.set(valueOf(item), counts.get(valueOf(item)) ?? 0);
    if (passes(page, item, field)) {
      counts.set(valueOf(item), (counts.get(valueOf(item)) ?? 0) + 1);
      total += 1;
    }
  }
  holder.replaceChildren();
  for (const [value, label, count] of [[ALL, 'All', total] as const, ...[...counts].map(([value, count]) => [value, value, count] as const)]) {
    if (!count && value !== ALL && filter[field] !== value) continue;
    const chip = page.element('button', `chip${filter[field] === value ? ' on' : ''}`, label);
    chip.append(page.element('span', '', String(count)));
    chip.dataset['value'] = value;
    chip.addEventListener('click', () => {
      filter[field] = value;
      page.render();
    });
    holder.append(chip);
  }
}

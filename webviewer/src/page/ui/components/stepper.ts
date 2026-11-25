// Stepping by the wheel and the Up and Down keys (SPEC-VIEWER 16.14,
// R-VIEW-140, R-VIEW-141): one base, `stepper`, and the three kinds of
// control that use it: a native select, a number input, and a list
// drop-down (dropdown.ts). The wheel steps while the pointer is over the
// control and does not scroll the page; the keys step while it has the
// focus. "Up" is the choice before, or the number one step up.

/** One step: up (the choice before, the number up) or down. True: the value moved. */
export type Step = (up: boolean) => boolean;

/** The base: wheel over `target` and Up/Down on it call `step`. */
export function stepper(target: HTMLElement, step: Step): void {
  target.classList.add('stepper');
  target.addEventListener(
    'wheel',
    (e) => {
      if (e.deltaY === 0) return;
      e.preventDefault();
      step(e.deltaY < 0);
    },
    { passive: false },
  );
  target.addEventListener('keydown', (e) => {
    if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return;
    if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
    // The browser's own step would come on top of this one.
    e.preventDefault();
    step(e.key === 'ArrowUp');
  });
}

/** The choice before or after `from` among `count`, skipping those `usable` refuses; null: none. */
export function nextIndex(from: number, count: number, up: boolean, usable: (index: number) => boolean): number | null {
  for (let at = from + (up ? -1 : 1); at >= 0 && at < count; at += up ? -1 : 1) if (usable(at)) return at;
  return null;
}

/** Tell the control's listeners it changed, as a choice by hand does. */
function changed(control: HTMLElement): void {
  control.dispatchEvent(new Event('input', { bubbles: true }));
  control.dispatchEvent(new Event('change', { bubbles: true }));
}

/** A native select steps through its enabled options. */
export function stepSelect(select: HTMLSelectElement): HTMLSelectElement {
  stepper(select, (up) => {
    if (select.disabled) return false;
    const at = nextIndex(select.selectedIndex, select.options.length, up, (index) => !select.options[index]?.disabled);
    if (at === null) return false;
    select.selectedIndex = at;
    changed(select);
    return true;
  });
  return select;
}

/** Decimals of a number as written ("0.05" has 2), to keep a sum free of float noise. */
const decimals = (text: string): number => (text.includes('.') ? (text.split('.')[1] ?? '').length : 0);

/** A number input steps by its `step`, within its `min` and `max`. */
export function stepNumber(input: HTMLInputElement): HTMLInputElement {
  stepper(input, (up) => {
    if (input.disabled || input.readOnly) return false;
    const step = Number.parseFloat(input.step);
    const by = Number.isFinite(step) && step > 0 ? step : 1;
    const now = Number.parseFloat(input.value);
    if (!Number.isFinite(now)) return false;
    let next = now + (up ? by : -by);
    const min = Number.parseFloat(input.min);
    const max = Number.parseFloat(input.max);
    if (Number.isFinite(min)) next = Math.max(next, min);
    if (Number.isFinite(max)) next = Math.min(next, max);
    const places = Math.max(decimals(input.step), decimals(input.value));
    next = Number(next.toFixed(places));
    if (next === now) return false;
    input.value = String(next);
    changed(input);
    return true;
  });
  return input;
}

/** A list of choices that is not a select: the chosen one, how many, which are usable, and how to choose one. */
export interface ListChoices {
  /** The index of the chosen entry; -1: none. */
  current(): number;
  count(): number;
  usable(index: number): boolean;
  /** Choose an entry, as a click on it does. */
  choose(index: number): void;
}

/** A list drop-down's button steps through its choices (dropdown.ts). */
export function stepList(button: HTMLElement, list: ListChoices): void {
  stepper(button, (up) => {
    const count = list.count();
    const from = list.current();
    // Nothing chosen: the first step takes the first or the last entry.
    const at = from < 0 ? nextIndex(up ? count : -1, count, up, list.usable) : nextIndex(from, count, up, list.usable);
    if (at === null) return false;
    list.choose(at);
    return true;
  });
}

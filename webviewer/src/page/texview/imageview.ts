// The picture of the texture window (SPEC-VIEWER 17.3): the original and,
// beside it, each result switched on, parted by lines that can be dragged.
// Wheel zooms, drag pans, Fit, 1:1, Tile, Smooth.

/** One side of the view: a picture and its width in pixels. */
export interface Side {
  label: string;
  image: string;
  width: number;
}

export interface Shown {
  original: Side;
  height: number;
  results: Side[];
}

const TAG_ROOM = 90; // screen pixels a side needs to show its tag

const element = <K extends keyof HTMLElementTagNameMap>(tag: K, className = '', text?: string): HTMLElementTagNameMap[K] => {
  const made = document.createElement(tag);
  if (className) made.className = className;
  if (text !== undefined) made.textContent = text;
  return made;
};

export interface ImageView {
  show(shown: Shown, keepView: boolean): void;
  clear(): void;
  fit(): void;
  actual(): void;
  toggle(name: 'tile' | 'smooth'): boolean;
  /** Screen pixels the shown texture is wide. */
  size(): number;
}

export function createImageView(view: HTMLElement, before: HTMLElement, tagBefore: HTMLElement, status: HTMLElement): ImageView {
  let layers: HTMLElement[] = [];
  let dividers: HTMLElement[] = [];
  let tags: HTMLElement[] = [];
  let current: Shown | null = null;
  // size: screen pixels the texture's width covers. x, y: its top left corner. splits: each line's place, as a part of the width.
  const state = { size: 0, x: 0, y: 0, splits: [] as number[], tile: false, smooth: false };
  let fitOwed = false;

  function setLayerCount(count: number): void {
    if (layers.length === count) return;
    for (const old of [...layers, ...dividers, ...tags]) old.remove();
    layers = [];
    dividers = [];
    tags = [];
    for (const [made, className] of [[layers, 'layer'], [dividers, 'divider'], [tags, 'tag']] as const) {
      for (let i = 0; i < count; i += 1) {
        const part = element('div', className);
        view.insertBefore(part, tagBefore);
        made.push(part);
      }
    }
    dividers.forEach((divider, i) => divider.style.setProperty('--knob', `${(i - (count - 1) / 2) * 34}px`));
    state.splits = dividers.map((_, i) => (i + 1) / (count + 1));
  }

  const aspect = (): number => (current ? current.height / current.original.width : 1);
  /** Screen pixels the texture is wide when one pixel of its largest side is one screen pixel. */
  const actualSize = (): number => (current ? Math.max(current.original.width, ...current.results.map((side) => side.width)) / window.devicePixelRatio : 1);

  function draw(): void {
    if (!current) return;
    const height = state.size * aspect();
    const sides: [HTMLElement, number, boolean][] = [[before, current.original.width, !state.smooth]];
    current.results.forEach((side, i) => {
      const layer = layers[i];
      if (layer) sides.push([layer, side.width, true]);
    });
    for (const [side, natural, pixels] of sides) {
      side.style.backgroundSize = `${state.size}px ${height}px`;
      side.style.backgroundPosition = `${state.x}px ${state.y}px`;
      side.style.backgroundRepeat = state.tile ? 'repeat' : 'no-repeat';
      // True pixels when enlarged; the browser averages when shrunk.
      side.style.imageRendering = pixels && state.size * window.devicePixelRatio >= natural ? 'pixelated' : 'auto';
    }
    const width = view.getBoundingClientRect().width;
    const count = layers.length;
    tagBefore.style.display = count && (state.splits[0] ?? 0) * width < TAG_ROOM ? 'none' : '';
    for (let i = 0; i < count; i += 1) {
      const start = state.splits[i] ?? 0;
      const end = state.splits[i + 1] ?? 1;
      const layer = layers[i];
      const divider = dividers[i];
      const tag = tags[i];
      if (!layer || !divider || !tag) continue;
      layer.style.clipPath = `inset(0 0 0 ${start * 100}%)`;
      divider.style.left = `${start * 100}%`;
      tag.style.left = `calc(${start * 100}% + 14px)`;
      tag.style.display = (end - start) * width < TAG_ROOM ? 'none' : '';
    }
    status.textContent = `${Math.round((state.size / actualSize()) * 100)}%`;
  }

  /** Line `index` goes to `value`: it stops at the line left of it and pushes the lines right of it. */
  function moveSplit(index: number, value: number): void {
    const low = index > 0 ? (state.splits[index - 1] ?? 0) : 0;
    state.splits[index] = Math.min(1, Math.max(low, value));
    for (let i = index + 1; i < state.splits.length; i += 1) state.splits[i] = Math.max(state.splits[i] ?? 0, state.splits[index] ?? 0);
  }

  function fit(): void {
    if (!current) return;
    const box = view.getBoundingClientRect();
    // A hidden view has no size: the fit is done when it gets one.
    fitOwed = box.width === 0 || box.height === 0;
    if (fitOwed) return;
    state.size = Math.min(box.width, box.height / aspect()) * 0.96;
    state.x = (box.width - state.size) / 2;
    state.y = (box.height - state.size * aspect()) / 2;
    draw();
  }

  function zoomTo(size: number, originX: number, originY: number): void {
    const factor = size / state.size;
    state.x = originX - (originX - state.x) * factor;
    state.y = originY - (originY - state.y) * factor;
    state.size = size;
    draw();
  }

  function actual(): void {
    if (!current) return;
    const box = view.getBoundingClientRect();
    zoomTo(actualSize(), box.width / 2, box.height / 2);
  }

  function show(shown: Shown, keepView: boolean): void {
    const sameShape = current !== null && aspect() === shown.height / shown.original.width;
    current = shown;
    setLayerCount(shown.results.length);
    shown.results.forEach((side, i) => {
      const tag = tags[i];
      const layer = layers[i];
      if (tag) tag.textContent = side.label;
      if (layer) layer.style.backgroundImage = `url("${side.image}")`;
    });
    tagBefore.textContent = shown.original.label;
    before.style.backgroundImage = `url("${shown.original.image}")`;
    if (keepView && sameShape) draw();
    else fit();
  }

  function clear(): void {
    current = null;
    setLayerCount(0);
    before.style.backgroundImage = '';
    tagBefore.style.display = 'none';
    status.textContent = '';
  }

  function toggle(name: 'tile' | 'smooth'): boolean {
    state[name] = !state[name];
    draw();
    return state[name];
  }

  window.addEventListener('resize', draw);
  new ResizeObserver(() => {
    if (fitOwed) fit();
  }).observe(view);
  view.addEventListener(
    'wheel',
    (event) => {
      event.preventDefault();
      if (!current) return;
      const box = view.getBoundingClientRect();
      const size = state.size * (event.deltaY < 0 ? 1.25 : 0.8);
      // From a sixteenth of the view up to 32 screen pixels per texture pixel.
      zoomTo(Math.min(Math.max(size, Math.min(box.width, box.height) / 16), actualSize() * 32), event.clientX - box.left, event.clientY - box.top);
    },
    { passive: false },
  );
  let drag: { grabbed: number; line: number; x: number; y: number } | null = null;
  // A selection would start the browser's own drag, which cancels the pointer.
  view.addEventListener('dragstart', (event) => event.preventDefault());
  view.addEventListener('pointerdown', (event) => {
    if (event.button !== 0) return;
    event.preventDefault();
    const target = event.target;
    drag = { grabbed: target instanceof HTMLElement ? dividers.indexOf(target) : -1, line: -1, x: event.clientX, y: event.clientY };
    view.setPointerCapture(event.pointerId);
    view.classList.toggle('panning', drag.grabbed < 0);
  });
  view.addEventListener('pointermove', (event) => {
    if (!drag) return;
    if (drag.grabbed >= 0) {
      const box = view.getBoundingClientRect();
      if (drag.line < 0) {
        if (event.clientX === drag.x) return;
        // Lines at one place lie on top of each other: moving left takes the leftmost, moving right the rightmost.
        const place = state.splits[drag.grabbed] ?? 0;
        const together = dividers.map((_, i) => i).filter((i) => Math.abs((state.splits[i] ?? 0) - place) * box.width < 1);
        drag.line = (event.clientX < drag.x ? together[0] : together[together.length - 1]) ?? drag.grabbed;
      }
      moveSplit(drag.line, (event.clientX - box.left) / box.width);
    } else {
      state.x += event.clientX - drag.x;
      state.y += event.clientY - drag.y;
      drag.x = event.clientX;
      drag.y = event.clientY;
    }
    draw();
  });
  for (const name of ['pointerup', 'pointercancel'] as const) {
    view.addEventListener(name, () => {
      drag = null;
      view.classList.remove('panning');
    });
  }

  return { show, clear, fit, actual, toggle, size: () => state.size };
}

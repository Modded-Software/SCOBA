// Framebuffer reads and pixel statistics, for the tests.

import type { FeatureContext } from '../../core/context';

interface Frame {
  width: number;
  height: number;
  data: Uint8Array;
}

/** A pixel channel; 0 outside the buffer. */
const at = (data: Uint8Array, i: number): number => data[i] ?? 0;
const rgbAt = (data: Uint8Array, i: number): [number, number, number] => [at(data, i), at(data, i + 1), at(data, i + 2)];

/** The framebuffer reads, bound to the render, scene and status services. */
export function createInspectFrame({ render, scene, status }: Pick<FeatureContext, 'render' | 'scene' | 'status'>) {
  /** Render one frame without advancing time and read the framebuffer back. */
  function grab(): Frame {
    const a = render;
    a.resize();
    render.draw(0);
    const gl = a.viewer.gl;
    const width = a.canvas.width;
    const height = a.canvas.height;
    const data = new Uint8Array(width * height * 4);
    gl.readPixels(0, 0, width, height, gl.RGBA, gl.UNSIGNED_BYTE, data);
    return { width, height, data };
  }

  /** Where a world point lands, as the renderer's camera computes it. */
  function toScreen(x: number, y: number, z: number): Float32Array {
    const scene = render.scene;
    const screen = new Float32Array(2);
    scene.camera.worldToScreen(screen, new Float32Array([x, y, z]), scene.viewport);
    return screen;
  }

  /** The drawn colours where world points [x, y, z?] land on the canvas, from one frame. */
  function groundPixels(points: readonly (readonly number[])[]): { px: number; py: number; rgb: number[] }[] {
    const frameData = grab();
    return points.map(([x = 0, y = 0, z = 0]) => {
      const screen = toScreen(x, y, z);
      const px = Math.min(frameData.width - 1, Math.max(0, screen[0] ?? 0));
      const py = Math.min(frameData.height - 1, Math.max(0, screen[1] ?? 0));
      const i = (py * frameData.width + px) * 4;
      return { px, py, rgb: rgbAt(frameData.data, i) };
    });
  }

  /** The drawn colour where a world point lands on the canvas. */
  function groundPixel(x: number, y: number, z = 0): { px: number; py: number; rgb: number[] } | undefined {
    return groundPixels([[x, y, z]])[0];
  }

  /**
   * For each ground point [x, y], the greenest pixel within `reach` pixels
   * of where it lands, from one frame: a one-pixel line is found even when
   * the point maps beside it. Null for a point that lands off the canvas.
   */
  function groundPeaks(points: readonly (readonly number[])[], reach = 1): ({ px: number; py: number; rgb: number[] } | null)[] {
    const frameData = grab();
    return points.map(([x = 0, y = 0]) => {
      const screen = toScreen(x, y, 0);
      const sx = screen[0] ?? 0;
      const sy = screen[1] ?? 0;
      const inside = sx >= reach && sy >= reach && sx < frameData.width - reach && sy < frameData.height - reach;
      if (!inside) return null;
      let best: { px: number; py: number; rgb: [number, number, number] } | null = null;
      for (let dy = -reach; dy <= reach; dy++) {
        for (let dx = -reach; dx <= reach; dx++) {
          const px = Math.min(frameData.width - 1, Math.max(0, Math.round(sx) + dx));
          const py = Math.min(frameData.height - 1, Math.max(0, Math.round(sy) + dy));
          const rgb = rgbAt(frameData.data, (py * frameData.width + px) * 4);
          if (!best || rgb[1] > best.rgb[1]) best = { px, py, rgb };
        }
      }
      return best;
    });
  }

  /**
   * Where a world point lands on the canvas, in canvas pixels, as the
   * renderer's camera computes it: x from the left; y as the library gives
   * it (the framebuffer row).
   */
  function worldToCanvas(x: number, y: number, z = 0): number[] {
    render.resize();
    const screen = toScreen(x, y, z);
    return [screen[0] ?? 0, screen[1] ?? 0];
  }

  let marked: Frame | null = null;

  /** Remember the current frame, to compare a later one against. */
  function mark(): void {
    marked = grab();
  }

  /**
   * How many pixels differ clearly from the marked frame.
   * Two renders of one still scene differ by a few low-amplitude pixels
   * (measured: 38 pixels, largest step 13 of 255), so small steps are ignored.
   */
  function changedSinceMark(): { changed: number; largest: number; delta: number[] } | null {
    const now = grab();
    const before = marked;
    if (!before || before.width !== now.width || before.height !== now.height) return null;
    let changed = 0;
    let largest = 0;
    // Summed signed change (now minus marked) of r, g, b over the changed pixels.
    const delta = [0, 0, 0];
    for (let i = 0; i < now.data.length; i += 4) {
      const d0 = at(now.data, i) - at(before.data, i);
      const d1 = at(now.data, i + 1) - at(before.data, i + 1);
      const d2 = at(now.data, i + 2) - at(before.data, i + 2);
      const step = Math.max(Math.abs(d0), Math.abs(d1), Math.abs(d2));
      if (step > largest) largest = step;
      if (step > 40) {
        changed++;
        delta[0] = (delta[0] ?? 0) + d0;
        delta[1] = (delta[1] ?? 0) + d1;
        delta[2] = (delta[2] ?? 0) + d2;
      }
    }
    return { changed, largest, delta };
  }

  /** The background colour, 0 to 255. */
  function background(): [number, number, number] {
    const b = render.BACKGROUND;
    return [Math.round(b[0] * 255), Math.round(b[1] * 255), Math.round(b[2] * 255)];
  }

  /** A test of "this pixel is the background colour". */
  function backgroundTest(): (r: number, g: number, b: number) => boolean {
    const bg = background();
    return (r, g, b) => Math.abs(r - bg[0]) <= 1 && Math.abs(g - bg[1]) <= 1 && Math.abs(b - bg[2]) <= 1;
  }

  /** Where the drawn pixels are. Rows count from the top, like the page. */
  function pixels(): Record<string, number | null> {
    const { width, height, data } = grab();
    const isBackground = backgroundTest();
    const colors = new Set<number>();
    let covered = 0;
    let sumX = 0;
    let minX = width;
    let maxX = -1;
    let minY = height;
    let maxY = -1;
    for (let i = 0, p = 0; i < data.length; i += 4, p++) {
      const [r, g, b] = rgbAt(data, i);
      if (isBackground(r, g, b)) continue;
      const x = p % width;
      const y = height - 1 - Math.floor(p / width); // the framebuffer is read bottom row first
      covered++;
      sumX += x;
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
      colors.add(((r >> 3) << 10) | ((g >> 3) << 5) | (b >> 3));
    }
    const box = covered ? { minX, maxX, minY, maxY } : { minX: null, maxX: null, minY: null, maxY: null };
    return { width, height, covered, colors: colors.size, centerX: covered ? sumX / covered : null, ...box };
  }

  /**
   * Colour statistics of the drawn (non-background) pixels: mean channel
   * values, mean brightness, the share of pixels that are clearly red
   * (red above 60 and over 1.6 times both green and blue), and the count
   * of clearly green pixels (the same rule for green).
   */
  function colorStats(): { pixels: number; mean: number[]; brightness: number; redShare: number; green: number; darkShare: number } {
    const { data } = grab();
    const isBackground = backgroundTest();
    let n = 0;
    let red = 0;
    let green = 0;
    let dark = 0;
    let s0 = 0;
    let s1 = 0;
    let s2 = 0;
    for (let i = 0; i < data.length; i += 4) {
      const [r, g, b] = rgbAt(data, i);
      if (isBackground(r, g, b)) continue;
      n++;
      s0 += r;
      s1 += g;
      s2 += b;
      if (r > 60 && r > 1.6 * g && r > 1.6 * b) red++;
      if (g > 60 && g > 1.6 * r && g > 1.6 * b) green++;
      if (r + g + b < 30) dark++;
    }
    const mean = [s0, s1, s2].map((s) => (n ? s / n : 0));
    const [m0 = 0, m1 = 0, m2 = 0] = mean;
    return { pixels: n, mean, brightness: (m0 + m1 + m2) / 3, redShare: n ? red / n : 0, green, darkShare: n ? dark / n : 0 };
  }

  /** The share of drawn (non-background) pixels that are near white: every channel above 235. */
  function whiteShare(): number {
    const { data } = grab();
    const isBackground = backgroundTest();
    let n = 0;
    let white = 0;
    for (let i = 0; i < data.length; i += 4) {
      const [r, g, b] = rgbAt(data, i);
      if (isBackground(r, g, b)) continue;
      n++;
      if (r > 235 && g > 235 && b > 235) white++;
    }
    return n ? white / n : 0;
  }

  /**
   * Grid lines along one canvas row (from the top): the centres, in pixels
   * from the left, of the runs of grid-line pixels. A grid-line pixel is
   * greener than the background: green at least 6 over it and 4 over red
   * (the faint grid away from units is about 14 and 10). Also the ground
   * quad's half size as last drawn.
   */
  function gridLines(row: number): { width: number; centres: number[]; radius: number } {
    const { width, height, data } = grab();
    const bg = background();
    const y = height - 1 - row; // the framebuffer is read bottom row first
    const centres = [];
    let start = -1;
    for (let x = 0; x <= width; x++) {
      let on = false;
      if (x < width) {
        const i = (y * width + x) * 4;
        on = at(data, i + 1) - bg[1] >= 6 && at(data, i + 1) - at(data, i) >= 4;
      }
      if (on && start < 0) start = x;
      if (!on && start >= 0) {
        centres.push((start + x - 1) / 2);
        start = -1;
      }
    }
    return { width, centres, radius: render.ground.drawnRadius };
  }

  /** True when nothing is loading: no model being added, no texture in flight. */
  function idle(): boolean {
    return status.pending === 0 && render.viewer.promiseMap.size === 0;
  }

  /**
   * For each page pixel [clientX, clientY]: is something drawn there (not
   * the background colour)? From one frame. Read with the grid and the sky
   * off and the mouse away, it is the units' silhouette.
   */
  function drawnAt(points: readonly (readonly number[])[]): (boolean | null)[] {
    const { width, height, data } = grab();
    const isBackground = backgroundTest();
    const canvas = render.canvas;
    const box = canvas.getBoundingClientRect();
    const k = width / canvas.clientWidth;
    return points.map(([cx = 0, cy = 0]) => {
      const x = Math.floor((cx - box.left) * k);
      const y = height - 1 - Math.floor((cy - box.top) * k);
      if (x < 0 || y < 0 || x >= width || y >= height) return null;
      const [r, g, b] = rgbAt(data, (y * width + x) * 4);
      return !isBackground(r, g, b);
    });
  }

  /** Draw only the solid (unblended) parts of every unit, or all parts again (tests compare the two). */
  function setSolidOnly(on: boolean): void {
    for (const item of scene.items) item.instance.solidOnly = Boolean(on);
  }

  return { groundPixels, groundPixel, groundPeaks, worldToCanvas, mark, changedSinceMark, pixels, colorStats, whiteShare, gridLines, idle, drawnAt, setSolidOnly };
}

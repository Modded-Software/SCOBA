import { test, expect } from '../fixtures.mjs';

// Animations play at the data's rate (model AnimSpeed x actor time scale) in
// real time, whatever the screen refresh rate. The page used to advance a
// fixed 1/60 s per frame, so a 120 Hz screen played everything twice as fast.

// A 125 Hz screen: frames every 8 ms with real timestamps.
const FAST_SCREEN = () => {
  window.requestAnimationFrame = (callback) => setTimeout(() => callback(performance.now()), 8);
};

async function open(page) {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => {
    if (m.text().startsWith('viewer:') || m.type() === 'error') errors.push(m.text());
  });
  await page.addInitScript(FAST_SCREEN);
  await page.goto('/');
  await expect.poll(() => errors.join(' | ') || page.evaluate(() => Boolean(window.scobaeditor && window.scobaeditor.ready)), { timeout: 10_000 }).toBe(true);
  return errors;
}

/** Animation time the renderer advanced over `ms` of real time, wraps skipped. */
async function measure(page, id, ms) {
  await page.evaluate((u) => window.scobaeditor.addUnit(u, { x: 0, y: 0 }), id);
  await page.waitForFunction(() => window.scobaeditor.idle(), null, { timeout: 15_000 });
  return page.evaluate(
    (span) =>
      new Promise((resolve) => {
        const item = () => window.scobaeditor.state().items.at(-1);
        let start = 0;
        let last = 0;
        let advanced = 0;
        let frames = 0;
        let gap = 0; // longest real time between two samples
        let then = 0;
        let counted = 0; // real time as the frame loop counts it: a stall as at most 100 ms
        const step = () => {
          const t = performance.now();
          gap = Math.max(gap, t - then);
          counted += Math.min(t - then, 100);
          then = t;
          const now = item().frame;
          if (now >= last) advanced += now - last; // a loop wrap is skipped
          last = now;
          frames += 1;
          const elapsed = t - start;
          if (elapsed >= span) resolve({ advanced, elapsed, counted, frames, gap, rate: item().rate, sequence: item().sequenceName });
          else setTimeout(step, 8);
        };
        // Warm up first: a freshly loaded page stalls once (shaders, first
        // texture uploads), and the frame loop counts a stall as at most
        // 100 ms (src/page/core/frame.ts MAX_STEP), by design.
        setTimeout(() => {
          start = then = performance.now();
          last = item().frame;
          setTimeout(step, 8);
        }, 700);
      }),
    ms,
  );
}

for (const [id, rate] of [
  ['Marine', 1],
  ['Mothership', 0.25],
]) {
  test(`${id}: animation advances ${rate} x real time on a 125 Hz screen`, async ({ page }) => {
    const errors = await open(page);
    const m = await measure(page, id, 1500);
    console.log(id, JSON.stringify(m));
    expect(m.rate).toBeCloseTo(rate, 5);
    // Against real time with stalls capped as the frame loop caps them (a
    // stall longer than 100 ms is a page hitch, not animation time).
    const ratio = m.advanced / (m.counted * rate);
    // Wraps and frame jitter cost a little; the old fixed step gave about 2.
    expect(ratio).toBeGreaterThan(0.8);
    expect(ratio).toBeLessThan(1.15);
    expect(errors).toEqual([]);
  });
}

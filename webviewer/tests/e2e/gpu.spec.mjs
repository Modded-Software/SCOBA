import { test, expect } from '../fixtures.mjs';
import { open } from '../page.mjs';

// The page renders on the GPU (playwright.config.mjs launch flags). A run
// that falls back to software WebGL fails here, not by timeouts elsewhere.

/** The WebGL vendor and renderer the page's canvas reports. */
const renderer = (page) =>
  page.evaluate(() => {
    const gl = document.createElement('canvas').getContext('webgl2') ?? document.createElement('canvas').getContext('webgl');
    if (!gl) return { vendor: 'none', renderer: 'no WebGL context' };
    const info = gl.getExtension('WEBGL_debug_renderer_info');
    return {
      vendor: info ? gl.getParameter(info.UNMASKED_VENDOR_WEBGL) : gl.getParameter(gl.VENDOR),
      renderer: info ? gl.getParameter(info.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER),
    };
  });

test('the page renders WebGL on a GPU, not in software', async ({ page }) => {
  // Read before the viewer starts, so a viewer failure does not hide which renderer it got.
  await page.goto('about:blank');
  const found = await renderer(page);
  console.log(`webgl ${JSON.stringify(found)}`);
  await open(page);
  // Negative: no software renderer.
  expect(found.renderer).not.toMatch(/swiftshader|llvmpipe|softpipe|software|no WebGL/i);
  expect(`${found.vendor} ${found.renderer}`).toMatch(/intel/i);
});

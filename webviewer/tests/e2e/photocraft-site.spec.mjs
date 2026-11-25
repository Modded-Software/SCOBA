import { test, expect } from '../fixtures.mjs';
import { open } from '../page.mjs';

// The PhotoCraft editor site (SPEC-PHOTOCRAFT section 7): the viewer's own
// server serves it below /photocraft/, and the health answer names the
// install. These tests need the install: without it they fail and say
// `make install-photocraft` (SPEC-PHOTOCRAFT section 12).

const SITE = '/photocraft/';

/** The health answer's PhotoCraft part; the install must be there. */
async function installed(request) {
  const { photocraft } = await (await request.get('/api/health')).json();
  expect(photocraft.reason, 'PhotoCraft is not installed: run make install-photocraft').toBeNull();
  expect(photocraft.installed).toBe(true);
  return photocraft;
}

test('the health answer names the install by its pins; the site page, its script and its .wasm are served, the .wasm as application/wasm; a file that is not there is a 404, never the page', async ({ request }) => {
  const photocraft = await installed(request);
  expect(photocraft.pins.some((line) => /^photocraft v\d+\.\d+\.\d+ [0-9a-f]{40}$/.test(line))).toBe(true);
  expect(photocraft.pins.some((line) => line.startsWith('rust '))).toBe(true);
  expect(photocraft.pins.some((line) => line.startsWith('trunk '))).toBe(true);

  const page = await request.get(SITE);
  expect(page.status()).toBe(200);
  expect(page.headers()['content-type']).toContain('text/html');
  const html = await page.text();
  const script = /from '\.\/([A-Za-z0-9._-]+\.js)'/.exec(html)?.[1];
  const wasm = /'\.\/([A-Za-z0-9._-]+\.wasm)'/.exec(html)?.[1];
  expect(script, 'the page names its script').toBeTruthy();
  expect(wasm, 'the page names its .wasm').toBeTruthy();
  const scriptReply = await request.get(SITE + script);
  expect(scriptReply.status()).toBe(200);
  expect(scriptReply.headers()['content-type']).toContain('text/javascript');
  const wasmReply = await request.get(SITE + wasm);
  expect(wasmReply.status()).toBe(200);
  expect(wasmReply.headers()['content-type']).toBe('application/wasm');
  expect((await wasmReply.body()).length).toBeGreaterThan(1024 * 1024);
  // The licence files are part of the site (R-PC-8).
  for (const name of ['LICENSE-MIT', 'LICENSE-APACHE', 'NOTICE', 'ATTRIBUTION.md']) expect((await request.get(SITE + name)).status(), name).toBe(200);

  // Negative: nothing but the site's own files, and no page in place of a missing file.
  for (const path of ['nope.js', 'snippets/nope.js', '../photocraft.pins', '%2e%2e/photocraft.pins', '..%2fphotocraft.pins', 'index.html/x', '.hidden']) {
    const reply = await request.get(SITE + path);
    expect(reply.status(), path).toBe(404);
    expect(reply.headers()['content-type'], path).toContain('application/json');
  }
  expect((await request.post(SITE)).status()).toBe(405);
});

test('the editor starts in a frame of the viewer page, served below a path, and asks nothing past this server', async ({ page, request }) => {
  test.setTimeout(150_000);
  await installed(request);
  const asked = [];
  page.on('request', (made) => asked.push(made.url()));
  const errors = await open(page);
  const origin = new URL(page.url()).origin;
  const started = Date.now();
  await page.evaluate((src) => {
    const frame = document.createElement('iframe');
    frame.id = 'photocraft-trial';
    frame.src = src;
    frame.style.cssText = 'position:fixed;left:0;top:0;width:900px;height:600px;z-index:99999;border:0';
    document.body.append(frame);
  }, SITE);
  const frame = page.frameLocator('#photocraft-trial');
  // The app removes its loading element once it runs.
  await expect(frame.locator('#photocraft_loading')).toHaveCount(0, { timeout: 120_000 });
  const took = Date.now() - started;
  await expect(frame.locator('#photocraft_stopped')).toBeHidden();
  const canvas = await frame.locator('#photocraft_canvas').evaluate((node) => ({ width: node.width, height: node.height }));
  expect(canvas.width).toBeGreaterThan(0);
  expect(canvas.height).toBeGreaterThan(0);
  const site = asked.filter((url) => url.startsWith(origin + SITE));
  // The raw values of trial S2.
  console.log(`photocraft: started in ${took} ms; canvas ${canvas.width}x${canvas.height}; site requests: ${site.map((url) => url.slice(origin.length)).join(' ')}`);
  expect(site.length).toBeGreaterThan(2);
  // Negative: no request leaves this server (R-PC-12).
  expect(asked.filter((url) => !url.startsWith(origin + '/') && !url.startsWith('data:') && !url.startsWith('blob:'))).toEqual([]);
  // Negative: the frame broke nothing in the viewer page.
  expect(errors).toEqual([]);
});

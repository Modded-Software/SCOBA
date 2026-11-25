// Edit sessions of SC2 for the tests (SPEC-PHOTOCRAFT 12): the routes, and a
// scratch changed as another program would, by the commands of PhotoCraft's
// own renderer. The tests that use these need the install: without it they
// fail (scripts/test.sh names PHOTOCRAFT_HOME; `make install-photocraft`).
import { rename } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { expect, envPath, run } from './fixtures.mjs';

/** The renderer of the install. */
export const cli = () => join(envPath('PHOTOCRAFT_HOME'), 'bin', 'photocraft-cli');

const query = (dataset) => new URLSearchParams({ dataset });

/** An edit route of SC2: `rest` is the path after `edit` ("", "/open", "/<session>/transfer"). */
export const editUrl = (dataset, rest = '') => `/api/sc2/textures/edit${rest}?${query(dataset)}`;
/** A route the editor's bridge asks: it names no dataset. */
export const hostUrl = (session, rest) => `/api/sc2/textures/edit/${session}${rest}`;

/** Open the session of a texture and a variant, or get the one that is there. */
export async function openSession(request, dataset, asset, variant = 'original') {
  const answer = await request.post(editUrl(dataset, '/open'), { data: { asset, variant } });
  expect(answer.status(), await answer.text()).toBe(200);
  return (await answer.json()).session;
}

export const sessionOf = async (request, dataset, session) => (await (await request.get(editUrl(dataset, `/${session}`))).json()).session;
export const sessionsOf = async (request, dataset) => (await (await request.get(editUrl(dataset))).json()).sessions;

/** The session once the check of its scratch as it is has run. A check that could not run fails the test with its reason. */
export async function checkedSession(request, dataset, session) {
  let now;
  await expect
    .poll(
      async () => {
        now = await sessionOf(request, dataset, session);
        return now.checkError || now.checking;
      },
      { timeout: 60_000 },
    )
    .toBe(false);
  return now;
}

/** One command of the renderer with its values, as words of a `run` command line. */
export const cmd = (name, params = {}) => ['--cmd', name, '--params', JSON.stringify(params)];

/** Select the layer `base` of a plane's group. The renderer counts the layers of one name from the bottom. */
export const baseOf = (session, plane) => cmd('layer.select', { name: 'base', occurrence: session.planes.length - 1 - session.planes.indexOf(plane) });

/** Renderer commands on a session's scratch, saved over it by rename, as another program would. */
export async function changeScratch(session, ...steps) {
  // The suffix names the format.
  const saved = join(dirname(session.scratch), 'changed.scratch.psd');
  await run(cli(), ['run', session.scratch, ...steps.flat(), '--out', saved, '--no-gpu']);
  await rename(saved, session.scratch);
}

/** A new layer over a plane's base, in its group, filled with one colour. */
export const painted = (session, plane, colour = '#ff0000', name = 'paint') => [
  ...baseOf(session, plane),
  ...cmd('layer.new.layer', { name }),
  ...cmd('edit.fill', { contents: 'color', color: colour }),
];

// ---- the page ----

/** The page's edit state (src/page/features/edits): the editor window, the dialogs, the sessions read, what was offered. */
export const editsState = (page) => page.evaluate(() => window.sc2viewer.edits.state());

/** The editor's frame, once the editor window is open on a session. */
export const editorFrame = (page) => page.frames().find((frame) => frame.url().includes('/photocraft/'));

/**
 * Open the texture window on a unit of the gallery (a double-click on its row), make `asset` its current
 * texture, and wait until the page has read and judged the textures. Returns the texture page's frame.
 */
export async function openTextures(page, unit, asset) {
  await page.fill('#search-units', unit);
  const row = page.locator('#units li', { has: page.locator('.name', { hasText: new RegExp(`^${unit}$`, 'i') }) }).first();
  await expect(row).toBeVisible();
  await row.dblclick();
  await expect(page.locator('#texture-window')).toBeVisible();
  await expect.poll(() => page.evaluate(() => window.sc2viewer.textureWindow().originals), { timeout: 30_000 }).toBe('done');
  const frame = page.frames().find((one) => one.url().includes('/texture-viewer.html'));
  // The pipeline reads each texture nobody asked for by name yet; a unit with many textures takes longer.
  const started = Date.now();
  await expect.poll(() => frame.evaluate(() => window.hdtex.state().judging), { timeout: 150_000 }).toBe(false);
  console.log(`textures of ${unit}: judged after ${Date.now() - started} ms`);
  await expect(async () => {
    const index = (await frame.evaluate(() => window.hdtex.entries())).findIndex((entry) => entry.asset === asset);
    expect(index, asset).toBeGreaterThanOrEqual(0);
    await frame.locator('#list .row').nth(index).click();
    expect(await frame.evaluate(() => window.hdtex.state().current?.asset)).toBe(asset);
  }).toPass({ timeout: 20_000 });
  return frame;
}

/** The tiles of the texture page's current texture, as its state lists them. */
export const tilesOf = (frame) => frame.evaluate(() => window.hdtex.state().tiles);

/** The top-level layers of a document, top first: "<kind> <name>", and each group's children. */
export async function layersOf(document) {
  const { stdout } = await run(cli(), ['info', document, '--compact'], { maxBuffer: 64 * 1024 * 1024 });
  const info = JSON.parse(stdout);
  const carried = (child) => ({ name: child.name, kind: child.kind, visible: child.visible, blend: child.blend, opacity: child.opacity, hasMask: child.hasMask ?? false, effects: (child.effects?.items ?? []).map((item) => item.kind), adjustment: child.adjustment?.kind ?? null });
  return {
    size: [info.width, info.height],
    top: info.layers.map((layer) => `${layer.kind} ${layer.name}`),
    children: Object.fromEntries(info.layers.map((layer) => [layer.name, (layer.children ?? []).map((child) => `${child.kind} ${child.name}`)])),
    /** By top-level layer: what each of its children carries (blend mode, mask, layer style, adjustment, shown or hidden). */
    carried: Object.fromEntries(info.layers.map((layer) => [layer.name, (layer.children ?? []).map(carried)])),
  };
}

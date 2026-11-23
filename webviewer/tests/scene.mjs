// The scene documents (SPEC-VIEWER section 10.2), for the tests: read the
// open scene, wait for its writes, reload, and build scene files.

/** The open scene as it would be stored now. */
export const sceneOf = (page) => page.evaluate(() => window.sc2viewer.scenes.document());

/** The scene list state: open, list, refused, loading, address. */
export const scenesState = (page) => page.evaluate(() => window.sc2viewer.scenes.state());

/** Wait until every scene write asked so far is on disk. */
export const flush = (page) => page.evaluate(() => window.sc2viewer.scenes.flush());

/** Wait for the page to be ready and the open scene's items added. */
export const settled = (page) => page.waitForFunction(() => window.sc2viewer && window.sc2viewer.ready && !window.sc2viewer.scenes.state().loading && window.sc2viewer.idle(), null, { timeout: 30_000 });

/** Write, reload, and wait until the scene is back. */
export async function reloadScene(page) {
  await flush(page);
  await page.reload();
  await settled(page);
}

/** One scene item, SC2, from "scoba", with every field given; `fields` override. */
export const sceneItem = (source, fields = {}) => ({ game: 'sc2', dataset: 'scoba', source, x: 0, y: 0, rot: 0, scale: 1, sequence: -1, pick: 0.5, options: {}, ...fields });

/** A scene file's text: a version 1 document with `items`. */
export const sceneText = (items, fields = {}) =>
  JSON.stringify({ format: 'viewer-scene', version: 1, id: 's-test1', name: 'test scene', created: '2026-11-23T12:00:00.000Z', modified: '2026-11-23T12:00:00.000Z', items, ...fields });

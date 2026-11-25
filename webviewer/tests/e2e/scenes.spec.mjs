import { allowErrors, test, expect } from '../fixtures.mjs';
import { flush, reloadScene, sceneItem, sceneOf, sceneText, scenesState, settled } from '../scene.mjs';
import { refusedRows, storeAndReload } from '../refused.mjs';
import { cleanOwner, makeSkin } from '../skins.mjs';

// Scene documents (SPEC-VIEWER section 10.2, R-VIEW-70 to 77): several named
// scenes in IndexedDB, checked on every read; export and import; the page
// address holds no scene. Each test has its own browser context, so its
// own empty database.

// Uncaught errors only: a refused scene is reported on the console by design.
async function open(page, path = '/') {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto(path);
  await settled(page);
  return errors;
}

const call = (page, name, ...args) => page.evaluate(([n, a]) => window.scobaeditor.scenes[n](...a), [name, args]);
const addUnit = (page, id, options) => page.evaluate(([i, o]) => window.scobaeditor.addUnit(i, o), [id, options]);
const units = async (page) => (await page.evaluate(() => window.scobaeditor.state())).items.map((i) => i.unit ?? i.doodad ?? i.path);
/** Every message of the page so far: the message log (R-VIEW-64). */
const log = async (page) => (await page.locator('#status-log').textContent()) ?? '';
const MARINE = sceneItem({ category: 'units', record: 'Marine', variant: null }, { x: 1, y: 2, rot: 30, sequence: 0, options: { team: 3, skin: 'hd' } });
const TREE = sceneItem({ category: 'doodads', record: 'ZerusTree', variant: 4 }, { x: -3 });

/** MARINE names the skin "hd": store it for this test (the worker's store), and take it away after. */
let hdMade = false;
async function hdSkin(page) {
  await cleanOwner(page.request, 'scoba', 'unit:Marine');
  await makeSkin(page.request, 'scoba', 'unit:Marine', 'hd', {});
  hdMade = true;
}
test.afterEach(async ({ page }) => {
  if (!hdMade) return;
  hdMade = false;
  await cleanOwner(page.request, 'scoba', 'unit:Marine');
});

/** Put a record straight into the scene store, past the page's check. */
const storeRaw = (page, value) =>
  page.evaluate(
    (v) =>
      new Promise((resolve, reject) => {
        const request = indexedDB.open('viewer', 1);
        request.onerror = () => reject(request.error);
        request.onsuccess = () => {
          const tx = request.result.transaction('scenes', 'readwrite');
          tx.objectStore('scenes').put(v);
          tx.oncomplete = () => {
            request.result.close();
            resolve(true);
          };
          tx.onerror = () => reject(tx.error);
        };
      }),
    value,
  );

test('a first start makes one empty scene, "scene 1", and opens it; the address stays empty', async ({ page }) => {
  const errors = await open(page);
  const s = await scenesState(page);
  expect(s.list).toHaveLength(1);
  expect(s.list[0]).toMatchObject({ name: 'scene 1', items: 0 });
  expect(s.open).toEqual({ id: s.list[0].id, name: 'scene 1' });
  expect(s.refused).toEqual([]);
  expect(s.address).toBe('empty');
  await expect(page.locator('#scenes-button')).toHaveText('scene 1');
  // The open scene id is a setting.
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem('viewer.scene')))).toBe(s.open.id);
  // Negative: adding, moving and removing never write the address.
  const id = await addUnit(page, 'Marine', { x: 0, y: 0, pick: 0.5 });
  await page.evaluate((i) => window.SCOBAEdit.setPosition(window.SCOBAEdit.items.find((x) => x.id === i), 4, 4), id);
  await page.evaluate((i) => window.scobaeditor.remove(i), id);
  expect(page.url()).not.toContain('#');
  expect(errors).toEqual([]);
});

// The one reload test of the scene store: every kind of item and every field
// comes back. A unit and a doodad of the default dataset, one of each other
// dataset, and a model file.
test('every change writes the scene; a reload opens it again with every field', async ({ page }) => {
  await hdSkin(page);
  await open(page);
  const STOCK = sceneItem({ category: 'units', record: 'Marine', variant: null }, { x: 4, dataset: 'stock' });
  const FX = sceneItem({ category: 'units', record: 'Marine', variant: null }, { x: 7, dataset: 'fx' });
  const STOCK_TREE = sceneItem({ category: 'doodads', record: 'ZerusTree', variant: 2 }, { x: 9, dataset: 'stock' });
  const FILE = sceneItem({ file: 'mods\\liberty.sc2mod\\base.sc2assets\\assets\\units\\protoss\\zealot\\zealot.m3' }, { x: -6, rot: 45, scale: 1.5 });
  await call(page, 'importText', sceneText([MARINE, TREE, STOCK, FX, STOCK_TREE, FILE]));
  await settled(page);
  // A change made in the page is written too.
  const rows = page.locator('#scene li');
  await rows.nth(5).locator('input.x').fill('-5');
  await rows.nth(5).locator('input.x').dispatchEvent('change');
  const before = (await page.evaluate(() => window.scobaeditor.state())).items;
  const stored = await sceneOf(page);
  expect(stored.items[5].x).toBe(-5);
  // Negative: the address holds none of it.
  expect(new URL(page.url()).hash).toBe('');

  await reloadScene(page);
  const again = await sceneOf(page);
  expect(again.id).toBe(stored.id);
  expect(again.items).toEqual(stored.items);
  expect(again.items[0]).toMatchObject({ x: 1, y: 2, rot: 30, sequence: 0, options: { team: 3, skin: 'hd' }, dataset: 'scoba', game: 'sc2' });
  expect(again.items[1].source).toEqual({ category: 'doodads', record: 'ZerusTree', variant: 4 });
  expect(again.items.map((i) => i.dataset)).toEqual(['scoba', 'scoba', 'stock', 'fx', 'stock', 'scoba']);
  expect(again.items[5]).toMatchObject({ source: { file: 'mods\\liberty.sc2mod\\base.sc2assets\\assets\\units\\protoss\\zealot\\zealot.m3' }, x: -5, rot: 45, scale: 1.5 });
  // An item without the option has Original.
  expect(again.items[1].options.skin).toBe('original');
  // What the view made of them is the same: model, place, dataset data, variation, skin.
  const items = (await page.evaluate(() => window.scobaeditor.state())).items;
  const key = (i) => ({ path: i.path, unit: i.unit, doodad: i.doodad, variation: i.variation, dataset: i.dataset, x: i.x, y: i.y, rot: i.rot, sequence: i.sequence, team: i.team, skin: i.skin, dataScale: i.dataScale, loaded: i.loaded });
  expect(items.map(key)).toEqual(before.map(key));
  expect(items.every((i) => i.loaded)).toBe(true);
  expect(items.map((i) => i.skin)).toEqual(['hd', 'original', 'original', 'original', 'original', 'original']);
  // Each dataset's own data: the map's Marine is 1.25, the stock one 1, the fixture's 2; the stock tree lacks the map's 4 to 6 times scale.
  expect(items.slice(2, 4).map((i) => i.dataScale[0])).toEqual([1, 2]);
  expect(items[0].dataScale[0]).toBe(1.25);
  expect(items[4]).toMatchObject({ doodad: 'ZerusTree', variation: 2 });
  expect(items[4].dataScale[0]).toBeLessThan(4);
  expect(items[1].path.toLowerCase()).toContain('zerustree_04.m3');
  await expect(rows).toHaveCount(6);
  await expect(rows.nth(5).locator('input.x')).toHaveValue('-5');
});

test('negative: an item with an option the game does not know, or a bad team, animation or skin type, is refused and names why', async ({ page }) => {
  allowErrors(/^console\.warning: scobaeditor: Error: (unknown item option "(hd|textures)"|option team: not a whole number|Marine: no team 99|option skin: not a name|Marine: no animation 9999)/);
  test.setTimeout(60_000);
  await open(page);
  const refused = [
    [{ team: 3, hd: false }, 'unknown item option "hd"'],
    [{ team: 3, textures: 'soft' }, 'unknown item option "textures"'],
    [{ team: 'red' }, 'option team: not a whole number'],
    [{ team: 99 }, 'no team 99'],
    [{ skin: 7 }, 'option skin: not a name'],
  ];
  for (const [options, why] of refused) {
    await call(page, 'importText', sceneText([{ ...MARINE, options }]));
    await settled(page);
    // Not added, and the reason is in the message log.
    expect(await units(page), JSON.stringify(options)).toEqual([]);
    expect(await log(page)).toContain(why);
  }
  await call(page, 'importText', sceneText([{ ...MARINE, sequence: 9999, options: { team: 3 } }]));
  await settled(page);
  expect(await units(page)).toEqual([]);
  expect(await log(page)).toContain('no animation 9999');
});

test('negative: an address with a "#" part is refused with a message and cleared; nothing of it is added', async ({ page }) => {
  const old = '#' + encodeURIComponent(JSON.stringify([{ u: 'Marine', x: 0, y: 0 }]));
  const errors = await open(page, '/' + old);
  expect(new URL(page.url()).hash).toBe('');
  expect((await scenesState(page)).address).toBe('refused');
  expect(await log(page)).toContain('no longer kept in the address');
  expect(await units(page)).toEqual([]);
  expect(errors).toEqual([]);
});

test('several named scenes: each keeps its own instances; the one open last opens after a reload', async ({ page }) => {
  await open(page);
  const first = (await scenesState(page)).open.id;
  await addUnit(page, 'Marine', { x: 0, y: 0, pick: 0.5 });
  const second = await call(page, 'create', 'zerg');
  await settled(page);
  // Negative: the new scene starts empty; the first is untouched.
  expect(await units(page)).toEqual([]);
  await addUnit(page, 'Zergling', { x: 0, y: 0, pick: 0.5 });
  await addUnit(page, 'Roach', { x: 2, y: 0, pick: 0.5 });
  const list = (await scenesState(page)).list;
  expect(list.map((s) => [s.name, s.items])).toEqual([['scene 1', 1], ['zerg', 2]]);
  await call(page, 'open', first);
  await settled(page);
  expect(await units(page)).toEqual(['Marine']);
  await call(page, 'open', second);
  await settled(page);
  expect(await units(page)).toEqual(['Zergling', 'Roach']);
  await reloadScene(page);
  expect((await scenesState(page)).open.id).toBe(second);
  expect(await units(page)).toEqual(['Zergling', 'Roach']);
  // The list opens a scene with a click.
  await page.click('#scenes-button');
  await page.locator(`#scenes-list li[data-id="${first}"] .go`).click();
  await settled(page);
  expect(await units(page)).toEqual(['Marine']);
  await expect(page.locator('#scenes-button')).toHaveText('scene 1');
});

test('new and rename ask a name; a taken name gets a number', async ({ page }) => {
  await open(page);
  await page.click('#scenes-button');
  await page.click('#scene-new');
  await expect(page.locator('#scene-name-dialog')).toBeVisible();
  await page.fill('#scene-name', 'scene 1');
  await page.click('#scene-name-yes');
  // The click starts the new scene; it opens after its first write.
  await expect.poll(async () => (await scenesState(page)).open?.name).toBe('scene 1 (2)');
  await settled(page);
  let s = await scenesState(page);
  expect(s.list.map((x) => x.name)).toEqual(['scene 1', 'scene 1 (2)']);
  expect(s.open.name).toBe('scene 1 (2)');
  // Rename through the list.
  await page.click('#scenes-button');
  await page.locator(`#scenes-list li[data-id="${s.open.id}"] .rename`).click();
  await page.fill('#scene-name', '  bases  ');
  await page.keyboard.press('Enter');
  await expect.poll(async () => (await scenesState(page)).open.name).toBe('bases');
  // Negative: an empty name cannot be saved; cancel changes nothing.
  await page.click('#scenes-button');
  await page.locator(`#scenes-list li[data-id="${s.open.id}"] .rename`).click();
  await page.fill('#scene-name', '   ');
  await expect(page.locator('#scene-name-yes')).toBeDisabled();
  await page.click('#scene-name-no');
  s = await scenesState(page);
  expect(s.list.map((x) => x.name)).toEqual(['bases', 'scene 1']);
  await flush(page);
  await reloadScene(page);
  expect((await scenesState(page)).open.name).toBe('bases');
});

test('delete asks first; the open scene gone, the newest other opens; the last gone, a new empty one', async ({ page }) => {
  await open(page);
  const first = (await scenesState(page)).open.id;
  await addUnit(page, 'Marine', { x: 0, y: 0, pick: 0.5 });
  const second = await call(page, 'create', 'two');
  await settled(page);
  // Negative: cancel keeps it.
  await page.click('#scenes-button');
  await page.locator(`#scenes-list li[data-id="${second}"] .trash`).click();
  await expect(page.locator('#scene-delete-dialog')).toContainText('Delete the scene "two"?');
  // The dialog names what it deletes (R-VIEW-136; that it is red is an operator check).
  await expect(page.locator('#scene-delete-dialog .answers button')).toHaveText(['Cancel', 'Delete Scene']);
  await page.click('#scene-delete-no');
  expect((await scenesState(page)).list).toHaveLength(2);
  // Yes deletes it; the other opens with its instance.
  await page.click('#scenes-button');
  await page.locator(`#scenes-list li[data-id="${second}"] .trash`).click();
  await page.click('#scene-delete-yes');
  await expect.poll(async () => (await scenesState(page)).open?.id).toBe(first);
  await settled(page);
  expect(await units(page)).toEqual(['Marine']);
  expect((await scenesState(page)).list.map((x) => x.id)).toEqual([first]);
  // The last one gone: a new empty "scene 1".
  await call(page, 'remove', first);
  await settled(page);
  const s = await scenesState(page);
  expect(s.list).toHaveLength(1);
  expect(s.list[0].id).not.toBe(first);
  expect(s.list[0]).toMatchObject({ name: 'scene 1', items: 0 });
  // Negative: it stays gone over a reload.
  await reloadScene(page);
  expect((await scenesState(page)).list.map((x) => x.id)).not.toContain(first);
});

test('export downloads the open scene; import of that file makes a new scene with the same items', async ({ page }) => {
  await hdSkin(page);
  await open(page);
  await call(page, 'importText', sceneText([MARINE, TREE], { name: 'exported' }));
  await settled(page);
  const original = await sceneOf(page);
  await page.click('#scenes-button');
  const downloading = page.waitForEvent('download');
  await page.click('#scene-export');
  const download = await downloading;
  expect(download.suggestedFilename()).toBe('exported.scene.json');
  const text = await (await download.createReadStream()).toArray().then((parts) => Buffer.concat(parts).toString('utf8'));
  const file = JSON.parse(text);
  expect(file).toEqual(original);
  // Import it through the file input.
  await page.locator('#scenes-import-file').setInputFiles({ name: 'exported.scene.json', mimeType: 'application/json', buffer: Buffer.from(text) });
  await expect.poll(async () => (await scenesState(page)).list.length).toBe(3);
  await settled(page);
  const imported = await sceneOf(page);
  expect(imported.id).not.toBe(original.id);
  expect(imported.name).toBe('exported (2)');
  expect(imported.items).toEqual(original.items);
  expect(await units(page)).toEqual(['Marine', 'ZerusTree']);
});

test('negative: a file that fails the check is refused, names the fault, and changes nothing', async ({ page }) => {
  await open(page);
  await addUnit(page, 'Marine', { x: 0, y: 0, pick: 0.5 });
  await flush(page);
  const before = await scenesState(page);
  const document = await sceneOf(page);
  // Text that is no JSON, and one document fault: the check is wired in. Every fault of the
  // check itself: tests/unit/scene-document.spec.mjs.
  const bad = [
    ['not json', /import refused/],
    [sceneText([MARINE, { ...TREE, x: '3' }]), /items\[1\]\.x: not a finite number/],
  ];
  for (const [text, fault] of bad) {
    const message = await page.evaluate((t) => window.scobaeditor.scenes.importText(t).then(() => 'imported', (e) => e.message), text);
    expect(message, String(text).slice(0, 60)).toMatch(fault);
  }
  const after = await scenesState(page);
  expect(after.list).toEqual(before.list);
  expect(after.open).toEqual(before.open);
  expect(await sceneOf(page)).toEqual(document);
  expect(await units(page)).toEqual(['Marine']);
});

test('an item the server does not have is reported and left out; the other items are added', async ({ page }) => {
  await hdSkin(page);
  allowErrors(/^http 404 GET .*\/api\/sc2\/record\/units\?.*id=NoSuchUnitXyzzy/, /^console\.error: Failed to load resource: the server responded with a status of 4\d\d/, 'NoSuchUnitXyzzy is not in dataset "scoba"', 'scene item 3: game "nogame"', 'scene item 4: no category "nosuch"');
  await open(page);
  const missing = sceneItem({ category: 'units', record: 'NoSuchUnitXyzzy', variant: null });
  const otherGame = sceneItem({ category: 'units', record: 'Marine', variant: null }, { game: 'nogame' });
  const noCategory = sceneItem({ category: 'nosuch', record: 'Marine', variant: null });
  await call(page, 'importText', sceneText([missing, MARINE, otherGame, noCategory]));
  await settled(page);
  expect(await units(page)).toEqual(['Marine']);
  const messages = await log(page);
  expect(messages).toContain('NoSuchUnitXyzzy');
  expect(messages).toContain('scene item 3: game "nogame": the server has no game "nogame"');
  expect(messages).toContain('scene item 4: no category "nosuch"');
});

test('negative: an open-scene setting that names no good scene stops the start with the panel; Clear opens the newest', async ({ page }) => {
  allowErrors('viewer: stored scene "s-broken1" refused: items[0].scale: not above 0', /^console\.error: viewer: stored settings refused: viewer\.scene: /);
  await open(page);
  await call(page, 'create', 'newer');
  await settled(page);
  await flush(page);
  const newer = (await scenesState(page)).open.id;
  await storeRaw(page, JSON.parse(sceneText([{ ...MARINE, scale: -1 }], { id: 's-broken1', name: 'broken' })));
  // The cases that need the stored scenes. A value that is no scene id: tests/unit/settings.spec.mjs.
  const cases = [
    ['"s-nosuch1"', /^there is no such scene$/],
    ['"s-broken1"', /^the scene is refused: items\[0\]\.scale: not above 0$/],
  ];
  for (const [stored, reason] of cases) {
    await storeAndReload(page, { 'viewer.scene': stored });
    const rows = await refusedRows(page);
    expect(rows.map((r) => [r.key, r.stored]), stored).toEqual([['viewer.scene', stored]]);
    expect(rows[0].reason, stored).toMatch(reason);
  }
  // Negative: no other scene was opened or written in its place.
  expect(await page.evaluate(() => localStorage.getItem('viewer.scene'))).toBe('"s-broken1"');
  await page.locator('#settings-refused-clear').click();
  await settled(page);
  expect((await scenesState(page)).open.id).toBe(newer);
});

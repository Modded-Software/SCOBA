import { test, expect } from '@playwright/test';
import { flush, reloadScene, sceneItem, sceneOf, sceneText, scenesState, settled } from './scene.mjs';

// Scene documents (SPEC-VIEWER section 10.2, R-VIEW-70 to 77): several named
// scenes in IndexedDB, checked on every read; export and import; the page
// address holds no scene. Each test has its own browser context, so its
// own empty database.

async function open(page, path = '/') {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto(path);
  await settled(page);
  return errors;
}

const call = (page, name, ...args) => page.evaluate(([n, a]) => window.sc2viewer.scenes[n](...a), [name, args]);
const addUnit = (page, id, options) => page.evaluate(([i, o]) => window.sc2viewer.addUnit(i, o), [id, options]);
const units = async (page) => (await page.evaluate(() => window.sc2viewer.state())).items.map((i) => i.unit ?? i.doodad ?? i.path);
/** Every message of the page so far: the message log (R-VIEW-64). */
const log = async (page) => (await page.locator('#status-log').textContent()) ?? '';
const MARINE = sceneItem({ category: 'units', record: 'Marine', variant: null }, { x: 1, y: 2, rot: 30, sequence: 0, options: { team: 3, hd: true } });
const TREE = sceneItem({ category: 'doodads', record: 'ZerusTree', variant: 4 }, { x: -3 });

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
  await page.evaluate((i) => window.SC2App.setPosition(window.SC2App.items.find((x) => x.id === i), 4, 4), id);
  await page.evaluate((i) => window.sc2viewer.remove(i), id);
  expect(page.url()).not.toContain('#');
  expect(errors).toEqual([]);
});

test('every change writes the scene; a reload opens it again with every field', async ({ page }) => {
  await open(page);
  await call(page, 'importText', sceneText([MARINE, TREE]));
  await settled(page);
  const stored = await sceneOf(page);
  await reloadScene(page);
  const again = await sceneOf(page);
  expect(again.id).toBe(stored.id);
  expect(again.items).toEqual(stored.items);
  expect(again.items[0]).toMatchObject({ x: 1, y: 2, rot: 30, sequence: 0, options: { team: 3, hd: true }, dataset: 'scoba', game: 'sc2' });
  expect(again.items[1].source).toEqual({ category: 'doodads', record: 'ZerusTree', variant: 4 });
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
  const bad = [
    ['not json', /import refused/],
    [sceneText([MARINE], { version: 2 }), /version: 2 is not 1/],
    [sceneText([MARINE], { format: 'other' }), /format: not "viewer-scene"/],
    [sceneText([MARINE], { extra: 1 }), /extra: unknown field/],
    [sceneText([{ ...MARINE, scale: 0 }]), /items\[0\]\.scale: not above 0/],
    [sceneText([MARINE, { ...TREE, x: '3' }]), /items\[1\]\.x: not a finite number/],
    [sceneText([{ ...MARINE, pick: 2 }]), /items\[0\]\.pick: not from 0 to 1/],
    [sceneText([{ ...MARINE, dataset: 'Bad Id' }]), /items\[0\]\.dataset: not an id/],
    [sceneText([], { name: '' }), /name: not 1 to 80 characters/],
    [sceneText([], { created: 'yesterday' }), /created: not an ISO 8601 UTC time/],
  ];
  for (const [text, fault] of bad) {
    const message = await page.evaluate((t) => window.sc2viewer.scenes.importText(t).then(() => 'imported', (e) => e.message), text);
    expect(message, String(text).slice(0, 60)).toMatch(fault);
  }
  const after = await scenesState(page);
  expect(after.list).toEqual(before.list);
  expect(after.open).toEqual(before.open);
  expect(await sceneOf(page)).toEqual(document);
  expect(await units(page)).toEqual(['Marine']);
});

test('an item the server does not have is reported and left out; the other items are added', async ({ page }) => {
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

test('negative: a stored scene that fails its check is listed as refused; the others open; it can be deleted', async ({ page }) => {
  await open(page);
  const good = (await scenesState(page)).open.id;
  await addUnit(page, 'Marine', { x: 0, y: 0, pick: 0.5 });
  await flush(page);
  await storeRaw(page, JSON.parse(sceneText([{ ...MARINE, scale: -1 }], { id: 's-broken1', name: 'broken' })));
  await storeRaw(page, JSON.parse(sceneText([], { id: 's-later1', name: 'later', version: 2 })));
  await reloadScene(page);
  const s = await scenesState(page);
  expect(s.open.id).toBe(good);
  expect(await units(page)).toEqual(['Marine']);
  expect(s.list.map((x) => x.id)).toEqual([good]);
  expect(s.refused).toEqual([
    { id: 's-broken1', name: 'broken', reason: 'items[0].scale: not above 0' },
    { id: 's-later1', name: 'later', reason: 'version: 2 is not 1' },
  ]);
  expect(await log(page)).toContain('2 stored scene(s) refused');
  await page.click('#scenes-button');
  await expect(page.locator('#scenes-list li.refused')).toHaveCount(2);
  // Negative: a refused scene has no open and no rename.
  await expect(page.locator('#scenes-list li.refused button.go, #scenes-list li.refused .rename')).toHaveCount(0);
  await page.locator('#scenes-list li.refused[data-id="s-broken1"] .trash').click();
  await page.click('#scene-delete-yes');
  await expect.poll(async () => (await scenesState(page)).refused.map((r) => r.id)).toEqual(['s-later1']);
  await reloadScene(page);
  expect((await scenesState(page)).refused.map((r) => r.id)).toEqual(['s-later1']);
  expect(await units(page)).toEqual(['Marine']);
});

test('negative: an open-scene setting that names no good scene opens the newest good one', async ({ page }) => {
  await open(page);
  await call(page, 'create', 'newer');
  await settled(page);
  await flush(page);
  const newer = (await scenesState(page)).open.id;
  for (const stored of ['"s-nosuch1"', 'not json', '42']) {
    await page.evaluate((v) => localStorage.setItem('viewer.scene', v), stored);
    await reloadScene(page);
    expect((await scenesState(page)).open.id, stored).toBe(newer);
  }
});

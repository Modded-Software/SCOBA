import { test, expect } from '@playwright/test';

// The texture window (public/js/textures.js): the HD texture viewer in a
// movable window, hidden until a double-click on a gallery row, an instance
// row, or an instance in the view. It lists the textures of that unit or
// doodad: the ones with an HD version, and every other texture of its model
// with the original alone. The tests' texture viewer is
// tools/hdtex-fixture.mjs: two entries used by Marine, one by ZerusTree, one
// terrain entry, none by Zergling.

const VIEW = { yaw: -Math.PI / 2, pitch: 0.5, distance: 12, target: [2, 0, 0.8] };
const TOKENS = ['--bg', '--panel', '--raised', '--line', '--text', '--dim', '--accent', '--accent-bg', '--radius'];

async function open(page) {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => {
    if (m.text().startsWith('viewer:') || m.type() === 'error') errors.push(m.text());
  });
  await page.goto('/');
  await expect.poll(() => errors.join(' | ') || page.evaluate(() => Boolean(window.sc2viewer && window.sc2viewer.ready)), { timeout: 10_000 }).toBe(true);
  return errors;
}

const state = (page) => page.evaluate(() => window.sc2viewer.state());
const idle = (page) => page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 15_000 });
const win = (page) => page.evaluate(() => window.sc2viewer.textureWindow());
// A pixel on the unit's picture: the mouse hit goes by pixel.
const onItem = (page, id) => page.evaluate((i) => window.sc2viewer.itemPixel(i), id);
const textureFrame = (page) => page.frames().find((frame) => frame.url().includes('/textures/'));

/**
 * The texture viewer's own state, once the window's page shows `user` and
 * the originals of the model were handed to it. `hd`: the listed entries
 * with an upscaled side; `only`: the ones with the original alone.
 */
async function inside(page, user) {
  await expect
    .poll(async () => {
      const frame = textureFrame(page);
      if (!frame) return 'no frame';
      return frame.evaluate(() => (window.hdtex ? window.hdtex.state().user : 'loading')).catch((error) => error.message);
    })
    .toBe(user);
  await expect.poll(async () => (await win(page)).originals, { timeout: 15_000 }).toBe('done');
  const shown = await textureFrame(page).evaluate(() => ({ ...window.hdtex.state(), entries: window.hdtex.entries(), problems: window.hdtex.problems() }));
  return { ...shown, hd: shown.entries.filter((entry) => entry.layers > 0), only: shown.entries.filter((entry) => entry.layers === 0) };
}

/** Each listed image, loaded in the texture viewer: its real size and the sum of its pixel bytes. */
const measured = (page, images) =>
  textureFrame(page).evaluate(
    (list) =>
      Promise.all(
        list.map(async (src) => {
          const image = new Image();
          image.src = src;
          await image.decode();
          const canvas = document.createElement('canvas');
          canvas.width = image.naturalWidth;
          canvas.height = image.naturalHeight;
          const context = canvas.getContext('2d');
          context.drawImage(image, 0, 0);
          const data = context.getImageData(0, 0, canvas.width, canvas.height).data;
          let sum = 0;
          let lit = 0;
          for (let i = 0; i < data.length; i += 4) {
            sum += data[i] + data[i + 1] + data[i + 2];
            if (data[i] + data[i + 1] + data[i + 2] > 0) lit++;
          }
          return { size: [image.naturalWidth, image.naturalHeight], sum, lit };
        }),
      ),
    images,
  );

async function unitRow(page, name) {
  await page.fill('#unit-search', name);
  const row = page.locator('#units li', { has: page.locator('.name', { hasText: new RegExp(`^${name}$`, 'i') }) }).first();
  await expect(row).toBeVisible();
  return row;
}

test('the window is hidden at first; a double-click on a unit of the gallery opens it with that unit\'s textures', async ({ page }) => {
  const errors = await open(page);
  await expect(page.locator('#texture-window')).toBeHidden();
  expect(await win(page)).toMatchObject({ open: false, user: null });
  const row = await unitRow(page, 'Marine');
  // Negative: one click previews the unit and opens nothing.
  await row.click();
  await expect(page.locator('#preview .name')).toHaveText('Marine');
  await expect(page.locator('#texture-window')).toBeHidden();

  await row.dblclick();
  await expect(page.locator('#texture-window')).toBeVisible();
  await expect(page.locator('#texture-window .window-title')).toContainText('Marine');
  expect(await win(page)).toMatchObject({ open: true, user: 'Marine' });
  const shown = await inside(page, 'Marine');
  expect(shown.embed).toBe(true);
  expect(shown.current.users).toEqual(['Marine']);
  // Only the unit's textures are listed: the two with an HD version, then
  // the other textures of its model, the original alone.
  console.log(`Marine: hd ${shown.hd.map((e) => e.id)}; original only ${shown.only.map((e) => e.id)}; problems ${shown.problems}`);
  expect(shown.hd.map((entry) => entry.texture)).toEqual(['marine_remastered_diff.dds', 'marine_normal.dds']);
  expect(shown.only.length).toBeGreaterThan(0);
  expect(shown.only.map((entry) => entry.texture)).toContain('marine_remastered_norm.dds');
  // Negative: a texture with an HD entry is not listed again as an original.
  expect(shown.only.map((entry) => entry.texture)).not.toContain('marine_remastered_diff.dds');
  for (const entry of shown.only) expect(entry.category).toBe('Original only');
  expect(shown.problems).toEqual([]);
  await expect(textureFrame(page).locator('#list .row')).toHaveCount(shown.entries.length);
  // A row with an upscaled side starts its second line with an HD badge; the others have none.
  const rows = await textureFrame(page).locator('#list .row').evaluateAll((list) =>
    list.map((row) => ({ name: row.querySelector('.name').textContent, badge: row.querySelectorAll('.badge').length, first: row.querySelector('.meta').firstChild.textContent, meta: row.querySelector('.meta').textContent })),
  );
  expect(rows.filter((row) => row.badge).map((row) => row.name)).toEqual(shown.hd.map((entry) => entry.texture));
  for (const row of rows.filter((item) => item.badge)) expect(row.first).toBe('HD');
  for (const row of rows.filter((item) => !item.badge)) expect(row.meta).not.toContain('HD');
  expect(rows.filter((row) => !row.badge).length).toBe(shown.only.length);
  // The category chips offer what the unit has; the others (Terrain, Doodads) are left out.
  expect(await textureFrame(page).locator('#categories .chip').evaluateAll((chips) => chips.map((chip) => chip.dataset.value))).toEqual(['', 'Marine', 'Original only']);
  // The double-click adds nothing to the scene (the "add to scene" button and a drag do).
  expect((await state(page)).items).toEqual([]);
  expect(errors).toEqual([]);
});

test('a double-click on a doodad of the gallery opens the window with the doodad\'s textures', async ({ page }) => {
  const errors = await open(page);
  await page.click('#tab-doodads');
  await page.fill('#doodad-search', 'zerus tree');
  const row = page.locator('#doodads li[data-id="ZerusTree"]');
  await expect(row).toBeVisible();
  await row.dblclick();
  await expect(page.locator('#texture-window')).toBeVisible();
  const shown = await inside(page, 'ZerusTree');
  expect(shown.hd.map((entry) => entry.texture)).toEqual(['zerustree_diffuse.dds']);
  expect(shown.current.texture).toBe('zerustree_diffuse.dds');
  expect(shown.only.length).toBeGreaterThan(0);
  expect((await state(page)).items).toEqual([]);
  expect(errors).toEqual([]);
});

test('a double-click on an instance, in its row or in the view, opens the window; on the ground it does not', async ({ page }) => {
  const errors = await open(page);
  const marine = await page.evaluate(() => window.sc2viewer.addUnit('Marine', { x: 0, y: 0, pick: 0.5 }));
  // The tree is large: far off, so it is not under the mouse at the marine.
  const tree = await page.evaluate(() => window.sc2viewer.addDoodad('ZerusTree', { x: 60, y: 0, pick: 0.5 }));
  await idle(page);
  await page.evaluate((v) => window.sc2viewer.view(v), VIEW);

  // Negative: one click on the row selects and opens nothing.
  await page.locator(`#scene li[data-id="${tree}"] .head .name`).click();
  expect((await state(page)).pick.selection).toEqual([tree]);
  await expect(page.locator('#texture-window')).toBeHidden();
  await page.locator(`#scene li[data-id="${tree}"] .head .name`).dblclick();
  await expect(page.locator('#texture-window')).toBeVisible();
  expect((await inside(page, 'ZerusTree')).hd.length).toBe(1);

  await page.click('#texture-window .window-close');
  await expect(page.locator('#texture-window')).toBeHidden();
  expect((await win(page)).open).toBe(false);

  // Negative: a double-click on the empty ground opens nothing.
  const ground = await page.evaluate(() => window.sc2viewer.screenOf([3, -3, 0]));
  await page.mouse.dblclick(ground[0], ground[1]);
  await expect(page.locator('#texture-window')).toBeHidden();

  const at = await onItem(page, marine);
  await page.mouse.dblclick(at[0], at[1]);
  await expect(page.locator('#texture-window')).toBeVisible();
  expect((await inside(page, 'Marine')).hd.length).toBe(2);
  // Both instances are still there, where they were.
  const items = (await state(page)).items;
  expect(items.map((i) => [i.id, i.x, i.y])).toEqual([[marine, 0, 0], [tree, 60, 0]]);
  expect(errors).toEqual([]);
});

test('a unit with no HD texture shows its original textures, decoded; so does a bare model file', async ({ page }) => {
  // Three window opens, each decoding a model's textures: 4 s alone, over 20 s beside 3 other workers.
  test.setTimeout(60_000);
  const errors = await open(page);
  const row = await unitRow(page, 'Zergling');
  await row.dblclick();
  await expect(page.locator('#texture-window')).toBeVisible();
  const shown = await inside(page, 'Zergling');
  console.log(`Zergling: ${shown.only.map((e) => `${e.id} ${e.size.join('x')}`).join(', ')}; problems ${shown.problems}`);
  // Negative: nothing of it has an upscaled side, and no other unit's texture is listed.
  expect(shown.hd).toEqual([]);
  expect(shown.only.length).toBeGreaterThan(0);
  expect(shown.only.some((entry) => entry.plane === 'color')).toBe(true);
  expect(shown.current.users).toEqual(['Zergling']);
  await expect(textureFrame(page).locator('#empty')).toHaveCount(0);
  // Every image is a real picture of the stated size, and not a black one.
  const images = await measured(page, shown.only.map((entry) => entry.image));
  shown.only.forEach((entry, i) => {
    expect(images[i].size, entry.id).toEqual(entry.size);
    expect(Math.min(...entry.size), entry.id).toBeGreaterThanOrEqual(4);
  });
  for (const [i, entry] of shown.only.entries()) if (entry.plane === 'color' && /diffuse/.test(entry.texture)) expect(images[i].lit, entry.id).toBeGreaterThan(images[i].size[0] * images[i].size[1] * 0.1);
  expect(shown.only.some((entry) => /diffuse/.test(entry.texture))).toBe(true);
  // The view shows the original alone: no layer, no line.
  await expect(textureFrame(page).locator('#view .divider')).toHaveCount(0);
  // The "used by" chip drops the filter: the four entries of the page and the unit's own.
  await textureFrame(page).locator('#user-clear').click();
  await expect.poll(() => textureFrame(page).evaluate(() => window.hdtex.state().visible)).toBe(4 + shown.only.length);
  await page.keyboard.press('Escape');
  await expect(page.locator('#texture-window')).toBeHidden();

  // A model file added by path is no unit: it goes by its file name.
  const path = (await (await page.request.get('/api/unit?id=Zergling')).json()).file;
  const id = await page.evaluate((p) => window.sc2viewer.add(p), path);
  await idle(page);
  await page.locator(`#scene li[data-id="${id}"] .head .name`).dblclick();
  await expect(page.locator('#texture-window')).toBeVisible();
  const bare = await inside(page, path.split('\\').pop());
  expect(bare.only.map((entry) => entry.id)).toEqual(shown.only.map((entry) => entry.id));

  // A texture with an HD entry that does not name this user is still the
  // model's: it is listed, with its upscaled side (the page names Marine alone).
  const marinePath = (await (await page.request.get('/api/unit?id=Marine')).json()).file;
  const marine = await page.evaluate((p) => window.sc2viewer.add(p), marinePath);
  await idle(page);
  await page.locator(`#scene li[data-id="${marine}"] .head .name`).dblclick();
  const shared = await inside(page, marinePath.split('\\').pop());
  expect(shared.hd.map((entry) => entry.texture)).toEqual(['marine_remastered_diff.dds']);
  expect(shared.only.map((entry) => entry.texture)).not.toContain('marine_remastered_diff.dds');
  expect(errors).toEqual([]);
});

test('the originals are the instance\'s dataset\'s: the fixture\'s Marine skin differs from the stock one, its other textures do not', async ({ page }) => {
  const errors = await open(page);
  const read = async (dataset) => {
    const id = await page.evaluate((d) => window.sc2viewer.addUnit('Marine', { x: 0, y: 0, pick: 0.5, dataset: d }), dataset);
    await idle(page);
    await page.locator(`#scene li[data-id="${id}"] .head .name`).dblclick();
    await expect.poll(async () => (await win(page)).dataset).toBe(dataset);
    const shown = await inside(page, 'Marine');
    const images = await measured(page, shown.only.map((entry) => entry.image));
    await page.evaluate((i) => window.sc2viewer.remove(i), id);
    return new Map(shown.only.map((entry, i) => [entry.id, images[i].sum]));
  };
  const stock = await read('stock');
  const fixture = await read('fx');
  console.log(`stock ${JSON.stringify([...stock])}; fx ${JSON.stringify([...fixture])}`);
  expect([...fixture.keys()]).toEqual([...stock.keys()]);
  // The fixture's map layer replaces this one file (scripts/test-fixture.sh).
  const skin = 'marine_diffuse_blood.color';
  expect(stock.has(skin)).toBe(true);
  expect(fixture.get(skin)).not.toBe(stock.get(skin));
  // Negative: every other texture is the same picture in both.
  for (const [key, sum] of stock) if (!key.startsWith('marine_diffuse_blood.')) expect(fixture.get(key), key).toBe(sum);
  expect(errors).toEqual([]);
});

test('the window moves by its title bar, stays inside the page, and closes', async ({ page }) => {
  const errors = await open(page);
  await (await unitRow(page, 'Marine')).dblclick();
  await expect(page.locator('#texture-window')).toBeVisible();
  await inside(page, 'Marine');
  const before = await page.locator('#texture-window').boundingBox();
  // It opens clear of the side panel.
  const side = await page.locator('#side').boundingBox();
  expect(before.x).toBeGreaterThanOrEqual(side.x + side.width);

  const grab = [before.x + 80, before.y + 12];
  await page.mouse.move(grab[0], grab[1]);
  await page.mouse.down();
  await page.mouse.move(grab[0] - 60, grab[1] + 40, { steps: 6 });
  await page.mouse.up();
  const moved = await page.locator('#texture-window').boundingBox();
  expect(moved.x - before.x).toBeCloseTo(-60, 0);
  expect(moved.y - before.y).toBeCloseTo(40, 0);
  expect([moved.width, moved.height]).toEqual([before.width, before.height]);
  // Negative: the drag did not reload or change the texture viewer.
  expect((await inside(page, 'Marine')).hd.length).toBe(2);

  // A fit asked for while the window is closed (the view has no size then)
  // is done when it opens again: the texture is not left 0 pixels wide.
  const fitted = (await inside(page, 'Marine')).size;
  expect(fitted).toBeGreaterThan(50);
  await page.click('#texture-window .window-close');
  await textureFrame(page).evaluate(() => document.getElementById('fit').click());
  await (await unitRow(page, 'Marine')).dblclick();
  await expect(page.locator('#texture-window')).toBeVisible();
  await expect.poll(() => textureFrame(page).evaluate(() => window.hdtex.state().size)).toBeCloseTo(fitted, 0);

  // Dragged far past the corner, the title bar stays reachable.
  await page.mouse.move(grab[0] - 60, grab[1] + 40);
  await page.mouse.down();
  await page.mouse.move(-500, -500, { steps: 4 });
  await page.mouse.up();
  const pinned = await page.locator('#texture-window').boundingBox();
  expect(pinned.y).toBeGreaterThanOrEqual(0);
  expect(pinned.x + pinned.width).toBeGreaterThanOrEqual(80);

  await page.click('#texture-window .window-close');
  await expect(page.locator('#texture-window')).toBeHidden();
  expect(errors).toEqual([]);
});

test('the model viewer and the texture viewer share one theme', async ({ page }) => {
  const errors = await open(page);
  const read = (names) => names.map((name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim());
  const mine = await page.evaluate(read, TOKENS);
  for (const value of mine) expect(value).not.toBe('');
  await page.goto('/textures/');
  await page.waitForFunction(() => Boolean(window.hdtex));
  expect(await page.evaluate(read, TOKENS)).toEqual(mine);
  // Stand-alone, the page shows every entry and is not in its embedded layout.
  expect(await page.evaluate(() => window.hdtex.state())).toMatchObject({ user: '', visible: 4, total: 4, embed: false });
  expect(await page.locator('#categories .chip').evaluateAll((chips) => chips.map((chip) => chip.dataset.value))).toEqual(['', 'Terrain', 'Marine', 'Doodads']);
  await expect(page.locator('#user-filter')).toBeHidden();
  expect(errors).toEqual([]);
});

test('the server serves the texture viewer and its images, and nothing outside its folder', async ({ request }) => {
  const page = await request.get('/textures/');
  expect(page.status()).toBe(200);
  expect(page.headers()['content-type']).toContain('text/html');
  expect(await page.text()).toContain('const PAIRS = [{');
  const image = await request.get('/textures/img/original.png');
  expect(image.status()).toBe(200);
  expect(image.headers()['content-type']).toBe('image/png');
  expect(await (await request.get('/api/textures')).json()).toMatchObject({ built: true });
  // Negative: no file, another type, or a path out of the folder.
  for (const path of ['/textures/img/none.png', '/textures/index.js', '/textures/..%2Fpackage.json', '/textures/%2e%2e/server.mjs', '/textures/..%2F..%2Fwebviewer%2Fpublic%2Findex.html']) {
    expect((await request.get(path)).status(), path).toBe(404);
  }
});

import { test, expect } from '@playwright/test';

// The left column (src/page/ui/drawers.ts, status.ts setStatus, instances.ts filterList):
// - status messages are a toast at the top centre of the view, not a line
//   in the gallery; they go away by themselves;
// - the instances panel has a search that hides the rows that do not match;
// - each panel is a drawer: its tab slides it out to the left and back.

const VIEW = { yaw: -Math.PI / 2, pitch: 0.5, distance: 9, target: [0, 0, 0.8] };

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

async function place(page, units) {
  const ids = [];
  for (const [id, x, y] of units) ids.push(await page.evaluate(([u, ux, uy]) => window.sc2viewer.addUnit(u, { x: ux, y: uy, pick: 0.5 }), [id, x, y]));
  await page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 15_000 });
  await page.evaluate((v) => window.sc2viewer.view(v), VIEW);
  return ids;
}

const status = (page) => page.evaluate(() => window.SC2App.statusState());
const visible = (page) => page.evaluate(() => window.SC2App.visibleRect());
const shownRows = (page) => page.locator('#scene li:not([hidden])').evaluateAll((rows) => rows.map((r) => Number(r.dataset.id)));
const selectRow = (page, id) => page.locator(`#scene li[data-id="${id}"] .head .name`).click();

/** Wait until no slide runs: the drawers, their tabs and the toast are where they stop. */
const settled = (page) =>
  page.waitForFunction(() => ['panel', 'instances', 'panel-tab', 'instances-tab', 'status'].every((id) => document.getElementById(id).getAnimations().length === 0));

/** The toast's centre is the visible view's centre, and it sits at the top. */
async function expectCentred(page) {
  const box = await page.locator('#status').boundingBox();
  const view = await visible(page);
  expect(Math.abs(box.x + box.width / 2 - (view.left + view.right) / 2)).toBeLessThanOrEqual(2);
  expect(box.y).toBeGreaterThanOrEqual(0);
  expect(box.y).toBeLessThanOrEqual(30);
}

test('a status message shows at the top centre of the view, not in the gallery, and goes away by itself', async ({ page }) => {
  test.setTimeout(40_000);
  const errors = await open(page);
  const [marine] = await place(page, [['Marine', 0, 0]]);
  // The add said "loading Marine"; with the add done, the toast goes down after that
  // message's minimum 0.1 s. Negative: nothing in the gallery either way.
  expect((await page.evaluate(() => window.SC2App.statusLog())).shown).toEqual(['loading Marine']);
  await expect.poll(async () => (await status(page)).up, { timeout: 6000 }).toBe(false);
  // It went down as a finished message (at least 0.1 s, as long as the add took),
  // not after a message's full 5 s. Timed in the page, so a slow test run does not count.
  const done = await page.evaluate(() => window.SC2App.statusLog());
  console.log('loading message up ms', done.lastUpMs);
  expect(done.shown).toEqual(['loading Marine']);
  expect(done.lastUpMs).toBeGreaterThanOrEqual(100);
  expect(done.lastUpMs).toBeLessThan(4500);
  await expect(page.locator('#status')).toBeHidden();
  await expect(page.locator('#panel #status, #side #status')).toHaveCount(0);

  await selectRow(page, marine);
  const pressed = Date.now();
  await page.keyboard.press('Control+l');
  await expect(page.locator('#status')).toBeVisible();
  await expect(page.locator('#status')).toHaveText('loop on');
  await settled(page);
  await expectCentred(page);
  const s = await status(page);
  expect(s).toEqual({ text: 'loop on', up: true, failure: false });
  // It is not over a panel.
  const box = await page.locator('#status').boundingBox();
  expect(box.x).toBeGreaterThanOrEqual((await visible(page)).left);

  // It goes away by itself after 5 s: not before 4.5 s, by 6.5 s.
  await expect.poll(async () => (await status(page)).up, { timeout: 7000, intervals: [100] }).toBe(false);
  const lasted = Date.now() - pressed;
  console.log('toast lasted ms', lasted);
  expect(lasted).toBeGreaterThanOrEqual(4500);
  expect(lasted).toBeLessThanOrEqual(6500);
  await expect(page.locator('#status')).toBeHidden();
  expect(errors).toEqual([]);
});

test('a failure shows as a failure; it re-centres when a drawer closes; a click opens the message log and takes the toast down', async ({ page }) => {
  const errors = await open(page);
  // The add must fail: its error message is read, and a success is a test failure.
  const failure = await page.evaluate(() => window.sc2viewer.add('nope.m3').then(() => 'added', (error) => `failed: ${error.message}`));
  console.log('add nope.m3:', failure);
  expect(failure).toMatch(/^failed: /);
  // "loading nope.m3" shows first, its minimum 0.1 s; then the failure replaces it.
  await expect.poll(async () => (await status(page)).failure, { timeout: 3000 }).toBe(true);
  expect((await status(page)).up).toBe(true);
  await expect(page.locator('#status')).toContainText('nope.m3');
  // Closing the gallery and the instances moves it to the canvas centre.
  await page.locator('#panel-tab').click();
  await page.locator('#instances-tab').click();
  await settled(page);
  expect((await visible(page)).left).toBe(0);
  await expectCentred(page);
  // A click opens the log and takes the toast down at once.
  await page.locator('#status').click();
  expect((await status(page)).up).toBe(false);
  const log = page.locator('#status-log-dialog');
  await expect(log).toBeVisible();
  // "loading nope.m3", then the failures (the renderer's fetch error and the add's).
  const rows = await log.locator('li').evaluateAll((list) => list.map((li) => ({ text: li.querySelector('.text').textContent, failure: li.classList.contains('failure') })));
  console.log('log rows', JSON.stringify(rows));
  expect(rows[0]).toEqual({ text: 'loading nope.m3', failure: false });
  expect(rows.length).toBeGreaterThanOrEqual(2);
  for (const row of rows.slice(1)) {
    expect(row.failure).toBe(true);
    expect(row.text).toContain('nope.m3');
  }
  await page.keyboard.press('Escape');
  await expect(log).toBeHidden();
  // The failure was logged by the viewer and the browser's 404 (both expected here); nothing else.
  expect(errors.filter((e) => !e.includes('nope.m3') && !e.includes('status of 404 (Not Found)'))).toEqual([]);
});

test('messages in a row replace each other with the toast up; each shows at least 0.1 s', async ({ page }) => {
  const errors = await open(page);
  // Watch the toast in the page: every text change and every "up" change, with the time.
  await page.evaluate(() => {
    const node = document.getElementById('status');
    window.__toastTrace = [];
    const note = () => window.__toastTrace.push({ t: performance.now(), text: node.querySelector('.text').textContent, up: node.classList.contains('up') });
    new MutationObserver(note).observe(node, { attributes: true, attributeFilter: ['class'], childList: true, subtree: true, characterData: true });
  });
  // Three messages at once, then an empty text (as an add does), then a fourth.
  await page.evaluate(() => {
    window.SC2App.setStatus('one');
    window.SC2App.setStatus('two');
    window.SC2App.setStatus('three', { failure: true });
    window.SC2App.setStatus('');
    window.SC2App.setStatus('four');
  });
  await expect.poll(() => page.evaluate(() => window.SC2App.statusLog().shown.length), { timeout: 8000 }).toBe(4);
  expect((await page.evaluate(() => window.SC2App.statusLog())).shown).toEqual(['one', 'two', 'three', 'four']);
  const trace = await page.evaluate(() => window.__toastTrace);
  // The toast went up once and did not go down between the messages.
  const ups = trace.filter((e, i) => i > 0 && e.up !== trace[i - 1].up);
  console.log('trace', JSON.stringify(trace.map((e) => [Math.round(e.t - trace[0].t), e.text, e.up])));
  expect(trace.filter((e) => !e.up && e.text === 'four')).toEqual([]);
  expect(ups.every((e) => e.up)).toBe(true);
  // Each text stayed at least 0.1 s (a little less for timer rounding) before the next,
  // and not the old 1 s: the ones waiting move on at the minimum.
  const firsts = ['one', 'two', 'three', 'four'].map((text) => trace.find((e) => e.text === text).t);
  for (let i = 1; i < firsts.length; i++) {
    expect(firsts[i] - firsts[i - 1], `${i}`).toBeGreaterThanOrEqual(90);
    expect(firsts[i] - firsts[i - 1], `${i}`).toBeLessThan(900);
  }
  // The failure kept its look only while it was shown.
  expect((await status(page)).failure).toBe(false);
  // Negative: a lone empty text with the toast down does nothing.
  await page.locator('#status').click();
  await page.keyboard.press('Escape');
  await page.evaluate(() => window.SC2App.setStatus(''));
  await page.waitForTimeout(300);
  expect((await status(page)).up).toBe(false);
  expect((await page.evaluate(() => window.SC2App.statusLog())).shown).toHaveLength(4);
  expect(errors).toEqual([]);
});

test('the message log holds every message, in order, with its time and failure mark, and grows while open', async ({ page }) => {
  const errors = await open(page);
  const log = page.locator('#status-log-dialog');
  // Negative: nothing opens it but a click on the toast.
  await expect(log).toBeHidden();
  const before = await page.locator('#status-log-dialog li').count();
  await page.evaluate(() => {
    window.SC2App.setStatus('alpha');
    window.SC2App.setStatus('beta', { failure: true });
    window.SC2App.setStatus('gamma');
  });
  await page.locator('#status').click();
  await expect(log).toBeVisible();
  const rows = log.locator('li');
  // Every message, also the ones still waiting when the toast was clicked.
  await expect(rows).toHaveCount(before + 3);
  const texts = await rows.locator('.text').allTextContents();
  expect(texts.slice(-3)).toEqual(['alpha', 'beta', 'gamma']);
  expect(await rows.evaluateAll((list) => list.slice(-3).map((li) => li.classList.contains('failure')))).toEqual([false, true, false]);
  // Each row has a clock time.
  for (const time of (await rows.locator('time').allTextContents()).slice(-3)) expect(time).toMatch(/^\d\d:\d\d:\d\d\.\d$/);
  // A message while the log is open joins it at the end.
  await page.evaluate(() => window.SC2App.setStatus('delta'));
  await expect(rows).toHaveCount(before + 4);
  await expect(rows.last().locator('.text')).toHaveText('delta');
  // The close button closes it; the history stays for the next look.
  await log.locator('.dialog-close').click();
  await expect(log).toBeHidden();
  await page.evaluate(() => window.SC2App.setStatus('epsilon'));
  await page.locator('#status').click();
  await expect(rows).toHaveCount(before + 5);
  await page.keyboard.press('Escape');
  expect(errors).toEqual([]);
});

test('a page bundle that does not load is reported as a failure, naming the file', async ({ page }) => {
  const problems = [];
  page.on('console', (m) => {
    if (m.type() === 'error') problems.push(m.text());
  });
  // The drawer tabs once died this way: a server that did not serve a page script.
  await page.route('**/vendor/renderer.js', (route) => route.fulfill({ status: 404, body: 'not found' }));
  await page.goto('/');
  const failure = page.locator('#load-failure');
  await expect(failure).toBeVisible({ timeout: 10_000 });
  const shown = await failure.textContent();
  console.log('reported', JSON.stringify(shown), JSON.stringify(problems));
  expect(shown).toMatch(/did not load: \/vendor\/renderer\.js/);
  expect(problems.some((p) => p.includes('did not load') && p.includes('/vendor/renderer.js'))).toBe(true);
  expect(await page.evaluate(() => typeof window.sc2viewer)).toBe('undefined');
  // Negative: a normal load reports nothing and hides the line.
  await page.unroute('**/vendor/renderer.js');
  problems.length = 0;
  await page.reload();
  await expect.poll(() => page.evaluate(() => Boolean(window.sc2viewer && window.sc2viewer.ready)), { timeout: 10_000 }).toBe(true);
  await expect(failure).toBeHidden();
  expect(problems.filter((p) => p.includes('did not load'))).toEqual([]);
});

test('the instance search hides the rows that do not match, and only the rows', async ({ page }) => {
  const errors = await open(page);
  const [marine, zealot, zergling] = await place(page, [['Marine', 0, 0], ['Zealot', 2, 0], ['Zergling', -2, 0]]);
  await expect(page.locator('#instances #instance-search')).toHaveCount(1);
  await expect(page.locator('#instance-count')).toHaveText('(3)');
  await selectRow(page, marine);

  // By name.
  await page.locator('#instance-search').fill('zeal');
  expect(await shownRows(page)).toEqual([zealot]);
  await expect(page.locator('#instance-count')).toHaveText('(1 of 3)');
  // By id, any case.
  await page.locator('#instance-search').fill('ZERGLING');
  expect(await shownRows(page)).toEqual([zergling]);
  // By model file.
  await page.locator('#instance-search').fill('.m3');
  expect(await shownRows(page)).toEqual([marine, zealot, zergling]);
  // A new instance follows the search.
  await page.locator('#instance-search').fill('zeal');
  const second = await page.evaluate(() => window.sc2viewer.addUnit('Marine', { x: 0, y: 2, pick: 0.5 }));
  await page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 15_000 });
  expect(await shownRows(page)).toEqual([zealot]);
  await expect(page.locator('#instance-count')).toHaveText('(1 of 4)');

  // Negative: no match hides every row, and nothing else changes.
  await page.locator('#instance-search').fill('no such unit');
  expect(await shownRows(page)).toEqual([]);
  await expect(page.locator('#instance-count')).toHaveText('(0 of 4)');
  const s = await page.evaluate(() => window.sc2viewer.state());
  expect(s.items.map((i) => i.id)).toEqual([marine, zealot, zergling, second]);
  expect(s.pick.selection).toEqual([marine]);

  // Cleared: all rows again.
  await page.locator('#instance-search').fill('');
  expect(await shownRows(page)).toEqual([marine, zealot, zergling, second]);
  await expect(page.locator('#instance-count')).toHaveText('(4)');
  expect(errors).toEqual([]);
});

test('each panel is a drawer: its tab slides it out to the left and back; the choice is kept', async ({ page }) => {
  const errors = await open(page);
  const box = (id) => page.locator(id).boundingBox();
  const open0 = { gallery: await box('#panel'), instances: await box('#instances') };
  expect(open0.gallery.x).toBe(0);
  expect(open0.instances.x).toBe(0);
  expect((await visible(page)).left).toBe(open0.gallery.width);

  // The gallery out; the instances stay.
  await page.locator('#panel-tab').click();
  await settled(page);
  const g = await box('#panel');
  expect(g.x + g.width).toBeLessThanOrEqual(0);
  expect((await box('#instances')).x).toBe(0);
  expect((await box('#panel-tab')).x).toBe(0);
  expect(await page.evaluate(() => window.SC2App.drawerState())).toEqual({ panel: false, instances: true });
  // A closed panel takes no keys.
  expect(await page.evaluate(() => {
    const input = document.getElementById('unit-search');
    input.focus();
    return document.activeElement === input;
  })).toBe(false);
  // The view still counts the open instances panel as covered.
  expect((await visible(page)).left).toBe(open0.instances.width);

  // The instances out too: the whole view is free.
  await page.locator('#instances-tab').click();
  await settled(page);
  expect((await visible(page)).left).toBe(0);

  // Kept over a reload.
  await page.reload();
  await expect.poll(() => page.evaluate(() => Boolean(window.sc2viewer && window.sc2viewer.ready))).toBe(true);
  expect(await page.evaluate(() => window.SC2App.drawerState())).toEqual({ panel: false, instances: false });
  expect((await visible(page)).left).toBe(0);

  // Back in.
  await page.locator('#panel-tab').click();
  await page.locator('#instances-tab').click();
  await settled(page);
  expect(await box('#panel')).toEqual(open0.gallery);
  expect(await box('#instances')).toEqual(open0.instances);
  expect(await page.evaluate(() => {
    const input = document.getElementById('unit-search');
    input.focus();
    return document.activeElement === input;
  })).toBe(true);
  expect(errors).toEqual([]);
});

test('with the drawers closed, a unit where the panels were is under the mouse; with them open it is not', async ({ page }) => {
  const errors = await open(page);
  const [marine] = await place(page, [['Marine', 0, 0]]);
  // Move the camera so that the marine stands where the panels are.
  let at = null;
  for (const tx of [2, 3, 4, 5, 6, 7]) {
    await page.evaluate((x) => window.sc2viewer.view({ ...window.sc2viewer.state().camera, target: [x, 0, 0.8] }), tx);
    await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))));
    const p = await page.evaluate((id) => window.sc2viewer.itemScreen(id, 0), marine);
    if (p && p[0] > 60 && p[0] < 260) break;
  }
  // Negative: drawers open, the mouse there is on a panel, not on the unit.
  at = await page.evaluate((id) => window.sc2viewer.itemPixel(id), marine);
  expect(at, 'a marine pixel under the panels').toBeTruthy();
  expect(at[0]).toBeLessThan(300);
  await page.mouse.move(at[0], at[1]);
  await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))));
  expect(await page.evaluate(([x, y]) => document.elementFromPoint(x, y).closest('#side') !== null, at)).toBe(true);
  // Closed: the same point reaches the view and hovers the unit.
  await page.locator('#panel-tab').click();
  await page.locator('#instances-tab').click();
  await settled(page);
  const now = await page.evaluate((id) => window.sc2viewer.itemPixel(id), marine);
  expect(await page.evaluate(([x, y]) => document.elementFromPoint(x, y).id, now)).toBe('view');
  await page.mouse.move(now[0], now[1]);
  await expect.poll(() => page.evaluate(() => window.sc2viewer.state().pick.hovered)).toBe(marine);
  expect(errors).toEqual([]);
});

import { test, expect } from '../fixtures.mjs';
import { frames, idle, open, state } from '../page.mjs';

// While a unit is dragged over the view, its model stands on the ground
// under the mouse. It goes when the drag leaves, ends or drops.

const ground = (page, x, y) => page.evaluate(([x, y]) => window.scobaeditor.groundUnder(x, y), [x, y]);
const row = (page, id) => page.locator(`#units li[data-id="${id}"]`);

/** Press on a unit row and drag the pointer to canvas point (x, y). */
async function dragOver(page, id, x, y) {
  await page.fill('#search-units', id.toLowerCase());
  await expect(row(page, id)).toBeVisible();
  await row(page, id).hover();
  await page.mouse.down();
  const box = await page.locator('canvas#view').boundingBox();
  await page.mouse.move(box.x + x, box.y + y, { steps: 8 });
  await idle(page);
  await page.mouse.move(box.x + x + 1, box.y + y, { steps: 2 }); // one more dragover once loaded
  return box;
}

test('dragging a unit over the view shows its model at the ground point under the mouse', async ({ page }) => {
  await open(page);
  const box = await dragOver(page, 'Marine', 700, 450);
  let s = await state(page);
  const expected = await ground(page, 701, 450);
  console.log('dragPreview', JSON.stringify(s.dragPreview), 'expected', JSON.stringify(expected));
  expect(s.dragPreview).toMatchObject({ unit: 'Marine', shown: true });
  expect(s.dragPreview.location[0]).toBeCloseTo(expected[0], 2);
  expect(s.dragPreview.location[1]).toBeCloseTo(expected[1], 2);
  // Negative: the preview is not a scene item.
  expect(s.items).toEqual([]);

  // It follows the mouse.
  await page.mouse.move(box.x + 850, box.y + 380, { steps: 4 });
  s = await state(page);
  const next = await ground(page, 850, 380);
  expect(s.dragPreview.location[0]).toBeCloseTo(next[0], 2);
  expect(s.dragPreview.location[1]).toBeCloseTo(next[1], 2);

  // Drop: the unit lands where the preview stood; the preview is gone.
  await page.mouse.up();
  await idle(page);
  s = await state(page);
  expect(s.dragPreview).toBe(null);
  expect(s.items).toHaveLength(1);
  expect(s.items[0].x).toBeCloseTo(next[0], 2);
  expect(s.items[0].y).toBeCloseTo(next[1], 2);
  expect(s.sceneInstances).toBe(1);
});

test('dragging off the view hides the preview; releasing outside adds nothing', async ({ page }) => {
  await open(page);
  await dragOver(page, 'Marine', 700, 450);
  expect((await state(page)).dragPreview).toMatchObject({ shown: true });
  // Back over the panel.
  await page.mouse.move(150, 300, { steps: 6 });
  expect((await state(page)).dragPreview).toMatchObject({ shown: false });
  await page.mouse.up();
  await frames(page);
  await idle(page);
  const s = await state(page);
  expect(s.dragPreview).toBe(null);
  expect(s.items).toEqual([]);
  expect(s.sceneInstances).toBe(0);
});

test('above the horizon there is no ground, so no preview', async ({ page }) => {
  await open(page);
  // Look nearly level: the top rows show sky.
  await page.evaluate(() => window.scobaeditor.view({ pitch: 0.1 }));
  await dragOver(page, 'Marine', 700, 5);
  expect(await ground(page, 701, 5)).toBe(null);
  expect((await state(page)).dragPreview).toMatchObject({ shown: false });
  await page.mouse.up();
});

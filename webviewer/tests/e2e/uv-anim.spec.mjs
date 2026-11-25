import { test, expect } from '../fixtures.mjs';
import { frames, idle, open } from '../page.mjs';

// Layer UV transform (gap G1): offset, angle and tiling, animated by the
// sequence. Rule (WhiteoutFlakes M3ComposeUvTransform, citing the SC2
// client): uv' = 0.5 + S(tiling) * R(angle.z) * (uv - 0.5 - offset).
// Survey: scripts/uv-anim-survey.sh. How the moving texture looks is an
// operator check (SPEC-VIEWER 14); these tests read the uploaded transforms.

const lastItem = async (page) => (await page.evaluate(() => window.sc2viewer.state())).items.at(-1);

/**
 * Two snapshots of the unit: after its first draws, and once its engine
 * frame has moved `ms` on (game time, a loop counts as moved).
 */
async function sample(page, id, ms) {
  await page.evaluate((u) => window.sc2viewer.addUnit(u, { x: 0, y: 0 }), id);
  await idle(page);
  await frames(page);
  await page.waitForFunction(() => window.sc2viewer.state().items.at(-1).uvLayers.some((l) => l.binds > 0));
  const a = await lastItem(page);
  await page.waitForFunction(([f, step]) => {
    const now = window.sc2viewer.state().items.at(-1).frame;
    return now < f || now - f >= step;
  }, [a.frame, ms]);
  await frames(page);
  const b = await lastItem(page);
  return { a, b };
}

/** The rule, applied to one point from the inputs: [u', v']. */
function apply(inputs, u, v) {
  const [ox, oy, , , az, tx, ty] = inputs;
  const du = u - 0.5 - ox;
  const dv = v - 0.5 - oy;
  const c = Math.cos(az);
  const s = Math.sin(az);
  return [0.5 + tx * (c * du - s * dv), 0.5 + ty * (s * du + c * dv)];
}

/** The uploaded rows must map three points as the rule maps them. */
function expectRule(layer) {
  const t = layer.transform;
  for (const x of [...layer.inputs, ...t]) expect(Number.isFinite(x), `${layer.material}/${layer.type} finite`).toBe(true);
  for (const [u, v] of [[0, 0], [1, 0], [0.3, 0.8]]) {
    const [eu, ev] = apply(layer.inputs, u, v);
    expect(t[0] * u + t[1] * v + t[2]).toBeCloseTo(eu, 4);
    expect(t[3] * u + t[4] * v + t[5]).toBeCloseTo(ev, 4);
  }
}

const show = (layers) => layers.map((l) => `${l.material}/${l.type} driven=${l.driven} binds=${l.binds} inputs [${l.inputs.map((x) => x.toFixed(4))}] rows [${l.transform.map((x) => x.toFixed(4))}]`).join('\n');

// Keys (scripts/uv-anim-survey.sh UNIT): the billboard's Standard_16 offset
// u scrolls in Stand; the Nexus Standard_17f;222 angle z runs 0 to -0.36
// over Stand's 5333 ms. Both materials are drawn by mesh batches.
for (const [id, material, type, axis, name] of [
  ['DestructibleBillboardScrollingText', 'Standard_16', 'diffuse', 0, 'offset'],
  ['Nexus', 'Standard_17f;222', 'diffuse', 4, 'angle'],
]) {
  test(`${id}: the ${name} track moves the ${material} ${type} texture over time`, async ({ page }) => {
    const errors = await open(page);
    const { a, b } = await sample(page, id, 600);
    console.log(`${id} sequence ${b.sequenceName} frame ${a.frame} -> ${b.frame}\n${show(a.uvLayers)}\n--\n${show(b.uvLayers)}`);
    expect(b.loaded).toBe(true);
    expect(b.drawn).toBe(true);
    const la = a.uvLayers.find((l) => l.material === material && l.type === type);
    const lb = b.uvLayers.find((l) => l.material === material && l.type === type);
    expect(lb, `layer ${material}/${type}`).toBeTruthy();
    expect(lb.driven).toBe(true);
    // Both snapshots come from draws, and draws happened in between.
    expect(la.binds).toBeGreaterThan(0);
    expect(lb.binds).toBeGreaterThan(la.binds);
    // The animated input changed between the two draws...
    expect(Math.abs(lb.inputs[axis] - la.inputs[axis])).toBeGreaterThan(1e-4);
    // ...and the uploaded rows follow the rule at both times.
    expectRule(la);
    expectRule(lb);
    expect(errors).toEqual([]);
  });
}

test('negative: a layer no sequence drives keeps one transform', async ({ page }) => {
  const errors = await open(page);
  const { a, b } = await sample(page, 'DestructibleBillboardScrollingText', 600);
  const still = b.uvLayers.filter((l) => !l.driven && l.binds > 0);
  console.log(show(still));
  expect(still.length).toBeGreaterThan(0);
  for (const l of still) {
    const before = a.uvLayers.find((x) => x.material === l.material && x.type === l.type);
    // Drawn again in between, with the same rows.
    expect(l.binds).toBeGreaterThan(before.binds);
    expect(l.transform).toEqual(before.transform);
    expectRule(l);
  }
  expect(errors).toEqual([]);
});

test('negative: a model with no UV transform draws every layer with the identity', async ({ page }) => {
  const errors = await open(page);
  const { a, b } = await sample(page, 'Armory', 600);
  console.log(`Armory\n${show(b.uvLayers)}`);
  expect(b.uvLayers.filter((l) => l.binds > 0).length).toBeGreaterThan(0);
  for (const snap of [a, b]) {
    for (const l of snap.uvLayers.filter((x) => x.binds > 0)) {
      expect(l.driven).toBe(false);
      const identity = [1, 0, 0, 0, 1, 0];
      l.transform.forEach((x, i) => expect(x).toBeCloseTo(identity[i], 6));
    }
  }
  expect(errors).toEqual([]);
});

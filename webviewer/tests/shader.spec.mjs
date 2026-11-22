import { test, expect } from '@playwright/test';

// Shader checks. Each one renders a unit with team colour 2 (blue), so red
// on the model can only come from a wrong shader, never from team colour.
// The raw stats are printed, so a failure shows what was drawn.

async function open(page) {
  await page.goto('/');
  await page.waitForFunction(() => window.sc2viewer && window.sc2viewer.ready);
  // Colour stats cover the model only: no ground grid behind it.
  await page.evaluate(() => window.sc2viewer.setGrid(false));
}

async function statsOf(page, unit) {
  // No animation (sequence -1): between the mark and the read only the team
  // colour changes the picture. An animated unit moved in that time too, and
  // a slow run counted the motion as team colour (Zealot 0.40, 0.61; full68, full71).
  await page.evaluate((id) => window.sc2viewer.addUnit(id, { team: 1, x: 0, y: 0, pick: 0.5, sequence: -1 }), unit);
  await page.waitForFunction(() => window.sc2viewer.idle());
  const stats = await page.evaluate(() => window.sc2viewer.colorStats());
  // For diagnosis only; no check reads it.
  await page.locator('canvas#view').screenshot({ path: `test-results/shader-${unit}.png` });
  // Team share: the part of the model that changes when the team colour does.
  await page.evaluate(() => window.sc2viewer.mark());
  await page.locator('#scene li select.team').selectOption('0');
  const changed = await page.evaluate(() => window.sc2viewer.changedSinceMark());
  stats.teamShare = changed.changed / stats.pixels;
  console.log(unit, JSON.stringify(stats));
  return stats;
}

// maxRed: units with no red paint. The zergling's carapace is red-brown, so
// it has no red limit. maxTeam: the part that may follow the team colour.
// Before the fix, measured: Marine brightness 42.8, Zergling 31.1; the
// siege tank's RGB-diffuse treads took team colour, team share 0.31.
const CASES = [
  { unit: 'Marine', maxRed: 0.02, maxTeam: 0.3 },
  { unit: 'Zealot', maxRed: 0.02, maxTeam: 0.3 },
  { unit: 'Zergling', maxRed: null, maxTeam: 0.35 },
  { unit: 'SiegeTank', maxRed: 0.02, maxTeam: 0.2 },
];

for (const { unit, maxRed, maxTeam } of CASES) {
  test(`shader: ${unit} is lit, not black, team colour on trim only`, async ({ page }) => {
    await open(page);
    const stats = await statsOf(page, unit);
    expect(stats.pixels).toBeGreaterThan(500);
    if (maxRed !== null) expect(stats.redShare).toBeLessThan(maxRed);
    expect(stats.darkShare).toBeLessThan(0.05);
    expect(stats.brightness).toBeGreaterThan(48);
    // Team colour marks trim, not the whole unit.
    expect(stats.teamShare).toBeGreaterThan(0.005);
    expect(stats.teamShare).toBeLessThan(maxTeam);
  });
}

// Lists units whose animation rate in data is not 1 (AnimSpeed x time scale).
// Usage: scripts/anim-rates.sh
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const data = process.argv[2];
if (!data) throw new Error('anim-rates: give the webviewer data folder');
const parsed = JSON.parse(readFileSync(join(data, 'catalog', 'units.json'), 'utf8'));
const units = Array.isArray(parsed) ? parsed : parsed.units;
if (!Array.isArray(units)) throw new Error('anim-rates: units.json holds no unit list');
for (const u of units) {
  const rate = u.animSpeed * u.timeScale;
  if (rate !== 1) console.log(`${u.id} animSpeed=${u.animSpeed} timeScale=${u.timeScale} m3=${u.m3}`);
}

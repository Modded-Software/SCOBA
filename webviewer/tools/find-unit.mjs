// Units whose name or id contains a text (case-insensitive): id, name, model file.
// usage: node tools/find-unit.mjs DATA_DIR TEXT
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const [data, text] = process.argv.slice(2);
if (!data || !text) throw new Error('usage: find-unit.mjs DATA_DIR TEXT');
const parsed = JSON.parse(readFileSync(join(data, 'catalog', 'units.json'), 'utf8'));
const units = Array.isArray(parsed) ? parsed : parsed.units;
if (!Array.isArray(units)) throw new Error('find-unit: units.json holds no unit list');
const needle = text.toLowerCase();
for (const u of units) if (u.id.toLowerCase().includes(needle) || String(u.name).toLowerCase().includes(needle)) console.log(`${u.id}\t${u.name}\t${u.m3}`);

// The gallery's preview card of an SC2 unit or doodad: the lines its data
// gives (SPEC-VIEWER 6.4 describe).

import type { DoodadRecord, PlacedRecord, UnitRecord } from '../shared/records';
import type { PreviewCard } from '../../../page/core/plugin';
import { dataScale } from './rules';

const shown = (value: number): string => String(Math.round(value * 1000) / 1000);
/** "1.2" or "1.2 to 1.5". */
const range = (low: number, high: number): string => (Math.abs(high - low) < 1e-6 ? shown(low) : `${shown(low)} to ${shown(high)}`);

function unitCard(unit: UnitRecord): PreviewCard {
  const facts = [`${unit.race} · ${unit.kind}${unit.family ? ' · ' + unit.family : ''}${unit.inMap ? ' · in map' : ''}`, `id ${unit.id}`, `scale ${range(dataScale(unit, 0)[0], dataScale(unit, 1)[0])}`];
  const rate = unit.animSpeed * unit.timeScale;
  const speeds = [];
  if (Math.abs(rate - 1) > 1e-6) speeds.push(`anim ×${shown(rate)}`);
  if (unit.speed > 0 && unit.walkAnimMoveSpeed !== null && unit.walkAnimMoveSpeed > 0) speeds.push(`walk ×${shown((rate * unit.speed) / unit.walkAnimMoveSpeed)}`);
  if (speeds.length) facts.push(speeds.join(' · '));
  if (unit.height) facts.push(`height ${shown(unit.height)}`);
  if (unit.tint) facts.push(`tint ${unit.tint.map(shown).join(', ')}`);
  return { name: unit.name, picture: unit.portrait || unit.icon, facts };
}

function doodadCard(doodad: DoodadRecord): PreviewCard {
  const notes = [doodad.type, doodad.id];
  if (doodad.variations > 1) notes.push(`${doodad.variations} variations`);
  if (doodad.editorOnly) notes.push('editor only');
  if (doodad.inMap) notes.push('in map');
  const facts = [notes.join(' · '), `scale ${range(dataScale(doodad, 0)[0], dataScale(doodad, 1)[0])} · ${doodad.autoRotate ? 'random angle' : 'fixed angle'}`];
  const rate = doodad.animSpeed * doodad.timeScale;
  if (Math.abs(rate - 1) > 1e-6) facts.push(`anim ×${shown(rate)}`);
  if (doodad.footprint) facts.push(`footprint ${doodad.footprint}`);
  if (doodad.tilesets.length) facts.push(`terrain sets: ${doodad.tilesets.join(', ')}`);
  if (doodad.tint) facts.push(`tint ${doodad.tint.map(shown).join(', ')}`);
  if (doodad.editorOnly) facts.push(`draws nothing in game; shown: editor model ${String(doodad.editorModel)}`);
  return { name: doodad.name, picture: null, facts };
}

export function describeRecord(record: PlacedRecord): PreviewCard {
  return record.doodad ? doodadCard(record) : unitCard(record);
}

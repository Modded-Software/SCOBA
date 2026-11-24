// StarCraft: Ghost on the page (SPEC-VIEWER-GHOST 6): how an actor or a
// model becomes an instance. The motions of the record's motion set are
// handed over as the placement's clips: two actors may share one model
// file and differ in motions.

import type { GameRecord, PageGame, Placement, PlacementWish } from '../../../page/core/plugin';
import type { GhostRecord } from '../shared/records';
import { ACTORS, MODELS, ghostRecord } from './records';

export const GHOST = 'ghost';

/** Checked records, by the object core holds. */
const checked = new WeakMap<GameRecord, GhostRecord>();

function recordOf(record: GameRecord): GhostRecord {
  const known = checked.get(record);
  if (!known) throw new Error(`${record.id} is not a checked ghost record`);
  return known;
}

/** What a placement of this game always is (6): no height, tint, variant, team, icon or backdrop. */
function placement(file: string, scale: number, wish: PlacementWish, clips: Placement['clips']): Placement {
  return { file, variant: null, variants: 0, scale: [scale, scale, scale], height: 0, rot: wish.rot ?? 0, tint: null, pick: wish.pick, asBackdrop: false, radius: null, hitRadius: null, team: false, icon: null, clips };
}

const plural = (n: number, word: string): string => `${n} ${word}${n === 1 ? '' : 's'}`;

export const ghostGame: PageGame = {
  id: GHOST,
  categories: [
    { id: ACTORS, noun: 'actor' },
    { id: MODELS, noun: 'model' },
  ],
  backdrop: 'backdrop',
  checkRecord(category, body) {
    const record = ghostRecord(category, body);
    checked.set(record, record);
    return record;
  },
  place(category, record, wish) {
    const ghost = recordOf(record);
    if (ghost.category !== category) throw new Error(`${ghost.id} is one of ${ghost.category}, not of ${category}`);
    // An actor: its model scale, the same on every axis; 1 when it has none. A model: 1.
    const scale = ghost.category === ACTORS ? (ghost.scale ?? 1) : 1;
    return placement(ghost.file, scale, wish, ghost.motions.map((m) => ({ name: m.name, reference: m.clip })));
  },
  placeFile: (file, wish) => placement(file, 1, wish, []),
  playRate: () => 1,
  describe(_category, record) {
    const ghost = recordOf(record);
    const facts: string[] = [];
    if (ghost.category === ACTORS) {
      facts.push(`model ${ghost.model}`);
      if (ghost.scale !== null) facts.push(`scale ${ghost.scale}`);
      if (ghost.kind !== null) facts.push(`type ${ghost.kind}`);
      if (ghost.script !== null) facts.push(`script ${ghost.script}`);
    } else {
      facts.push(`${plural(ghost.bones, 'bone')}, ${plural(ghost.groups, 'group')}, ${plural(ghost.materials, 'material')}`);
      facts.push(ghost.skinned ? 'skinned' : 'rigid');
    }
    facts.push(ghost.motionSet === null ? 'no motion set' : `${ghost.motionSet}: ${plural(ghost.motions.length, 'motion')}`);
    if (ghost.missingClips.length) facts.push(`${plural(ghost.missingClips.length, 'clip')} missing: ${ghost.missingClips.join(', ')}`);
    return { name: ghost.name, picture: null, facts };
  },
  /** `stand`; else the first motion; else none (6). */
  restSequence(sequences) {
    if (!sequences.length) return -1;
    const stand = sequences.findIndex((s) => s.name.toLowerCase() === 'stand');
    return stand >= 0 ? stand : 0;
  },
  listName(category, query) {
    const words = [query['motion'] === 'with' ? 'Animated' : query['motion'] === 'without' ? 'Still' : '', query['skin'] === 'skinned' ? 'Skinned' : query['skin'] === 'rigid' ? 'Rigid' : ''].filter(Boolean);
    const q = query['q'] ?? '';
    const head = words.length ? words.join(' ') : q ? '' : 'All';
    return [head, `Ghost ${category}`, q ? `"${q}"` : ''].filter(Boolean).join(' ');
  },
};

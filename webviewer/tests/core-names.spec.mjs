// R-VIEW-1 on the source: core code (page/core, page/ui, page/features,
// server/core) holds no game id and no game model or clip file extension
// in its code. Comments are read out first: an example in a comment is not
// a rule. The legacy test object names (window.sc2viewer, window.SC2App,
// the "sc2viewer:" log prefix; R-VIEW-14, step 8) are listed and allowed.
import { test, expect } from '@playwright/test';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const CORE = ['src/page/core', 'src/page/ui', 'src/page/features', 'src/server/core'];
const GAME_IDS = ['sc2', 'ghost'];
const EXTENSIONS = ['m3', 'm3a', 'nod', 'nad', 'nms', 'sc2map', 'sc2mod'];
const LEGACY = /\bsc2viewer\b|\bSC2App\b/g;

const files = (dir) => readdirSync(dir).flatMap((name) => (statSync(join(dir, name)).isDirectory() ? files(join(dir, name)) : name.endsWith('.ts') ? [join(dir, name)] : []));

/** The code of a file: block and line comments gone (a // inside a string or a regex literal is kept). */
function code(text) {
  return text.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`\\])\/\/.*$/gm, '$1');
}

/** Every game id as a string literal and every game file extension in a literal, with its line. */
function findings(path, text) {
  const out = [];
  const lines = code(text).replace(LEGACY, '').split('\n');
  const ids = new RegExp(`(['"\`])(${GAME_IDS.join('|')})\\1`, 'i');
  const ext = new RegExp(`['"\`/][^'"\`\\n]*\\.(${EXTENSIONS.join('|')})\\b`, 'i');
  lines.forEach((line, i) => {
    if (ids.test(line) || ext.test(line)) out.push(`${path}:${i + 1}: ${line.trim()}`);
  });
  return out;
}

test('core code names no game and no game file extension', () => {
  const found = CORE.flatMap((dir) => files(dir)).flatMap((file) => findings(relative('.', file), readFileSync(file, 'utf8')));
  expect(found).toEqual([]);
});

test('negative: the check finds a game id, an extension and a regex of one; a comment is not read', () => {
  expect(findings('a.ts', "const game = 'sc2';")).toHaveLength(1);
  expect(findings('a.ts', 'if (id === "ghost") {}')).toHaveLength(1);
  expect(findings('a.ts', "const m = path.endsWith('.m3');")).toHaveLength(1);
  expect(findings('a.ts', 'const nod = /\\.nod$/i;')).toHaveLength(1);
  expect(findings('a.ts', '// an SC2 unit: .m3 files, the ghost game\nconst x = 1;')).toEqual([]);
  expect(findings('a.ts', '/* sc2 \'sc2\' */ const x = 1;')).toEqual([]);
  expect(findings('a.ts', "console.warn('sc2viewer: failed');")).toEqual([]);
});

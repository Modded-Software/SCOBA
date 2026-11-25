// R-VIEW-13: a type error fails the type check, which scripts/test.sh runs first
// (set -e: a failing step ends the script). Checked on a small settings file
// that extends ours and holds one source file.
import { test, expect } from '../fixtures.mjs';
import { spawnSync } from 'node:child_process';
import { mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const DIR = 'build/typecheck-fixture';

/** Run scripts/typecheck.sh on a settings file that extends ours and checks one file holding `source`. */
function typecheck(name, source) {
  const dir = join(DIR, name);
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, 'case.ts'), source);
  writeFileSync(join(dir, 'tsconfig.json'), JSON.stringify({ extends: '../../../tsconfig.json', include: ['case.ts'] }));
  const run = spawnSync('bash', ['scripts/typecheck.sh', join(dir, 'tsconfig.json')], { encoding: 'utf8' });
  rmSync(dir, { recursive: true, force: true });
  return { code: run.status, out: run.stdout + run.stderr };
}

test('code without a type error passes the type check', () => {
  const r = typecheck('good', 'const n: number = 1;\nexport const twice = n * 2;\n');
  console.log(r.out.trim());
  expect(r.code).toBe(0);
  expect(r.out).toContain('types ok');
});

test('negative: a type error fails the type check and is named', () => {
  const r = typecheck('bad', "const n: number = 'one';\nexport const twice = n * 2;\n");
  console.log(r.out.trim());
  expect(r.code).toBe(1);
  expect(r.out).toContain('case.ts(1,7): error TS2322');
  expect(r.out).toContain('ERROR: type errors');
});

test('negative: an index read may be undefined (noUncheckedIndexedAccess is on)', () => {
  const r = typecheck('index', 'const list: number[] = [1];\nexport const first: number = list[0];\n');
  console.log(r.out.trim());
  expect(r.code).toBe(1);
  expect(r.out).toContain('ERROR: type errors');
});

test('scripts/test.sh runs the type check before the tests, and stops on a failure', async () => {
  const { readFileSync } = await import('node:fs');
  const lines = readFileSync('scripts/test.sh', 'utf8').split('\n');
  const strict = lines.findIndex((l) => l.startsWith('set -euo pipefail'));
  const check = lines.findIndex((l) => l.trim() === 'bash scripts/typecheck.sh');
  const tests = lines.findIndex((l) => l.includes('playwright test'));
  expect(strict).toBeGreaterThanOrEqual(0);
  expect(check).toBeGreaterThan(strict);
  expect(tests).toBeGreaterThan(check);
});

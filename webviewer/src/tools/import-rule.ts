// The import rule of SPEC-VIEWER section 3, checked over a source folder.
// Usage: node build/tools/import-rule.js <src folder>
// Reads every .ts file, finds its import, export-from, import() and require()
// paths, and checks each against the layer rule. Prints every forbidden import;
// exit 1 when there is one. The packages allowed are those of the package.json
// next to the source folder.

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, relative, resolve, sep } from 'node:path';

/** Where a file or an import target sits. */
type Place =
  | { kind: 'shared' | 'page-core' | 'page-ui' | 'page-features' | 'page-main' | 'server-core' | 'server-main' | 'tools' }
  | { kind: 'format'; id: string }
  | { kind: 'game'; id: string; side: 'page' | 'server' | 'shared' }
  | { kind: 'library' | 'package' | 'node' }
  | { kind: 'outside' | 'unknown'; why: string };

/** One forbidden import. */
export interface Violation {
  file: string;
  line: number;
  path: string;
  reason: string;
}

const LIBRARY = '@renderer/';

// Static imports and exports start a line, so text in strings and comments is not read as one.
const PATTERNS = [
  /^\s*import\s+(?:type\s+)?[\w*\s{},$]+?\s+from\s+['"]([^'"]+)['"]/gm,
  /^\s*import\s+['"]([^'"]+)['"]/gm,
  /^\s*export\s+(?:type\s+)?(?:\*(?:\s+as\s+\w+)?|\{[^}]*\})\s+from\s+['"]([^'"]+)['"]/gm,
  /\bimport\(\s*['"]([^'"]+)['"]\s*\)/g,
  /\brequire\(\s*['"]([^'"]+)['"]\s*\)/g,
];

/** The place of a path inside the source folder, given with forward slashes and without extension. */
export function placeOf(path: string): Place {
  const parts = path.replace(/\.(ts|js|mjs|cjs)$/, '').split('/');
  const [top, second, third] = parts;
  if (top === 'shared') return { kind: 'shared' };
  if (top === 'tools') return { kind: 'tools' };
  if (top === 'page') {
    if (second === 'core') return { kind: 'page-core' };
    if (second === 'ui') return { kind: 'page-ui' };
    if (second === 'features') return { kind: 'page-features' };
    if (second === 'main' && parts.length === 2) return { kind: 'page-main' };
  }
  if (top === 'server') {
    if (second === 'core') return { kind: 'server-core' };
    if (second === 'main' && parts.length === 2) return { kind: 'server-main' };
  }
  if (top === 'formats' && second !== undefined && parts.length > 2) return { kind: 'format', id: second };
  if (top === 'games' && second !== undefined && (third === 'page' || third === 'server' || third === 'shared')) {
    return { kind: 'game', id: second, side: third };
  }
  return { kind: 'unknown', why: `${path} is in no layer` };
}

/** The packages named in a package.json. */
export function packagesOf(packageJson: string): Set<string> {
  const data: unknown = JSON.parse(readFileSync(packageJson, 'utf8'));
  const names = new Set<string>();
  if (typeof data !== 'object' || data === null) return names;
  for (const key of ['dependencies', 'devDependencies']) {
    const block: unknown = Reflect.get(data, key);
    if (typeof block === 'object' && block !== null) for (const name of Object.keys(block)) names.add(name);
  }
  return names;
}

/** The package name of a bare import path: "a" of "a/b", "@s/a" of "@s/a/b". */
function packageName(path: string): string {
  const parts = path.split('/');
  return path.startsWith('@') ? parts.slice(0, 2).join('/') : (parts[0] ?? path);
}

/** The place an import path leads to, seen from a file. */
function targetOf(path: string, fromFile: string, root: string, packages: Set<string>): Place {
  if (path.startsWith(LIBRARY)) return { kind: 'library' };
  if (path.startsWith('node:')) return { kind: 'node' };
  if (path.startsWith('.')) {
    const inside = relative(root, resolve(dirname(fromFile), path));
    if (inside.startsWith('..') || inside === '') return { kind: 'outside', why: `${path} leaves the source folder` };
    return placeOf(inside.split(sep).join('/'));
  }
  if (packages.has(packageName(path)) && packageName(path) !== 'mdx-m3-viewer') return { kind: 'package' };
  return { kind: 'outside', why: `${path} is not a package of package.json (the renderer library is ${LIBRARY}...)` };
}

const same = (a: Place, b: Place): boolean => JSON.stringify(a) === JSON.stringify(b);

/** Why `from` may not import `to`, or null when it may. */
export function refusal(from: Place, to: Place): string | null {
  if (from.kind === 'unknown') return from.why;
  if (to.kind === 'outside' || to.kind === 'unknown') return to.why;
  if (same(from, to) || to.kind === 'package' || to.kind === 'shared') return null;
  const node = to.kind === 'node';
  const library = to.kind === 'library';
  const pageCore = to.kind === 'page-core';
  let ok = false;
  switch (from.kind) {
    case 'shared':
      break;
    case 'page-core':
      ok = library;
      break;
    case 'page-ui':
      ok = pageCore;
      break;
    case 'page-features':
      ok = pageCore || to.kind === 'page-ui';
      break;
    case 'page-main':
      ok = pageCore || to.kind === 'page-ui' || to.kind === 'page-features' || to.kind === 'format' || (to.kind === 'game' && to.side !== 'server');
      break;
    case 'format':
      ok = pageCore || library;
      break;
    case 'game':
      if (to.kind === 'game') ok = to.id === from.id && to.side === 'shared';
      else if (from.side === 'page') ok = pageCore || to.kind === 'format';
      else if (from.side === 'server') ok = node || to.kind === 'server-core';
      break;
    case 'server-core':
      ok = node;
      break;
    case 'server-main':
      ok = node || to.kind === 'server-core' || (to.kind === 'game' && to.side !== 'page');
      break;
    case 'tools':
      ok = node || library || to.kind === 'format' || to.kind === 'server-core' || (to.kind === 'game' && to.side !== 'page');
      break;
    default:
      break;
  }
  return ok ? null : `${describe(from)} may not import ${describe(to)}`;
}

function describe(place: Place): string {
  if (place.kind === 'format') return `formats/${place.id}`;
  if (place.kind === 'game') return `games/${place.id}/${place.side}`;
  if (place.kind === 'library') return 'the renderer library';
  if (place.kind === 'node') return 'a Node module';
  return place.kind.replace('-', '/');
}

/** Every .ts file under a folder. */
function sources(dir: string): string[] {
  const out: string[] = [];
  for (const name of readdirSync(dir).sort()) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) out.push(...sources(path));
    else if (name.endsWith('.ts')) out.push(path);
  }
  return out;
}

/** The forbidden imports of one file. */
export function checkFile(file: string, root: string, packages: Set<string>): Violation[] {
  const text = readFileSync(file, 'utf8');
  const from = placeOf(relative(root, file).split(sep).join('/'));
  const found: Violation[] = [];
  const rel = relative(root, file).split(sep).join('/');
  if (from.kind === 'unknown') return [{ file: rel, line: 1, path: '', reason: from.why }];
  for (const pattern of PATTERNS) {
    for (const match of text.matchAll(pattern)) {
      const path = match[1];
      if (path === undefined) continue;
      const reason = refusal(from, targetOf(path, file, root, packages));
      if (reason === null) continue;
      // The leading space of a match can hold line breaks: count from its first word.
      const start = match.index + Math.max(0, match[0].search(/\S/));
      const line = text.slice(0, start).split('\n').length;
      found.push({ file: rel, line, path, reason });
    }
  }
  return found;
}

function main(): void {
  const arg = process.argv[2];
  if (arg === undefined) {
    console.error('usage: import-rule <src folder>');
    process.exit(2);
  }
  const root = resolve(arg);
  const packages = packagesOf(join(root, '..', 'package.json'));
  const files = sources(root);
  const violations = files.flatMap((file) => checkFile(file, root, packages));
  for (const v of violations) console.error(`${v.file}:${v.line}: import '${v.path}': ${v.reason}`);
  console.log(`import rule: ${files.length} files, ${violations.length} forbidden imports`);
  process.exit(violations.length ? 1 : 0);
}

main();

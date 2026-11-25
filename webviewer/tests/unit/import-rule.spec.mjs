// The import rule of SPEC-VIEWER section 3 (src/tools/import-rule.ts), on small
// source folders written for each case. scripts/typecheck.sh builds the tool
// (build/tools/import-rule.js) before the tests run.
import { test, expect } from '../fixtures.mjs';
import { spawnSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';

const TOOL = 'build/tools/import-rule.js';

/** Write the files into a fresh folder with a package.json; run the checker over its src/. */
function check(files) {
  const dir = mkdtempSync(join(tmpdir(), 'import-rule-'));
  try {
    writeFileSync(join(dir, 'package.json'), JSON.stringify({ dependencies: { 'gl-matrix': '3.4.4', 'mdx-m3-viewer': '5.12.0' } }));
    for (const [path, text] of Object.entries(files)) {
      const full = join(dir, 'src', path);
      mkdirSync(dirname(full), { recursive: true });
      writeFileSync(full, text);
    }
    const run = spawnSync('node', [TOOL, join(dir, 'src')], { encoding: 'utf8' });
    return { code: run.status, out: run.stdout + run.stderr };
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

test('allowed imports pass: each layer imports what section 3 lets it', () => {
  const r = check({
    'shared/ids.ts': "import { vec3 } from 'gl-matrix';\nexport const a = 1;\n",
    'page/core/scene.ts': "import { a } from '../../shared/ids';\nimport Viewer from '@renderer/viewer/viewer';\nexport const s = a;\n",
    'page/ui/list.ts': "import { s } from '../core/scene';\nexport const l = s;\n",
    'page/features/pick.ts': "import { l } from '../ui/list';\nimport { s } from '../core/scene';\nexport const p = l + s;\n",
    'page/texview/main.ts': "import { s } from '../core/scene';\nimport { a } from '../../shared/ids';\nexport const t = s + a;\n",
    'formats/m3/index.ts': "import { s } from '../../page/core/scene';\nimport M3 from '@renderer/viewer/handlers/m3/handler';\n",
    'games/sc2/shared/records.ts': "import { a } from '../../../shared/ids';\n",
    'games/sc2/page/plugin.ts': "import '../shared/records';\nimport '../../../formats/m3/index';\nimport '../../../page/core/scene';\n",
    'games/sc2/server/backend.ts': "import { readFile } from 'node:fs/promises';\nimport '../shared/records';\nimport '../../../server/core/http';\n",
    'server/core/http.ts': "import { createServer } from 'node:http';\n",
    'server/main.ts': "import './core/http';\nimport '../games/sc2/server/backend';\n",
    'page/main.ts': "import './core/scene';\nimport './features/pick';\nimport '../games/sc2/page/plugin';\n",
    'tools/survey.ts': "import '../formats/m3/index';\nimport '../games/sc2/server/backend';\nimport M3 from '@renderer/parsers/m3/model';\nimport { join } from 'node:path';\n",
  });
  console.log(r.out.trim());
  expect(r.out).toContain('13 files, 0 forbidden imports');
  expect(r.code).toBe(0);
});

// Each case: one file, one import that the rule refuses, and the words the report must hold.
const REFUSED = [
  ['ui imports features', 'page/ui/list.ts', "import { p } from '../features/pick';", 'page/ui may not import page/features'],
  ['the texture page imports features', 'page/texview/main.ts', "import '../features/pick';", 'page/texview may not import page/features'],
  ['the texture page imports a game', 'page/texview/main.ts', "import '../../games/sc2/page/plugin';", 'page/texview may not import games/sc2/page'],
  ['core imports a game', 'page/core/scene.ts', "import '../../games/sc2/page/plugin';", 'page/core may not import games/sc2/page'],
  ['core imports a format', 'page/core/scene.ts', "import '../../formats/m3/index';", 'page/core may not import formats/m3'],
  ['a game imports another game', 'games/sc2/page/plugin.ts', "import '../../ghost/page/plugin';", 'games/sc2/page may not import games/ghost/page'],
  ['a game page imports its own server', 'games/sc2/page/plugin.ts', "import '../server/backend';", 'games/sc2/page may not import games/sc2/server'],
  ['page code imports server code', 'page/features/pick.ts', "import '../../server/core/http';", 'page/features may not import server/core'],
  ['server code imports page code', 'server/core/http.ts', "import '../../page/core/scene';", 'server/core may not import page/core'],
  ['a tool imports page code', 'tools/survey.ts', "import '../page/core/scene';", 'tools may not import page/core'],
  ['ui imports the renderer library', 'page/ui/list.ts', "import Viewer from '@renderer/viewer/viewer';", 'page/ui may not import the renderer library'],
  ['shared imports a Node module', 'shared/ids.ts', "import { join } from 'node:path';", 'shared may not import a Node module'],
  ['page code imports a Node module', 'page/core/scene.ts', "import { readFile } from 'node:fs';", 'page/core may not import a Node module'],
  ['a path that leaves src', 'page/core/scene.ts', "import Viewer from '../../../ref/mdx-m3-viewer/src/viewer/viewer';", 'leaves the source folder'],
  ['a package not in package.json', 'page/core/scene.ts', "import x from 'left-pad';", 'is not a package of package.json'],
  ['the npm copy of the renderer', 'page/core/scene.ts', "import x from 'mdx-m3-viewer';", 'is not a package of package.json'],
  ['a multi-line import', 'page/ui/list.ts', "import {\n  p,\n  q,\n} from '../features/pick';", 'page/ui may not import page/features'],
  ['an export from', 'page/ui/list.ts', "export { p } from '../features/pick';", 'page/ui may not import page/features'],
  ['a dynamic import', 'page/ui/list.ts', "const m = await import('../features/pick');", 'page/ui may not import page/features'],
  ['a file in no layer', 'page/other.ts', 'export const x = 1;', 'page/other.ts is in no layer'],
];

for (const [name, file, line, words] of REFUSED) {
  test(`negative: ${name} is refused`, () => {
    const r = check({ [file]: `// one import\n${line}\n` });
    console.log(r.out.trim());
    expect(r.code).toBe(1);
    expect(r.out).toContain(words);
    expect(r.out).toContain('1 forbidden imports');
    // The line of the import is named; a file in no layer is named at line 1.
    expect(r.out).toContain(words.endsWith('in no layer') ? `${file}:1:` : `${file}:2:`);
  });
}

test('negative: text in a string is not read as an import', () => {
  const r = check({ 'page/ui/list.ts': "const s = `import '../features/pick'`;\n// import x from '../features/pick';\n" });
  expect(r.out).toContain('1 files, 0 forbidden imports');
  expect(r.code).toBe(0);
});

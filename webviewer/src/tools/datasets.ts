// The datasets, for the shell scripts (rules: src/games/sc2/server/datasets.ts).
// Started with scripts/tool.sh, which sets WEBVIEWER_DIR.
//
//   tool.sh datasets list
//       one line per dataset: id, stock folder, map layer (or "none"),
//       catalog folder, separated by tabs
//   tool.sh datasets signature ID
//       the fingerprint of what the dataset is built from
//   tool.sh datasets dir
//       the folder that holds the extra datasets
//
// A folder under the datasets folder that is not a dataset is an error.

import { folders, listDatasets, signature } from '../games/sc2/server/datasets';

const viewerDir = process.env['WEBVIEWER_DIR'];
if (viewerDir === undefined || viewerDir === '') throw new Error('WEBVIEWER_DIR is not set; start this tool with scripts/tool.sh');
const [command, id] = process.argv.slice(2);
const dirs = folders(viewerDir);

if (command === 'dir') {
  console.log(dirs.datasets);
} else if (command === 'list' || command === 'signature') {
  const { datasets, problems } = await listDatasets(dirs);
  if (problems.length) {
    for (const problem of problems) console.error(`datasets: ${problem.dir}: ${problem.reason}`);
    process.exit(1);
  }
  if (command === 'list') {
    for (const d of datasets) console.log([d.id, d.stockDir, d.mapDir ?? 'none', d.catalogDir].join('\t'));
  } else {
    const dataset = datasets.find((d) => d.id === id);
    if (!dataset) {
      console.error(`datasets: no dataset "${id ?? ''}" (have: ${datasets.map((d) => d.id).join(', ')})`);
      process.exit(1);
    }
    console.log(await signature(dataset));
  }
} else {
  console.error('usage: tool.sh datasets list | signature ID | dir');
  process.exit(2);
}

// The datasets, for the shell scripts (rules: server-datasets.mjs).
//
//   node tools/datasets.mjs list
//       one line per dataset: id, stock folder, map layer (or "none"),
//       catalog folder, separated by tabs
//   node tools/datasets.mjs signature ID
//       the fingerprint of what the dataset is built from
//   node tools/datasets.mjs dir
//       the folder that holds the extra datasets
//
// A folder under the datasets folder that is not a dataset is an error.

import { folders, listDatasets, signature } from '../server-datasets.mjs';

const [command, id] = process.argv.slice(2);
const dirs = folders();

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
  console.error('usage: datasets.mjs list | signature ID | dir');
  process.exit(2);
}

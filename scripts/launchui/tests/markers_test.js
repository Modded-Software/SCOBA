// The step markers and the hints of actions.js against the scripts that
// print them. A reworded log line in a script fails here, not in the dialog.
//
// usage: gjs -m markers_test.js <project folder>

import GLib from 'gi://GLib';
import System from 'system';

import {ACTIONS, HINTS} from '../actions.js';
import {equal, ok, run, test} from './harness.js';

const ROOT = System.programArgs[0];
const TS = '2026-11-26 15:28:14 ';
const decoder = new TextDecoder('utf-8');

// The scripts whose lines reach each source of an action.
const PRINTERS = {
    'launch': {pipe: ['scripts/playtest.sh', 'scripts/build.sh'], file: ['scripts/launch-scoba.sh']},
    'launch-built': {pipe: ['scripts/playtest.sh'], file: ['scripts/launch-scoba.sh']},
    'editor': {pipe: [], file: ['scripts/launch-editor.sh']},
};
// Where each failure message of the hints comes from.
const MESSAGE_FILES = [
    'scripts/playtest.sh', 'scripts/build.sh', 'scripts/launch-scoba.sh', 'scripts/launch-editor.sh',
    'scripts/paths.sh', 'scripts/hdtex/core/package.py',
];

function linesOf(relative) {
    const [, bytes] = GLib.file_get_contents(GLib.build_filenamev([ROOT, relative]));
    return decoder.decode(bytes).split('\n');
}

// The lines a script prints with `log "..."`, as they show in their source:
// the launchers stamp each line of their log file.
function printed(files, source) {
    const lines = [];
    for (const file of files) {
        for (const line of linesOf(file)) {
            const match = line.match(/^\s*log "(.*)"/);
            if (match !== null)
                lines.push(source === 'file' ? `${TS}${match[1]}` : match[1]);
        }
    }
    return lines;
}

function shows(marker, files, source) {
    return printed(files, source).some(line => marker.test(line));
}

for (const [id, action] of Object.entries(ACTIONS)) {
    test(`${id}: a script prints each step marker`, () => {
        ok(id in PRINTERS, `printers of ${id}`);
        let markers = 0;
        for (const step of action.steps) {
            if (step.marker === null)
                continue;
            markers += 1;
            ok(shows(step.marker, PRINTERS[id][step.source], step.source),
                `${id}/${step.id}: ${step.marker} in ${PRINTERS[id][step.source].join(', ')}`);
        }
        equal(markers, action.steps.length - 1, `${id}: every step but the first has a marker`);
        equal(action.steps[0].marker, null, `${id}: the first step begins with the command`);
    });

    test(`${id}: its launcher appends to the log file the dialog follows`, () => {
        const text = PRINTERS[id].file.map(file => linesOf(file).join('\n')).join('\n');
        ok(text.includes(`exec >>"$LOG_DIR/${action.tail}" 2>&1`), `exec >> ${action.tail}`);
        ok(text.includes('LOG_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/scoba"'), 'the state folder');
    });
}

test('negative: a marker no script prints is not found', () => {
    equal(shows(/^expanding the map$/, PRINTERS['launch'].pipe, 'pipe'), false, 'reworded marker');
    // A stamped line is a line of the log file, not of the pipe.
    equal(shows(ACTIONS['launch'].steps[5].marker, PRINTERS['launch'].file, 'pipe'), false, 'no stamp on the pipe');
});

test('hints: a script prints the message of each hint', () => {
    const lines = MESSAGE_FILES.flatMap(linesOf);
    ok(HINTS.length > 0, 'hints');
    for (const [pattern] of HINTS)
        ok(lines.some(line => pattern.test(line)), `${pattern} in the scripts`);
});

run();

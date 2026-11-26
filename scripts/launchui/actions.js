// What the launch dialog can run (REQ-LAUNCH-DIALOG). Plain data, no toolkit.
//
// A step begins when its marker line shows in its source: `pipe` is the
// output of the command, `file` is the log file the launcher appends to
// once it has taken its output off the pipe. The first step of an action
// begins with the command. The last step ends when the target process shows.

const STAMP = '^\\d{4}-\\d\\d-\\d\\d \\d\\d:\\d\\d:\\d\\d ';

// scripts/playtest.sh and scripts/build.sh print these lines.
const BUILD_STEPS = [
    {id: 'prepare', name: 'Prepare the build', source: 'pipe', marker: null, seconds: 2, build: true},
    {id: 'expand', name: 'Expand the map', source: 'pipe', marker: /^expanding map$/, seconds: 90, build: true},
    {id: 'eol', name: 'Normalize line endings', source: 'pipe', marker: /^normalizing line endings$/, seconds: 20, build: true},
    {id: 'stamp', name: 'Write the stamp and the manifest', source: 'pipe', marker: /^writing build stamp$/, seconds: 5, build: true},
    {id: 'validate', name: 'Validate the map', source: 'pipe', marker: /^validating map$/, seconds: 15, build: true},
];

// scripts/launch-scoba.sh writes these lines to launcher.log.
const GAME_STEPS = [
    {id: 'stage', name: 'Stage the map in StarCraft II', source: 'file', marker: new RegExp(`${STAMP}gpu: `), seconds: 2, build: false},
    {id: 'metrics', name: 'Write the clip metrics', source: 'file', marker: new RegExp(`${STAMP}stamp: `), seconds: 13, build: false},
    {id: 'start', name: 'Start StarCraft II', source: 'file', marker: new RegExp(`${STAMP}launching `), seconds: 20, build: false},
];

export const ACTIONS = {
    'launch': {
        id: 'launch',
        title: 'Build and launch',
        command: ['bash', 'scripts/playtest.sh', 'launch'],
        tail: 'launcher.log',
        target: 'StarCraft II',
        // A bracket keeps the pattern from matching a command line that names it.
        process: 'SC2_x64[.]exe',
        steps: [...BUILD_STEPS, ...GAME_STEPS],
    },
    'launch-built': {
        id: 'launch-built',
        title: 'Launch the last build',
        command: ['bash', 'scripts/playtest.sh', 'launch-built'],
        tail: 'launcher.log',
        target: 'StarCraft II',
        process: 'SC2_x64[.]exe',
        steps: [
            {id: 'prepare', name: 'Check the built map', source: 'pipe', marker: null, seconds: 1, build: false},
            ...GAME_STEPS,
        ],
    },
    'editor': {
        id: 'editor',
        title: 'Open the map in the editor',
        command: ['bash', 'scripts/launch-editor.sh'],
        tail: 'editor.log',
        target: 'The editor',
        process: 'SC2Editor_x64[.]exe',
        steps: [
            {id: 'check', name: 'Check the map and the editor', source: 'file', marker: null, seconds: 1, build: false},
            {id: 'start', name: 'Start the editor', source: 'file', marker: new RegExp(`${STAMP}command: `), seconds: 15, build: false},
        ],
    },
};

const ERROR_PATTERNS = [/\bERROR\b/, /^Traceback \(most recent call last\):/, /^FAIL(ED)?\b/, /^error: /i];
const WARNING_PATTERNS = [/\bwarning\b/i, /\bWARN\b/];

// 'error', 'warning' or 'plain'. An error line keeps the dialog open.
export function classify(line) {
    if (ERROR_PATTERNS.some(pattern => pattern.test(line)))
        return 'error';
    if (WARNING_PATTERNS.some(pattern => pattern.test(line)))
        return 'warning';
    return 'plain';
}

// Each pattern is a message one of the launch scripts prints.
export const HINTS = [
    [/another build is running/, 'Another build is running. Wait for it to end, then retry.'],
    [/cannot be packaged/, 'HD texture bakes block the build. The log names each texture and the command that fixes it.'],
    [/no built map/, 'There is no built map yet. Run Build and launch first.'],
    [/unpacked map folder not found/, 'There is no built map yet. Build it with the SCOBA icon first.'],
    [/uv not (found|executable)/, 'uv is missing. Run make deps-check.'],
    [/GE-Proton not found/, 'GE-Proton is missing. Run make deps-check.'],
    [/StarCraft II (editor )?not found/, 'StarCraft II is not where env/paths.conf says. Run make deps-check.'],
    [/is on the disk of the repository/, 'The work folder is on the repository disk. Set SC2_WORK in env/paths.conf.'],
];

// The advice for the lines of a failed run, each one once, in table order.
export function hintsFor(lines) {
    return HINTS.filter(([pattern]) => lines.some(line => pattern.test(line))).map(([, text]) => text);
}

export function formatSeconds(seconds) {
    const whole = Math.max(0, Math.floor(seconds));
    return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, '0')}`;
}

// The launch dialog of the dock icons (REQ-LAUNCH-DIALOG).
// Started by scripts/launch-dialog.sh with `gjs -m`.

import Adw from 'gi://Adw?version=1';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Gtk from 'gi://Gtk?version=4.0';
import System from 'system';

import {ACTIONS} from './actions.js';
import {LaunchWindow} from './window.js';

const APP_ID = 'org.scoba.Launcher';
const USAGE = `usage: main.js --root <project folder> --action <${Object.keys(ACTIONS).join('|')}>
               [--process <pgrep pattern>] [--report <file>]
       main.js --check

  --root     the project folder; the action's command runs there
  --action   what to run
  --process  the target process to wait for, in place of the action's own
             (for a run against scripted commands)
  --report   write the dialog's state to this JSON file when the run ends
             and when the window closes
  --check    load the toolkit, print its versions, open nothing`;

function fail(message) {
    printerr(`ERROR: ${message}\n${USAGE}`);
    System.exit(2);
}

function parse(args) {
    const options = {root: null, actionId: null, processPattern: null, reportPath: null, check: false};
    const names = {'--root': 'root', '--action': 'actionId', '--process': 'processPattern', '--report': 'reportPath'};
    for (let i = 0; i < args.length; i += 1) {
        const arg = args[i];
        if (arg === '--check') {
            options.check = true;
        } else if (arg === '--help') {
            print(USAGE);
            System.exit(0);
        } else if (arg in names) {
            i += 1;
            if (i >= args.length)
                fail(`${arg} needs a value`);
            options[names[arg]] = args[i];
        } else {
            fail(`unknown argument: ${arg}`);
        }
    }
    return options;
}

const options = parse(System.programArgs);
if (options.check) {
    // System.version is one number: 18002 is 1.80.2.
    const gjs = `${Math.floor(System.version / 10000)}.${Math.floor(System.version / 100) % 100}.${System.version % 100}`;
    print(`gjs ${gjs}, GTK ${Gtk.MAJOR_VERSION}.${Gtk.MINOR_VERSION}.${Gtk.MICRO_VERSION}, ` +
        `libadwaita ${Adw.MAJOR_VERSION}.${Adw.MINOR_VERSION}.${Adw.MICRO_VERSION}`);
    System.exit(0);
}
if (options.root === null || !GLib.file_test(options.root, GLib.FileTest.IS_DIR))
    fail(`--root is not a folder: ${options.root}`);
if (!(options.actionId in ACTIONS))
    fail(`--action is not one of ${Object.keys(ACTIONS).join(', ')}: ${options.actionId}`);

GLib.set_application_name('SCOBA Launcher');
// Each click of a dock icon is a run of its own.
const application = new Adw.Application({application_id: APP_ID, flags: Gio.ApplicationFlags.NON_UNIQUE});
const windows = [];
application.connect('activate', () => {
    Gtk.Window.set_default_icon_name('scoba');
    const window = new LaunchWindow(application, options);
    windows.push(window);
    window.present();
});
application.run([System.programInvocationName]);

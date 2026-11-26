// The widgets of the launch dialog (REQ-LAUNCH-DIALOG). No run logic here:
// window.js tells this view what to show.

import Adw from 'gi://Adw?version=1';
import Gtk from 'gi://Gtk?version=4.0';
import Pango from 'gi://Pango';

import {formatSeconds} from './actions.js';

const KEPT_LOG_LINES = 5000;
const TRIM_AT_LINES = 6000;
const STEP_ICONS = {
    done: ['object-select-symbolic', 'success'],
    failed: ['dialog-error-symbolic', 'error'],
    cancelled: ['process-stop-symbolic', 'warning'],
};

function button(label, classes) {
    return new Gtk.Button({label, css_classes: classes, visible: false});
}

export class View {
    constructor(application) {
        this.title = new Adw.WindowTitle({title: 'SCOBA', subtitle: ''});
        this.banner = new Adw.Banner({revealed: false});
        this.status = new Gtk.Label({xalign: 0, wrap: true, css_classes: ['title-2']});
        this.detail = new Gtk.Label({xalign: 0, wrap: true, selectable: true, visible: false});
        this.progress = new Gtk.ProgressBar();
        this.progressText = new Gtk.Label({xalign: 0, css_classes: ['dim-label', 'caption']});
        this.steps = new Gtk.ListBox({
            selection_mode: Gtk.SelectionMode.NONE,
            css_classes: ['boxed-list'],
            valign: Gtk.Align.START,
        });
        this.rows = [];
        this.stopDialog = null;   // the open "Stop the build?" question
        this._buildLog();

        this.copy = new Gtk.Button({label: 'Copy Log'});
        this.path = new Gtk.Label({
            xalign: 0,
            hexpand: true,
            selectable: true,
            ellipsize: Pango.EllipsizeMode.MIDDLE,
            css_classes: ['dim-label', 'caption'],
        });
        this.lastBuild = button('Launch Last Build', []);
        this.retry = button('Retry', ['suggested-action']);
        this.main = button('Cancel', []);
        this.main.visible = true;

        const head = new Gtk.Box({orientation: Gtk.Orientation.VERTICAL, spacing: 6});
        for (const widget of [this.status, this.detail, this.progress, this.progressText])
            head.append(widget);
        const stepScroll = new Gtk.ScrolledWindow({
            child: this.steps,
            hscrollbar_policy: Gtk.PolicyType.NEVER,
            width_request: 300,
        });
        const middle = new Gtk.Box({spacing: 12, vexpand: true});
        middle.append(stepScroll);
        middle.append(new Gtk.Frame({child: this.logScroll, hexpand: true}));
        const body = new Gtk.Box({
            orientation: Gtk.Orientation.VERTICAL,
            spacing: 12,
            margin_top: 12,
            margin_bottom: 12,
            margin_start: 12,
            margin_end: 12,
        });
        body.append(head);
        body.append(middle);
        const bar = new Gtk.Box({spacing: 8, margin_top: 8, margin_bottom: 8, margin_start: 12, margin_end: 12});
        for (const widget of [this.copy, this.path, this.lastBuild, this.retry, this.main])
            bar.append(widget);

        const frame = new Adw.ToolbarView({content: body});
        frame.add_top_bar(new Adw.HeaderBar({title_widget: this.title}));
        frame.add_top_bar(this.banner);
        frame.add_bottom_bar(bar);
        this.toasts = new Adw.ToastOverlay({child: frame});
        this.window = new Adw.ApplicationWindow({
            application,
            title: 'SCOBA',
            default_width: 940,
            default_height: 600,
            content: this.toasts,
        });
    }

    _buildLog() {
        this.buffer = new Gtk.TextBuffer();
        this.tags = {
            error: new Gtk.TextTag({name: 'error', foreground: '#e01b24'}),
            warning: new Gtk.TextTag({name: 'warning', foreground: '#e66100'}),
            step: new Gtk.TextTag({name: 'step', weight: Pango.Weight.BOLD}),
        };
        for (const tag of Object.values(this.tags))
            this.buffer.get_tag_table().add(tag);
        this.endMark = this.buffer.create_mark('end', this.buffer.get_end_iter(), false);
        this.log = new Gtk.TextView({
            buffer: this.buffer,
            editable: false,
            cursor_visible: false,
            monospace: true,
            wrap_mode: Gtk.WrapMode.WORD_CHAR,
            top_margin: 8,
            bottom_margin: 8,
            left_margin: 8,
            right_margin: 8,
        });
        this.logScroll = new Gtk.ScrolledWindow({child: this.log, hexpand: true, vexpand: true});
    }

    // One row per step: a state mark, the name, the time.
    setSteps(steps) {
        this.steps.remove_all();
        this.rows = steps.map(step => {
            const spinner = new Gtk.Spinner();
            const icon = new Gtk.Image({pixel_size: 16});
            const mark = new Gtk.Stack({width_request: 20});
            mark.add_named(new Gtk.Box(), 'pending');
            mark.add_named(spinner, 'running');
            mark.add_named(icon, 'icon');
            const name = new Gtk.Label({label: step.name, xalign: 0, hexpand: true, wrap: true});
            const time = new Gtk.Label({css_classes: ['dim-label', 'numeric']});
            const box = new Gtk.Box({spacing: 10, margin_top: 8, margin_bottom: 8, margin_start: 10, margin_end: 10});
            for (const widget of [mark, name, time])
                box.append(widget);
            this.steps.append(new Gtk.ListBoxRow({child: box, activatable: false}));
            return {spinner, icon, mark, name, time, state: null};
        });
    }

    // seconds: null for a step that has not begun.
    setStep(index, state, seconds) {
        const row = this.rows[index];
        row.time.label = seconds === null ? '' : formatSeconds(seconds);
        if (row.state === state)
            return;
        row.state = state;
        row.spinner.spinning = state === 'running';
        row.name.css_classes = state === 'pending' ? ['dim-label'] : [];
        if (state === 'pending' || state === 'running') {
            row.mark.visible_child_name = state;
            return;
        }
        const [iconName, cssClass] = STEP_ICONS[state];
        row.icon.icon_name = iconName;
        row.icon.css_classes = [cssClass];
        row.mark.visible_child_name = 'icon';
    }

    clearLog() {
        this.buffer.set_text('', 0);
    }

    // segments: [{kind, text}], text ends with a line end. The view stays at
    // the end only when it was there: a reader who scrolled up is left alone.
    appendLog(segments) {
        const adjustment = this.logScroll.get_vadjustment();
        const atEnd = adjustment.get_value() + adjustment.get_page_size() >= adjustment.get_upper() - 24;
        for (const {kind, text} of segments) {
            const offset = this.buffer.get_end_iter().get_offset();
            this.buffer.insert(this.buffer.get_end_iter(), text, -1);
            if (kind in this.tags)
                this.buffer.apply_tag(this.tags[kind], this.buffer.get_iter_at_offset(offset), this.buffer.get_end_iter());
        }
        const lines = this.buffer.get_line_count();
        if (lines > TRIM_AT_LINES) {
            const [, cut] = this.buffer.get_iter_at_line(lines - KEPT_LOG_LINES);
            this.buffer.delete(this.buffer.get_start_iter(), cut);
        }
        if (atEnd)
            this.log.scroll_to_mark(this.endMark, 0, false, 0, 1);
    }

    logText() {
        return this.buffer.get_text(this.buffer.get_start_iter(), this.buffer.get_end_iter(), false);
    }

    setDetail(text) {
        this.detail.label = text;
        this.detail.visible = text !== '';
    }

    setBanner(text) {
        this.banner.title = text;
        this.banner.revealed = text !== '';
    }

    toast(text) {
        this.toasts.add_toast(new Adw.Toast({title: text, timeout: 2}));
    }

    // Ask before a running build is stopped. onStop runs when the answer is yes.
    confirmStop(stepName, onStop) {
        const dialog = new Adw.AlertDialog({
            heading: 'Stop the build?',
            body: `${stepName} is running. Closing this window stops it.`,
        });
        dialog.add_response('keep', 'Keep Running');
        dialog.add_response('stop', 'Stop');
        dialog.set_response_appearance('stop', Adw.ResponseAppearance.DESTRUCTIVE);
        dialog.set_default_response('keep');
        dialog.set_close_response('keep');
        dialog.connect('response', (_dialog, response) => {
            this.stopDialog = null;
            if (response === 'stop')
                onStop();
        });
        this.stopDialog = dialog;
        dialog.present(this.window);
    }

    // Take the question away: there is no build to stop any more.
    dismissStop() {
        if (this.stopDialog === null)
            return;
        const dialog = this.stopDialog;
        this.stopDialog = null;
        dialog.force_close();
    }
}

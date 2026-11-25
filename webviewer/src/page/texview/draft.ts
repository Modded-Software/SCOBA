// The draft bar of the texture window (SPEC-VIEWER 17.3, R-VIEW-133): how
// many textures are picked and not saved, Revert Changes and Save to Skin….
// main.ts owns the picks; this builds the bar over them.

/** One picked variant of a texture, as the main page saves it. */
export interface Pick {
  asset: string;
  variant: string;
}

/** What the bar reads and calls of the page. */
export interface DraftPage {
  /** Save the picks through the main page; the skin they went into, or null when the person cancelled. */
  save: ((picks: Pick[]) => Promise<string | null>) | undefined;
  picks: Map<string, string>;
  compared: Map<string, Set<string>>;
  saving(): boolean;
  setSaving(on: boolean): void;
  /** Draw the list again, then show the current texture again. */
  redraw(): void;
  /** Draw the list again only. */
  render(): void;
  say(text: string): void;
  element(tag: 'div' | 'span' | 'button', className: string, text?: string): HTMLElement;
}

export function draftBar(page: DraftPage): HTMLElement {
  const { save, picks, compared } = page;
  const bar = page.element('div', 'skin-draft');
  bar.id = 'draft';
  bar.hidden = !save || picks.size === 0;
  const count = page.element('span', 'draft-count', `${picks.size} ${picks.size === 1 ? 'texture' : 'textures'} picked, not saved`);
  const revert = page.element('button', 'skin-draft-revert', 'Revert Changes');
  revert.title = 'Drop the picks; nothing was saved';
  revert.addEventListener('click', () => {
    picks.clear();
    compared.clear();
    page.redraw();
  });
  const saveTo = page.element('button', 'primary skin-draft-save', 'Save to Skin…') as HTMLButtonElement;
  saveTo.title = 'Choose the skin, see each change, then save the picks';
  saveTo.disabled = page.saving();
  saveTo.addEventListener('click', () => {
    if (!save) return;
    page.setSaving(true);
    page.render();
    save([...picks].map(([asset, variant]) => ({ asset, variant }))).then(
      (into) => {
        page.setSaving(false);
        if (into !== null) {
          picks.clear();
          compared.clear();
        }
        page.redraw();
      },
      (error: unknown) => {
        page.setSaving(false);
        page.say(`the picks were not saved: ${error instanceof Error ? error.message : String(error)}`);
        page.render();
      },
    );
  });
  bar.append(count, revert, saveTo);
  return bar;
}

// The chosen ground's controls in the ground dialog (SPEC-VIEWER 17.7,
// R-VIEW-125): a variant select, Upscale and Bake. The select changes what
// the view shows; Bake writes the terrain bake of the texture, after a
// question. A refusal shows its reason; nothing changes (R-VIEW-123).

import { isUsable, textureRoutes, type TextureState } from '../../../shared/textures';
import type { FeatureContext } from '../../core/context';
import { make, messageOf } from '../../core/dom';
import type { GroundChoice } from '../../core/types';
import { ConfirmDialog } from '../../ui/components/dialog';
import { stepSelect } from '../../ui/components/stepper';

/** The select's value for "what the bake shows, else the original". */
const BAKED = '';

export interface GroundRow {
  node: HTMLElement;
  /** Show the controls of the ground as it is now. */
  update(): Promise<void>;
  /** `bake`: the button's verb; `badge`: the shown bake badge, null when hidden. */
  state(): { shown: boolean; variants: string[]; value: string; bake: string; badge: string | null; error: string };
}

export function createGroundRow({ scene, skins, events, status }: Pick<FeatureContext, 'scene' | 'skins' | 'events' | 'status'>): GroundRow {
  const name = make('span', { className: 'ground-name' });
  const select = stepSelect(make('select', { className: 'ground-variant', title: 'the variant the view shows; it writes no bake' }));
  const upscale = make('button', { className: 'ground-upscale', textContent: 'Upscale' });
  const bake = make('button', { className: 'ground-bake' });
  const badge = make('span', { className: 'skin-baked', hidden: true });
  const error = make('div', { className: 'ground-error failure' });
  const node = make('div', { className: 'ground-row', hidden: true }, [name, select, upscale, bake, badge, error]);
  const confirm = new ConfirmDialog({ id: 'bake-ground-dialog', title: 'Bake ground texture', yesText: 'Bake', content: [make('p', { className: 'bake-question' })] });
  let state: TextureState | null = null;

  const ground = (): GroundChoice | null => scene.ground();

  async function update(): Promise<void> {
    const mine = ground();
    node.hidden = mine === null;
    if (!mine) return;
    state = (await skins.states(mine.game, mine.dataset, [mine.texture])).textures[0] ?? null;
    if (ground() !== mine) return;
    name.textContent = mine.name;
    const usable = state ? state.variants.filter(isUsable).map((variant) => variant.id) : [];
    select.replaceChildren(make('option', { value: BAKED, textContent: state?.bake ? `bake: ${state.bake}` : 'original' }), ...usable.map((id) => make('option', { value: id, textContent: id })));
    select.value = mine.variant && usable.includes(mine.variant) ? mine.variant : BAKED;
    // Button names are verbs; the badge says what is baked (SPEC-VIEWER 17.7).
    bake.textContent = select.value === BAKED && state?.bake ? 'Unbake' : 'Bake';
    badge.hidden = !state?.bake;
    badge.textContent = state?.bake ? `🍞 ${state.bake}` : '';
    badge.title = state?.bake ? `baked in this dataset: ${state.bake}` : '';
    bake.disabled = !state || (select.value === BAKED && !state.bake);
    upscale.disabled = !state || !state.judged || Boolean(state.reason);
  }

  const report = (failure: unknown): void => {
    error.textContent = messageOf(failure);
  };

  select.addEventListener('change', () => {
    const mine = ground();
    if (!mine) return;
    const { variant: _old, ...rest } = mine;
    scene.setGround(select.value === BAKED ? rest : { ...rest, variant: select.value }).catch(status.reportFailure);
  });
  upscale.addEventListener('click', () => {
    const mine = ground();
    if (mine) events.emit('texture-upscale', { game: mine.game, dataset: mine.dataset, asset: mine.texture });
  });
  bake.addEventListener('click', () => {
    const mine = ground();
    if (!mine || !state) return;
    const variant = select.value;
    const question = confirm.dialog.body.querySelector('p.bake-question');
    if (question) question.textContent = variant === BAKED ? `Unbake ${mine.texture} in dataset ${mine.dataset}?` : `Bake ${variant} for ${mine.texture} in dataset ${mine.dataset}?`;
    error.textContent = '';
    confirm
      .ask()
      .then(async (yes) => {
        if (!yes) return;
        if (variant === BAKED) await skins.change(mine.game, mine.dataset, textureRoutes.unbake(mine.game, mine.dataset), { asset: mine.texture });
        else await skins.change(mine.game, mine.dataset, textureRoutes.bake(mine.game, mine.dataset), { asset: mine.texture, variant });
      })
      .catch(report);
  });
  events.on('view-changed', () => update().catch(report));
  events.on('textures-changed', ({ game, dataset }) => {
    const mine = ground();
    if (mine && mine.game === game && mine.dataset === dataset) update().catch(report);
  });

  return { node, update, state: () => ({ shown: !node.hidden, variants: [...select.options].map((option) => option.value).filter(Boolean), value: select.value, bake: bake.textContent, badge: badge.hidden ? null : badge.textContent, error: error.textContent }) };
}

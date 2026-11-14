"""Engine probes for WASD / Point & Click.

The probes record raw engine values for unconfirmed engine assumptions.
The only verdicts are run validity. The raw lines are the output.
"""

from __future__ import annotations

from pathlib import Path

from project_root import project_root

from ..map_builder import TestMapSpec
from ..runner import TestRunSpec
from .registry import PROFILE_BANKS, PROFILE_OUTPUTS

ROOT = project_root()

END_SECTIONS = ()
TO_SINGLE_SECTIONS = ()
BUTTON_SECTIONS = ()
TOGGLE_TAGS: dict = {
}
FIRE_SECTIONS = ()


def map_spec() -> TestMapSpec:
    return TestMapSpec(
        profile="pncprobe",
        source=ROOT / "out" / "SCOBA256.SC2Map",
        output=PROFILE_OUTPUTS["pncprobe"],
        bank_names=PROFILE_BANKS["pncprobe"],
        galaxy_files=(
            ROOT / "scripts" / "testkit" / "galaxy" / "common.galaxy",
            ROOT / "scripts" / "testkit" / "galaxy" / "pncprobe.galaxy",
        ),
        galaxy_includes=(
            "scripts/test/pncprobe/common",
            "scripts/test/pncprobe/pncprobe",
        ),
        init_calls=("gt_PncProbe_Init();",),
    )


def on_ready(ctx, data: dict) -> None:
    return


def _delta(raw: dict, tag_a: str, tag_b: str, key: str):
    before = raw.get(tag_a + key)
    after = raw.get(tag_b + key)
    if before is None or after is None:
        return None
    return after - before


def check(ctx, data: dict, checks) -> None:
    for error in ctx.errors:
        print(f"{error} FAIL")
        checks.failures += 1

    checks.eq("meta", "", "done", 1)
    checks.eq("done", "tend", "RealClicks", 0)

    for section in END_SECTIONS:
        raw = data.get(section, {})
        print(
            f"{section}: firstShot={raw.get('firstShot')} issued={raw.get('issued')}"
            f" stopExists={raw.get('stopAbilExists')} stopValid={raw.get('stopOrderValid')}"
            f" | orders shot=[{raw.get('shotOrders')}] t0=[{raw.get('t0000Orders')}]"
            f" t250=[{raw.get('t0250Orders')}] end=[{raw.get('tendOrders')}]"
            f" | shotsAfter={_delta(raw, 'shot', 'tend', 'Shots')}"
            f" hpAfter={_delta(raw, 'shot', 'tend', 'EnemyHp')}"
        )
        print(
            f"{section} cooldown t250: unitLink={raw.get('t0250CdUnitLinkMs')}"
            f" weaponSlash={raw.get('t0250CdWeaponSlashMs')} weaponId={raw.get('t0250CdWeaponIdMs')}"
            f" abilAttack={raw.get('t0250CdAbilAttackMs')} statusAbil={raw.get('t0250CdStatusAbilMs')}"
            f" weaponRemain={raw.get('t0250Weapon1RemainMs')} period={raw.get('t0250Weapon1PeriodMs')}"
        )
        print(
            f"{section} button: pre mask={raw.get('preCmdStateMask')} valid={raw.get('preButtonOrderValid')}"
            f" link={raw.get('preCdUnitLinkMs')}"
            f" | t250 mask={raw.get('t0250CmdStateMask')} valid={raw.get('t0250ButtonOrderValid')}"
            f" | end mask={raw.get('tendCmdStateMask')} valid={raw.get('tendButtonOrderValid')}"
            f" link={raw.get('tendCdUnitLinkMs')}"
        )


    for section in TO_SINGLE_SECTIONS:
        raw = data.get(section, {})
        print(
            f"{section}: auto={raw.get('t0000Auto')} before=[{raw.get('t0000Orders')}]"
            f" shotsAfter={_delta(raw, 't0000', 'tend', 'Shots')} hpAfter={_delta(raw, 't0000', 'tend', 'EnemyHp')}"
            f" orderTicks={raw.get('orderTicks')} first=[{raw.get('tfirstOrders')}]"
        )

    for section in BUTTON_SECTIONS:
        raw = data.get(section, {})
        print(
            f"{section}:"
            + "".join(
                f" | {tag} mask={raw.get(tag + 'CmdStateMask')} valid={raw.get(tag + 'ButtonOrderValid')}"
                f" link={raw.get(tag + 'CdUnitLinkMs')} abil={raw.get(tag + 'CdStatusAbilMs')}"
                for tag in ("pre", "mid", "end")
            )
        )

    for section, tags in TOGGLE_TAGS.items():
        raw = data.get(section, {})
        for tag in tags:
            print(
                f"{section} {tag}: behavior={raw.get(tag + 'Behavior')}"
                f" on(mask={raw.get(tag + 'OnMask')} valid={raw.get(tag + 'OnValid')})"
                f" off(mask={raw.get(tag + 'OffMask')} valid={raw.get(tag + 'OffValid')})"
                f" issued={raw.get(tag + 'Issued')}"
            )

    for section in FIRE_SECTIONS:
        raw = data.get(section, {})
        dx = _delta(raw, "t0000", "tend", "HeroX")
        dy = _delta(raw, "t0000", "tend", "HeroY")
        print(
            f"{section}: moved=({dx},{dy}) shots={_delta(raw, 't0000', 'tend', 'Shots')}"
            f" hp={_delta(raw, 't0000', 'tend', 'EnemyHp')}"
            f" inRange0={raw.get('t0000InRange')} inRangeEnd={raw.get('tendInRange')}"
            f" | orders t500=[{raw.get('t0500Orders')}] facing={raw.get('t0500Facing')}"
        )


def run_spec(launch_timeout_s: float, case_timeout_s: float, run_root: Path) -> TestRunSpec:
    return TestRunSpec(
        profile="pncprobe",
        map_name="SCOBA.SC2Map",
        map_source=PROFILE_OUTPUTS["pncprobe"],
        map_cache_name="SCOBA.SC2Map",
        bank_names=PROFILE_BANKS["pncprobe"],
        ready_section="meta",
        ready_key="ready",
        launch_timeout_s=launch_timeout_s,
        case_timeout_s=case_timeout_s,
        run_root=run_root,
        on_ready=on_ready,
        check=check,
    )

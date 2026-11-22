"""pncprobe group "all" report: TPS shots, walk shots and the spawn scan."""

from __future__ import annotations

TPS_SHOT_SECTIONS = (
    "tps_ff_own_tosh",
    "tps_ff_enemy_tosh",
    "tps_ff_own_kerr",
    "tps_ff_enemy_kerr",
    "tps_ff_own_close",
    "tps_rng_kerr_05",
    "tps_rng_tosh_11",
)
WALK_SECTIONS = (
    "walk_none",
    "walk_order",
    "walk_auto_frame",
    "walk_auto_tick",
    "walk_auto_proxy",
    "walk_auto_decoy",
    "walk_effect",
    "walk_auto_idle",
)


def _delta(raw: dict, tag_a: str, tag_b: str, key: str):
    before = raw.get(tag_a + key)
    after = raw.get(tag_b + key)
    if before is None or after is None:
        return None
    return after - before


def print_shots(data: dict) -> None:
    for section in TPS_SHOT_SECTIONS:
        raw = data.get(section, {})
        print(
            f"{section}: weapon={raw.get('weapon')} range10={raw.get('range10')} valid={raw.get('orderValid')}"
            f" issued={raw.get('issued')} firstTick={raw.get('firstShotTick')}"
            f" shots={_delta(raw, 't0000', 'tend', 'Shots')}"
            f" moved10=({_delta(raw, 't0000', 'tend', 'HeroX10')},{_delta(raw, 't0000', 'tend', 'HeroY10')})"
            f" ally={raw.get('allyHp')}/{raw.get('allyHpMax')} dist10={raw.get('allyDist10')}"
            f" missiles=({raw.get('missiles4')},{raw.get('missiles8')},{raw.get('missiles47')}) orderZ100={raw.get('orderZ100')} proxyZ100={raw.get('proxyZ100')}"
            f" | orders t0=[{raw.get('t0000Orders')}] t250=[{raw.get('t0250Orders')}]"
            f" end=[{raw.get('tendOrders')}]"
            f" | cd t250 link={raw.get('t0250CdUnitLinkMs')} btn={raw.get('t0250CdStatusAbilMs')}"
            f" w1={raw.get('t0250Weapon1RemainMs')} end btn={raw.get('tendButtonCdMs')}"
        )

    for section in WALK_SECTIONS:
        raw = data.get(section, {})
        print(
            f"{section}: y10=({raw.get('y10_t00')},{raw.get('y10_t4')},{raw.get('y10_t8')},"
            f"{raw.get('y10_t16')},{raw.get('y10_t32')})"
            f" shots={raw.get('shots')} firstTick={raw.get('firstShotTick')} moveTick={raw.get('moveTick')}"
            f" targetHp={raw.get('targetHp')} dist10={raw.get('targetDist10')}"
            f" decoy={raw.get('decoyHp')}/{raw.get('decoyHpMax')}"
            f" cd link={raw.get('cdLinkMs')} btn={raw.get('cdButtonMs')}"
            f" | orders t1=[{raw.get('t1Orders')}] t2=[{raw.get('t2Orders')}] t4=[{raw.get('t4Orders')}]"
        )

    scan = data.get("spawn_scan", {})
    for step in range(17):
        print(
            f"spawn_scan dx10={120 + step * 5}: dist10={scan.get(f'dist10_{step}')}"
            f" passable={scan.get(f'pass_{step}')}"
        )

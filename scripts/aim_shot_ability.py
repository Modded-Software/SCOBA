#!/usr/bin/env python3
"""Add aim-shot abilities and the shared hero attack cooldown link."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

from project_root import project_root

ROOT = project_root()
DEFAULT_MAP = ROOT / "out" / "SCOBA256.SC2Map"
GAMEDATA = Path("Base.SC2Data") / "GameData"

COOLDOWN_LINK = "SCOBA/Attack"
STATUS_ABILITY = "SCOBAAutoAttackStatus"
ABILITY_FILTERS = "Visible;Self,Player,Ally,Missile,Stasis,Dead,Hidden,Invulnerable"

# Weapon id -> period. The period is the aim-shot cooldown TimeUse.
WEAPON_PERIODS = {
    "Tosh": "1",
    "RazorTalons": "1.5",
    "QueenOfBladesPsiBlast": "1",
}

# Ability id, effect, weapon that supplies the period.
ABILITIES = (
    ("SCOBAAimShotTosh", "ToshU", "Tosh"),
    ("SCOBAAimShotToshPoint", "SCOBAToshShotPoint", "Tosh"),
    ("SCOBAAimShotTalons", "SCOBATalonsShot", "RazorTalons"),
    ("SCOBAAimShotPsiBlast", "PsiBlastLaunchMissile", "QueenOfBladesPsiBlast"),
    ("SCOBAAimShotPsiBlastPoint", "SCOBAPsiBlastLaunchPoint", "QueenOfBladesPsiBlast"),
)

UNIT_ABILITIES = {
    "ToshSCOBA": ("SCOBAAimShotTosh", "SCOBAAimShotToshPoint"),
    "KerriganSCOBA": (
        "SCOBAAimShotTalons",
        "SCOBAAimShotPsiBlast",
        "SCOBAAimShotPsiBlastPoint",
    ),
}

EFFECTS = {
    "SCOBAToshShotPoint": (
        '    <CEffectSet id="SCOBAToshShotPoint">',
        '        <TargetLocationType value="Point"/>',
        "    </CEffectSet>",
    ),
    "SCOBATalonsShot": (
        '    <CEffectCreatePersistent id="SCOBATalonsShot">',
        '        <WhichLocation Value="TargetUnit"/>',
        '        <PeriodCount value="2"/>',
        '        <PeriodicEffectArray value="RazorTalonsDamage"/>',
        '        <PeriodicPeriodArray value="0"/>',
        '        <PeriodicPeriodArray value="0.3"/>',
        "    </CEffectCreatePersistent>",
    ),
    "SCOBAPsiBlastLaunchPoint": (
        '    <CEffectLaunchMissile id="SCOBAPsiBlastLaunchPoint">',
        '        <AmmoUnit value="KerriganWeapon"/>',
        '        <ImpactLocation Value="TargetPoint"/>',
        "    </CEffectLaunchMissile>",
    ),
}

ACTORS = {
    "SCOBAToshPointAttack": (
        '    <CActorAction id="SCOBAToshPointAttack" parent="GenericAttack" effectAttack="SCOBAToshShotPoint">',
        '        <LaunchAssets Model="ToshAttackLaunch" Sound="Tosh_AttackLaunch"/>',
        "    </CActorAction>",
    ),
    "SCOBAPsiBlastPointAttack": (
        '    <CActorAction id="SCOBAPsiBlastPointAttack" parent="GenericAttack" effectLaunch="SCOBAPsiBlastLaunchPoint">',
        '        <LaunchAssets Sound="Val03QueenRangedAttackLaunch"/>',
        '        <LaunchAttachQuery Methods="Weapon"/>',
        '        <Missile value="QueenOfBladesRangedAttackMissile"/>',
        "    </CActorAction>",
    ),
}


def newline(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def append_entry(text: str, entry_id: str, lines: tuple[str, ...]) -> str:
    """Append one catalog entry before </Catalog> unless the id exists."""
    if f'id="{entry_id}"' in text:
        return text
    if "</Catalog>" not in text:
        raise SystemExit(f"catalog end not found while adding {entry_id}")
    eol = newline(text)
    block = eol.join(lines) + eol
    return text.replace("</Catalog>", block + "</Catalog>", 1)


def add_child(text: str, tag: str, entry_id: str, marker: str, lines: tuple[str, ...]) -> str:
    """Append child lines to an existing entry unless the marker is present."""
    pattern = re.compile(
        rf'(<{tag}\b[^>]*\bid="{re.escape(entry_id)}"[^>]*>)(.*?)([ \t]*</{tag}>)',
        re.S,
    )
    match = pattern.search(text)
    if match is None:
        raise SystemExit(f"{tag} {entry_id} not found")
    if marker in match.group(2):
        return text
    eol = newline(text)
    body = match.group(2).rstrip() + eol + eol.join(lines) + eol
    return text[: match.start()] + match.group(1) + body + match.group(3) + text[match.end() :]


def cooldown_line(time_use: str | None) -> str:
    extra = "" if time_use is None else f' TimeUse="{time_use}"'
    return f'<Cooldown Link="{COOLDOWN_LINK}" Location="Unit"{extra}/>'


def patch_weapons(text: str) -> str:
    for weapon in WEAPON_PERIODS:
        lines = (
            "        <Cost>",
            f"            {cooldown_line(None)}",
            "        </Cost>",
        )
        text = add_child(text, "CWeaponLegacy", weapon, COOLDOWN_LINK, lines)
    return text


def ability_lines(ability: str, effect: str, weapon: str) -> tuple[str, ...]:
    return (
        f'    <CAbilEffectTarget id="{ability}">',
        f'        <Effect index="0" value="{effect}"/>',
        f'        <TargetFilters value="{ABILITY_FILTERS}"/>',
        '        <Range value="500"/>',
        '        <Arc value="360"/>',
        '        <Flags index="Transient" value="1"/>',
        '        <Cost index="0">',
        f"            {cooldown_line(WEAPON_PERIODS[weapon])}",
        "        </Cost>",
        '        <EditorCategories value="AbilityorEffectType:Units"/>',
        f'        <CmdButtonArray index="Execute" DefaultButtonFace="{STATUS_ABILITY}"/>',
        "    </CAbilEffectTarget>",
    )


def patch_abilities(text: str) -> str:
    # The Weapon Attack button cooldown is owned by the source AbilData.xml.
    # This step must not rewrite it.
    for ability, effect, weapon in ABILITIES:
        text = append_entry(text, ability, ability_lines(ability, effect, weapon))
    return text


def patch_effects(text: str) -> str:
    for effect_id, lines in EFFECTS.items():
        text = append_entry(text, effect_id, lines)
    return text


def patch_actors(text: str) -> str:
    for actor_id, lines in ACTORS.items():
        text = append_entry(text, actor_id, lines)
    return text


def patch_units(text: str) -> str:
    for unit, abilities in UNIT_ABILITIES.items():
        for ability in abilities:
            line = f'        <AbilArray Link="{ability}"/>'
            text = add_child(text, "CUnit", unit, f'Link="{ability}"', (line,))
    return text


PATCHES = (
    ("WeaponData.xml", patch_weapons),
    ("AbilData.xml", patch_abilities),
    ("EffectData.xml", patch_effects),
    ("ActorData.xml", patch_actors),
    ("UnitData.xml", patch_units),
)


def apply(map_dir: Path) -> int:
    changed = 0
    for name, patch in PATCHES:
        path = Path(map_dir) / GAMEDATA / name
        with path.open(encoding="utf-8", newline="") as handle:
            before = handle.read()
        after = patch(before)
        if after != before:
            with path.open("w", encoding="utf-8", newline="") as handle:
                handle.write(after)
            changed += 1
    return changed


def revert() -> int:
    env = {**os.environ, "SC2_NO_AIM_SHOT": "1"}
    return subprocess.call([sys.executable, str(ROOT / "scripts" / "expand_map.py")], env=env)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", type=Path, default=DEFAULT_MAP)
    parser.add_argument("--revert", action="store_true")
    args = parser.parse_args(argv[1:])
    if args.revert:
        return revert()
    changed = apply(args.map)
    print(f"patched {changed} data files for aim shots")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

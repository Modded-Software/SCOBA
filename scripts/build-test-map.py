#!/usr/bin/env python3
"""Build an instrumented copy of the expanded map for automated integration tests.

- Clears MapInfo GAMEOPTS_WAIT_FOR_KEY (bit 1) so the map starts without input.
- Recomputes the MapInfo integrity hash after changing game_options_flags.
- Adds the test bank to BankList.xml.
- Injects a Galaxy trigger that drives probe units and logs positions to a bank.
"""

from __future__ import annotations

import os
import shutil
import struct
from pathlib import Path

from project_root import project_root

ROOT = project_root()
SRC = ROOT / "out" / "SCOBA256.SC2Map"
DST = ROOT / "out" / "SCOBA256_test.SC2Map"
BANK_NAME = "SCOBATEST"

HARNESS = r'''
//--------------------------------------------------------------------------------------------------
// Minimal test: order player character to opposite diagonal, wait, log position
//--------------------------------------------------------------------------------------------------
void gf_DbgLogUnit (bank lp_bank, string lp_section, unit lp_unit) {
    if (UnitIsValid(lp_unit)) {
        BankValueSetFromInt(lp_bank, lp_section, "x", FixedToInt(PointGetX(UnitGetPosition(lp_unit))));
        BankValueSetFromInt(lp_bank, lp_section, "y", FixedToInt(PointGetY(UnitGetPosition(lp_unit))));
        BankValueSetFromInt(lp_bank, lp_section, "valid", 1);
    }
    else {
        BankValueSetFromInt(lp_bank, lp_section, "valid", 0);
    }
}

bool gt_DbgTest_Func (bool testConds, bool runActions) {
    int lv_i;
    if (!runActions) { return true; }
    Wait(3.0, c_timeGame);
    gv_dbgBank = BankLoad("SCOBATEST", 1);
    BankValueSetFromInt(gv_dbgBank, "meta", "done", 0);
    BankValueSetFromInt(gv_dbgBank, "meta", "tick", -1);
    BankValueSetFromInt(gv_dbgBank, "meta", "startX", FixedToInt(PointGetX(UnitGetPosition(gv_tPSUNIT[1]))));
    BankValueSetFromInt(gv_dbgBank, "meta", "startY", FixedToInt(PointGetY(UnitGetPosition(gv_tPSUNIT[1]))));
    BankValueSetFromInt(gv_dbgBank, "meta", "targetX", FixedToInt(PointGetX(UnitGetPosition(gv_tPSUNIT[1])) - 20.0));
    BankValueSetFromInt(gv_dbgBank, "meta", "targetY", FixedToInt(PointGetY(UnitGetPosition(gv_tPSUNIT[1]))));
    BankSave(gv_dbgBank);
    gf_DbgLogUnit(gv_dbgBank, "P1", gv_tPSUNIT[1]);
    UnitIssueOrder(gv_tPSUNIT[1], OrderTargetingPoint(AbilityCommand("move", 0), Point(PointGetX(UnitGetPosition(gv_tPSUNIT[1])) - 20.0, PointGetY(UnitGetPosition(gv_tPSUNIT[1])))), c_orderQueueReplace);
    for (lv_i = 0; lv_i < 30; lv_i += 1) {
        BankValueSetFromInt(gv_dbgBank, "meta", "tick", lv_i);
        gf_DbgLogUnit(gv_dbgBank, "P1", gv_tPSUNIT[1]);
        BankSave(gv_dbgBank);
        Wait(1.0, c_timeGame);
    }
    BankSectionCreate(gv_dbgBank, "behavior");
    BankValueSetFromInt(gv_dbgBank, "behavior", "startAuto", UnitBehaviorCount(gv_tPSUNIT[1], "SCOBAAutoAttackBehavior"));
    BankValueSetFromInt(gv_dbgBank, "behavior", "startStand", UnitBehaviorCount(gv_tPSUNIT[1], "SCOBARightClickStandBehavior"));
    UnitIssueOrder(gv_tPSUNIT[1], Order(AbilityCommand("SCOBAAutoAttackToggle", 0)), c_orderQueueReplace);
    Wait(1.0, c_timeGame);
    BankValueSetFromInt(gv_dbgBank, "behavior", "autoOn", UnitBehaviorCount(gv_tPSUNIT[1], "SCOBAAutoAttackBehavior"));
    BankValueSetFromFlag(gv_dbgBank, "behavior", "autoOrder", UnitOrderHasAbil(gv_tPSUNIT[1], "SCOBAAutoAttackToggle"));
    BankValueSetFromInt(gv_dbgBank, "behavior", "autoOrders", UnitOrderCount(gv_tPSUNIT[1]));
    UnitIssueOrder(gv_tPSUNIT[1], Order(AbilityCommand("SCOBAAutoAttackToggle", 1)), c_orderQueueReplace);
    Wait(0.5, c_timeGame);
    BankValueSetFromInt(gv_dbgBank, "behavior", "autoOffEarly", UnitBehaviorCount(gv_tPSUNIT[1], "SCOBAAutoAttackBehavior"));
    UnitIssueOrder(gv_tPSUNIT[1], Order(AbilityCommand("SCOBAAutoAttackToggle", 0)), c_orderQueueReplace);
    Wait(1.0, c_timeGame);
    BankValueSetFromInt(gv_dbgBank, "behavior", "standStartX", FixedToInt(PointGetX(UnitGetPosition(gv_tPSUNIT[1]))));
    BankValueSetFromInt(gv_dbgBank, "behavior", "standStartY", FixedToInt(PointGetY(UnitGetPosition(gv_tPSUNIT[1]))));
    libNtve_gf_CreateUnitsAtPoint2(2, "Zergling", 0, 4, PointWithOffset(UnitGetPosition(gv_tPSUNIT[1]), 3.0, 0.0));
    BankValueSetFromInt(gv_dbgBank, "behavior", "enemiesNear", UnitGroupCount(UnitGroupAlliance(1, c_unitAllianceEnemy, RegionCircle(UnitGetPosition(gv_tPSUNIT[1]), 6.0), UnitFilter(0, 0, (1 << c_targetFilterMissile), (1 << (c_targetFilterDead - 32)) | (1 << (c_targetFilterHidden - 32))), 0), c_unitCountAlive));
    Wait(3.0, c_timeGame);
    BankValueSetFromInt(gv_dbgBank, "behavior", "enemiesAfter", UnitGroupCount(UnitGroupAlliance(1, c_unitAllianceEnemy, RegionCircle(UnitGetPosition(gv_tPSUNIT[1]), 6.0), UnitFilter(0, 0, (1 << c_targetFilterMissile), (1 << (c_targetFilterDead - 32)) | (1 << (c_targetFilterHidden - 32))), 0), c_unitCountAlive));
    BankValueSetFromInt(gv_dbgBank, "behavior", "standOrders", UnitOrderCount(gv_tPSUNIT[1]));
    BankValueSetFromFlag(gv_dbgBank, "behavior", "standAttack", UnitOrderHasAbil(gv_tPSUNIT[1], "attack"));
    BankValueSetFromInt(gv_dbgBank, "behavior", "standX", FixedToInt(PointGetX(UnitGetPosition(gv_tPSUNIT[1]))));
    BankValueSetFromInt(gv_dbgBank, "behavior", "standY", FixedToInt(PointGetY(UnitGetPosition(gv_tPSUNIT[1]))));
    BankSave(gv_dbgBank);
    UnitIssueOrder(gv_tPSUNIT[1], Order(AbilityCommand("SCOBAAutoAttackToggle", 1)), c_orderQueueReplace);
    Wait(1.0, c_timeGame);
    BankValueSetFromInt(gv_dbgBank, "behavior", "autoOff", UnitBehaviorCount(gv_tPSUNIT[1], "SCOBAAutoAttackBehavior"));
    BankValueSetFromFlag(gv_dbgBank, "behavior", "offOrder", UnitOrderHasAbil(gv_tPSUNIT[1], "SCOBAAutoAttackToggle"));
    UnitIssueOrder(gv_tPSUNIT[1], Order(AbilityCommand("SCOBARightClickToggle", 0)), c_orderQueueReplace);
    Wait(1.0, c_timeGame);
    UnitIssueOrder(gv_tPSUNIT[1], Order(AbilityCommand("SCOBARightClickToggle", 1)), c_orderQueueReplace);
    Wait(1.0, c_timeGame);
    BankValueSetFromInt(gv_dbgBank, "behavior", "walkStand", UnitBehaviorCount(gv_tPSUNIT[1], "SCOBARightClickStandBehavior"));
    UnitIssueOrder(gv_tPSUNIT[1], Order(AbilityCommand("SCOBARightClickToggle", 0)), c_orderQueueReplace);
    Wait(1.0, c_timeGame);
    BankValueSetFromInt(gv_dbgBank, "behavior", "standAgain", UnitBehaviorCount(gv_tPSUNIT[1], "SCOBARightClickStandBehavior"));
    gv_tARGET[1] = gv_sCOBAMedic[1];
    gf_OrderEnter(1);
    Wait(0.5, c_timeGame);
    BankValueSetFromFlag(gv_dbgBank, "behavior", "orderHeroSelected", UnitIsSelected(gv_tPSUNIT[1], 1));
    BankValueSetFromFlag(gv_dbgBank, "behavior", "orderUnitSelected", UnitIsSelected(gv_sCOBAMedic[1], 1));
    BankValueSetFromFlag(gv_dbgBank, "behavior", "orderModeOn", gv_sCOBAOrderMode[1]);
    BankValueSetFromFlag(gv_dbgBank, "behavior", "orderUnitValid", UnitIsValid(gv_sCOBAOrderUnit[1]));
    gf_OrderExit(1);
    BankValueSetFromInt(gv_dbgBank, "meta", "done", 1);
    gf_DbgLogUnit(gv_dbgBank, "P1", gv_tPSUNIT[1]);
    BankSave(gv_dbgBank);
    return true;
}

void gt_DbgTest_Init () {
    gt_DbgTest = TriggerCreate("gt_DbgTest_Func");
    TriggerAddEventMapInit(gt_DbgTest);
}

'''




def _read_cstr(data: bytes, pos: int) -> tuple[bytes, int]:
    end = data.index(b"\x00", pos)
    return data[pos:end], end + 1


def patch_mapinfo(path: Path) -> None:
    data = bytearray(path.read_bytes())
    version = struct.unpack_from("<I", data, 4)[0]
    pos = 8 + 8
    struct.unpack_from("<II", data, pos)
    pos += 8
    locale_mode = struct.unpack_from("<I", data, pos)[0]
    pos += 4
    if locale_mode == 2:
        pos = data.index(b"\x00", pos) + 1
    if version >= 22:
        preview_type = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        if preview_type == 2:
            pos = data.index(b"\x00", pos) + 1
    if version >= 28:
        pos = data.index(b"\x00", pos) + 1
    if version >= 37:
        pos = data.index(b"\x00", pos) + 1
    if version >= 29:
        pos += 4
    if version >= 11:
        pos += 4
    if version >= 3:
        pos = data.index(b"\x00", pos) + 1
    desc_start = pos
    desc, pos = _read_cstr(data, pos)
    bounds_off = pos
    left, bottom, right, top = struct.unpack_from("<4i", data, bounds_off)
    pos += 16
    if version >= 19:
        pos += 4
    if version >= 14:
        pos += 4
        pos = data.index(b"\x00", pos) + 1
    if version >= 23:
        bar_len = struct.unpack_from("<H", data, pos)[0]
        pos += 2 + bar_len
    if version >= 20:
        pos += 24
    if version >= 35:
        pos = data.index(b"\x00", pos) + 1
        locale_len = struct.unpack_from("<H", data, pos)[0]
        pos += 2 + locale_len
    if version >= 39:
        str_len = struct.unpack_from("<H", data, pos)[0]
        pos += 2 + str_len
    flags_off = pos
    flags = struct.unpack_from("<I", data, flags_off)[0]
    flags &= ~0x02
    struct.pack_into("<I", data, flags_off, flags)
    popcount = bin(flags).count("1")
    dx, dy = right - left, top - bottom
    width, height = struct.unpack_from("<II", data, 16)
    hash_value = (
        len(desc)
        + 7 * height
        + 2 * (dx * dx + dy * dy)
        + 3 * width
        - popcount
        - 17
    )
    struct.pack_into("<Q", data, 8, hash_value)
    path.write_bytes(bytes(data))


def patch_banklist(path: Path) -> None:
    text = path.read_text()
    if BANK_NAME in text:
        return
    text = text.replace("</BankList>", f'    <Bank Name="{BANK_NAME}" Player="1"/>\n</BankList>')
    path.write_text(text)


def patch_script(path: Path) -> None:
    text = path.read_text()
    if "gt_DbgTest_Func" in text:
        return
    text = text.replace(
        "unit[8] gv_tPSUNIT;",
        "unit[8] gv_tPSUNIT;\nbank gv_dbgBank;\nunit gv_dbgA;\nunit gv_dbgB;\nunit gv_dbgC;\nunit gv_dbgD;",
        1,
    )
    text = text.replace(
        "trigger gt_DisableCloakingField;",
        "trigger gt_DisableCloakingField;\ntrigger gt_DbgTest;",
        1,
    )
    anchor = (
        "//--------------------------------------------------------------------------------------------------\n"
        "// Trigger Initialization\n"
        "//--------------------------------------------------------------------------------------------------\n"
        "void InitTriggers () {"
    )
    if anchor not in text:
        raise SystemExit("InitTriggers anchor not found")
    text = text.replace(anchor, HARNESS + anchor, 1)
    text = text.replace(
        "void InitTriggers () {\n    gt_MapInit_Init();",
        "void InitTriggers () {\n    gt_DbgTest_Init();\n    gt_MapInit_Init();",
        1,
    )
    path.write_text(text)


def patch_script_modules(root: Path) -> None:
    main_path = root / "scripts" / "app" / "main.galaxy"
    if not main_path.is_file():
        return
    text = main_path.read_text(encoding="utf-8")
    if "gt_DbgTest_Func" in text:
        return
    globals_path = root / "scripts" / "app" / "core" / "globals.galaxy"
    globals_text = globals_path.read_text(encoding="utf-8")
    globals_text = globals_text.replace(
        "unit[8] gv_tPSUNIT;",
        "unit[8] gv_tPSUNIT;\nbank gv_dbgBank;\nunit gv_dbgA;\nunit gv_dbgB;\nunit gv_dbgC;\nunit gv_dbgD;",
        1,
    )
    globals_text = globals_text.replace(
        "trigger gt_DisableCloakingField;",
        "trigger gt_DisableCloakingField;\ntrigger gt_DbgTest;",
        1,
    )
    globals_path.write_text(globals_text, encoding="utf-8")
    anchor = "void main () {\n    InitGlobals();"
    if anchor not in text:
        raise SystemExit("main anchor not found")
    text = text.replace(anchor, HARNESS + "\n" + anchor, 1)
    text = text.replace(
        anchor,
        "void main () {\n    InitGlobals();\n    gt_DbgTest_Init();",
        1,
    )
    main_path.write_text(text, encoding="utf-8")


def main() -> int:
    if not SRC.is_dir():
        raise SystemExit(f"missing expanded map: {SRC}")
    if DST.exists():
        shutil.rmtree(DST)
    shutil.copytree(SRC, DST)
    if os.environ.get("ZERO_PNP") == "1":
        for path in DST.glob("CellAttribute_*"):
            data = bytearray(path.read_bytes())
            if len(data) <= 4:
                continue
            struct.pack_into("<I", data, 0, (len(data) - 4) * 8)
            data[4:] = b"\x00" * (len(data) - 4)
            path.write_bytes(bytes(data))
    if os.environ.get("ADD_PATHING") == "1":
        n = 256
        body = bytearray(n * n * 2)
        for y in range(n):
            for x in range(n):
                v = 0x23 if (x < 2 or y < 2 or x >= n - 2 or y >= n - 2) else 0
                struct.pack_into("<H", body, (y * n + x) * 2, v)
        header = struct.pack("<4sIII", b"PATH", 100, n, n) + b"\x00" * 16
        (DST / "t3SyncPathingInfo").write_bytes(header + bytes(body))
    if os.environ.get("ZERO_FLAGS") == "1":
        path = DST / "t3CellFlags"
        data = bytearray(path.read_bytes())
        data[32:] = b"\x00" * (len(data) - 32)
        path.write_bytes(bytes(data))
    patch_mapinfo(DST / "MapInfo")
    patch_banklist(DST / "BankList.xml")
    if (DST / "scripts" / "app" / "main.galaxy").is_file():
        patch_script_modules(DST)
    else:
        patch_script(DST / "MapScript.galaxy")
    print(DST)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from pathlib import Path
import os
import sys
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from project_root import project_root

ROOT = project_root()
SRC = ROOT / "src" / "SCOBA.SC2Map"
DST = ROOT / "out" / "SCOBA128TEST.SC2Map"

HARNESS = '''void gf_DbgLogUnit (bank lp_bank, string lp_section, unit lp_unit) {
    if (UnitIsValid(lp_unit)) {
        BankValueSetFromInt(lp_bank, lp_section, "x", FixedToInt(PointGetX(UnitGetPosition(lp_unit))));
        BankValueSetFromInt(lp_bank, lp_section, "y", FixedToInt(PointGetY(UnitGetPosition(lp_unit))));
    }
}

bool gt_DbgTest_Func (bool testConds, bool runActions) {
    int lv_i;
    if (!runActions) { return true; }
    Wait(3.0, c_timeGame);
    gv_dbgBank = BankLoad("SCOBATEST", 1);
    BankValueSetFromInt(gv_dbgBank, "meta", "done", 0);
    BankValueSetFromInt(gv_dbgBank, "meta", "tick", -1);
    BankSave(gv_dbgBank);
    libNtve_gf_CreateUnitsAtPoint2(1, "Marine", 0, 1, Point(75.0, 64.0));
    gv_dbgA = UnitLastCreated();
    libNtve_gf_CreateUnitsAtPoint2(1, "Zergling", 0, 7, Point(75.0, 64.0));
    gv_dbgB = UnitLastCreated();
    UnitSetState(gv_dbgA, c_unitStateInvulnerable, true);
    UnitSetState(gv_dbgB, c_unitStateInvulnerable, true);
    UnitIssueOrder(gv_dbgA, OrderTargetingPoint(AbilityCommand("move", 0), Point(3.0, 64.0)), c_orderQueueReplace);
    UnitIssueOrder(gv_dbgB, OrderTargetingPoint(AbilityCommand("move", 0), Point(3.0, 64.0)), c_orderQueueReplace);
    for (lv_i = 0; lv_i < 60; lv_i += 1) {
        BankValueSetFromInt(gv_dbgBank, "meta", "tick", lv_i);
        gf_DbgLogUnit(gv_dbgBank, "P1", gv_dbgA);
        gf_DbgLogUnit(gv_dbgBank, "P7", gv_dbgB);
        BankSave(gv_dbgBank);
        Wait(0.5, c_timeGame);
    }
    BankValueSetFromInt(gv_dbgBank, "meta", "done", 1);
    gf_DbgLogUnit(gv_dbgBank, "P1", gv_dbgA);
    gf_DbgLogUnit(gv_dbgBank, "P7", gv_dbgB);
    BankSave(gv_dbgBank);
    return true;
}

void gt_DbgTest_Init () {
    gt_DbgTest = TriggerCreate("gt_DbgTest_Func");
    TriggerAddEventMapInit(gt_DbgTest);
}

'''


def main() -> int:
    if DST.exists():
        shutil.rmtree(DST)
    shutil.copytree(SRC, DST)
    script = DST / "MapScript.galaxy"
    text = script.read_text(encoding="utf-8")
    anchor = 'include "scripts/main"'
    assert anchor in text
    text = text.replace(anchor, anchor + "\n\n" + HARNESS, 1)
    line = "unit[8] gv_tPSUNIT;"
    assert line in text
    text = text.replace(line, line + "\nbank gv_dbgBank;\nunit gv_dbgA;\nunit gv_dbgB;", 1)
    line = "trigger gt_DisableCloakingField;"
    assert line in text
    text = text.replace(line, line + "\ntrigger gt_DbgTest;", 1)
    line = "void InitTriggers () {"
    assert line in text
    text = text.replace(line, line + "\n    gt_DbgTest_Init();", 1)
    script.write_text(text, encoding="utf-8")
    banklist = ROOT / "out" / "SCOBA256.SC2Map" / "BankList.xml"
    shutil.copyfile(banklist, DST / "BankList.xml")
    print("built", DST)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

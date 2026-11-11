from pathlib import Path
import os
import sys
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from project_root import project_root

ROOT = project_root()
SRC = ROOT / "src" / "SCOBA.SC2Map"
DST = ROOT / "out" / "SCOBA128GRID.SC2Map"

HARNESS = '''bool gt_DbgTest_Func (bool testConds, bool runActions) {
    int lv_i;
    int lv_x;
    int lv_y;
    if (!runActions) { return true; }
    Wait(2.0, c_timeGame);
    gv_dbgBank = BankLoad("SCOBATEST", 1);
    BankValueSetFromInt(gv_dbgBank, "meta", "done", 0);
    lv_i = 0;
    for (lv_y = 0; lv_y < 33; lv_y += 1) {
        for (lv_x = 0; lv_x < 33; lv_x += 1) {
            if (PointPathingPassable(Point(IntToFixed(4 + lv_x * 3), IntToFixed(4 + lv_y * 3)))) {
                BankValueSetFromInt(gv_dbgBank, "grid", IntToString(lv_i), 1);
            } else {
                BankValueSetFromInt(gv_dbgBank, "grid", IntToString(lv_i), 0);
            }
            lv_i = lv_i + 1;
        }
    }
    BankValueSetFromInt(gv_dbgBank, "meta", "done", 1);
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
    text = text.replace(line, line + "\nbank gv_dbgBank;", 1)
    line = "trigger gt_DisableCloakingField;"
    text = text.replace(line, line + "\ntrigger gt_DbgTest;", 1)
    line = "void InitTriggers () {"
    text = text.replace(line, line + "\n    gt_DbgTest_Init();", 1)
    script.write_text(text, encoding="utf-8")
    print("built", DST)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

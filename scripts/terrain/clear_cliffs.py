import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import workpaths


def main() -> None:
    p = workpaths.path("SC2_BUILT_MAP") / "t3Terrain.xml"
    text = p.read_text(encoding="utf-8")
    new = re.sub(
        r'<cliffCellList num="\d+" numOccupied="\d+">.*?</cliffCellList>',
        '<cliffCellList num="16384" numOccupied="0">\n        </cliffCellList>',
        text,
        flags=re.S,
    )
    p.write_text(new, encoding="utf-8")
    print("cliffs cleared", len(text), "->", len(new))


if __name__ == "__main__":
    main()

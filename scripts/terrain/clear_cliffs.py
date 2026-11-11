from pathlib import Path
import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from project_root import project_root

MAP = project_root() / "out" / "SCOBA256.SC2Map"
p = MAP / "t3Terrain.xml"
text = p.read_text(encoding="utf-8")
new = re.sub(r'<cliffCellList num="\d+" numOccupied="\d+">.*?</cliffCellList>',
             '<cliffCellList num="16384" numOccupied="0">\n        </cliffCellList>',
             text, flags=re.S)
p.write_text(new, encoding="utf-8")
print("cliffs cleared", len(text), "->", len(new))

"""Copy the built map to SCOBA256_mix and swap in NOTD refs from SC2_TMP/notd_<name>."""

import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import workpaths


def main() -> None:
    dst = workpaths.path("SC2_OUT") / "SCOBA256_mix.SC2Map"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(workpaths.path("SC2_BUILT_MAP"), dst)
    for name in sys.argv[1:]:
        ref = workpaths.path("SC2_TMP") / f"notd_{name}"
        if not ref.exists() or ref.stat().st_size < 100:
            raise SystemExit(f"no notd ref for {name}")
        shutil.copyfile(ref, dst / name)
        print("swapped in NOTD", name)
    print("built", dst)


if __name__ == "__main__":
    main()

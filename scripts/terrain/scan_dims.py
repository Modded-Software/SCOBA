import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import workpaths


def main() -> None:
    for p in sorted(workpaths.path("SC2_BUILT_MAP").iterdir()):
        if not p.is_file():
            continue
        data = p.read_bytes()
        hits = []
        for off in range(0, min(96, len(data) - 3), 1):
            v = struct.unpack_from("<I", data, off)[0]
            if v in (128, 129):
                hits.append((off, v))
        if hits:
            print(p.name, "size", len(data), "128/129 at", hits)


if __name__ == "__main__":
    main()

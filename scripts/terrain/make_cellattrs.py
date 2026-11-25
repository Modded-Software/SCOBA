import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import workpaths

SIZE = 256


def main() -> None:
    built = workpaths.path("SC2_BUILT_MAP")
    bits = SIZE * SIZE * 8
    for name in ["CellAttribute_Pcl", "CellAttribute_Pgr", "CellAttribute_Pnb"]:
        data = bytearray(4 + SIZE * SIZE)
        struct.pack_into("<I", data, 0, bits)
        (built / name).write_bytes(bytes(data))
        print("wrote", name, len(data))


if __name__ == "__main__":
    main()

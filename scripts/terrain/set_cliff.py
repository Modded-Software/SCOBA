import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import workpaths


def main() -> None:
    value = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    p = workpaths.path("SC2_BUILT_MAP") / "t3SyncCliffLevel"
    data = bytearray(p.read_bytes())
    w, h = struct.unpack_from("<II", data, 8)
    for i in range(w * h):
        struct.pack_into("<H", data, 32 + i * 2, value)
    p.write_bytes(bytes(data))
    print("cliff set", value, w, h)


if __name__ == "__main__":
    main()

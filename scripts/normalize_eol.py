from pathlib import Path
import sys


def normalize(path: Path, eol: str) -> None:
    data = path.read_bytes()
    text = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    if eol == "crlf":
        text = text.replace(b"\n", b"\r\n")
    path.write_bytes(text)


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[2] not in {"lf", "crlf"}:
        print("usage: normalize_eol.py <file> <lf|crlf>")
        return 2
    normalize(Path(argv[1]), argv[2])
    print(f"normalized {argv[1]} to {argv[2]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

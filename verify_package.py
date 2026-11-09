"""Check that the code in this package is byte-identical (LF) to the code pinned before each study run.

Usage: python verify_package.py
Exit code 0 if every pinned script hash matches the packaged file, 1 otherwise.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESEARCH = ROOT / "code" / "backend" / "scripts" / "research"
PINS = ["03-s3-code-pin.json", "03-s3-hourly-pin.json", "03-s3-d4s-pin.json", "04-s4-fs-pin.json", "05-s5-pin.json",
        "08-s4ext-pin-A3_1.json", "12-v2-pin.json"]
SCRIPTS = ROOT / "code" / "backend" / "scripts"


def sha256_lf(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def main() -> int:
    ok = True
    for pin_name in PINS:
        pin = json.loads((ROOT / "study" / pin_name).read_text(encoding="utf-8"))
        for name, expected in pin.items():
            if not name.endswith(".py"):
                continue
            path = RESEARCH / name if (RESEARCH / name).exists() else SCRIPTS / name
            actual = sha256_lf(path)
            match = actual == expected
            ok &= match
            print(f"{'OK  ' if match else 'FAIL'} {pin_name}: {name}")
    for record in json.loads((ROOT / "code" / "SOURCES.json").read_text(encoding="utf-8")):
        match = sha256_lf(ROOT / record["path"]) == record["sha256_lf"]
        ok &= match
        print(f"{'OK  ' if match else 'FAIL'} SOURCES.json: {record['path']} @ {record['source_commit']}")
    print("all code files match" if ok else "MISMATCH")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

"""Read-only: SHA-256 of every input file listed in 03-freeze.json (pre-outcome freeze addendum)."""
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

freeze = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
started = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
rows = []
for item in freeze["input_inventory"]:
    h = hashlib.sha256()
    with open(item["path"], "rb") as fh:
        for block in iter(lambda: fh.read(8 * 1024 * 1024), b""):
            h.update(block)
    rows.append({"year": item["year"], "month": item["month"], "path": item["path"], "bytes": item["bytes"], "sha256": h.hexdigest()})
    print(item["year"], item["month"], flush=True)
Path(sys.argv[2]).write_text(json.dumps({
    "schema": "auth003-s3-input-sha256-v1", "freeze_input_inventory_sha256": freeze["input_inventory_sha256"],
    "started_utc": started, "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    "note": "Computed before any S3 outcome.", "files": rows}, indent=1), encoding="utf-8")

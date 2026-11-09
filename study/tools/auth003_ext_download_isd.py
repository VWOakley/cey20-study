"""AUTH-003 S4 part 2, stage A: download NOAA ISD Global Hourly files for California candidate stations.

Usage:
  python -B auth003_ext_download_isd.py --station-metadata <station_metadata.csv> --states-zip <cb_2024_us_state_500k.zip>
      --out <E:/40_work/AUTH-003_external-comparison/raw> [--workers 4]

Candidates: preferred_source == "NOAA ISD" and coordinates inside the California polygon (spec section 2).
Downloads isd-history.csv (NCEI) and Global Hourly <year>/<USAF><WBAN>.csv for 2006-2025 from the NOAA Open Data
bucket on AWS (amendment A1: the NCEI access path now redirects there). Every file is checked to start with the
expected CSV header; anything else is recorded as invalid_content and not written. Existing files are never
overwritten (append only). Writes raw/inventory_isd_s3.json (url, path, bytes, sha256, retrieved_utc, status) and
raw/candidates_isd.csv. No credentials are involved.
"""
import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import shapefile  # pyshp
from shapely.geometry import Point, shape

YEARS = range(2006, 2026)
HISTORY_URL = "https://www.ncei.noaa.gov/pub/data/noaa/isd-history.csv"
HOURLY_URL = "https://noaa-global-hourly-pds.s3.amazonaws.com/{year}/{sid}.csv"  # NCEI access path redirects here (amendment A1)
UA = {"User-Agent": "climetry-research-AUTH-003 (non-commercial study download)"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def california(states_zip: Path):
    with zipfile.ZipFile(states_zip) as z:
        base = next(n[:-4] for n in z.namelist() if n.endswith(".shp"))
        r = shapefile.Reader(shp=io.BytesIO(z.read(base + ".shp")), dbf=io.BytesIO(z.read(base + ".dbf")),
                             shx=io.BytesIO(z.read(base + ".shx")))
        for rec, shp in zip(r.records(), r.shapes()):
            if rec.as_dict().get("STUSPS") == "CA":
                return shape(shp.__geo_interface__)
    raise SystemExit("California polygon not found")


def fetch(url: str, path: Path, magic: bytes = b"") -> dict:
    row = {"url": url, "path": path.as_posix()}
    if path.exists():
        row.update(status="present", bytes=path.stat().st_size, sha256=sha256(path))
        return row
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as resp:
                data = resp.read()
            if magic and not data.startswith(magic):
                row.update(status="invalid_content", bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
                return row
            tmp = path.with_suffix(path.suffix + ".part")
            tmp.write_bytes(data)
            tmp.rename(path)
            row.update(status="downloaded", bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                       retrieved_utc=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"))
            return row
        except urllib.error.HTTPError as e:
            if e.code == 404:
                row.update(status="not_available", http=404)
                return row
            err = f"HTTP {e.code}"
        except Exception as e:  # network errors: retry
            err = type(e).__name__
        time.sleep(5 * (attempt + 1))
    row.update(status="failed", error=err)
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--station-metadata", type=Path, required=True)
    ap.add_argument("--states-zip", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    isd = a.out / "isd_s3"
    isd.mkdir(parents=True, exist_ok=True)
    inventory = [fetch(HISTORY_URL, a.out / "isd" / "isd-history.csv", b'"USAF"')]
    ca = california(a.states_zip)
    with a.station_metadata.open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["preferred_source"] == "NOAA ISD"
                and ca.contains(Point(float(r["longitude"]), float(r["latitude"])))]
    with (a.out / "candidates_isd.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} candidate stations inside California")
    jobs = []
    for r in rows:
        _, usaf, wban = r["station_id"].split("_")
        for y in YEARS:
            (isd / str(y)).mkdir(exist_ok=True)
            jobs.append((HOURLY_URL.format(year=y, sid=usaf + wban), isd / str(y) / f"{usaf}{wban}.csv"))
    with ThreadPoolExecutor(a.workers) as ex:
        inventory += list(ex.map(lambda j: fetch(*j, b'"STATION"'), jobs))
    (a.out / "inventory_isd_s3.json").write_text(json.dumps(inventory, indent=1), encoding="utf-8")
    counts = {}
    for row in inventory:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    print(counts, round(sum(r.get("bytes", 0) for r in inventory) / 1e9, 2), "GB")


if __name__ == "__main__":
    main()

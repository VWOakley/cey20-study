"""AUTH-003 S4 part 2, stage B: retrieve PVGIS-TMY and NSRDB GOES TMY v4.0.0 for the eligible stations
(products frozen in amendment A2).

Usage:
  python -B -I auth003_ext_download_tmy.py --prepared <.../prepared> --raw <.../raw> --secrets <secrets .env>

Station coordinates: the most frequent (latitude, longitude) of the station's used ISD segment (spec 2.2). The NREL
API key and e-mail are read from the secrets file (NREL_API_KEY, NREL_USERNAME) into memory only; they never appear
in files, logs or the inventory. Existing files are not overwritten. Writes raw/inventory_tmy.json.
"""
import argparse
import csv
import datetime as dt
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

PVGIS = "https://re.jrc.ec.europa.eu/api/v5_3/tmy"
PVGIS_PARAMS = {"raddatabase": "PVGIS-ERA5", "startyear": "2006", "endyear": "2023", "outputformat": "json"}
NSRDB = "https://developer.nlr.gov/api/nsrdb/v2/solar/nsrdb-GOES-tmy-v4-0-0-download.csv"
NSRDB_PARAMS = {"names": "tmy-2024", "attributes": "air_temperature,dew_point,relative_humidity",
                "utc": "true", "leap_day": "false", "interval": "60"}
UA = {"User-Agent": "climetry-research-AUTH-003 (non-commercial study)"}


def secrets(path: Path) -> dict:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            if k.strip() in ("NREL_API_KEY", "NREL_USERNAME"):
                out[k.strip()] = v.strip().strip('"').strip("'")
    if set(out) != {"NREL_API_KEY", "NREL_USERNAME"}:
        raise SystemExit("NREL_API_KEY / NREL_USERNAME missing in the secrets file")
    return out


def station_location(raw: Path, sid: str, segment: str) -> tuple[float, float]:
    usaf_wban = "".join(sid.split("_")[1:])
    files = sorted((raw / "isd_s3").glob(f"*/{usaf_wban}.csv"))
    if segment:                                   # "YYYY-MM-DD..YYYY-MM-DD (...)": use files inside the segment
        first, last = int(segment[:4]), int(segment[12:16])
        files = [f for f in files if first <= int(f.parent.name) <= last]
    counts = Counter()
    with files[-1].open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            counts[(float(r["LATITUDE"]), float(r["LONGITUDE"]))] += 1
    return counts.most_common(1)[0][0]


def get(url: str, params: dict, timeout: int = 180) -> bytes:
    req = urllib.request.Request(url + "?" + urllib.parse.urlencode(params), headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prepared", type=Path, required=True)
    ap.add_argument("--raw", type=Path, required=True)
    ap.add_argument("--secrets", type=Path, required=True)
    a = ap.parse_args()
    cred = secrets(a.secrets)
    (a.raw / "pvgis").mkdir(exist_ok=True)
    (a.raw / "nsrdb").mkdir(exist_ok=True)
    with (a.prepared / "stations.csv").open(encoding="utf-8") as f:
        stations = [r for r in csv.DictReader(f) if r["status"] == "eligible"]
    inventory = []
    for st in stations:
        sid = st["station_id"]
        lat, lon = station_location(a.raw, sid, st.get("segment_used", ""))
        for source, url, params, path, magic in (
                ("pvgis", PVGIS, {**PVGIS_PARAMS, "lat": f"{lat:.5f}", "lon": f"{lon:.5f}"},
                 a.raw / "pvgis" / f"{sid}.json", b"{"),
                ("nsrdb", NSRDB, {**NSRDB_PARAMS, "wkt": f"POINT({lon:.5f} {lat:.5f})"},
                 a.raw / "nsrdb" / f"{sid}.csv", b"Source")):
            row = {"station_id": sid, "source": source, "endpoint": url, "params": params, "path": path.as_posix()}
            if path.exists():
                data = path.read_bytes()
                row.update(status="present")
            else:
                full = dict(params)
                if source == "nsrdb":
                    full.update(api_key=cred["NREL_API_KEY"], email=cred["NREL_USERNAME"])
                data, err = None, None
                for attempt in range(3):
                    try:
                        data = get(url, full)
                        break
                    except urllib.error.HTTPError as e:
                        err = f"HTTP {e.code}"
                    except Exception as e:  # network
                        err = type(e).__name__
                    time.sleep(10 * (attempt + 1))
                if data is None:
                    row.update(status="failed", error=err)
                    inventory.append(row)
                    print(sid, source, "failed", err, flush=True)
                    continue
                if not data.lstrip().startswith(magic):
                    row.update(status="invalid_content", bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                               head=data[:200].decode("utf-8", "replace"))
                    inventory.append(row)
                    print(sid, source, "invalid content", flush=True)
                    time.sleep(2)
                    continue
                path.write_bytes(data)
                row.update(status="downloaded",
                           retrieved_utc=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"))
                time.sleep(2)                     # NSRDB: at most 1 CSV request per second
            row.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
            inventory.append(row)
            print(sid, source, row["status"], len(data), flush=True)
    (a.raw / "inventory_tmy.json").write_text(json.dumps(inventory, indent=1), encoding="utf-8")
    print(Counter((r["source"], r["status"]) for r in inventory))


if __name__ == "__main__":
    main()

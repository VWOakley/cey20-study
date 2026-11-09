"""AUTH-003 S4 part 2, stage A feasibility: parse NOAA ISD Global Hourly files into paired hourly T/Td series and
report completeness, eligibility and station history (spec 08, sections 2.1-2.3; amendment A1). Outcome-blind: no
candidate (CEY20, ERA5-Land, PVGIS, NSRDB) is read and no comparison metric is computed.

Usage:
  python -B auth003_ext_isd_prepare.py --raw <.../raw> --out <.../prepared>

Writes per station `<out>/hourly/<id>.npz` (slot index 0..175199 over 2006-2025 without 29 Feb, T, Td, offset in
minutes, all for selected slots only) and `<out>/stations.csv`, `<out>/completeness.csv`, `<out>/funnel.json`.
"""
import argparse
import csv
import datetime as dt
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

YEARS = list(range(2006, 2026))
MONTH_HOURS = [744, 672, 744, 720, 744, 720, 744, 744, 720, 744, 720, 744]
ACCEPT_QC = set("01459")                 # NCEI: passed / not checked; others rejected (spec 2.1)
ACCEPT_REPORT = {"FM-15", "FM-12"}       # METAR and SYNOP
T_RANGE, TD_RANGE = (-70.0, 60.0), (-75.0, 45.0)
MIN_COMPLETENESS, MIN_YEARS = 0.80, 15
RELOC_KM, ELEV_M = 1.0, 50.0


def year_slot_offset(year: int) -> int:
    return 8760 * YEARS.index(year)


def slot_of(t: dt.datetime) -> int | None:
    """Slot index of a UTC datetime on the 365-day calendar, None for 29 February or outside the period."""
    if t.year not in YEARS or (t.month == 2 and t.day == 29):
        return None
    doy = sum(MONTH_HOURS[: t.month - 1]) // 24 + t.day - 1
    return year_slot_offset(t.year) + doy * 24 + t.hour


def value(field: str, scale: float = 10.0):
    """'+0123,1' -> (12.3, '1'); sentinel or malformed -> (None, qc)."""
    if not field or "," not in field:
        return None, ""
    v, qc = field.split(",", 1)
    v = v.strip()
    if v in {"+9999", "-9999", "9999"}:
        return None, qc.strip()
    try:
        return int(v) / scale, qc.strip()
    except ValueError:
        return None, qc.strip()


def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def parse_station(files: list[Path], counters: Counter) -> tuple[dict, list]:
    """Return {slot: (offset_min, ts, order, T, Td)} of selected observations and the location records."""
    seen, best, locs, order = set(), {}, [], 0
    for path in files:
        with path.open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                counters["rows_read"] += 1
                key = tuple(r.get(k, "") for k in ("DATE", "REPORT_TYPE", "TMP", "DEW", "SOURCE"))
                if key in seen:
                    counters["exact_duplicates"] += 1
                    continue
                seen.add(key)
                order += 1
                try:
                    lat, lon, elev = float(r["LATITUDE"]), float(r["LONGITUDE"]), float(r["ELEVATION"])
                    ts = dt.datetime.fromisoformat(r["DATE"])
                except (KeyError, ValueError):
                    counters["unparseable_rows"] += 1
                    continue
                locs.append((ts, lat, lon, elev))
                if r.get("REPORT_TYPE", "").strip() not in ACCEPT_REPORT:
                    counters["report_type_dropped"] += 1
                    continue
                t, tq = value(r.get("TMP", ""))
                d, dq = value(r.get("DEW", ""))
                if t is None or tq not in ACCEPT_QC or not T_RANGE[0] <= t <= T_RANGE[1]:
                    counters["t_invalid"] += 1
                    continue
                if d is None or dq not in ACCEPT_QC or not TD_RANGE[0] <= d <= TD_RANGE[1] or d > t + 1.0:
                    counters["td_invalid"] += 1
                    continue
                base = ts.replace(minute=0, second=0, microsecond=0)
                slot_t = base + dt.timedelta(hours=1) if ts.minute >= 30 else base
                s = slot_of(slot_t)
                if s is None:
                    counters["outside_period_or_29feb"] += 1
                    continue
                off = abs((ts - slot_t).total_seconds()) / 60.0
                cand = (off, ts, order, t, d)
                if s in best:
                    counters["slot_conflicts"] += 1
                    if cand[:3] == best[s][:3]:
                        counters["selection_ties"] += 1
                    if cand[:3] < best[s][:3]:
                        best[s] = cand
                else:
                    best[s] = cand
    return best, locs


def segments(locs: list) -> list[dict]:
    """Location segments in time order; a new segment starts at a move > RELOC_KM or elevation change > ELEV_M."""
    locs.sort(key=lambda x: x[0])
    segs = []
    for ts, lat, lon, elev in locs:
        if segs and km((lat, lon), segs[-1]["loc"]) <= RELOC_KM and abs(elev - segs[-1]["elev"]) <= ELEV_M:
            segs[-1]["end"] = ts
            continue
        segs.append(dict(start=ts, end=ts, loc=(lat, lon), elev=elev))
    return segs


def completeness(slots: np.ndarray) -> np.ndarray:
    """(20 years, 12 months) share of paired hours."""
    have = np.zeros(20 * 8760, bool)
    have[slots] = True
    out = np.zeros((20, 12))
    for y in range(20):
        start = y * 8760
        for m in range(12):
            h0 = start + sum(MONTH_HOURS[:m])
            out[y, m] = have[h0:h0 + MONTH_HOURS[m]].mean()
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    (a.out / "hourly").mkdir(parents=True, exist_ok=True)
    with (a.raw / "candidates_isd.csv").open(encoding="utf-8") as f:
        cands = list(csv.DictReader(f))
    funnel, stations, comp_rows = Counter(candidates=len(cands)), [], []
    for c in cands:
        sid = "".join(c["station_id"].split("_")[1:])
        files = sorted((a.raw / "isd_s3").glob(f"*/{sid}.csv"))
        counters = Counter()
        best, locs = parse_station(files, counters) if files else ({}, [])
        segs = segments(locs)
        moved = len(segs) > 1
        row = dict(station_id=c["station_id"], name=c["city"], lat=c["latitude"], lon=c["longitude"],
                   elev_m=c["elevation_m"], files=len(files), location_segments=len(segs),
                   **{k: counters[k] for k in ("rows_read", "exact_duplicates", "report_type_dropped", "t_invalid",
                                                 "td_invalid", "outside_period_or_29feb", "slot_conflicts",
                                                 "selection_ties", "unparseable_rows")})
        slots = np.array(sorted(best), dtype=np.int64)
        if moved and len(slots):
            # longest metadata-screened segment (ties: earliest start); keep it only if it is eligible on its own
            seg = max(segs, key=lambda s: ((s["end"] - s["start"]).total_seconds(), -s["start"].timestamp()))
            keep = np.array([seg["start"] <= best[s][1] <= seg["end"] for s in slots], bool)
            slots = slots[keep]
            row["segment_used"] = f'{seg["start"].date()}..{seg["end"].date()} {seg["loc"]} {seg["elev"]} m'
        comp = completeness(slots) if len(slots) else np.zeros((20, 12))
        usable_years = (comp >= MIN_COMPLETENESS).sum(axis=0)
        row["min_usable_years_per_month"] = int(usable_years.min())
        if not files:
            row["status"], row["reason"] = "excluded", "no data files"
        elif not len(slots):
            row["status"], row["reason"] = "excluded", "no paired hour"
        elif usable_years.min() < MIN_YEARS:
            row["status"], row["reason"] = "excluded", f"a calendar month has {int(usable_years.min())} < {MIN_YEARS} usable years"
        else:
            row["status"], row["reason"] = "eligible", ""
        funnel[row["status"]] += 1
        stations.append(row)
        for y in range(20):
            for m in range(12):
                comp_rows.append(dict(station_id=c["station_id"], year=YEARS[y], month=m + 1,
                                      completeness=round(float(comp[y, m]), 4), usable=bool(comp[y, m] >= MIN_COMPLETENESS)))
        if len(slots):
            sel = [best[s] for s in slots]
            np.savez_compressed(a.out / "hourly" / f"{c['station_id']}.npz", slot=slots,
                                t=np.array([x[3] for x in sel], np.float32), td=np.array([x[4] for x in sel], np.float32),
                                offset_min=np.array([x[0] for x in sel], np.float32))
    keys = sorted({k for r in stations for k in r}, key=lambda k: list(stations[0]).index(k) if k in stations[0] else 99)
    with (a.out / "stations.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(stations)
    with (a.out / "completeness.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(comp_rows[0]))
        w.writeheader()
        w.writerows(comp_rows)
    (a.out / "funnel.json").write_text(json.dumps(dict(funnel), indent=1), encoding="utf-8")
    print(dict(funnel))


if __name__ == "__main__":
    main()

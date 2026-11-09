"""AUTH-003 S4 part 2: external comparison at California NOAA ISD stations (spec 08 r3, amendments A1, A2, A2.1).

Candidates per eligible station: C1 CEY20 v2 (S10 build), C2_full ERA5-Land 20-year climatology at the same point,
C2_matched ERA5-Land on the station's observed paired-hour slots, C3 PVGIS-TMY, C4 NSRDB GOES TMY v4.0.0. Yardstick:
the estimated station climatology (spec section 3) with missing-data bounds and an hour-of-day sensitivity reference.
The study's thresholds are applied unchanged as external diagnostics; results are descriptive.

Usage:
  python -B auth003_s4ext_compare.py --work <E:/40_work/AUTH-003_external-comparison> --s10 <S10 build dir>
      --freeze <03-freeze.json> --input-hashes <03-freeze-input-sha256.json> --koppen-tif <tif> --pin <pin.json>
      --output <new empty dir>
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path

import netCDF4
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import auth003_s3 as R  # noqa: E402
import auth003_study as S  # noqa: E402

YEARS = list(S.YEARS)
MONTH_HOURS = [744, 672, 744, 720, 744, 720, 744, 744, 720, 744, 720, 744]
MONTH_START = np.concatenate([[0], np.cumsum(MONTH_HOURS)[:-1]]).astype(int)
METRICS = ("hours_rh_ge_80", "hours_rh_ge_90", "hours_dewpoint_depression_le_2c")
REL_TOL, T_TOL, RH_TOL = 0.05, 0.5, 2.0
MAX_MATCH_KM = 25.0
CANDIDATES = ("C1_cey20", "C2_full", "C2_matched", "C3_pvgis", "C4_nsrdb")
PINNED = ("auth003_s4ext_compare.py", "auth003_s3.py", "auth003_study.py")


# ----------------------------------------------------------------------------
# pure functions (unit-tested)
# ----------------------------------------------------------------------------

def rh_from(t: np.ndarray, td: np.ndarray) -> np.ndarray:
    """Study convention: builder Magnus over water, float32 before thresholds."""
    return S._relative_humidity_from_dewpoint(t, td).astype(np.float32)


def td_from_rh(t: np.ndarray, rh: np.ndarray) -> np.ndarray:
    """Invert the same Magnus form (17.67/243.5); RH <= 0 or > 100 gives NaN (reported, not clipped)."""
    t = np.asarray(t, np.float64)
    rh = np.asarray(rh, np.float64)
    ok = (rh > 0) & (rh <= 100) & np.isfinite(t)
    out = np.full(t.shape, np.nan)
    gamma = np.log(rh[ok] / 100.0) + 17.67 * t[ok] / (t[ok] + 243.5)
    out[ok] = 243.5 * gamma / (17.67 - gamma)
    return out.astype(np.float32)


def events(t: np.ndarray, td: np.ndarray) -> dict[str, np.ndarray]:
    rh = rh_from(t, td)
    return {"hours_rh_ge_80": rh >= 80.0, "hours_rh_ge_90": rh >= 90.0,
            "hours_dewpoint_depression_le_2c": (t - td) <= 2.0}


def month_slice(m: int) -> slice:
    return slice(MONTH_START[m - 1], MONTH_START[m - 1] + MONTH_HOURS[m - 1])


def year_stats(t: np.ndarray, td: np.ndarray, mask: np.ndarray | None = None, hour_of_day: np.ndarray | None = None):
    """Stats of one year (8760 h) per month on the hours where `mask` (and finite T, Td) holds.

    Returns per month: mean_t, mean_rh, and per metric event fraction, observed events, missing hours, and the
    hour-of-day equal-weight fraction (NaN if an hour of day has no observation)."""
    valid = np.isfinite(t) & np.isfinite(td)
    if mask is not None:
        valid &= mask
    ev = events(np.where(valid, t, 0.0), np.where(valid, td, 0.0))
    rh = rh_from(np.where(valid, t, 0.0), np.where(valid, td, 0.0))
    out = []
    for m in range(1, 13):
        s = month_slice(m)
        v = valid[s]
        n = int(v.sum())
        row = {"n": n, "expected": MONTH_HOURS[m - 1], "mean_t": float(np.mean(t[s][v])) if n else np.nan,
               "mean_rh": float(np.mean(rh[s][v])) if n else np.nan}
        hod = (np.arange(MONTH_HOURS[m - 1]) % 24) if hour_of_day is None else hour_of_day[s]
        for k in METRICS:
            e = ev[k][s] & v
            row[k + "_events"] = int(e.sum())
            row[k + "_frac"] = e.sum() / n if n else np.nan
            per_hour = [e[hod == h].sum() / v[hod == h].sum() if v[hod == h].sum() else np.nan for h in range(24)]
            row[k + "_frac_hod"] = float(np.mean(per_hour)) if np.all(np.isfinite(per_hour)) else np.nan
        out.append(row)
    return out


def climatology(stats_by_year: list[list[dict]], usable: np.ndarray) -> dict:
    """Equal-year-weighted calendar-month climatology over usable year-months (spec section 3).

    stats_by_year[y][m-1] from year_stats; usable (years, 12) bool. Monthly counts = expected x mean event fraction;
    annual = sum of months. Bounds: missing hours as non-events / as events. Sensitivity: hour-of-day fractions."""
    out = {"monthly": [], "annual": {}}
    ann = {k: 0.0 for k in METRICS}
    low = {k: 0.0 for k in METRICS}
    high = {k: 0.0 for k in METRICS}
    sens = {k: 0.0 for k in METRICS}
    for m in range(12):
        ys = [y for y in range(len(stats_by_year)) if usable[y, m]]
        rows = [stats_by_year[y][m] for y in ys]
        exp = MONTH_HOURS[m]
        rec = {"month": m + 1, "n_years": len(ys),
               "mean_t": float(np.mean([r["mean_t"] for r in rows])) if rows else np.nan,
               "mean_rh": float(np.mean([r["mean_rh"] for r in rows])) if rows else np.nan}
        for k in METRICS:
            frac = np.mean([r[k + "_frac"] for r in rows]) if rows else np.nan
            rec[k] = exp * frac
            ann[k] += rec[k]
            low[k] += np.mean([r[k + "_events"] for r in rows]) if rows else np.nan
            high[k] += np.mean([r[k + "_events"] + (exp - r["n"]) for r in rows]) if rows else np.nan
            hod = [r[k + "_frac_hod"] for r in rows]
            sens[k] += exp * np.mean(hod) if rows and np.all(np.isfinite(hod)) else np.nan
        out["monthly"].append(rec)
    for k in METRICS:
        out["annual"][k] = {"value": ann[k], "low": low[k], "high": high[k], "sensitivity_hod": sens[k]}
    return out


def tmy_stats(t: np.ndarray, td: np.ndarray, rh: np.ndarray | None = None) -> dict:
    """Single 8760-h year: monthly means and annual counts; `rh` overrides the RH used for RH metrics (PVGIS)."""
    valid = np.isfinite(t) & np.isfinite(td)
    rh_used = rh_from(t, td) if rh is None else np.asarray(rh, np.float32)
    ev = {"hours_rh_ge_80": (rh_used >= 80.0) & np.isfinite(rh_used),
          "hours_rh_ge_90": (rh_used >= 90.0) & np.isfinite(rh_used),
          "hours_dewpoint_depression_le_2c": ((t - td) <= 2.0) & valid}
    out = {"monthly": [], "annual": {}, "missing_hours": int((~valid).sum())}
    for m in range(1, 13):
        s = month_slice(m)
        out["monthly"].append({"month": m, "mean_t": float(np.nanmean(t[s])), "mean_rh": float(np.nanmean(rh_used[s])),
                               **{k: float(ev[k][s].sum()) for k in METRICS}})
    for k in METRICS:
        out["annual"][k] = {"value": float(ev[k].sum())}
    return out


def evaluate(cand: dict, ref: dict) -> tuple[list[dict], list[dict]]:
    """Annual (3 metrics) and monthly (12) checks of a candidate against a reference climatology."""
    annual = []
    for k in METRICS:
        c, r = cand["annual"][k]["value"], ref["annual"][k]["value"]
        rel = (c - r) / r if r else (0.0 if c == 0 else math.inf)
        annual.append({"metric": k, "value": c, "reference": r, "signed": c - r,
                       "rel_error": rel if r else None, "pass": bool(abs(rel) <= REL_TOL) if r else bool(c == 0)})
    monthly = []
    for cm, rm in zip(cand["monthly"], ref["monthly"]):
        d_t, d_rh = cm["mean_t"] - rm["mean_t"], cm["mean_rh"] - rm["mean_rh"]
        monthly.append({"month": cm["month"], "d_t": d_t, "d_rh": d_rh,
                        "pass_t": bool(abs(d_t) <= T_TOL), "pass_rh": bool(abs(d_rh) <= RH_TOL)})
    return annual, monthly


def great_circle_km(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * np.arcsin(np.sqrt(a))


def calendar_index(month: np.ndarray, day: np.ndarray, hour: np.ndarray) -> np.ndarray:
    """(month, day, hour) -> slot 0..8759 on the 365-day calendar; -1 for 29 February."""
    doy = MONTH_START[month - 1] // 24 + day - 1
    idx = doy * 24 + hour
    return np.where((month == 2) & (day == 29), -1, idx)


def place_8760(month, day, hour, *series) -> tuple[list[np.ndarray], dict]:
    """Put hourly series onto the 8760 calendar; report duplicates, gaps and dropped 29 February rows."""
    idx = calendar_index(np.asarray(month), np.asarray(day), np.asarray(hour))
    keep = idx >= 0
    report = {"rows": int(len(idx)), "feb29_dropped": int((~keep).sum())}
    idx = idx[keep]
    report["duplicates"] = int(len(idx) - len(np.unique(idx)))
    out = []
    for s in series:
        a = np.full(8760, np.nan, np.float32)
        a[idx] = np.asarray(s, np.float32)[keep]
        out.append(a)
    report["missing_slots"] = int(8760 - len(np.unique(idx)))
    return out, report


def require_complete_tmy(name: str, series: dict, rep: dict, utc_minutes: str | None = None) -> None:
    """Gate (review finding): a typical year must have exactly one row per non-leap slot, finite T and RH (and Td
    where supplied), and for NSRDB UTC rows stamped hh:30. Anything else aborts the run; nothing is repaired."""
    if rep["duplicates"] or rep["missing_slots"]:
        raise SystemExit(f"{name}: {rep['duplicates']} duplicate and {rep['missing_slots']} missing hourly slots")
    for k in ("t", "rh", "td"):                  # td is derived for PVGIS: RH <= 0 or > 100 gives NaN and aborts here
        if not np.all(np.isfinite(series[k])):
            raise SystemExit(f"{name}: non-finite {k}")
    if utc_minutes is not None:
        if str(rep.get("time_zone")) != "0" or set(rep.get("minutes", {})) != {utc_minutes}:
            raise SystemExit(f"{name}: not UTC rows at minute {utc_minutes} ({rep.get('time_zone')}, {rep.get('minutes')})")


def require_finite(name: str, stats: dict) -> None:
    vals = [stats["annual"][k]["value"] for k in METRICS] + [r[q] for r in stats["monthly"] for q in ("mean_t", "mean_rh")]
    if not np.all(np.isfinite(vals)):
        raise SystemExit(f"{name}: non-finite statistic")


# ----------------------------------------------------------------------------
# readers
# ----------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_pvgis(path: Path) -> tuple[dict, dict]:
    d = json.loads(path.read_text(encoding="utf-8"))
    rows = d["outputs"]["tmy_hourly"]
    stamp = [r["time(UTC)"] for r in rows]
    month = np.array([int(s[4:6]) for s in stamp])
    day = np.array([int(s[6:8]) for s in stamp])
    hour = np.array([int(s[9:11]) for s in stamp])
    (t, rh), rep = place_8760(month, day, hour, [r["T2m"] for r in rows], [r["RH"] for r in rows])
    rep["rh_out_of_domain"] = int(np.sum(~((rh > 0) & (rh <= 100)) & np.isfinite(rh)))
    rep["months_selected"] = d["outputs"].get("months_selected")
    rep["meta"] = {"location": d["inputs"]["location"], "meteo_data": d["inputs"]["meteo_data"]}
    return {"t": t, "td": td_from_rh(t, rh), "rh": rh}, rep


def read_nsrdb(path: Path) -> tuple[dict, dict]:
    with path.open(encoding="utf-8") as f:
        head = next(csv.reader([f.readline()]))
        meta_vals = next(csv.reader([f.readline()]))
        rows = list(csv.DictReader(f))
    meta = dict(zip(head, meta_vals))
    minutes = Counter(r["Minute"] for r in rows)
    month = np.array([int(r["Month"]) for r in rows])
    day = np.array([int(r["Day"]) for r in rows])
    hour = np.array([int(r["Hour"]) for r in rows])   # rows are stamped hh:30 UTC; assigned to slot hh (A2.1 note)
    (t, td, rh), rep = place_8760(month, day, hour, [float(r["Temperature"]) for r in rows],
                                  [float(r["Dew Point"]) for r in rows], [float(r["Relative Humidity"]) for r in rows])
    years = {}
    for r in rows:
        years.setdefault(int(r["Month"]), set()).add(int(r["Year"]))
    rep.update(minutes=dict(minutes), time_zone=meta.get("Time Zone"), site_lat=meta.get("Latitude"),
               site_lon=meta.get("Longitude"), site_elevation=meta.get("Elevation"),
               source_years={m: sorted(v) for m, v in sorted(years.items())})
    rh_cons = rh_from(t, td)
    rep["rh_consistency_max_abs_pp"] = float(np.nanmax(np.abs(rh_cons - rh)))
    return {"t": t, "td": td, "rh": rh}, rep


def station_hourly(npz: Path) -> tuple[np.ndarray, np.ndarray]:
    d = np.load(npz)
    t = np.full((20, 8760), np.nan, np.float32)
    td = np.full((20, 8760), np.nan, np.float32)
    y, h = np.divmod(d["slot"], 8760)
    t[y, h] = d["t"]
    td[y, h] = d["td"]
    return t, td


def koppen(tif: Path, legend: Path, points: list[tuple[float, float]]) -> list[str]:
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    names = {}
    for line in legend.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split()
        if parts and parts[0].endswith(":") and parts[0][:-1].isdigit():
            names[int(parts[0][:-1])] = parts[1]
    img = Image.open(tif)
    out = []
    for lat, lon in points:
        col, row = int(math.floor((lon + 180) * 120)), int(math.floor((90 - lat) * 120))
        out.append(names.get(int(img.getpixel((col, row))), "unknown"))
    return out


# ----------------------------------------------------------------------------
# run
# ----------------------------------------------------------------------------

def summarise(stations: list, station_rows: list[dict], annual_rows: list[dict], monthly_rows: list[dict]) -> dict:
    """Per-candidate summary of the annual and monthly checks; plain Python types only (json-serialisable)."""
    summary = {"label": "descriptive; transferred diagnostic thresholds against an estimated station climatology",
               "stations": len(stations), "distinct_s10_points": len({r["s10_point"] for r in station_rows if r["s10_point"] != ""})}
    for key in CANDIDATES:
        a_rows = [r for r in annual_rows if r["candidate"] == key and r["status"] == "ok"]
        m_rows = [r for r in monthly_rows if r["candidate"] == key]
        st_ok = {r["station_id"] for r in a_rows}
        summary[key] = {
            "stations_available": len(st_ok),
            "annual_pass": {k: [sum(r["pass"] for r in a_rows if r["metric"] == k), sum(1 for r in a_rows if r["metric"] == k)] for k in METRICS},
            "annual_under": {k: sum(bool(r["signed"] < 0) for r in a_rows if r["metric"] == k) for k in METRICS},
            "annual_median_rel_error": {k: float(np.median([r["rel_error"] for r in a_rows if r["metric"] == k and r["rel_error"] is not None]))
                                        for k in METRICS} if a_rows else None,
            "monthly_t_pass": [sum(r["pass_t"] for r in m_rows), len(m_rows)],
            "monthly_rh_pass": [sum(r["pass_rh"] for r in m_rows), len(m_rows)],
            "monthly_median_abs_d_t": float(np.median([abs(r["d_t"]) for r in m_rows])) if m_rows else None,
            "monthly_median_abs_d_rh": float(np.median([abs(r["d_rh"]) for r in m_rows])) if m_rows else None,
            "stations_all_12_t": sum(all(r["pass_t"] for r in m_rows if r["station_id"] == s) for s in st_ok),
            "stations_all_12_rh": sum(all(r["pass_rh"] for r in m_rows if r["station_id"] == s) for s in st_ok)}
    return summary


def verify_pin(pin: dict) -> None:
    here = Path(__file__).resolve().parent
    for name in PINNED:
        got = hashlib.sha256((here / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        if pin.get(name) != got:
            raise SystemExit(f"{name} does not match the pin")


def run(a) -> int:
    started = dt.datetime.now(dt.timezone.utc)
    out = Path(a.output)
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} is not empty")
    pin = json.loads(Path(a.pin).read_text(encoding="utf-8"))
    verify_pin(pin)
    work = Path(a.work)
    frozen = json.loads(Path(a.input_inventory).read_text(encoding="utf-8"))
    for rel, digest in frozen["files_sha256"].items():          # second freeze: station set, usability, hourly data
        if sha256_file(work / rel) != digest:
            raise SystemExit(f"{rel} differs from the frozen input inventory")
    # Gates: S10 files, TMY inventory, prepared station files, ERA5-Land inputs (before any metric).
    s10 = Path(a.s10)
    manifest = json.loads((s10 / "manifest.json").read_text(encoding="utf-8"))
    nc = s10 / "cey20_v2_california_points.nc"
    if sha256_file(nc) != manifest["output_sha256"][nc.name]:
        raise SystemExit("S10 dataset differs from its manifest")
    inv = {(r["station_id"], r["source"]): r for r in json.loads((work / "raw/inventory_tmy.json").read_text())}
    for r in inv.values():
        if r["status"] not in ("downloaded", "present") or sha256_file(Path(r["path"])) != r["sha256"]:
            raise SystemExit(f"TMY file {r['path']} is missing or differs from the inventory")
    with (work / "prepared/stations.csv").open(encoding="utf-8") as f:
        stations = [r for r in csv.DictReader(f) if r["status"] == "eligible"]
    if [r["station_id"] for r in stations] != frozen["eligible_station_ids"]:
        raise SystemExit("eligible stations differ from the frozen input inventory")
    usable_all, seen = {}, Counter()
    with (work / "prepared/completeness.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            usable_all.setdefault(r["station_id"], np.zeros((20, 12), bool))[YEARS.index(int(r["year"])), int(r["month"]) - 1] = r["usable"] == "True"
            seen[r["station_id"]] += 1
    for st in stations:
        u = usable_all.get(st["station_id"])
        if seen[st["station_id"]] != 240 or u is None or u.sum(axis=0).min() < 15:
            raise SystemExit(f"{st['station_id']}: completeness record incomplete or a month with < 15 usable years")
        if not (work / "prepared/hourly" / f"{st['station_id']}.npz").exists():
            raise SystemExit(f"{st['station_id']}: prepared hourly file missing")
    freeze = json.loads(Path(a.freeze).read_text(encoding="utf-8"))
    sources = S.discover_sources(S.builder.DEFAULT_EXTENSION_ROOT, S.builder.DEFAULT_LEGACY_ROOT, list(range(1, 13)))
    R.verify_inputs(sources, freeze)
    R.verify_input_hashes(sources, json.loads(Path(a.input_hashes).read_text(encoding="utf-8")), freeze)
    print("gates passed", flush=True)

    with netCDF4.Dataset(nc) as d:
        plat = np.asarray(d["latitude"][:], np.float64)
        plon = np.asarray(d["longitude"][:], np.float64)
        pidx = np.asarray(d["product_point_index"][:])
        ct = np.asarray(d["temperature_c"][:], np.float32)
        ctd = np.asarray(d["dewpoint_c"][:], np.float32)
    plon = np.where(plon > 180, plon - 360, plon)

    # station location = the coordinates used for the TMY requests (most frequent location of the used ISD segment)
    loc = {sid: (float(r["params"]["lat"]), float(r["params"]["lon"])) for (sid, src), r in inv.items() if src == "pvgis"}
    match = {}
    for st in stations:
        lat, lon = loc[st["station_id"]]
        dist = great_circle_km(lat, lon, plat, plon)
        j = int(np.argmin(dist))
        match[st["station_id"]] = (j, float(dist[j])) if dist[j] <= MAX_MATCH_KM else (None, float(dist[j]))
    cols = sorted({match[s][0] for s in match if match[s][0] is not None})
    era5 = {"t": np.full((20, 8760, len(cols)), np.nan, np.float32), "td": np.full((20, 8760, len(cols)), np.nan, np.float32)}
    for m in range(1, 13):
        md = S.load_points_month(sources, m, [int(pidx[c]) for c in cols])
        era5["t"][:, month_slice(m), :] = md["temperature_c"]
        era5["td"][:, month_slice(m), :] = md["dewpoint_c"]
        print(f"ERA5-Land month {m:02d} loaded", flush=True)
    kop = koppen(Path(a.koppen_tif), Path(a.koppen_tif).parent.parent / "legend.txt", [loc[s["station_id"]] for s in stations])

    station_rows, annual_rows, monthly_rows, decomp_rows, conv_rows = [], [], [], [], []
    for st, kcls in zip(stations, kop):
        sid = st["station_id"]
        usable = usable_all[sid]
        t_obs, td_obs = station_hourly(work / "prepared/hourly" / f"{sid}.npz")
        have = np.isfinite(t_obs) & np.isfinite(td_obs)
        ref = climatology([year_stats(t_obs[y], td_obs[y]) for y in range(20)], usable)
        j, dist = match[sid]
        cands = {}
        if j is not None:
            c = cols.index(j)
            cands["C1_cey20"] = tmy_stats(ct[:, j], ctd[:, j])
            full = [year_stats(era5["t"][y, :, c], era5["td"][y, :, c]) for y in range(20)]
            cands["C2_full"] = climatology(full, np.ones((20, 12), bool))
            matched = [year_stats(era5["t"][y, :, c], era5["td"][y, :, c], mask=have[y]) for y in range(20)]
            cands["C2_matched"] = climatology(matched, usable)
        for key, reader in (("C3_pvgis", read_pvgis), ("C4_nsrdb", read_nsrdb)):
            series, rep = reader(Path(inv[(sid, key[3:])]["path"]))
            require_complete_tmy(f"{sid} {key}", series, rep, "30" if key == "C4_nsrdb" else None)
            cands[key] = tmy_stats(series["t"], series["td"], series["rh"] if key == "C3_pvgis" else None)
            conv_rows.append({"station_id": sid, "candidate": key, **{k: json.dumps(v) if isinstance(v, (dict, list)) else v
                                                                      for k, v in rep.items()}})
        lat, lon = loc[sid]
        station_rows.append({"station_id": sid, "name": st["name"], "lat": lat, "lon": lon, "elevation_m": st["elev_m"],
                             "koppen": kcls, "s10_point": "" if j is None else int(pidx[j]), "s10_distance_km": round(dist, 2),
                             "min_usable_years": st["min_usable_years_per_month"],
                             **{f"ref_{k}": round(ref["annual"][k]["value"], 1) for k in METRICS},
                             **{f"ref_{k}_low": round(ref["annual"][k]["low"], 1) for k in METRICS},
                             **{f"ref_{k}_high": round(ref["annual"][k]["high"], 1) for k in METRICS},
                             **{f"ref_{k}_sens_hod": ref["annual"][k]["sensitivity_hod"] for k in METRICS}})
        require_finite(f"{sid} station reference", ref)
        for key, c in cands.items():
            require_finite(f"{sid} {key}", c)
        for key in CANDIDATES:
            if key not in cands:
                annual_rows.append({"station_id": sid, "candidate": key, "status": "unavailable"})
                continue
            ann, mon = evaluate(cands[key], ref)
            annual_rows += [{"station_id": sid, "candidate": key, "status": "ok", **r} for r in ann]
            monthly_rows += [{"station_id": sid, "candidate": key, **r} for r in mon]
        if "C1_cey20" in cands:                           # C1 - station = (C1 - C2_full) + (C2_full - station)
            c1, c2 = cands["C1_cey20"], cands["C2_full"]
            for k in METRICS:
                decomp_rows.append({"station_id": sid, "statistic": k, "c1_minus_station": c1["annual"][k]["value"] - ref["annual"][k]["value"],
                                    "c1_minus_c2full": c1["annual"][k]["value"] - c2["annual"][k]["value"],
                                    "c2full_minus_station": c2["annual"][k]["value"] - ref["annual"][k]["value"]})
            for m in range(12):
                for q in ("mean_t", "mean_rh"):
                    decomp_rows.append({"station_id": sid, "statistic": f"{q}_m{m + 1:02d}",
                                        "c1_minus_station": c1["monthly"][m][q] - ref["monthly"][m][q],
                                        "c1_minus_c2full": c1["monthly"][m][q] - c2["monthly"][m][q],
                                        "c2full_minus_station": c2["monthly"][m][q] - ref["monthly"][m][q]})

    summary = summarise(stations, station_rows, annual_rows, monthly_rows)
    out.mkdir(parents=True, exist_ok=True)
    for name, rows in (("stations.csv", station_rows), ("annual.csv", annual_rows), ("monthly.csv", monthly_rows),
                       ("decomposition.csv", decomp_rows), ("conventions.csv", conv_rows)):
        keys = list(dict.fromkeys(k for r in rows for k in r))
        with (out / name).open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)
    (out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    files = ["stations.csv", "annual.csv", "monthly.csv", "decomposition.csv", "conventions.csv", "summary.json"]
    (out / "manifest.json").write_text(json.dumps({
        "command": "auth003_s4ext_compare", "started_utc": started.isoformat(timespec="seconds"),
        "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "pin": pin,
        "s10_dataset_sha256": manifest["output_sha256"][nc.name], "freeze_input_inventory_sha256": freeze["input_inventory_sha256"],
        "tmy_inventory_sha256": sha256_file(work / "raw/inventory_tmy.json"),
        "input_inventory_freeze_sha256": sha256_file(Path(a.input_inventory)),
        "prepared_stations_sha256": sha256_file(work / "prepared/stations.csv"),
        "outputs_sha256": {f: sha256_file(out / f) for f in files}}, indent=1), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in CANDIDATES}, indent=1))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    for name in ("--work", "--s10", "--freeze", "--input-hashes", "--koppen-tif", "--pin", "--output"):
        p.add_argument(name, required=True)
    p.add_argument("--input-inventory", required=True, help="08-input-inventory-freeze.json")
    return run(p.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())

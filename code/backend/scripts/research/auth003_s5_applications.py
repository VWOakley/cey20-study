"""AUTH-003 S5: engineering screening applications and regional envelopes of the CEY20 product year.

Implements docs/research/auth003-tmy/05-applications-spec.md (frozen r4). Descriptive screening values,
no pass/fail limits, no design values and no conformity with ISO 9223 or EN 14825.

Gates before any outcome: the S3 gates (code pin incl. this file, builder identity, 14 frozen points,
inventory, content SHA-256, coverage 1.0, CEY20 selection equal to the S3 run), the pinned product inventory
(`05-s5-inputs.json`: month-file SHA-256, manifest SHA-256, coordinate identity), the product series at
the six S3 region centres equal to the S3 CEY20 series, and for Iqaluit the product series equal to the
series reconstructed from the reference sources and the product's selected source years.

Outputs (all in --output): a1_duration.csv, a1_curves.csv, a2_heat_pump.csv, a3_tow.csv,
a4_saturation_zero_crossing.csv, regional_envelopes.csv, summary.json, manifest.json.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import netCDF4
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import auth003_s3 as R  # noqa: E402
import auth003_s3_hourly as H  # noqa: E402
import auth003_study as S  # noqa: E402

PINNED_FILES = dict(H.PINNED_FILES, **{"auth003_s5_applications.py": Path(__file__).resolve()})
QUANTILES = (0.01, 0.05, 0.50, 0.95, 0.99)
HDH_BASE_C, CDH_BASE_C = 15.0, 24.0
COLD_THRESHOLDS_C = (-7.0, 2.0, 7.0)
TOW_LEVELS = ((10.0, "tau1"), (250.0, "tau2"), (2500.0, "tau3"), (5500.0, "tau4"))
BOX_HALF_DEG = 1.0
SPATIAL_PERCENTILES = (10.0, 50.0, 90.0)
REGIONS = (("Singapore", 197100), ("Dubai", 160629), ("Houston", 149373), ("Frankfurt", 93901),
           ("Helsinki", 60358), ("Fairbanks", 41781), ("Iqaluit", 46334))
EXTRA_CENTRE = "Iqaluit"
PRODUCT_FILE = "cey20_landpoints_month{:02d}.nc"
MONTH_HOURS = H.MONTH_HOURS


def verify_pin(pin: dict) -> None:
    for name, path in PINNED_FILES.items():
        if pin.get(name) != hashlib.sha256(R._lf(path.read_bytes())).hexdigest():
            raise SystemExit(f"{name} does not match the pinned SHA-256")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(8 << 20), b""):
            h.update(block)
    return h.hexdigest()


def coordinates_sha256(lat: np.ndarray, lon: np.ndarray) -> str:
    return hashlib.sha256(np.asarray(lat, np.float32).tobytes() + np.asarray(lon, np.float32).tobytes()).hexdigest()


def verify_product(root: Path, inputs: dict) -> tuple[np.ndarray, np.ndarray]:
    """Pinned product inventory; returns the land-point coordinates (float32) of the month files."""
    if sha256_file(root / "hourly_manifest.json") != inputs["hourly_manifest.json"]["sha256"]:
        raise SystemExit("product hourly_manifest.json differs from the pinned SHA-256")
    lat = lon = None
    for m in range(1, 13):
        name = PRODUCT_FILE.format(m)
        path = root / "hourly" / name
        st, rec = path.stat(), inputs["month_files"][name]
        mtime = dt.datetime.fromtimestamp(st.st_mtime, dt.timezone.utc).isoformat(timespec="seconds")
        if st.st_size != rec["bytes"] or mtime != rec["mtime_utc"] or sha256_file(path) != rec["sha256"]:
            raise SystemExit(f"{name} differs from the pinned inventory")
        with netCDF4.Dataset(path) as d:
            missing = [v for v in inputs["variables_used"] if v not in d.variables]
            if missing or d.dimensions["time"].size != MONTH_HOURS[m - 1]:
                raise SystemExit(f"{name}: variables {missing} missing or hour count differs")
            la, lo = np.asarray(d["latitude"][:], np.float32), np.asarray(d["longitude"][:], np.float32)
        if coordinates_sha256(la, lo) != inputs["coordinates_sha256"]:
            raise SystemExit(f"{name}: land-point coordinates differ from the pinned identity")
        lat, lon = la, lo
    return lat, lon


# ----------------------------------------------------------------------------
# pure computations (unit-tested with synthetic data)
# ----------------------------------------------------------------------------

def context(value: float, actual: list[float]) -> dict:
    """Spec section 3: min/median/max of the 20 actual years and percentile = 100 x share <= value (ties in)."""
    a = np.asarray(actual, dtype=np.float64)
    return {"cey20": value, "years_min": float(a.min()), "years_median": float(np.percentile(a, 50, method="linear")),
            "years_max": float(a.max()), "percentile": 100.0 * float(np.mean(a <= value)), "n_years": int(a.size)}


def duration_levels() -> np.ndarray:
    return (np.arange(1, 8761) - 0.5) / 8760.0


def quantiles(x: np.ndarray, p) -> np.ndarray:
    return np.percentile(np.asarray(x, dtype=np.float64), np.asarray(p) * 100.0, method="linear")


def duration_distance(series: np.ndarray, q_pool: np.ndarray) -> float:
    """max_k |Q_y(p_k) - Q_pool(p_k)| on the frozen grid p_k = (k - 0.5)/8760."""
    return float(np.max(np.abs(quantiles(series, duration_levels()) - q_pool)))


def heat_pump(t: np.ndarray) -> dict:
    t = np.asarray(t, dtype=np.float64)
    out = {"hdh_15_c_h": float(np.sum(np.maximum(0.0, HDH_BASE_C - t))),
           "cdh_24_c_h": float(np.sum(np.maximum(0.0, t - CDH_BASE_C)))}
    for th in COLD_THRESHOLDS_C:
        out[f"hours_t_le_{th:g}c"] = int(np.count_nonzero(t <= th))
    return out


def tow_hours(t: np.ndarray, rh: np.ndarray) -> int:
    return int(np.count_nonzero((rh > 80.0) & (t > 0.0)))


def tow_level(tau: float) -> str:
    for upper, name in TOW_LEVELS:
        if tau <= upper:
            return name
    return "tau5"


def saturation_hours(t: np.ndarray, td: np.ndarray) -> int:
    return int(np.count_nonzero(np.asarray(t) - np.asarray(td) <= 1.0))


def zero_crossing_days(t: np.ndarray) -> int:
    """UTC days (24 h blocks of an 8760 h year) with hourly min T < 0 and hourly max T > 0 (strict)."""
    days = np.asarray(t).reshape(-1, 24)
    return int(np.count_nonzero((days.min(axis=1) < 0.0) & (days.max(axis=1) > 0.0)))


def box_members(lat: np.ndarray, lon: np.ndarray, clat: float, clon: float, half: float = BOX_HALF_DEG) -> np.ndarray:
    """Indices of land points with |lat - clat| <= half and |lon - clon| <= half (longitude wrapped)."""
    dlon = (np.asarray(lon, np.float64) - clon + 180.0) % 360.0 - 180.0
    dlat = np.asarray(lat, np.float64) - clat
    return np.flatnonzero((np.abs(dlat) <= half + 1e-9) & (np.abs(dlon) <= half + 1e-9))


def monthly_point_values(t: np.ndarray, td: np.ndarray, hours: int) -> dict[str, np.ndarray]:
    """t, td (hours, points) of one month -> mean T, mean RH (hourly first) and RH >= 80 % hours per point."""
    if t.shape[0] != hours or td.shape[0] != hours or not (np.all(np.isfinite(t)) and np.all(np.isfinite(td))):
        raise SystemExit("regional point-month incomplete or not finite")
    rh = H.rh_of(t, td)
    return {"mean_t_c": t.mean(axis=0, dtype=np.float64), "mean_rh_pct": rh.mean(axis=0, dtype=np.float64),
            "hours_rh_ge_80": np.count_nonzero(rh >= 80.0, axis=0).astype(np.float64)}


def spatial_summary(values: np.ndarray) -> dict:
    v = np.asarray(values, dtype=np.float64)
    out = {"n_points": int(v.size), "min": float(v.min())}
    for q in SPATIAL_PERCENTILES:
        out[f"p{q:g}"] = float(np.percentile(v, q, method="linear"))
    out["max"] = float(v.max())
    return out


def centre_gate(name: str, prod_t: np.ndarray, prod_td: np.ndarray, t: np.ndarray, td: np.ndarray,
                y: int, col: int) -> None:
    """Product series of one month at a centre must equal the reference year y at column col exactly."""
    if not (np.array_equal(np.asarray(prod_t, np.float32), t[y, :, col])
            and np.array_equal(np.asarray(prod_td, np.float32), td[y, :, col])):
        raise SystemExit(f"product series at {name} differs from the reference reconstruction")


def duration_curves(name: str, sel_t: np.ndarray, years_t: np.ndarray) -> list[dict]:
    """Rows for the S6 duration-curve figure: CEY20, pooled and the pointwise min-max band on p_k."""
    p = duration_levels()
    sel = quantiles(sel_t, p)
    pool = quantiles(years_t.ravel(), p)
    band = np.stack([quantiles(years_t[y], p) for y in range(years_t.shape[0])])
    lo, hi = band.min(axis=0), band.max(axis=0)
    return [{"point": name, "k": k + 1, "p": float(p[k]), "exceedance": float(1.0 - p[k]), "cey20_c": float(sel[k]),
             "pooled_c": float(pool[k]), "years_min_c": float(lo[k]), "years_max_c": float(hi[k])} for k in range(p.size)]


def application_rows(name: str, sel_t, sel_td, years_t, years_td) -> dict[str, list]:
    """A1-A4 for one point: sel_* (8760,), years_* (years, 8760)."""
    sel_rh, years_rh = H.rh_of(sel_t, sel_td), H.rh_of(years_t, years_td)
    n_y = years_t.shape[0]
    rows = {"a1": [], "a2": [], "a3": [], "a4": []}
    q_sel, q_years = quantiles(sel_t, QUANTILES), [quantiles(years_t[y], QUANTILES) for y in range(n_y)]
    for i, p in enumerate(QUANTILES):
        rows["a1"].append(dict(point=name, statistic=f"t_quantile_p{p:g}", **context(float(q_sel[i]), [q[i] for q in q_years])))
    q_pool = quantiles(years_t.ravel(), duration_levels())
    rows["a1"].append(dict(point=name, statistic="duration_curve_max_abs_diff_c",
                           **context(duration_distance(sel_t, q_pool), [duration_distance(years_t[y], q_pool) for y in range(n_y)])))
    hp_sel, hp_years = heat_pump(sel_t), [heat_pump(years_t[y]) for y in range(n_y)]
    for k in hp_sel:
        rows["a2"].append(dict(point=name, statistic=k, **context(hp_sel[k], [h[k] for h in hp_years])))
    tau_sel, tau_years = tow_hours(sel_t, sel_rh), [tow_hours(years_t[y], years_rh[y]) for y in range(n_y)]
    lvl = tow_level(tau_sel)
    rows["a3"].append(dict(point=name, statistic="tow_hours", **context(tau_sel, tau_years), level_cey20=lvl,
                           years_same_level=sum(tow_level(t) == lvl for t in tau_years)))
    for k, fn in (("hours_t_minus_td_le_1c", lambda t, td: saturation_hours(t, td)),
                  ("zero_crossing_days", lambda t, td: zero_crossing_days(t))):
        rows["a4"].append(dict(point=name, statistic=k,
                               **context(fn(sel_t, sel_td), [fn(years_t[y], years_td[y]) for y in range(n_y)])))
    return rows


# ----------------------------------------------------------------------------
# run
# ----------------------------------------------------------------------------

def run(args) -> int:
    started = dt.datetime.now(dt.timezone.utc)
    repo = Path(args.repo).resolve()
    freeze = json.loads(Path(args.freeze).read_text(encoding="utf-8"))
    pin = json.loads(Path(args.pin).read_text(encoding="utf-8"))
    inputs = json.loads(Path(args.product_inputs).read_text(encoding="utf-8"))
    verify_pin(pin)
    H.verify_s3_selection_file(Path(args.s3_monthly), pin)
    if pin.get("05-s5-inputs.json") != hashlib.sha256(R._lf(Path(args.product_inputs).read_bytes())).hexdigest():
        raise SystemExit("product inventory file is not the pinned 05-s5-inputs.json")
    R.verify_code(repo, freeze)
    points = R.frozen_points(freeze)
    months = list(range(1, 13))
    sources = S.discover_sources(args.extension_root, args.legacy_root, months)
    R.verify_inputs(sources, freeze)
    R.verify_input_hashes(sources, json.loads(Path(args.input_hashes).read_text(encoding="utf-8")), freeze)
    s3_idx = H.read_s3_selection(Path(args.s3_monthly), points)
    prod_root = Path(args.product_root)
    lat, lon = verify_product(prod_root, inputs)
    if args.verify_only:
        print(json.dumps({"verified_without_selection_check": True, "points": len(points), "inputs": len(sources)}))
        return 0
    pos = {p["name"]: i for i, p in enumerate(points)}
    for name, index in REGIONS:
        if name in pos and points[pos[name]]["index"] != index:
            raise SystemExit(f"region centre {name} differs from the frozen point index")
    load_points = [p["index"] for p in points] + [dict(REGIONS)[EXTRA_CENTRE]]
    n_p = len(points)
    extra = n_p                                         # column of the Iqaluit centre in the loaded arrays

    t_months, td_months, idx = [], [], np.zeros((12, n_p), dtype=np.int16)
    extra_idx = np.zeros(12, dtype=np.int16)
    envelope_rows, centre_checks = [], {}
    boxes = {name: box_members(lat, lon, float(lat[i]), float(lon[i])) for name, i in REGIONS}
    for mo in months:
        md = S.load_points_month(sources, mo, load_points)
        res = S.analyse_month({k: v[:, :, :n_p] for k, v in md.items()})       # asserts production parity
        R.require_complete(mo, res, points)
        if not np.array_equal(res["idx"], s3_idx[mo - 1]):
            raise SystemExit(f"month {mo}: CEY20 selection differs from the S3 run")
        t, td = md["temperature_c"], md["dewpoint_c"]
        if S.valid_hour_coverage(t[:, :, extra:], td[:, :, extra:]).min() < 1.0:
            raise SystemExit(f"month {mo}: Iqaluit reference coverage below 1")
        idx[mo - 1] = res["idx"]
        hours = t.shape[1]
        with netCDF4.Dataset(prod_root / "hourly" / PRODUCT_FILE.format(mo)) as d:
            year_extra = int(d["selected_source_year"][dict(REGIONS)[EXTRA_CENTRE]])
            extra_idx[mo - 1] = S.YEARS.index(year_extra)
            if t.shape[0] != len(S.YEARS) or hours != MONTH_HOURS[mo - 1]:
                raise SystemExit(f"month {mo}: reference axes {t.shape} differ from 20 years x {MONTH_HOURS[mo - 1]} h")
            for name, i in REGIONS:                    # centre gates: product series == CEY20 / reconstructed series
                col = pos[name] if name in pos else extra
                y = idx[mo - 1, col] if name in pos else extra_idx[mo - 1]
                centre_gate(name, d["temperature_c"][:, i], d["dewpoint_c"][:, i], t, td, int(y), col)
                centre_checks[name] = "equal"
            for name, ci in REGIONS:
                members = boxes[name]
                bt = np.asarray(d["temperature_c"][:, members], np.float32)
                btd = np.asarray(d["dewpoint_c"][:, members], np.float32)
                vals = monthly_point_values(bt, btd, hours)
                col = pos[name] if name in pos else extra
                yv = monthly_point_values_years(t[:, :, col], td[:, :, col])
                for q in vals:
                    envelope_rows.append(dict(region=name, month=mo, quantity=q, **spatial_summary(vals[q]),
                                              centre_years_min=float(yv[q].min()),
                                              centre_years_median=float(np.percentile(yv[q], 50, method="linear")),
                                              centre_years_max=float(yv[q].max())))
        t_months.append(t[:, :, :n_p]); td_months.append(td[:, :, :n_p])
        print(f"month {mo:02d} done", flush=True)

    years_t = np.concatenate(t_months, axis=1)          # (years, 8760, points)
    years_td = np.concatenate(td_months, axis=1)
    sel_t, sel_td = H.assemble(t_months, idx), H.assemble(td_months, idx)
    rows = {"a1": [], "a2": [], "a3": [], "a4": []}
    curves = []
    for p, pt in enumerate(points):
        r = application_rows(pt["name"], sel_t[:, p], sel_td[:, p], years_t[:, :, p], years_td[:, :, p])
        for k in rows:
            rows[k] += r[k]
        curves += duration_curves(pt["name"], sel_t[:, p], years_t[:, :, p])

    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    files = {"a1_duration.csv": rows["a1"], "a1_curves.csv": curves, "a2_heat_pump.csv": rows["a2"], "a3_tow.csv": rows["a3"],
             "a4_saturation_zero_crossing.csv": rows["a4"], "regional_envelopes.csv": envelope_rows}
    for f, rws in files.items():
        S.write_csv(out / f, rws)
    summary = {
        "label": "screening; descriptive; in-sample; no conformity with ISO 9223 or EN 14825",
        "a3_levels_cey20": {r["point"]: r["level_cey20"] for r in rows["a3"]},
        "a3_years_same_level": {r["point"]: r["years_same_level"] for r in rows["a3"]},
        "region_points": {name: int(boxes[name].size) for name, _ in REGIONS},
        "centre_gates": centre_checks,
        "iqaluit_selected_years": [S.YEARS[i] for i in extra_idx],
    }
    S.write_json(out / "summary.json", summary)
    S.write_json(out / "manifest.json", {
        "command": "auth003_s5_applications", "started_utc": started.isoformat(timespec="seconds"),
        "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "code_sha": S.git_sha(), "freeze": str(args.freeze), "freeze_code_sha": freeze["code_sha"],
        "freeze_input_inventory_sha256": freeze["input_inventory_sha256"], "points": points,
        "regions": [dict(region=n, point_index=i, lat=float(lat[i]), lon=float(lon[i]), n_points=int(boxes[n].size))
                    for n, i in REGIONS],
        "input_hashes": str(args.input_hashes), "pin": str(args.pin), "s3_monthly": str(args.s3_monthly),
        "product_root": str(prod_root), "product_inputs": inputs, "files": [*files, "summary.json"]})
    print(json.dumps({k: summary[k] for k in ("a3_levels_cey20", "region_points")}))
    return 0


def monthly_point_values_years(t: np.ndarray, td: np.ndarray) -> dict[str, np.ndarray]:
    """Centre context: per actual year (years, hours) -> the three monthly quantities, shape (years,)."""
    vals = [monthly_point_values(t[y][:, None], td[y][:, None], t.shape[1]) for y in range(t.shape[0])]
    return {k: np.array([v[k][0] for v in vals]) for k in vals[0]}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="AUTH-003 S5 screening applications (05-applications-spec.md).")
    p.add_argument("--freeze", type=Path, required=True)
    p.add_argument("--input-hashes", type=Path, required=True)
    p.add_argument("--pin", type=Path, required=True,
                   help="JSON with SHA-256 of the study/S3/hourly/S5 scripts, s3_targets_monthly.csv and 05-s5-inputs.json")
    p.add_argument("--s3-monthly", type=Path, required=True, help="targets_monthly.csv of the S3 run (selection cross-check)")
    p.add_argument("--product-inputs", type=Path, required=True, help="05-s5-inputs.json (pinned product inventory)")
    p.add_argument("--product-root", type=Path, default=Path("E:/ERA_DATA/cey_2006_2025"))
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    p.add_argument("--extension-root", type=Path, default=S.builder.DEFAULT_EXTENSION_ROOT)
    p.add_argument("--legacy-root", type=Path, default=S.builder.DEFAULT_LEGACY_ROOT)
    p.add_argument("--verify-only", action="store_true")
    return run(p.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())

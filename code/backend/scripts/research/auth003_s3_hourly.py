"""AUTH-003 S3: held-out hourly diagnostics of the CEY20 selection at the frozen pilot points.

Implements docs/research/auth003-tmy/03-diagnostics-spec.md (D1-D5).  No pass/fail limits: every
quantity is reported with its reference and its position among the 20 actual years.

Runs the same pre-outcome gates as auth003_s3.py (code pin incl. this file, builder identity,
14 frozen points, inventory, content SHA-256, coverage 1.0) and aborts if the recomputed
selection differs from the S3 run's targets_monthly.csv.

Outputs (all in --output): d1_joint.csv, d2_spells.csv, d3_humid_temperature.csv,
d4_boundaries.csv, d5_conventions.csv, summary.json, manifest.json.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import auth003_s3 as R  # noqa: E402
import auth003_study as S  # noqa: E402

PINNED_FILES = dict(R.PINNED_FILES, **{"auth003_s3_hourly.py": Path(__file__).resolve()})
T_EDGES = np.arange(-60.0, 60.0 + 2.0, 2.0)
RH_EDGES = np.arange(0.0, 100.0 + 5.0, 5.0)
SPELL_THRESHOLDS = (80.0, 90.0)
HUMID_T_BANDS = ((-np.inf, 0.0), (0.0, 10.0), (10.0, 20.0), (20.0, 30.0), (30.0, np.inf))
BOUNDARY_WINDOW_H = 72
MONTH_HOURS = [S.builder._standard_month_hours(m) for m in range(1, 13)]


S3_SELECTION_KEY = "s3_targets_monthly.csv"


def verify_pin(pin: dict) -> None:
    for name, path in PINNED_FILES.items():
        if pin.get(name) != hashlib.sha256(R._lf(path.read_bytes())).hexdigest():
            raise SystemExit(f"{name} does not match the pinned SHA-256")


def verify_s3_selection_file(path: Path, pin: dict) -> None:
    """The comparison target must be the S3 run's targets_monthly.csv, pinned before this run."""
    if pin.get(S3_SELECTION_KEY) != hashlib.sha256(R._lf(path.read_bytes())).hexdigest():
        raise SystemExit(f"{path} is not the pinned S3 targets_monthly.csv")


# ----------------------------------------------------------------------------
# pure computations (unit-tested with synthetic data)
# ----------------------------------------------------------------------------

def rh_of(t: np.ndarray, td: np.ndarray) -> np.ndarray:
    return S._relative_humidity_from_dewpoint(t, td).astype(np.float32)


def joint_hist(t: np.ndarray, rh: np.ndarray) -> np.ndarray:
    """Normalised 2-D histogram; T clipped into the edge bins, RH 100 in the last bin."""
    tc = np.clip(t, T_EDGES[0], T_EDGES[-1] - 1e-6)
    rc = np.clip(rh, RH_EDGES[0], RH_EDGES[-1] - 1e-6)
    h, _, _ = np.histogram2d(tc.ravel(), rc.ravel(), bins=[T_EDGES, RH_EDGES])
    return h / h.sum()


def hellinger(p: np.ndarray, q: np.ndarray) -> float:
    return float(np.sqrt(0.5 * np.sum((np.sqrt(p) - np.sqrt(q)) ** 2)))


def total_variation(p: np.ndarray, q: np.ndarray) -> float:
    return float(0.5 * np.sum(np.abs(p - q)))


def runs(mask: np.ndarray) -> tuple[list[int], list[int]]:
    """(spell lengths of True runs, gap lengths of False runs strictly between two True runs)."""
    m = np.asarray(mask, dtype=bool)
    if m.size == 0:
        return [], []
    change = np.flatnonzero(np.diff(m.astype(np.int8))) + 1
    starts = np.concatenate([[0], change])
    lengths = np.diff(np.concatenate([starts, [m.size]]))
    values = m[starts]
    spells = [int(n) for n, v in zip(lengths, values) if v]
    inner = [(n, v) for i, (n, v) in enumerate(zip(lengths, values)) if 0 < i < len(values) - 1]
    gaps = [int(n) for n, v in inner if not v]
    return spells, gaps


def spell_stats(rh: np.ndarray, threshold: float) -> dict:
    spells, gaps = runs(rh >= threshold)
    return {"n_spells": len(spells),
            "mean_spell_h": float(np.mean(spells)) if spells else None,
            "p90_spell_h": float(np.percentile(spells, 90)) if spells else None,
            "max_spell_h": int(max(spells)) if spells else None,
            "n_gaps": len(gaps),
            "median_gap_h": float(np.median(gaps)) if gaps else None,
            "p10_gap_h": float(np.percentile(gaps, 10)) if gaps else None}


def humid_temperature(t: np.ndarray, rh: np.ndarray) -> dict:
    hot = t[rh >= 80.0]
    out = {"n_humid_hours": int(hot.size), "mean_t_humid_c": float(hot.mean()) if hot.size else None}
    for lo, hi in HUMID_T_BANDS:
        key = f"share_t_{'lt' if lo == -np.inf else int(lo)}_{'inf' if hi == np.inf else int(hi)}"
        out[key] = float(np.mean((hot >= lo) & (hot < hi))) if hot.size else None
    return out


def context(value, actual: list) -> dict:
    """CEY20 value against the 20 actual-year values (None values ignored)."""
    vals = [v for v in actual if v is not None]
    if value is None or not vals:
        return {"cey20": value, "years_min": min(vals) if vals else None, "years_median": float(np.median(vals)) if vals else None,
                "years_max": max(vals) if vals else None, "percentile": None, "n_years": len(vals)}
    return {"cey20": value, "years_min": min(vals), "years_median": float(np.median(vals)), "years_max": max(vals),
            "percentile": float(np.mean(np.asarray(vals) <= value)), "n_years": len(vals)}


def assemble(months_data: list[np.ndarray], idx: np.ndarray) -> np.ndarray:
    """CEY20 series (8760, points) from per-month arrays (years, hours, points) and idx (12, points)."""
    parts = [m[idx[i], :, np.arange(m.shape[2])].T for i, m in enumerate(months_data)]
    return np.concatenate(parts, axis=0)


def boundary_jump(series: np.ndarray, month: int) -> float:
    """|change| between the last hour of `month` (1..11) and the first hour of month+1 in an 8760 series."""
    b = int(np.sum(MONTH_HOURS[:month]))
    return float(abs(series[b] - series[b - 1]))


def boundary_reference(years_series: np.ndarray, month: int) -> np.ndarray:
    """|hour-to-hour changes| within +-72 h of the boundary after `month` (1..11) over all actual years."""
    b = int(np.sum(MONTH_HOURS[:month]))
    w = years_series[:, b - BOUNDARY_WINDOW_H : b + BOUNDARY_WINDOW_H + 1]
    return np.abs(np.diff(w, axis=1)).ravel()


def wrap_reference(years_series: np.ndarray) -> np.ndarray:
    """|changes| around 31 Dec Y -> 1 Jan Y+1 (19 year pairs), +-72 h."""
    out = []
    for y in range(years_series.shape[0] - 1):
        w = np.concatenate([years_series[y, -BOUNDARY_WINDOW_H:], years_series[y + 1, : BOUNDARY_WINDOW_H + 1]])
        out.append(np.abs(np.diff(w)))
    return np.concatenate(out)


def percentile_of(value: float, ref: np.ndarray) -> float:
    return float(np.mean(ref <= value))


# ----------------------------------------------------------------------------
# run
# ----------------------------------------------------------------------------

def read_s3_selection(path: Path, points: list[dict]) -> np.ndarray:
    """(12, points) year indices from the S3 run's targets_monthly.csv."""
    out = np.full((12, len(points)), -1, dtype=np.int16)
    pos = {p["name"]: i for i, p in enumerate(points)}
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out[int(r["month"]) - 1, pos[r["point"]]] = S.YEARS.index(int(r["selected_year"]))
    if (out < 0).any():
        raise SystemExit("S3 selection file is incomplete")
    return out


def run(args) -> int:
    started = dt.datetime.now(dt.timezone.utc)
    repo = Path(args.repo).resolve()
    freeze = json.loads(Path(args.freeze).read_text(encoding="utf-8"))
    pin = json.loads(Path(args.pin).read_text(encoding="utf-8"))
    verify_pin(pin)
    verify_s3_selection_file(Path(args.s3_monthly), pin)
    R.verify_code(repo, freeze)
    points = R.frozen_points(freeze)
    lons = np.asarray([next(p["grid_lon"] for p in freeze["points"] if p["name"] == q["name"]) for q in points])
    months = list(range(1, 13))
    sources = S.discover_sources(args.extension_root, args.legacy_root, months)
    R.verify_inputs(sources, freeze)
    R.verify_input_hashes(sources, json.loads(Path(args.input_hashes).read_text(encoding="utf-8")), freeze)
    s3_idx = read_s3_selection(Path(args.s3_monthly), points)
    if args.verify_only:
        # Selection equality needs the month data; it is checked per month in the full run.
        print(json.dumps({"verified_without_selection_check": True, "points": len(points), "inputs": len(sources)}))
        return 0
    indices = [p["index"] for p in points]
    n_p = len(points)

    t_months, td_months, idx = [], [], np.zeros((12, n_p), dtype=np.int16)
    idx_local, idx_mixed = np.zeros_like(idx), np.zeros_like(idx)
    cnt_base, cnt_mixed = [], []
    for m in months:
        md = S.load_points_month(sources, m, indices)
        res = S.analyse_month(md)                       # asserts production parity
        R.require_complete(m, res, points)
        if not np.array_equal(res["idx"], s3_idx[m - 1]):
            raise SystemExit(f"month {m}: selection differs from the S3 run")
        t, td = md["temperature_c"], md["dewpoint_c"]
        idx[m - 1] = res["idx"]
        f_loc = S.compute_features(t, td, dtr=S.dtr_local_day(t, lons))
        idx_local[m - 1] = S.select_year(S.score_candidates(f_loc))[0]
        f_mix = S.compute_features(t, td, rh_fn=S.rh_mixed, ah_fn=S.ah_mixed)
        idx_mixed[m - 1] = S.select_year(S.score_candidates(f_mix))[0]
        cnt_base.append(R.counts(t, td))
        cnt_mixed.append({k: f_mix[k].astype(np.float64) for k in R.COUNT_KEYS})
        t_months.append(t); td_months.append(td)
        print(f"month {m:02d} loaded", flush=True)

    years_t = np.concatenate(t_months, axis=1)          # (years, 8760, points)
    years_td = np.concatenate(td_months, axis=1)
    years_rh = rh_of(years_t, years_td)
    cey_t, cey_td = assemble(t_months, idx), assemble(td_months, idx)
    cey_rh = rh_of(cey_t, cey_td)
    n_y = years_t.shape[0]

    d1, d2, d3, d4 = [], [], [], []
    for p, pt in enumerate(points):
        name = pt["name"]
        pooled = joint_hist(years_t[:, :, p], years_rh[:, :, p])
        cey_h = joint_hist(cey_t[:, p], cey_rh[:, p])
        for metric, fn in (("hellinger", hellinger), ("total_variation", total_variation)):
            c = fn(cey_h, pooled)
            yrs = [fn(joint_hist(years_t[y, :, p], years_rh[y, :, p]), pooled) for y in range(n_y)]
            d1.append(dict(point=name, metric=metric, **context(c, yrs),
                           rank_closest=1 + sum(v < c for v in yrs)))
        for th in SPELL_THRESHOLDS:
            cs = spell_stats(cey_rh[:, p], th)
            ys = [spell_stats(years_rh[y, :, p], th) for y in range(n_y)]
            for k in cs:
                d2.append(dict(point=name, threshold=th, statistic=k, **context(cs[k], [y[k] for y in ys])))
        ch = humid_temperature(cey_t[:, p], cey_rh[:, p])
        ph = humid_temperature(years_t[:, :, p].ravel(), years_rh[:, :, p].ravel())
        ph["n_humid_hours"] = ph["n_humid_hours"] / n_y          # per year, comparable with the 8760 h CEY20
        yh = [humid_temperature(years_t[y, :, p], years_rh[y, :, p]) for y in range(n_y)]
        for k in ch:
            row = dict(point=name, statistic=k, pooled=ph[k],
                       diff=(ch[k] - ph[k]) if ch[k] is not None and ph[k] is not None else None)
            d3.append(dict(row, **context(ch[k], [y[k] for y in yh])))
        series = {"temperature_c": (cey_t[:, p], years_t[:, :, p]),
                  "dewpoint_c": (cey_td[:, p], years_td[:, :, p]),
                  "rh_pct": (cey_rh[:, p], years_rh[:, :, p])}
        for m in range(1, 13):
            same = bool(idx[m - 1, p] == idx[m % 12, p]) and m < 12
            for var, (cs_, ys_) in series.items():
                if m < 12:
                    jump, ref = boundary_jump(cs_, m), boundary_reference(ys_, m)
                else:
                    jump, ref = float(abs(cs_[0] - cs_[-1])), wrap_reference(ys_)
                p99 = float(np.percentile(ref, 99))
                d4.append({"point": name, "boundary": f"{m:02d}->{m % 12 + 1:02d}", "wrap": m == 12,
                           "variable": var, "jump": jump, "percentile": percentile_of(jump, ref),
                           "ref_p99": p99, "above_ref_p99": jump > p99, "same_year": same,
                           "year_before": S.YEARS[idx[m - 1, p]], "year_after": S.YEARS[idx[m % 12, p]]})

    def annual(sel_idx, cnt):
        all_c = {k: np.stack([c[k] for c in cnt]) for k in R.COUNT_KEYS}
        sel = {k: np.stack([R.take(cnt[i][k], sel_idx[i]) for i in range(12)]) for k in R.COUNT_KEYS}
        return R.annual_target(sel, all_c)

    d5 = []
    for variant, vidx, cnt in (("baseline", idx, cnt_base), ("local_solar_day", idx_local, cnt_base),
                               ("humidity_mixed_ice", idx_mixed, cnt_mixed)):
        changed = int(np.sum(vidx != idx))
        for r in annual(vidx, cnt):
            d5.append(dict(r, point=points[r["point"]]["name"], variant=variant, point_months_changed=changed))

    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    files = {"d1_joint.csv": d1, "d2_spells.csv": d2, "d3_humid_temperature.csv": d3,
             "d4_boundaries.csv": d4, "d5_conventions.csv": d5}
    for f, rows in files.items():
        S.write_csv(out / f, rows)
    inner = [r for r in d4 if not r["wrap"]]
    summary = {
        "d1_rank_closest_hellinger": {r["point"]: r["rank_closest"] for r in d1 if r["metric"] == "hellinger"},
        "d4_inner_above_ref_p99": {v: sum(r["above_ref_p99"] for r in inner if r["variable"] == v)
                                   for v in ("temperature_c", "dewpoint_c", "rh_pct")},
        "d4_inner_checked_per_variable": len(inner) // 3,
        "d4_wrap_above_ref_p99": {v: sum(r["above_ref_p99"] for r in d4 if r["wrap"] and r["variable"] == v)
                                  for v in ("temperature_c", "dewpoint_c", "rh_pct")},
        "d5": {v: {"point_months_changed": next(r["point_months_changed"] for r in d5 if r["variant"] == v),
                   "target1_failed": sum(not r["pass"] for r in d5 if r["variant"] == v)}
               for v in ("baseline", "local_solar_day", "humidity_mixed_ice")},
    }
    S.write_json(out / "summary.json", summary)
    S.write_json(out / "manifest.json", {
        "command": "auth003_s3_hourly", "started_utc": started.isoformat(timespec="seconds"),
        "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "code_sha": S.git_sha(), "freeze": str(args.freeze), "freeze_code_sha": freeze["code_sha"],
        "freeze_input_inventory_sha256": freeze["input_inventory_sha256"], "points": points,
        "input_hashes": str(args.input_hashes), "pin": str(args.pin), "s3_monthly": str(args.s3_monthly),
        "files": [*files, "summary.json"]})
    print(json.dumps(summary["d5"]))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="AUTH-003 S3 held-out hourly diagnostics (03-diagnostics-spec.md).")
    p.add_argument("--freeze", type=Path, required=True)
    p.add_argument("--input-hashes", type=Path, required=True)
    p.add_argument("--pin", type=Path, required=True,
                   help="JSON with SHA-256 of auth003_study.py, auth003_s3.py, auth003_s3_hourly.py and s3_targets_monthly.csv")
    p.add_argument("--s3-monthly", type=Path, required=True, help="targets_monthly.csv of the S3 run (selection cross-check)")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    p.add_argument("--extension-root", type=Path, default=S.builder.DEFAULT_EXTENSION_ROOT)
    p.add_argument("--legacy-root", type=Path, default=S.builder.DEFAULT_LEGACY_ROOT)
    p.add_argument("--verify-only", action="store_true")
    return run(p.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())

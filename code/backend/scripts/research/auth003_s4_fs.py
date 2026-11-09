"""AUTH-003 S4: exploratory FS-based selection (FS-A, FS-B) at the 14 frozen S3 points.

Implements docs/research/auth003-tmy/04-fs-exploratory-spec.md. Finkelstein-Schafer statistics of
daily indices per calendar month, weighted sum, minimum-WS year (earliest year on ties), no secondary
ranking and no persistence screening. CEY20, FS-A and FS-B are evaluated side by side with the
unchanged S3 targets 1/2 and diagnostics D1-D5 plus the supplementary D4s. Exploratory; it does not
replace the CEY20 baseline and claims no TMY3 or ISO 15927-4 conformity.

Same pre-outcome gates as the S3 runners (code pin incl. this file, builder identity, 14 frozen points,
inventory, content SHA-256, coverage 1.0, recomputed CEY20 selection equal to the S3 run).

Outputs (all in --output): selection.csv, top5.csv, targets_annual.csv, targets_monthly.csv,
d1_joint.csv, d2_spells.csv, d3_humid_temperature.csv, d4_boundaries.csv, d4s_boundaries.csv,
d5_conventions.csv, d5_selection.csv, summary.json, manifest.json.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import auth003_s3 as R  # noqa: E402
import auth003_s3_d4s as D  # noqa: E402
import auth003_s3_hourly as H  # noqa: E402
import auth003_study as S  # noqa: E402

PINNED_FILES = dict(D.PINNED_FILES, **{"auth003_s4_fs.py": Path(__file__).resolve()})
THERMO = ("t_max", "t_min", "t_mean", "td_max", "td_min", "td_mean")
EXPOSURE = ("h_rh80", "h_rh90", "h_dpd2")
# Spec section 5 (frozen, Codex 2026-11-04): Wilcox & Marion 2008 Table 2-1 renormalised; FS-B 1/2 + 3 x 1/6.
WEIGHTS = {
    "FS-A": {"t_max": 1 / 8, "t_min": 1 / 8, "t_mean": 2 / 8, "td_max": 1 / 8, "td_min": 1 / 8, "td_mean": 2 / 8},
    "FS-B": {"t_max": 1 / 16, "t_min": 1 / 16, "t_mean": 1 / 8, "td_max": 1 / 16, "td_min": 1 / 16, "td_mean": 1 / 8,
             "h_rh80": 1 / 6, "h_rh90": 1 / 6, "h_dpd2": 1 / 6},
}
METHODS = ("CEY20", "FS-A", "FS-B")
TOP_N = 5


def verify_pin(pin: dict) -> None:
    for name, path in PINNED_FILES.items():
        if pin.get(name) != hashlib.sha256(R._lf(path.read_bytes())).hexdigest():
            raise SystemExit(f"{name} does not match the pinned SHA-256")


# ----------------------------------------------------------------------------
# pure computations (unit-tested with synthetic data)
# ----------------------------------------------------------------------------

def daily_indices(t: np.ndarray, td: np.ndarray, start: int = 0, rh_fn=None) -> dict[str, np.ndarray]:
    """Daily indices (years, days) of one point from hourly t, td (years, hours).

    Days are full 24 h blocks beginning at hour `start` (0 = UTC days); partial edge days are dropped.
    Exposure counts are hours per day with RH >= 80 %, RH >= 90 % (builder formula unless rh_fn) and
    T - Td <= 2 degC, with the same comparisons as the S3 counts."""
    rh_fn = rh_fn or S._relative_humidity_from_dewpoint
    years, hours = t.shape
    days = (hours - start) // 24
    tt = t[:, start:start + days * 24].reshape(years, days, 24)
    dd = td[:, start:start + days * 24].reshape(years, days, 24)
    rh = rh_fn(tt, dd).astype(np.float32)
    return {"t_max": tt.max(axis=2), "t_min": tt.min(axis=2), "t_mean": tt.mean(axis=2),
            "td_max": dd.max(axis=2), "td_min": dd.min(axis=2), "td_mean": dd.mean(axis=2),
            "h_rh80": np.count_nonzero(rh >= 80.0, axis=2).astype(np.float64),
            "h_rh90": np.count_nonzero(rh >= 90.0, axis=2).astype(np.float64),
            "h_dpd2": np.count_nonzero(tt - dd <= 2.0, axis=2).astype(np.float64)}


def fs_statistic(values: np.ndarray) -> np.ndarray:
    """FS per candidate year for one index: values (years, n) -> (years,).

    Long-term CDF over all years' daily values (candidate included), candidate CDF over its n days, both
    right-continuous (F(x) = #{v <= x} / N), evaluated at every candidate value including repetitions."""
    if not np.all(np.isfinite(values)):
        raise SystemExit("non-finite daily index value")
    pool = np.sort(values.ravel())
    out = np.empty(values.shape[0])
    for y, v in enumerate(values):
        f_cand = np.searchsorted(np.sort(v), v, side="right") / v.size
        f_lt = np.searchsorted(pool, v, side="right") / pool.size
        out[y] = float(np.mean(np.abs(f_cand - f_lt)))
    return out


def weighted_sum(indices: dict[str, np.ndarray], weights: dict[str, float]) -> np.ndarray:
    return sum(w * fs_statistic(indices[k]) for k, w in weights.items())


def select_min(ws: np.ndarray) -> int:
    """Minimum WS; np.argmin returns the first minimum, i.e. the earliest year on exact ties."""
    return int(np.argmin(ws))


def select_fs(t: np.ndarray, td: np.ndarray, weights: dict[str, float], starts=None, rh_fn=None):
    """t, td: (years, hours, points). Returns (idx (points,), ws (years, points))."""
    n_p = t.shape[2]
    ws = np.stack([weighted_sum(daily_indices(t[:, :, p], td[:, :, p], 0 if starts is None else starts[p], rh_fn),
                                weights) for p in range(n_p)], axis=1)
    return np.array([select_min(ws[:, p]) for p in range(n_p)], dtype=np.int16), ws


def local_starts(lons: np.ndarray) -> list[int]:
    """First UTC hour of a local-solar day per point (same shift as S.dtr_local_day)."""
    return [(-S.local_day_shift_hours(lon)) % 24 for lon in lons]


def boundary_rows(name: str, idx_p: np.ndarray, series: dict, ref_fn, wrap_fn, with_n: bool) -> list[dict]:
    """D4 / D4s rows for one point; series[var] = (selected 8760 series, actual years (years, 8760))."""
    rows = []
    for m in range(1, 13):
        same = bool(idx_p[m - 1] == idx_p[m % 12]) and m < 12
        for var, (cs_, ys_) in series.items():
            if m < 12:
                jump, ref = H.boundary_jump(cs_, m), ref_fn(ys_, m)
            else:
                jump, ref = float(abs(cs_[0] - cs_[-1])), wrap_fn(ys_)
            p99 = float(np.percentile(ref, 99))
            row = {"point": name, "boundary": f"{m:02d}->{m % 12 + 1:02d}", "wrap": m == 12, "variable": var,
                   "jump": jump, "percentile": H.percentile_of(jump, ref), "ref_p99": p99}
            if with_n:
                row["ref_n"] = int(ref.size)
            rows.append(dict(row, above_ref_p99=jump > p99, same_year=same, year_before=S.YEARS[idx_p[m - 1]],
                             year_after=S.YEARS[idx_p[m % 12]]))
    return rows


def hourly_diagnostics(method: str, idx: np.ndarray, t_months: list, td_months: list, points: list[dict],
                       years_t: np.ndarray, years_td: np.ndarray, years_rh: np.ndarray) -> dict[str, list]:
    """D1-D4 and D4s for one selection idx (12, points), as defined in 03-diagnostics-spec.md."""
    sel_t, sel_td = H.assemble(t_months, idx), H.assemble(td_months, idx)
    sel_rh = H.rh_of(sel_t, sel_td)
    n_y = years_t.shape[0]
    out = {"d1": [], "d2": [], "d3": [], "d4": [], "d4s": []}
    for p, pt in enumerate(points):
        name, tag = pt["name"], {"method": method}
        pooled = H.joint_hist(years_t[:, :, p], years_rh[:, :, p])
        sel_h = H.joint_hist(sel_t[:, p], sel_rh[:, p])
        for metric, fn in (("hellinger", H.hellinger), ("total_variation", H.total_variation)):
            c = fn(sel_h, pooled)
            yrs = [fn(H.joint_hist(years_t[y, :, p], years_rh[y, :, p]), pooled) for y in range(n_y)]
            out["d1"].append(dict(tag, point=name, metric=metric, **H.context(c, yrs),
                                  rank_closest=1 + sum(v < c for v in yrs)))
        for th in H.SPELL_THRESHOLDS:
            cs = H.spell_stats(sel_rh[:, p], th)
            ys = [H.spell_stats(years_rh[y, :, p], th) for y in range(n_y)]
            for k in cs:
                out["d2"].append(dict(tag, point=name, threshold=th, statistic=k, **H.context(cs[k], [y[k] for y in ys])))
        ch = H.humid_temperature(sel_t[:, p], sel_rh[:, p])
        ph = H.humid_temperature(years_t[:, :, p].ravel(), years_rh[:, :, p].ravel())
        ph["n_humid_hours"] = ph["n_humid_hours"] / n_y
        yh = [H.humid_temperature(years_t[y, :, p], years_rh[y, :, p]) for y in range(n_y)]
        for k in ch:
            row = dict(tag, point=name, statistic=k, pooled=ph[k],
                       diff=(ch[k] - ph[k]) if ch[k] is not None and ph[k] is not None else None)
            out["d3"].append(dict(row, **H.context(ch[k], [y[k] for y in yh])))
        series = {"temperature_c": (sel_t[:, p], years_t[:, :, p]), "dewpoint_c": (sel_td[:, p], years_td[:, :, p]),
                  "rh_pct": (sel_rh[:, p], years_rh[:, :, p])}
        out["d4"] += [dict(tag, **r) for r in boundary_rows(name, idx[:, p], series, H.boundary_reference,
                                                            H.wrap_reference, False)]
        out["d4s"] += [dict(tag, **r) for r in boundary_rows(name, idx[:, p], series,
                                                             lambda ys, m: D.midnight_reference(ys, m, S.YEARS),
                                                             D.midnight_wrap_reference, True)]
    return out


def d5_selection_rows(method: str, variant: str, base: np.ndarray, vidx: np.ndarray, points: list[dict]) -> list[dict]:
    """One row per point-month: baseline and variant year, and whether the selection changed."""
    return [{"method": method, "variant": variant, "point": pt["name"], "month": mo + 1,
             "baseline_year": S.YEARS[base[mo, p]], "variant_year": S.YEARS[vidx[mo, p]],
             "selection_changed": bool(base[mo, p] != vidx[mo, p])}
            for p, pt in enumerate(points) for mo in range(base.shape[0])]


def annual_rows(sel_idx: np.ndarray, cnt: list[dict]) -> list[dict]:
    """Target 1 for selection sel_idx (12, points) and monthly counts cnt[m][k] (years, points)."""
    all_c = {k: np.stack([c[k] for c in cnt]) for k in R.COUNT_KEYS}
    sel = {k: np.stack([R.take(cnt[i][k], sel_idx[i]) for i in range(12)]) for k in R.COUNT_KEYS}
    return R.annual_target(sel, all_c)


def summarise(method: str, annual: list, monthly: list, diag: dict) -> dict:
    inner = [r for r in diag["d4"] if not r["wrap"]]
    inner_s = [r for r in diag["d4s"] if not r["wrap"]]
    variables = ("temperature_c", "dewpoint_c", "rh_pct")
    return {
        "target1_annual": {"checked": len(annual), "failed": sum(not r["pass"] for r in annual)},
        "target2_monthly_t": {"checked": len(monthly), "failed": sum(not r["pass_t"] for r in monthly)},
        "target2_monthly_rh": {"checked": len(monthly), "failed": sum(not r["pass_rh"] for r in monthly)},
        "d1_rank_closest_hellinger": {r["point"]: r["rank_closest"] for r in diag["d1"] if r["metric"] == "hellinger"},
        "d4_inner_above_ref_p99": {v: sum(r["above_ref_p99"] for r in inner if r["variable"] == v) for v in variables},
        "d4_wrap_above_ref_p99": {v: sum(r["above_ref_p99"] for r in diag["d4"] if r["wrap"] and r["variable"] == v)
                                  for v in variables},
        "d4s_inner_above_ref_p99": {v: sum(r["above_ref_p99"] for r in inner_s if r["variable"] == v) for v in variables},
        "d4s_wrap_above_ref_p99": {v: sum(r["above_ref_p99"] for r in diag["d4s"] if r["wrap"] and r["variable"] == v)
                                   for v in variables},
    }


# ----------------------------------------------------------------------------
# run
# ----------------------------------------------------------------------------

def run(args) -> int:
    started = dt.datetime.now(dt.timezone.utc)
    repo = Path(args.repo).resolve()
    freeze = json.loads(Path(args.freeze).read_text(encoding="utf-8"))
    pin = json.loads(Path(args.pin).read_text(encoding="utf-8"))
    verify_pin(pin)
    H.verify_s3_selection_file(Path(args.s3_monthly), pin)
    R.verify_code(repo, freeze)
    points = R.frozen_points(freeze)
    lons = np.asarray([next(p["grid_lon"] for p in freeze["points"] if p["name"] == q["name"]) for q in points])
    months = list(range(1, 13))
    sources = S.discover_sources(args.extension_root, args.legacy_root, months)
    R.verify_inputs(sources, freeze)
    R.verify_input_hashes(sources, json.loads(Path(args.input_hashes).read_text(encoding="utf-8")), freeze)
    s3_idx = H.read_s3_selection(Path(args.s3_monthly), points)
    if args.verify_only:
        print(json.dumps({"verified_without_selection_check": True, "points": len(points), "inputs": len(sources)}))
        return 0
    indices = [p["index"] for p in points]
    n_p = len(points)
    starts = local_starts(lons)

    idx = {m: np.zeros((12, n_p), dtype=np.int16) for m in METHODS}
    d5_idx = {(m, v): np.zeros((12, n_p), dtype=np.int16) for m in METHODS for v in ("local_solar_day", "humidity_mixed_ice")}
    t_months, td_months, feats_m, cnt_base, cnt_mixed, sel_rows, top_rows = [], [], [], [], [], [], []
    for mo in months:
        md = S.load_points_month(sources, mo, indices)
        res = S.analyse_month(md)                       # asserts production parity
        R.require_complete(mo, res, points)
        if not np.array_equal(res["idx"], s3_idx[mo - 1]):
            raise SystemExit(f"month {mo}: CEY20 selection differs from the S3 run")
        t, td = md["temperature_c"], md["dewpoint_c"]
        idx["CEY20"][mo - 1] = res["idx"]
        for name, w in WEIGHTS.items():
            sel, ws = select_fs(t, td, w)
            idx[name][mo - 1] = sel
            for p in range(n_p):
                order = np.argsort(ws[:, p], kind="stable")[:TOP_N]
                top_rows += [{"method": name, "point": points[p]["name"], "month": mo, "rank": r + 1,
                              "year": S.YEARS[y], "ws": float(ws[y, p])} for r, y in enumerate(order)]
            d5_idx[(name, "local_solar_day")][mo - 1] = select_fs(t, td, w, starts=starts)[0]
            d5_idx[(name, "humidity_mixed_ice")][mo - 1] = select_fs(t, td, w, rh_fn=S.rh_mixed)[0]
        f_loc = S.compute_features(t, td, dtr=S.dtr_local_day(t, lons))
        d5_idx[("CEY20", "local_solar_day")][mo - 1] = S.select_year(S.score_candidates(f_loc))[0]
        f_mix = S.compute_features(t, td, rh_fn=S.rh_mixed, ah_fn=S.ah_mixed)
        d5_idx[("CEY20", "humidity_mixed_ice")][mo - 1] = S.select_year(S.score_candidates(f_mix))[0]
        for p in range(n_p):
            sel_rows.append({"point": points[p]["name"], "month": mo,
                             **{f"year_{m}": S.YEARS[idx[m][mo - 1, p]] for m in METHODS}})
        cnt_base.append(R.counts(t, td))
        cnt_mixed.append({k: f_mix[k].astype(np.float64) for k in R.COUNT_KEYS})
        feats_m.append(res["features"])
        t_months.append(t); td_months.append(td)
        print(f"month {mo:02d} done", flush=True)

    years_t = np.concatenate(t_months, axis=1)          # (years, 8760, points)
    years_td = np.concatenate(td_months, axis=1)
    years_rh = H.rh_of(years_t, years_td)
    if years_t.shape[0] != len(S.YEARS):
        raise SystemExit("year axis does not match S.YEARS")

    annual, monthly, diag, d5, d5_sel, summary = [], [], {k: [] for k in ("d1", "d2", "d3", "d4", "d4s")}, [], [], {}
    for m in METHODS:
        a = [dict(r, method=m, point=points[r["point"]]["name"]) for r in annual_rows(idx[m], cnt_base)]
        mon = []
        for i, mo in enumerate(months):
            mon += [dict(r, method=m, point=points[r["point"]]["name"]) for r in R.monthly_target(mo, feats_m[i], idx[m][i])]
        dg = hourly_diagnostics(m, idx[m], t_months, td_months, points, years_t, years_td, years_rh)
        annual += a; monthly += mon
        for k in diag:
            diag[k] += dg[k]
        for variant, cnt in (("baseline", cnt_base), ("local_solar_day", cnt_base), ("humidity_mixed_ice", cnt_mixed)):
            vidx = idx[m] if variant == "baseline" else d5_idx[(m, variant)]
            changed = int(np.sum(vidx != idx[m]))
            if variant != "baseline":
                d5_sel += d5_selection_rows(m, variant, idx[m], vidx, points)
            d5 += [dict(r, method=m, point=points[r["point"]]["name"], variant=variant, point_months_changed=changed)
                   for r in annual_rows(vidx, cnt)]
        summary[m] = summarise(m, a, mon, dg)
        summary[m]["d5"] = {v: {"point_months_changed": next(r["point_months_changed"] for r in d5
                                                             if r["method"] == m and r["variant"] == v),
                                "target1_failed": sum(not r["pass"] for r in d5 if r["method"] == m and r["variant"] == v)}
                            for v in ("baseline", "local_solar_day", "humidity_mixed_ice")}
    summary["selection_agreement_with_cey20"] = {
        m: {"same_year_point_months": int(np.sum(idx[m] == idx["CEY20"])), "point_months": int(idx[m].size)}
        for m in ("FS-A", "FS-B")}
    summary["label"] = "exploratory comparison; descriptive; does not replace the CEY20 baseline"

    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    files = {"selection.csv": sel_rows, "top5.csv": top_rows, "targets_annual.csv": annual,
             "targets_monthly.csv": monthly, "d1_joint.csv": diag["d1"], "d2_spells.csv": diag["d2"],
             "d3_humid_temperature.csv": diag["d3"], "d4_boundaries.csv": diag["d4"],
             "d4s_boundaries.csv": diag["d4s"], "d5_conventions.csv": d5, "d5_selection.csv": d5_sel}
    for f, rows in files.items():
        S.write_csv(out / f, rows)
    S.write_json(out / "summary.json", summary)
    S.write_json(out / "manifest.json", {
        "command": "auth003_s4_fs", "started_utc": started.isoformat(timespec="seconds"),
        "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "code_sha": S.git_sha(), "freeze": str(args.freeze), "freeze_code_sha": freeze["code_sha"],
        "freeze_input_inventory_sha256": freeze["input_inventory_sha256"], "points": points,
        "input_hashes": str(args.input_hashes), "pin": str(args.pin), "s3_monthly": str(args.s3_monthly),
        "weights": WEIGHTS, "files": [*files, "summary.json"]})
    print(json.dumps({m: {k: v for k, v in summary[m].items() if k.startswith("target")} for m in METHODS}))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="AUTH-003 S4 exploratory FS-based selection (04-fs-exploratory-spec.md).")
    p.add_argument("--freeze", type=Path, required=True)
    p.add_argument("--input-hashes", type=Path, required=True)
    p.add_argument("--pin", type=Path, required=True,
                   help="JSON with SHA-256 of the study/S3/hourly/D4s/S4 scripts and s3_targets_monthly.csv")
    p.add_argument("--s3-monthly", type=Path, required=True, help="targets_monthly.csv of the S3 run (selection cross-check)")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    p.add_argument("--extension-root", type=Path, default=S.builder.DEFAULT_EXTENSION_ROOT)
    p.add_argument("--legacy-root", type=Path, default=S.builder.DEFAULT_LEGACY_ROOT)
    p.add_argument("--verify-only", action="store_true")
    return run(p.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())

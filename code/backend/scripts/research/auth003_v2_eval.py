"""AUTH-003 amendment V2: evaluate the released CEY20 v2 product at the 14 frozen points (12-amendment-V2.md, r3).

Pre-outcome gates (abort on failure, before any outcome is written):
  1 artifact identity: pinned code, pinned S3 selection file, pinned v2 inventory (manifest + 12 month files: SHA-256,
    size, mtime, variables, hour counts, coordinates), manifest version and generating commit, variable units,
    hourly time axis;
  2 selection identity: v2 `selected_source_year` at the 14 points == S3 selection, and the recomputed selection
    == S3 selection, in all 168 point-months;
  3 untouched hours: outside the smoothing mask, v2 T/Td/p == the reconstructed selected-source series exactly;
  4 smoothing implementation: the pinned smoothing (`smooth_cey20_month_interfaces.py` @ 388cfdb4) applied to the
    reconstructed series reproduces every v2 value inside the mask exactly; every modification lies in the mask;
    mask <= 144 positions per point;
  5 integrity: 8,760 hours, finite T/Td/p; Td <= T inside the mask; Td > T outside the mask counted and reported.

Analyses (paired v1 = reconstructed unsmoothed series, v2 = product series; unchanged definitions):
  Target 1 and 2, D1-D3, D4 (J_b and M_b for T, Td, RH and p against the +-72 h reference p99) and D4s (hour-matched
  23->00 UTC reference), D5 (variant selections smoothed with the same pinned function; clarification V2.1),
  S5 A1-A4 at the 14 points and the seven regional envelopes read from the v2 product.

Reads local files only. No network.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import netCDF4
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import auth003_s3 as R  # noqa: E402
import auth003_s3_d4s as D  # noqa: E402
import auth003_s3_hourly as H  # noqa: E402
import auth003_s5_applications as A  # noqa: E402
import auth003_study as S  # noqa: E402

SMOOTHING_PATH = Path(__file__).resolve().parents[1] / "smooth_cey20_month_interfaces.py"
PINNED_FILES = dict(A.PINNED_FILES, **{"auth003_s3_d4s.py": Path(D.__file__).resolve(),
                                       "auth003_v2_eval.py": Path(__file__).resolve(),
                                       "smooth_cey20_month_interfaces.py": SMOOTHING_PATH})
INPUTS_KEY = "12-v2-inputs.json"
EXPECTED_VERSION = "v2-month-interface-smoothing"
EXPECTED_COMMIT = "388cfdb4d90348750df65035cd5e94c2d2cb103a"
VARS = ("temperature_c", "dewpoint_c", "surface_pressure_pa")
EXPECTED_UNITS = {"temperature_c": ("degree_Celsius",), "dewpoint_c": ("degree_Celsius",), "surface_pressure_pa": ("Pa",)}
TIME_UNITS = "hours since 2001-01-01 00:00:00"
N_SIDE = 6
MAX_MASK = 2 * N_SIDE * 12                                # 144 positions per point
HOURS = int(sum(H.MONTH_HOURS))


def load_smoothing(path: Path = SMOOTHING_PATH):
    spec = importlib.util.spec_from_file_location("cey20_v2_smoothing", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if (module.N, module.W, module.B) != (N_SIDE, 2 * N_SIDE + 2, N_SIDE + 1):
        raise SystemExit("smoothing window constants differ from the amendment (N=6, W=14, B=7)")
    return module


def verify_pin(pin: dict, inputs_path: Path) -> None:
    for name, path in PINNED_FILES.items():
        if pin.get(name) != hashlib.sha256(R._lf(path.read_bytes())).hexdigest():
            raise SystemExit(f"{name} does not match the pinned SHA-256")
    if pin.get(INPUTS_KEY) != hashlib.sha256(R._lf(inputs_path.read_bytes())).hexdigest():
        raise SystemExit(f"product inventory is not the pinned {INPUTS_KEY}")


def verify_manifest(root: Path) -> dict:
    meta = json.loads((root / "hourly_manifest.json").read_text(encoding="utf-8"))
    if meta.get("version") != EXPECTED_VERSION or meta.get("generating_commit") != EXPECTED_COMMIT:
        raise SystemExit("v2 manifest version or generating commit differs from the amendment")
    if meta.get("working_tree_clean_at_start") is not True:
        raise SystemExit("v2 manifest does not record a clean generating tree")
    return meta


def verify_month_file(path: Path, month: int, indices: list[int], lat_lon: list[tuple[float, float]]) -> None:
    """Units, dimensions, hourly time axis and the frozen point coordinates of one v2 month file."""
    with netCDF4.Dataset(path) as d:
        for v in VARS:
            var = d.variables[v]
            if var.dimensions != ("time", "point"):
                raise SystemExit(f"{path.name}: {v} dimensions {var.dimensions}")
            if var.dtype != np.float32:
                raise SystemExit(f"{path.name}: {v} dtype {var.dtype} is not float32")
            if getattr(var, "units", None) not in EXPECTED_UNITS[v]:
                raise SystemExit(f"{path.name}: {v} units {getattr(var, 'units', None)!r}")
        if getattr(d["time"], "units", None) != TIME_UNITS:
            raise SystemExit(f"{path.name}: time units {getattr(d['time'], 'units', None)!r}")
        tv = np.asarray(d["time"][:], dtype=np.float64)
        start = float(sum(H.MONTH_HOURS[:month - 1]))
        if tv.size != H.MONTH_HOURS[month - 1] or not np.array_equal(tv, start + np.arange(tv.size)):
            raise SystemExit(f"{path.name}: time axis is not hourly and complete")
        la = np.asarray(d["latitude"][indices], np.float64)
        lo = np.asarray(d["longitude"][indices], np.float64)
    want = np.asarray(lat_lon, np.float64)
    if not (np.allclose(la, want[:, 0], atol=1e-4) and np.allclose(lo, want[:, 1], atol=1e-4)):
        raise SystemExit(f"{path.name}: coordinates at the frozen indices differ from 03-freeze.json")


# ----------------------------------------------------------------------------
# pure computations (unit-tested with synthetic data)
# ----------------------------------------------------------------------------

def _require_f32(a, name: str) -> np.ndarray:
    """Exact gates compare float32 values; any other dtype is refused instead of being coerced."""
    a = np.asarray(a)
    if a.dtype != np.float32:
        raise SystemExit(f"{name}: dtype {a.dtype} is not float32")
    return a


def boundary_hours() -> list[int]:
    """Index b of the first hour of the following month for boundaries 01->02 .. 12->01 (12->01: b = 0)."""
    starts = np.cumsum([0] + list(H.MONTH_HOURS))
    return [int(starts[m]) % HOURS for m in range(1, 13)]


def expected_v2(recon: dict[str, np.ndarray], years: np.ndarray, smoothing) -> tuple[dict, dict]:
    """Apply the pinned smoothing to reconstructed series (8760, points); years (12, points) actual source years.

    Returns (expected series per variable, smoothing mask per variable (8760, points)). The mask holds the 12-hour
    support x[b-6]..x[b+5] of every boundary that the pinned eligibility rules smooth for that point: T and Td share
    one mask, pressure has its own. Boundaries skipped as consecutive or non-finite are outside the mask.
    """
    W, B = smoothing.W, smoothing.B
    out = {v: _require_f32(recon[v], v).copy() for v in VARS}
    shape = out[VARS[0]].shape
    mask = {v: np.zeros(shape, dtype=bool) for v in VARS}
    for m, b in zip(range(1, 13), boundary_hours()):
        rows = (b - B + np.arange(W)) % HOURS                  # x[b-7] .. x[b+6], cyclic for Dec->Jan
        source = {v: _require_f32(recon[v], v)[rows] for v in VARS}       # immutable source windows
        elig = smoothing.eligibility({v: w.copy() for v, w in source.items()}, m, years[m - 1], years[m % 12])
        smoothed, _ = smoothing.smooth_boundary({v: w.copy() for v, w in source.items()}, m,
                                                years[m - 1], years[m % 12])
        for v in VARS:
            out[v][rows[1:W - 1]] = smoothed[v][1:W - 1]
            ok = elig["pressure"] if v == "surface_pressure_pa" else elig["t_td"]
            block = mask[v][rows[1:W - 1]]
            block[:, ok] = True
            mask[v][rows[1:W - 1]] = block
    return out, mask


def gate_compare(product: dict, recon: dict, expected: dict, mask: dict) -> dict:
    """Gates 3-5 per variable: exact equality outside and inside the mask; modifications only inside the mask."""
    report = {}
    for v in VARS:
        prod, rec, exp_ = (_require_f32(x[v], f"{v}") for x in (product, recon, expected))
        support = mask[v]
        modified = prod != rec
        report[v] = {
            "outside_support_mismatches": int(np.sum(modified & ~support)),
            "inside_support_mismatches_vs_reproduction": int(np.sum((prod != exp_) & support)),
            "modified_positions": int(modified.sum()),
            "modified_per_point_max": int(modified.sum(axis=0).max()),
            "nonfinite": int(np.sum(~np.isfinite(prod))),
        }
    union = np.zeros(mask[VARS[0]].shape, dtype=bool)
    support_any = np.zeros_like(union)
    for v in VARS:
        union |= _require_f32(product[v], v) != _require_f32(recon[v], v)
        support_any |= mask[v]
    t, td = _require_f32(product["temperature_c"], "temperature_c"), _require_f32(product["dewpoint_c"], "dewpoint_c")
    support = mask["temperature_c"]
    report["union"] = {"modified_positions": int(union.sum()), "modified_per_point_max": int(union.sum(axis=0).max()),
                       "support_per_point": int(support_any.sum(axis=0).max())}
    report["td_gt_t_inside_support"] = int(np.sum((td > t) & support))
    outside = (td > t) & ~support
    report["td_gt_t_outside_support_per_point"] = outside.sum(axis=0).astype(int).tolist()
    report["td_minus_t_outside_support_max"] = float(np.max(np.where(outside, td - t, -np.inf))) if outside.any() else None
    return report


def gates_pass(report: dict) -> list[str]:
    errs = []
    for v in VARS:
        r = report[v]
        if r["outside_support_mismatches"] or r["inside_support_mismatches_vs_reproduction"] or r["nonfinite"]:
            errs.append(f"{v}: {r}")
    if report["union"]["support_per_point"] > MAX_MASK or report["union"]["modified_per_point_max"] > MAX_MASK:
        errs.append(f"support exceeds {MAX_MASK}: {report['union']}")
    if report["td_gt_t_inside_support"]:
        errs.append(f"Td > T inside the support: {report['td_gt_t_inside_support']}")
    return errs


def join_step(series: np.ndarray, b: int) -> float:
    """J_b = |x_b - x_{b-1}| (cyclic)."""
    return float(abs(series[b % HOURS] - series[(b - 1) % HOURS]))


def local_max_step(series: np.ndarray, b: int) -> float:
    """M_b = max_{k=-6..6} |x_{b+k} - x_{b+k-1}| (cyclic): every increment touching the support x_{b-6}..x_{b+5}."""
    k = np.arange(-N_SIDE, N_SIDE + 1)
    return float(np.max(np.abs(series[(b + k) % HOURS] - series[(b + k - 1) % HOURS])))


def monthly_counts(series_t: np.ndarray, series_td: np.ndarray, rh_fn=None) -> dict[str, np.ndarray]:
    """(12, points) exposure counts of one 8760 series per calendar month, builder humidity unless rh_fn given."""
    starts = np.cumsum([0] + list(H.MONTH_HOURS))
    out = {k: [] for k in R.COUNT_KEYS}
    for m in range(12):
        t, td = series_t[starts[m]:starts[m + 1]], series_td[starts[m]:starts[m + 1]]
        rh = (rh_fn or S._relative_humidity_from_dewpoint)(t, td).astype(np.float32)
        out["hours_rh_ge_80"].append(np.count_nonzero(rh >= 80.0, axis=0))
        out["hours_rh_ge_90"].append(np.count_nonzero(rh >= 90.0, axis=0))
        out["hours_dewpoint_depression_le_2c"].append(np.count_nonzero((t - td) <= 2.0, axis=0))
    return {k: np.asarray(v, np.float64) for k, v in out.items()}


def monthly_means(series_t: np.ndarray, series_td: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(12, points) mean T and mean RH (builder feature definitions) of one 8760 series."""
    starts = np.cumsum([0] + list(H.MONTH_HOURS))
    mt, mrh = [], []
    for m in range(12):
        f = S.compute_features(series_t[None, starts[m]:starts[m + 1]], series_td[None, starts[m]:starts[m + 1]])
        mt.append(f["temperature_mean_c"][0]); mrh.append(f["relative_humidity_mean_pct"][0])
    return np.asarray(mt, np.float64), np.asarray(mrh, np.float64)


def monthly_target_rows(label: str, means_t, means_rh, ref_t, ref_rh, years, points) -> list[dict]:
    rows = []
    for m in range(12):
        for p, pt in enumerate(points):
            d_t, d_rh = float(means_t[m, p] - ref_t[m, p]), float(means_rh[m, p] - ref_rh[m, p])
            rows.append({"version": label, "point": pt["name"], "month": m + 1, "selected_year": int(years[m, p]),
                         "d_temperature_c": d_t, "d_rh_pct": d_rh, "pass_t": abs(d_t) <= R.MONTHLY_T_TOL_C,
                         "pass_rh": abs(d_rh) <= R.MONTHLY_RH_TOL_PCT})
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
    verify_pin(pin, Path(args.product_inputs))
    H.verify_s3_selection_file(Path(args.s3_monthly), pin)
    R.verify_code(repo, freeze)
    smoothing = load_smoothing()
    points = R.frozen_points(freeze)
    months = list(range(1, 13))
    sources = S.discover_sources(args.extension_root, args.legacy_root, months)
    R.verify_inputs(sources, freeze)
    R.verify_input_hashes(sources, json.loads(Path(args.input_hashes).read_text(encoding="utf-8")), freeze)
    s3_idx = H.read_s3_selection(Path(args.s3_monthly), points)
    root = Path(args.product_root)
    meta = verify_manifest(root)
    lat, lon = A.verify_product(root, inputs)                  # SHA-256, size, mtime, variables, hours, coordinates
    pos = {p["name"]: i for i, p in enumerate(points)}
    for name, index in A.REGIONS:
        if name in pos and points[pos[name]]["index"] != index:
            raise SystemExit(f"region centre {name} differs from the frozen point index")
    load_points = [p["index"] for p in points] + [dict(A.REGIONS)[A.EXTRA_CENTRE]]
    frz = {p["name"]: p for p in freeze["points"]}
    lat_lon = [(frz[p["name"]]["grid_lat"], frz[p["name"]]["grid_lon"]) for p in points]
    lat_lon.append((float(lat[load_points[-1]]), float(lon[load_points[-1]])))
    for m in months:
        verify_month_file(root / "hourly" / A.PRODUCT_FILE.format(m), m, load_points, lat_lon)
    if args.verify_only:
        print(json.dumps({"verified_without_selection_and_value_gates": True, "points": len(points)}))
        return 0

    n_p, extra = len(points), len(points)
    lons = np.asarray([frz[p["name"]]["grid_lon"] for p in points])
    data = {v: [] for v in VARS}                               # per month (years, hours, n_p + 1)
    product = {v: [] for v in VARS}                            # per month (hours, n_p + 1)
    idx = np.zeros((12, n_p + 1), dtype=np.int16)
    idx_local, idx_mixed = np.zeros((12, n_p), np.int16), np.zeros((12, n_p), np.int16)
    boxes = {name: A.box_members(lat, lon, float(lat[i]), float(lon[i])) for name, i in A.REGIONS}
    envelope_rows = []
    for m in months:
        md = S.load_points_month(sources, m, load_points)
        res = S.analyse_month({k: v[:, :, :n_p] for k, v in md.items()})      # asserts production parity
        R.require_complete(m, res, points)
        if not np.array_equal(res["idx"], s3_idx[m - 1]):
            raise SystemExit(f"month {m}: recomputed selection differs from the S3 run")
        if S.valid_hour_coverage(md["temperature_c"][:, :, extra:], md["dewpoint_c"][:, :, extra:]).min() < 1.0:
            raise SystemExit(f"month {m}: Iqaluit reference coverage below 1")
        t, td = md["temperature_c"][:, :, :n_p], md["dewpoint_c"][:, :, :n_p]
        idx_local[m - 1] = S.select_year(S.score_candidates(S.compute_features(t, td, dtr=S.dtr_local_day(t, lons))))[0]
        idx_mixed[m - 1] = S.select_year(S.score_candidates(
            S.compute_features(t, td, rh_fn=S.rh_mixed, ah_fn=S.ah_mixed)))[0]
        with netCDF4.Dataset(root / "hourly" / A.PRODUCT_FILE.format(m)) as d:
            years = np.asarray(d["selected_source_year"][load_points], dtype=np.int32)
            if not np.array_equal(years[:n_p], [S.YEARS[i] for i in s3_idx[m - 1]]):
                raise SystemExit(f"month {m}: v2 selected_source_year differs from the S3 selection")
            idx[m - 1, :n_p] = s3_idx[m - 1]
            idx[m - 1, extra] = S.YEARS.index(int(years[extra]))
            for v in VARS:
                product[v].append(np.asarray(d[v][:, load_points]))
            for name, _ in A.REGIONS:
                members = boxes[name]
                vals = A.monthly_point_values(np.asarray(d["temperature_c"][:, members], np.float32),
                                              np.asarray(d["dewpoint_c"][:, members], np.float32),
                                              H.MONTH_HOURS[m - 1])
                col = pos[name] if name in pos else extra
                yv = A.monthly_point_values_years(md["temperature_c"][:, :, col], md["dewpoint_c"][:, :, col])
                for q in vals:
                    envelope_rows.append(dict(region=name, month=m, quantity=q, **A.spatial_summary(vals[q]),
                                              centre_years_min=float(yv[q].min()),
                                              centre_years_median=float(np.percentile(yv[q], 50, method="linear")),
                                              centre_years_max=float(yv[q].max())))
        for v in VARS:
            data[v].append(md[v])
        print(f"month {m:02d} loaded", flush=True)

    recon = {v: H.assemble(data[v], idx) for v in VARS}        # v1 construction (8760, n_p + 1)
    prod = {v: np.concatenate(product[v], axis=0) for v in VARS}
    sel_years = np.asarray([[S.YEARS[i] for i in row] for row in idx], dtype=np.int32)
    expected, mask = expected_v2(recon, sel_years, smoothing)
    report = gate_compare(prod, recon, expected, mask)
    errors = gates_pass(report)
    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    S.write_json(out / "gates.json", report)
    if errors:
        raise SystemExit("v2 value gates failed (no outcomes written): " + "; ".join(errors))
    print("pre-outcome gates passed", flush=True)

    # ---- outcomes (14 points; the Iqaluit column is used for envelopes and gates only) ----
    cols = slice(0, n_p)
    years = {v: np.concatenate([x[:, :, cols] for x in data[v]], axis=1) for v in VARS}     # (20, 8760, n_p)
    series = {"v1": {v: recon[v][:, cols] for v in VARS}, "v2": {v: prod[v][:, cols] for v in VARS}}
    all_counts = {k: np.stack([R.counts(x_t[:, :, cols], x_td[:, :, cols])[k]
                               for x_t, x_td in zip(data["temperature_c"], data["dewpoint_c"])])
                  for k in R.COUNT_KEYS}                                   # (12, 20, n_p)
    ref_rh = np.stack([S.compute_features(x_t[:, :, cols], x_td[:, :, cols])["relative_humidity_mean_pct"].mean(axis=0)
                       for x_t, x_td in zip(data["temperature_c"], data["dewpoint_c"])])
    ref_t = np.stack([S.compute_features(x_t[:, :, cols], x_td[:, :, cols])["temperature_mean_c"].mean(axis=0)
                      for x_t, x_td in zip(data["temperature_c"], data["dewpoint_c"])])
    annual_rows, monthly_rows = [], []
    for label, s in series.items():
        sel = monthly_counts(s["temperature_c"], s["dewpoint_c"])
        annual_rows += [dict(r, version=label, point=points[r["point"]]["name"]) for r in R.annual_target(sel, all_counts)]
        mt, mrh = monthly_means(s["temperature_c"], s["dewpoint_c"])
        monthly_rows += monthly_target_rows(label, mt, mrh, ref_t, ref_rh, sel_years[:, :n_p], points)

    years_rh = H.rh_of(years["temperature_c"], years["dewpoint_c"])
    d1, d2, d3, d4 = [], [], [], []
    n_y = years_rh.shape[0]
    for label, s in series.items():
        rh = H.rh_of(s["temperature_c"], s["dewpoint_c"])
        for p, pt in enumerate(points):
            name = pt["name"]
            pooled = H.joint_hist(years["temperature_c"][:, :, p], years_rh[:, :, p])
            c_h = H.joint_hist(s["temperature_c"][:, p], rh[:, p])
            for metric, fn in (("hellinger", H.hellinger), ("total_variation", H.total_variation)):
                c = fn(c_h, pooled)
                yrs = [fn(H.joint_hist(years["temperature_c"][y, :, p], years_rh[y, :, p]), pooled) for y in range(n_y)]
                d1.append(dict(version=label, point=name, metric=metric, **H.context(c, yrs),
                               rank_closest=1 + sum(v < c for v in yrs)))
            for th in H.SPELL_THRESHOLDS:
                cs = H.spell_stats(rh[:, p], th)
                ys = [H.spell_stats(years_rh[y, :, p], th) for y in range(n_y)]
                for k in cs:
                    d2.append(dict(version=label, point=name, threshold=th, statistic=k,
                                   **H.context(cs[k], [y[k] for y in ys])))
            ch = H.humid_temperature(s["temperature_c"][:, p], rh[:, p])
            ph = H.humid_temperature(years["temperature_c"][:, :, p].ravel(), years_rh[:, :, p].ravel())
            ph["n_humid_hours"] = ph["n_humid_hours"] / n_y
            yh = [H.humid_temperature(years["temperature_c"][y, :, p], years_rh[y, :, p]) for y in range(n_y)]
            for k in ch:
                d3.append(dict(version=label, point=name, statistic=k, pooled=ph[k],
                               diff=(ch[k] - ph[k]) if ch[k] is not None and ph[k] is not None else None,
                               **H.context(ch[k], [y[k] for y in yh])))
            var_series = {"temperature_c": (s["temperature_c"][:, p], years["temperature_c"][:, :, p]),
                          "dewpoint_c": (s["dewpoint_c"][:, p], years["dewpoint_c"][:, :, p]),
                          "rh_pct": (rh[:, p], years_rh[:, :, p]),
                          "surface_pressure_pa": (s["surface_pressure_pa"][:, p], years["surface_pressure_pa"][:, :, p])}
            for m, b in zip(range(1, 13), boundary_hours()):
                same_source = bool(sel_years[m - 1, p] == sel_years[m % 12, p])
                same = same_source and m < 12              # frozen D4 definition: Dec->Jan is never consecutive
                for var, (cs_, ys_) in var_series.items():
                    if m < 12:
                        ref, ref_mid = H.boundary_reference(ys_, m), D.midnight_reference(ys_, m, S.YEARS)
                    else:
                        ref, ref_mid = H.wrap_reference(ys_), D.midnight_wrap_reference(ys_)
                    p99, p99_mid = float(np.percentile(ref, 99)), float(np.percentile(ref_mid, 99))
                    j, mb = join_step(cs_, b), local_max_step(cs_, b)
                    d4.append({"version": label, "point": name, "boundary": f"{m:02d}->{m % 12 + 1:02d}",
                               "wrap": m == 12, "variable": var, "same_year": same,
                               "same_source_year": same_source,
                               "new_in_amendment_v2": var == "surface_pressure_pa",
                               "J_b": j, "M_b": mb, "ref_p99": p99, "ref_p99_midnight": p99_mid,
                               "J_above_ref_p99": j > p99, "M_above_ref_p99": mb > p99,
                               "J_above_ref_p99_midnight": j > p99_mid, "M_above_ref_p99_midnight": mb > p99_mid})

    # D5 (clarification V2.1): variant selections smoothed with the same pinned function
    d5 = []
    for variant, vidx, rh_fn in (("baseline", idx[:, :n_p], None), ("local_solar_day", idx_local, None),
                                 ("humidity_mixed_ice", idx_mixed, S.rh_mixed)):
        vyears = np.asarray([[S.YEARS[i] for i in row] for row in vidx], dtype=np.int32)
        if variant == "baseline":
            v2s = series["v2"]
        else:
            vrec = {v: H.assemble([x[:, :, cols] for x in data[v]], vidx) for v in VARS}
            v2s, _ = expected_v2(vrec, vyears, smoothing)
        if rh_fn is None:
            ref_counts = all_counts
        else:
            ref_counts = {k: np.stack([S.compute_features(x_t[:, :, cols], x_td[:, :, cols], rh_fn=S.rh_mixed,
                                                          ah_fn=S.ah_mixed)[k].astype(np.float64)
                                       for x_t, x_td in zip(data["temperature_c"], data["dewpoint_c"])])
                          for k in R.COUNT_KEYS}
        sel = monthly_counts(v2s["temperature_c"], v2s["dewpoint_c"], rh_fn)
        changed = int(np.sum(vidx != idx[:, :n_p]))
        d5 += [dict(r, version="v2", variant=variant, point=points[r["point"]]["name"], point_months_changed=changed)
               for r in R.annual_target(sel, ref_counts)]

    rows = {"a1": [], "a2": [], "a3": [], "a4": []}
    curves = []
    for label, s in series.items():
        for p, pt in enumerate(points):
            r = A.application_rows(pt["name"], s["temperature_c"][:, p], s["dewpoint_c"][:, p],
                                   years["temperature_c"][:, :, p], years["dewpoint_c"][:, :, p])
            for k in rows:
                rows[k] += [dict(x, version=label) for x in r[k]]
            curves += [dict(x, version=label) for x in A.duration_curves(pt["name"], s["temperature_c"][:, p],
                                                                         years["temperature_c"][:, :, p])]

    files = {"targets_annual.csv": annual_rows, "targets_monthly.csv": monthly_rows, "d1_joint.csv": d1,
             "d2_spells.csv": d2, "d3_humid_temperature.csv": d3, "d4_boundaries.csv": d4, "d5_conventions.csv": d5,
             "a1_duration.csv": rows["a1"], "a1_curves.csv": curves, "a2_heat_pump.csv": rows["a2"],
             "a3_tow.csv": rows["a3"], "a4_saturation_zero_crossing.csv": rows["a4"],
             "regional_envelopes_v2.csv": envelope_rows}
    for f, rws in files.items():
        S.write_csv(out / f, rws)

    def count(rows_, key, label):
        return sum(not r[key] for r in rows_ if r["version"] == label)

    def d4_counts(rows_):
        return {v: {"n": sum(1 for r in rows_ if r["variable"] == v),
                    **{f"{s}_above_{ref}": sum(r[f"{s}_above_{ref}"] for r in rows_ if r["variable"] == v)
                       for s in ("J", "M") for ref in ("ref_p99", "ref_p99_midnight")}}
                for v in ("temperature_c", "dewpoint_c", "rh_pct", "surface_pressure_pa")}

    d4_groups = {"inner_cross_year": lambda r: not r["wrap"] and not r["same_year"],
                 "inner_same_year": lambda r: not r["wrap"] and r["same_year"],
                 "wrap": lambda r: r["wrap"]}
    summary = {
        "label": "amendment V2 (outcome-informed); descriptive; in-sample",
        "target1_failed": {lab: count(annual_rows, "pass", lab) for lab in series},
        "target2_t_failed": {lab: count(monthly_rows, "pass_t", lab) for lab in series},
        "target2_rh_failed": {lab: count(monthly_rows, "pass_rh", lab) for lab in series},
        "d1_rank1_hellinger": {lab: sum(r["rank_closest"] == 1 for r in d1 if r["version"] == lab and r["metric"] == "hellinger")
                               for lab in series},
        "d4": {lab: {g: d4_counts([r for r in d4 if r["version"] == lab and f(r)]) for g, f in d4_groups.items()}
               for lab in series},
        "d5_target1_failed": {v: sum(not r["pass"] for r in d5 if r["variant"] == v)
                              for v in ("baseline", "local_solar_day", "humidity_mixed_ice")},
        "gates": "passed (gates.json)",
    }
    S.write_json(out / "summary.json", summary)
    S.write_json(out / "manifest.json", {
        "command": "auth003_v2_eval", "started_utc": started.isoformat(timespec="seconds"),
        "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "code_sha": S.git_sha(), "freeze": str(args.freeze), "freeze_code_sha": freeze["code_sha"],
        "freeze_input_inventory_sha256": freeze["input_inventory_sha256"], "points": points,
        "input_hashes": str(args.input_hashes), "pin": str(args.pin), "s3_monthly": str(args.s3_monthly),
        "product_root": str(root), "product_inputs": inputs, "product_version": meta["version"],
        "product_generating_commit": meta["generating_commit"], "files": ["gates.json", *files, "summary.json"]})
    print(json.dumps({k: summary[k] for k in ("target1_failed", "target2_t_failed", "target2_rh_failed")}))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="AUTH-003 amendment V2: evaluation of the released CEY20 v2 product.")
    p.add_argument("--freeze", type=Path, required=True)
    p.add_argument("--input-hashes", type=Path, required=True)
    p.add_argument("--pin", type=Path, required=True, help="12-v2-pin.json committed before the run")
    p.add_argument("--s3-monthly", type=Path, required=True, help="targets_monthly.csv of the S3 run")
    p.add_argument("--product-inputs", type=Path, required=True, help="12-v2-inputs.json (pinned v2 inventory)")
    p.add_argument("--product-root", type=Path, required=True, help="v2 root with hourly_manifest.json and hourly/")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    p.add_argument("--extension-root", type=Path, default=S.builder.DEFAULT_EXTENSION_ROOT)
    p.add_argument("--legacy-root", type=Path, default=S.builder.DEFAULT_LEGACY_ROOT)
    p.add_argument("--verify-only", action="store_true")
    return run(p.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())

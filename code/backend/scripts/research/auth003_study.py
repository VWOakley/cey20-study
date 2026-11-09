"""AUTH-003 study package: analysis of the CEY20 representative-year selection.

Runs on the operator's machine against the packed ERA5-Land monthly archives.
It reuses the production helpers of ``build_global_cey20_landpoint_dataset``
(weights, scales, loaders, selection, humidity formulas); the only code that
mirrors the builder is the feature block, because the builder does not expose
its features.  Every subcommand re-checks the mirrored selection against
``_select_representative_year`` and aborts on a mismatch.

No result is claimed by this module; see docs/research/auth003-tmy/02-study-package.md.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import importlib.util
import json
import subprocess
import sys
import warnings
from pathlib import Path

import numpy as np

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = SCRIPTS_DIR.parent


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


builder = _load_module(
    "auth003_cey20_builder", SCRIPTS_DIR / "build_global_cey20_landpoint_dataset.py"
)
FEATURE_WEIGHTS = builder.FEATURE_WEIGHTS
FEATURE_SCALES = builder.FEATURE_SCALES
YEARS = builder.YEARS
discover_sources = builder.discover_sources
_load_month_chunk = builder._load_month_chunk
_select_representative_year = builder._select_representative_year
_relative_humidity_from_dewpoint = builder._relative_humidity_from_dewpoint
_absolute_humidity_from_dewpoint = builder._absolute_humidity_from_dewpoint
_daily_temperature_range_mean = builder._daily_temperature_range_mean

FEATURES = tuple(FEATURE_WEIGHTS)
EXPOSURE_FEATURES = ("hours_rh_ge_80", "hours_rh_ge_90", "hours_dewpoint_depression_le_2c")
TIE_TOLERANCE = 1e-6
# Magnus-type coefficients over ice (hPa, degC). Listed under the WMO CIMO Guide
# (2008) in H. Voemel's online overview of vapour-pressure formulations (secondary
# source). Primary citation NOT verified: UNVERIFIED. Not claimed to be
# Alduchov-Eskridge (1996), whose ice coefficients differ.
ICE_COEFFICIENTS = (6.112, 22.46, 272.62)
ICE_CITATION_STATUS = "UNVERIFIED (secondary: WMO CIMO Guide 2008 via Voemel overview)"


# ----------------------------------------------------------------------------
# core computation
# ----------------------------------------------------------------------------

def compute_features(
    temperature: np.ndarray,
    dewpoint: np.ndarray,
    *,
    rh_fn=None,
    ah_fn=None,
    dtr: np.ndarray | None = None,
) -> dict[str, np.ndarray]:
    """Ten monthly features, shape (years, points); mirrors the builder block."""
    rh_fn = rh_fn or _relative_humidity_from_dewpoint
    ah_fn = ah_fn or _absolute_humidity_from_dewpoint
    rh = rh_fn(temperature, dewpoint).astype(np.float32)
    ah = ah_fn(temperature, dewpoint).astype(np.float32)
    spread = temperature - dewpoint
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return {
            "temperature_mean_c": np.nanmean(temperature, axis=1),
            "temperature_p95_c": np.nanpercentile(temperature, 95, axis=1),
            "relative_humidity_mean_pct": np.nanmean(rh, axis=1),
            "relative_humidity_p90_pct": np.nanpercentile(rh, 90, axis=1),
            "absolute_humidity_mean_g_m3": np.nanmean(ah, axis=1),
            "dewpoint_depression_p10_c": np.nanpercentile(spread, 10, axis=1),
            "hours_rh_ge_80": np.count_nonzero(rh >= 80.0, axis=1).astype(np.float32),
            "hours_rh_ge_90": np.count_nonzero(rh >= 90.0, axis=1).astype(np.float32),
            "hours_dewpoint_depression_le_2c": np.count_nonzero(spread <= 2.0, axis=1).astype(np.float32),
            "daily_temperature_range_mean_c": (
                _daily_temperature_range_mean(temperature) if dtr is None else dtr
            ),
        }


UNKNOWN = "UNKNOWN"


def valid_hour_coverage(temperature: np.ndarray, dewpoint: np.ndarray) -> np.ndarray:
    """Fraction (0..1) of hours with finite temperature AND dew point, shape (years, points).

    Exposure counts are computed over valid hours only; a NaN hour is neither an
    exceedance nor a non-exceedance, so any coverage < 1 makes the count incomplete.
    """
    valid = np.isfinite(temperature) & np.isfinite(dewpoint)
    return valid.mean(axis=1)


def _exposure_value(value: float, coverage: float):
    """Numeric count only when coverage is 100 %; otherwise UNKNOWN (never a silent number)."""
    return float(value) if coverage >= 1.0 else UNKNOWN


def climatology(features: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return {k: np.nanmean(v, axis=0) for k, v in features.items()}


def interannual_std(features: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Sample standard deviation (ddof=1) over candidate years, NaN ignored."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return {k: np.nanstd(v, axis=0, ddof=1) for k, v in features.items()}


def score_candidates(
    features: dict[str, np.ndarray],
    weights: dict[str, float] | None = None,
    scales: dict[str, np.ndarray | float] | None = None,
) -> np.ndarray:
    """Weighted scaled L1 score, shape (years, points); float32 like the builder.

    A zero/NaN per-point scale (e.g. local std of a constant feature) removes
    that feature's term: all deviations of a zero-variance feature are 0 anyway.
    """
    weights = weights or FEATURE_WEIGHTS
    scales = scales or FEATURE_SCALES
    first = next(iter(features.values()))
    scores = np.zeros_like(first, dtype=np.float32)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        for name, values in features.items():
            scale = np.asarray(scales[name], dtype=np.float32)
            safe = np.where(np.isfinite(scale) & (scale > 0), scale, np.inf)
            scores += weights[name] * np.abs(values - np.nanmean(values, axis=0, keepdims=True)) / safe
    return scores


def select_year(scores: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(selected index, score, all_nan flag) per point; all-NaN points give -1/NaN.

    The builder raises ValueError for an all-NaN score column; here the guard is
    explicit so the study can report it instead of aborting.
    """
    all_nan = np.all(np.isnan(scores), axis=0)
    filled = np.where(np.isnan(scores), np.inf, scores)
    idx = np.argmin(filled, axis=0)  # first minimum = earliest year
    best = scores[idx, np.arange(scores.shape[1])]
    idx = np.where(all_nan, -1, idx).astype(np.int16)
    return idx, np.where(all_nan, np.nan, best).astype(np.float32), all_nan


def builder_selection(month_data: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    """Production selection; falls back to per-point calls if the chunk raises."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            return _select_representative_year(month_data)
    except ValueError:
        points = month_data["temperature_c"].shape[2]
        idx = np.full(points, -1, dtype=np.int16)
        score = np.full(points, np.nan, dtype=np.float32)
        for p in range(points):
            sub = {k: v[:, :, p : p + 1] for k, v in month_data.items()}
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    i, s = _select_representative_year(sub)
                idx[p], score[p] = i[0], s[0]
            except ValueError:
                pass
        return idx, score


def assert_parity(month_data, idx, score) -> None:
    ref_idx, ref_score = builder_selection(month_data)
    if not np.array_equal(ref_idx, idx):
        raise RuntimeError("selection parity failure: study selection differs from builder")
    both = np.isfinite(ref_score) & np.isfinite(score)
    if not np.allclose(ref_score[both], score[both], rtol=1e-5, atol=1e-6):
        raise RuntimeError("score parity failure: study score differs from builder")


# --- variants used by sensitivity / checks ---------------------------------

def saturation_hpa_water(t):
    return 6.112 * np.exp((17.67 * t) / (t + 243.5))


def saturation_hpa_mixed(t):
    """Water for t >= 0 degC, ice (ICE_COEFFICIENTS) for t < 0 degC."""
    a, b, c = ICE_COEFFICIENTS
    return np.where(t < 0, a * np.exp(b * t / (t + c)), saturation_hpa_water(t))


def rh_mixed(temperature, dewpoint):
    return np.clip(saturation_hpa_mixed(dewpoint) / saturation_hpa_mixed(temperature) * 100.0, 0.0, 100.0)


def ah_mixed(temperature, dewpoint):
    return 216.7 * saturation_hpa_mixed(dewpoint) / (temperature + 273.15)


def local_day_shift_hours(longitude: float) -> int:
    """Approximate local solar offset: round(lon / 15) hours (no equation of time/DST)."""
    return int(round(float(longitude) / 15.0))


def dtr_local_day(temperature: np.ndarray, longitudes: np.ndarray) -> np.ndarray:
    """Daily temperature range mean over local-solar 24 h blocks, shape (years, points).

    Local day boundaries fall at UTC hours h with (h + shift) % 24 == 0.  Only
    full local days inside the month window are used (edge partial days are
    dropped), so shift 0 reproduces the builder's UTC value exactly.
    """
    years, hours, points = temperature.shape
    out = np.full((years, points), np.nan, dtype=np.float32)
    for p in range(points):
        start = (-local_day_shift_hours(longitudes[p])) % 24
        blocks = (hours - start) // 24
        sub = temperature[:, start : start + blocks * 24, p : p + 1]
        out[:, p] = _daily_temperature_range_mean(sub)[:, 0]
    return out


def weight_variants() -> list[tuple[str, dict[str, float]]]:
    variants = [("equal_weights", {k: 1.0 for k in FEATURES})]
    for name in FEATURES:
        for label, factor in (("+25%", 1.25), ("-25%", 0.75)):
            w = dict(FEATURE_WEIGHTS)
            w[name] *= factor
            variants.append((f"{name}{label}", w))
    return variants


# ----------------------------------------------------------------------------
# data access and points
# ----------------------------------------------------------------------------

def read_coordinates(sample_path: Path) -> tuple[np.ndarray, np.ndarray]:
    import netCDF4

    with netCDF4.Dataset(sample_path) as ds:
        return (
            np.asarray(ds.variables["latitude"][:], dtype=np.float64),
            np.asarray(ds.variables["longitude"][:], dtype=np.float64),
        )


def _nearest_indices(sample_path: Path, requests: list[tuple[str, float, float]]):
    """Nearest landpoint per requested lat/lon.

    Uses the city builder's ``_resolve_city_point`` when it can be imported
    (needs the backend app dependencies); otherwise a plain haversine search
    with the same 6371 km radius.
    """
    try:
        sys.path.insert(0, str(BACKEND_DIR))
        city = _load_module(
            "auth003_city_builder", SCRIPTS_DIR / "build_city_cey10_from_era5_land_hourly.py"
        )
        out = []
        for name, lat, lon in requests:
            p = city._resolve_city_point(sample_path, name, name, lat, lon)
            out.append((name, p.point_index, p.distance_km))
        return out, "build_city_cey10_from_era5_land_hourly._resolve_city_point"
    except ImportError:
        pass
    finally:
        if sys.path and sys.path[0] == str(BACKEND_DIR):
            sys.path.pop(0)
    lats, lons = read_coordinates(sample_path)
    out = []
    for name, lat, lon in requests:
        lat1, lat2 = np.deg2rad(lats), np.deg2rad(lat)
        a = (np.sin((lat2 - lat1) / 2) ** 2
             + np.cos(lat1) * np.cos(lat2) * np.sin(np.deg2rad(lon - lons) / 2) ** 2)
        dist = 2 * 6371.0 * np.arcsin(np.sqrt(a))
        i = int(np.nanargmin(dist))
        out.append((name, i, float(dist[i])))
    return out, "fallback_haversine"


def resolve_points(args, sample_path: Path) -> list[dict]:
    lats, lons = read_coordinates(sample_path)
    requests, direct = [], []
    if args.points_file:
        with open(args.points_file, newline="", encoding="utf-8") as handle:
            for n, row in enumerate(csv.DictReader(handle)):
                name = row.get("name") or f"point{n}"
                if row.get("index") not in (None, ""):
                    direct.append((name, int(row["index"])))
                elif row.get("lat") and row.get("lon"):
                    requests.append((name, float(row["lat"]), float(row["lon"])))
                else:
                    raise SystemExit(f"{args.points_file}: row {n + 2} needs index or lat+lon")
    for text in args.point or []:
        try:
            lat_s, lon_s = text.split(",")
            requests.append((f"lat{lat_s}_lon{lon_s}", float(lat_s), float(lon_s)))
        except ValueError:
            raise SystemExit(f"--point expects 'lat,lon', got {text!r}")
    for index in args.point_index or []:
        direct.append((f"index{index}", int(index)))
    resolved, method = _nearest_indices(sample_path, requests) if requests else ([], "n/a")
    points = []
    for name, index in direct:
        if not 0 <= index < len(lats):
            raise SystemExit(f"point index {index} outside 0..{len(lats) - 1}")
        points.append({"name": name, "index": index, "distance_km": 0.0})
    for name, index, dist in resolved:
        points.append({"name": name, "index": index, "distance_km": round(dist, 3)})
    if not points:
        raise SystemExit("no points given: use --points-file, --point or --point-index")
    seen = set()
    for p in points:
        if p["index"] in seen:
            raise SystemExit(f"duplicate point index {p['index']}")
        seen.add(p["index"])
        p["lat"], p["lon"] = float(lats[p["index"]]), float(lons[p["index"]])
    return points


def load_points_month(sources, month: int, indices: list[int]) -> dict[str, np.ndarray]:
    """Month data (years, hours, n_points) for explicit landpoint indices."""
    import netCDF4
    from contextlib import ExitStack

    with ExitStack() as stack:
        datasets = {y: stack.enter_context(netCDF4.Dataset(sources[(y, month)].path)) for y in YEARS}
        parts = [_load_month_chunk(sources, month, i, i + 1, datasets=datasets) for i in indices]
    return {k: np.concatenate([p[k] for p in parts], axis=2) for k in parts[0]}


# ----------------------------------------------------------------------------
# per-month analysis (pure functions of month_data; used by subcommands + tests)
# ----------------------------------------------------------------------------

def analyse_month(month_data: dict[str, np.ndarray]) -> dict:
    t, td = month_data["temperature_c"], month_data["dewpoint_c"]
    feats = compute_features(t, td)
    scores = score_candidates(feats)
    idx, best, all_nan = select_year(scores)
    assert_parity(month_data, idx, best)
    return {"features": feats, "scores": scores, "idx": idx, "best": best, "all_nan": all_nan,
            "coverage": valid_hour_coverage(t, td)}


def _year_of(idx: int):
    return YEARS[idx] if idx >= 0 else ""


def _take(values: np.ndarray, idx: np.ndarray) -> np.ndarray:
    """values[(years, points)] at selected years; NaN where idx == -1."""
    out = values[np.maximum(idx, 0), np.arange(values.shape[1])].astype(np.float64)
    return np.where(idx >= 0, out, np.nan)


def rows_features(month, points, res):
    rows = []
    clim = climatology(res["features"])
    for p, point in enumerate(points):
        for yi, year in enumerate(YEARS):
            row = {"point": point["name"], "month": month, "year": year}
            cov = float(res["coverage"][yi, p])
            row.update({k: (_exposure_value(v[yi, p], cov) if k in EXPOSURE_FEATURES else float(v[yi, p]))
                        for k, v in res["features"].items()})
            row["valid_hour_coverage"] = cov
            row["exposure_complete"] = int(cov >= 1.0)
            row["score"] = float(res["scores"][yi, p])
            row["selected"] = int(res["idx"][p] == yi)
            rows.append(row)
        rows.append({"point": point["name"], "month": month, "year": "climatology",
                     **{k: (float(v[p]) if k not in EXPOSURE_FEATURES
                            else (float(v[p]) if bool(np.all(res["coverage"][:, p] >= 1.0)) else UNKNOWN))
                        for k, v in clim.items()},
                     "valid_hour_coverage": float(np.min(res["coverage"][:, p])),
                     "exposure_complete": int(bool(np.all(res["coverage"][:, p] >= 1.0))),
                     "score": "", "selected": ""})
    return rows


def rows_effective_weights(month, points, res):
    std = interannual_std(res["features"])
    rows = []
    total_w = sum(FEATURE_WEIGHTS.values())
    for p, point in enumerate(points):
        eff = {k: FEATURE_WEIGHTS[k] * float(std[k][p]) / FEATURE_SCALES[k] for k in FEATURES}
        total = sum(v for v in eff.values() if np.isfinite(v))
        for k in FEATURES:
            rows.append({
                "point": point["name"], "month": month, "feature": k,
                "interannual_std": float(std[k][p]), "scale": FEATURE_SCALES[k],
                "weight": FEATURE_WEIGHTS[k], "nominal_share": FEATURE_WEIGHTS[k] / total_w,
                "effective_share": eff[k] / total if total > 0 else float("nan"),
            })
    return rows


def rows_representativeness(month, points, res):
    clim = climatology(res["features"])
    rows = []
    for p, point in enumerate(points):
        for k in FEATURES:
            sel = _take(res["features"][k], res["idx"])[p]
            c = float(clim[k][p])
            sel_idx = int(res["idx"][p])
            sel_cov = float(res["coverage"][sel_idx, p]) if sel_idx >= 0 else 0.0
            clim_cov = float(np.min(res["coverage"][:, p]))
            dev = abs(float(sel) - c)
            rel = dev / abs(c) if c != 0.0 and np.isfinite(c) else float("nan")
            row = {
                "point": point["name"], "month": month, "feature": k,
                "selected_year": _year_of(sel_idx), "selected_value": float(sel),
                "climatology": c, "abs_deviation": dev, "rel_deviation": float(rel),
                "selected_valid_hour_coverage": sel_cov, "climatology_min_valid_hour_coverage": clim_cov,
                "exposure_complete": 1,
            }
            if k in EXPOSURE_FEATURES and (sel_cov < 1.0 or clim_cov < 1.0):
                row.update({"selected_value": UNKNOWN, "climatology": UNKNOWN, "abs_deviation": UNKNOWN,
                            "rel_deviation": UNKNOWN, "exposure_complete": 0})
            rows.append(row)
    return rows


def summarise_annual(per_month: dict[int, dict], points, months):
    """Annual exposure hours of assembled year vs long-term mean (complete years only).

    Missing (NaN) hours are not zero exposure.  The assembled total is UNKNOWN if any
    selected month has coverage < 100 %.  Long-term statistics use only candidate years
    whose months are all fully covered (``n_complete_years``); ``stats_status`` is
    INCOMPLETE when any year was excluded and UNKNOWN when none remains.
    """
    rows = []
    complete = list(months) == list(range(1, 13))
    for p, point in enumerate(points):
        year_ok = np.all([per_month[m]["coverage"][:, p] >= 1.0 for m in months], axis=0)
        for k in EXPOSURE_FEATURES:
            sel_ok = all(
                per_month[m]["idx"][p] >= 0 and per_month[m]["coverage"][per_month[m]["idx"][p], p] >= 1.0
                for m in months
            )
            assembled = (sum(float(_take(per_month[m]["features"][k], per_month[m]["idx"])[p]) for m in months)
                         if sel_ok else None)
            by_year = np.sum([per_month[m]["features"][k][:, p].astype(np.float64) for m in months], axis=0)
            by_year = np.where(year_ok, by_year, np.nan)
            n_ok = int(year_ok.sum())
            stats = n_ok > 0
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                mean = float(np.nanmean(by_year)) if stats else None
                std = float(np.nanstd(by_year, ddof=1)) if stats else None
                lo = float(np.nanmin(by_year)) if stats else None
                hi = float(np.nanmax(by_year)) if stats else None
            known = assembled is not None and mean is not None
            rows.append({
                "point": point["name"], "feature": k, "months": len(months), "complete_year": complete,
                "assembled_hours": assembled if assembled is not None else UNKNOWN,
                "long_term_mean_hours": mean if stats else UNKNOWN,
                "abs_deviation_h": abs(assembled - mean) if known else UNKNOWN,
                "rel_deviation": (abs(assembled - mean) / abs(mean) if mean else float("nan")) if known else UNKNOWN,
                "interannual_std_h": std if stats else UNKNOWN,
                "min_year_h": lo if stats else UNKNOWN, "max_year_h": hi if stats else UNKNOWN,
                "n_complete_years": n_ok, "n_candidate_years": len(YEARS),
                "min_valid_hour_coverage": float(min(per_month[m]["coverage"][:, p].min() for m in months)),
                "assembled_complete": int(assembled is not None),
                "stats_status": ("COMPLETE" if n_ok == len(YEARS) else "INCOMPLETE" if stats else UNKNOWN),
            })
    return rows


# --- sensitivity -----------------------------------------------------------

def sensitivity_month(month_data, res):
    """{variant: (idx, hours dict (3, points))} for all required variants."""
    feats = res["features"]
    std = interannual_std(feats)
    variants = [(n, feats, w, FEATURE_SCALES) for n, w in weight_variants()]
    variants.append(("local_interannual_std_scales", feats, FEATURE_WEIGHTS, std))
    out = {}
    for name, f, w, s in variants:
        idx, _, _ = select_year(score_candidates(f, w, s))
        out[name] = {"idx": idx, "hours": {k: _take(f[k], idx) for k in EXPOSURE_FEATURES}}
    return out


def _sel_complete(res, idx, p) -> bool:
    """True if a selection exists for point p and its selected year has 100 % valid-hour coverage."""
    i = int(idx[p])
    return i >= 0 and float(res["coverage"][i, p]) >= 1.0


def sensitivity_tables(per_month_sens, per_month, points, months):
    """Variant-vs-baseline tables with coverage carried into every exposure aggregate.

    A point-month delta is numeric only if BOTH the baseline and the variant selected a
    year with 100 % valid-hour coverage.  Per-point sums over the requested months are
    UNKNOWN unless every requested month is complete (``status`` COMPLETE/INCOMPLETE/
    UNKNOWN, with ``n_complete_months`` of ``n_requested_months``).  Summary means are
    UNKNOWN unless all requested point-months are complete; ``partial_*`` columns are
    valid-only means over ``n_complete_point_months`` (the actual denominator).
    """
    base = {m: {"idx": per_month[m]["idx"],
                "hours": {k: _take(per_month[m]["features"][k], per_month[m]["idx"]) for k in EXPOSURE_FEATURES}}
            for m in months}
    names = list(per_month_sens[months[0]])
    summary, per_point = [], []
    for name in names:
        changed = total = n_complete = 0
        requested = len(points) * len(months)
        dh = {k: [] for k in EXPOSURE_FEATURES}
        for p, point in enumerate(points):
            pchanged, pcomplete, psel = 0, 0, 0
            pdh = {k: 0.0 for k in EXPOSURE_FEATURES}
            for m in months:
                v, b = per_month_sens[m][name], base[m]
                if b["idx"][p] >= 0 and v["idx"][p] >= 0:
                    total += 1
                    psel += 1
                    diff = int(v["idx"][p] != b["idx"][p])
                    changed += diff
                    pchanged += diff
                if not (_sel_complete(per_month[m], b["idx"], p) and _sel_complete(per_month[m], v["idx"], p)):
                    continue  # missing/incomplete selection: no delta, never an initialised zero
                n_complete += 1
                pcomplete += 1
                for k in EXPOSURE_FEATURES:
                    d = float(v["hours"][k][p] - b["hours"][k][p])
                    dh[k].append(d)
                    pdh[k] += d
            pstatus = ("COMPLETE" if pcomplete == len(months) else "INCOMPLETE" if pcomplete else UNKNOWN)
            # selection changes count only where both selections exist; never a silent subset
            per_point.append({"variant": name, "point": point["name"],
                              "point_months_changed": pchanged if psel == len(months) else UNKNOWN,
                              "partial_point_months_changed": pchanged, "n_selection_months": psel,
                              "n_requested_months": len(months), "n_complete_months": pcomplete,
                              "status": pstatus,
                              **{f"delta_{k}_sum_over_months": (pdh[k] if pstatus == "COMPLETE" else UNKNOWN)
                                 for k in EXPOSURE_FEATURES}})
        sstatus = ("COMPLETE" if n_complete == requested else "INCOMPLETE" if n_complete else UNKNOWN)
        selection_status = ("COMPLETE" if total == requested else "INCOMPLETE" if total else UNKNOWN)
        row = {"variant": name, "point_months": total,
               "changed": changed if selection_status == "COMPLETE" else UNKNOWN,
               "fraction_changed": changed / total if selection_status == "COMPLETE" else UNKNOWN,
               "partial_changed": changed,
               "partial_fraction_changed": changed / total if total else UNKNOWN,
               "n_selection_point_months": total, "selection_status": selection_status,
               "n_requested_point_months": requested, "n_complete_point_months": n_complete,
               "status": sstatus}
        for k in EXPOSURE_FEATURES:
            arr = np.asarray(dh[k]) if dh[k] else None
            mean = float(np.mean(arr)) if arr is not None else UNKNOWN
            mabs = float(np.mean(np.abs(arr))) if arr is not None else UNKNOWN
            row[f"mean_delta_{k}"] = mean if sstatus == "COMPLETE" else UNKNOWN
            row[f"mean_abs_delta_{k}"] = mabs if sstatus == "COMPLETE" else UNKNOWN
            row[f"partial_mean_delta_{k}"] = mean
            row[f"partial_mean_abs_delta_{k}"] = mabs
        summary.append(row)
    return summary, per_point


# --- checks ----------------------------------------------------------------

def checks_month(month, month_data, points, res):
    t, td = month_data["temperature_c"], month_data["dewpoint_c"]
    feats, scores = res["features"], res["scores"]
    hours = t.shape[1]
    lons = np.array([p["lon"] for p in points])
    out = {"nan": [], "ties": [], "dtr": [], "magnus": [], "allnan": []}
    for p, point in enumerate(points):
        for yi, year in enumerate(YEARS):
            out["nan"].append({
                "point": point["name"], "month": month, "year": year, "hours": hours,
                "nan_temperature": int(np.isnan(t[yi, :, p]).sum()),
                "nan_dewpoint": int(np.isnan(td[yi, :, p]).sum()),
            })
        out["allnan"].append({"point": point["name"], "month": month,
                              "all_nan_scores": bool(res["all_nan"][p]),
                              "builder_status": "raises" if _builder_raises(month_data, p) else "ok"})
    # ties (earliest-year rule)
    for p, point in enumerate(points):
        col = scores[:, p]
        if res["all_nan"][p]:
            continue
        best = np.nanmin(col)
        tied = np.flatnonzero(np.abs(col - best) < TIE_TOLERANCE)
        gap = np.sort(col[np.isfinite(col)])
        second = float(gap[1] - gap[0]) if len(gap) > 1 else float("nan")
        row = {"point": point["name"], "month": month, "n_tied": int(len(tied)),
               "gap_to_second": second, "selected_year": _year_of(int(res["idx"][p])),
               "earliest_tied_year": YEARS[tied[0]]}
        if len(tied) > 1:
            row["latest_tied_year"] = YEARS[tied[-1]]
            for k in EXPOSURE_FEATURES:
                vals = feats[k][tied, p]
                row[f"max_spread_{k}"] = float(np.max(vals) - np.min(vals))
        out["ties"].append(row)
    # UTC vs local solar day DTR, and effect on selection
    dtr_loc = dtr_local_day(t, lons)
    feats_loc = compute_features(t, td, dtr=dtr_loc)
    idx_loc, _, _ = select_year(score_candidates(feats_loc))
    for p, point in enumerate(points):
        utc = feats["daily_temperature_range_mean_c"][:, p]
        out["dtr"].append({
            "point": point["name"], "month": month, "lon": point["lon"],
            "shift_hours": local_day_shift_hours(lons[p]),
            "mean_dtr_utc_c": float(np.nanmean(utc)), "mean_dtr_local_c": float(np.nanmean(dtr_loc[:, p])),
            "mean_diff_c": float(np.nanmean(dtr_loc[:, p] - utc)),
            "max_abs_diff_c": float(np.nanmax(np.abs(dtr_loc[:, p] - utc))),
            "selection_changed": bool(idx_loc[p] != res["idx"][p]),
        })
    # Magnus water vs mixed (ice below 0 degC).  Exposure counts are averaged over
    # complete-coverage candidate years only; n_complete_years/status label the subset
    # and with no complete year the values are UNKNOWN (never 0.0 from NaN comparisons).
    feats_ice = compute_features(t, td, rh_fn=rh_mixed, ah_fn=ah_mixed)
    idx_ice, _, _ = select_year(score_candidates(feats_ice))
    cov = res["coverage"]
    for p, point in enumerate(points):
        ok = cov[:, p] >= 1.0
        n_ok = int(ok.sum())
        status = "COMPLETE" if n_ok == len(YEARS) else "INCOMPLETE" if n_ok else UNKNOWN
        row = {"point": point["name"], "month": month,
               "n_complete_years": n_ok, "n_candidate_years": len(YEARS), "status": status,
               "hours_below_0c_mean_per_year": (float(np.mean(np.sum(t[ok, :, p] < 0, axis=1)))
                                                if n_ok else UNKNOWN),
               "selection_changed": bool(idx_ice[p] != res["idx"][p])}
        for k in ("hours_rh_ge_80", "hours_rh_ge_90"):
            if n_ok:
                row[f"{k}_water_mean"] = float(np.mean(feats[k][ok, p]))
                row[f"{k}_mixed_mean"] = float(np.mean(feats_ice[k][ok, p]))
                row[f"{k}_mean_diff"] = row[f"{k}_mixed_mean"] - row[f"{k}_water_mean"]
            else:
                row[f"{k}_water_mean"] = row[f"{k}_mixed_mean"] = row[f"{k}_mean_diff"] = UNKNOWN
        out["magnus"].append(row)
    return out


def _builder_raises(month_data, p) -> bool:
    sub = {k: v[:, :, p : p + 1] for k, v in month_data.items()}
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            _select_representative_year(sub)
        return False
    except ValueError:
        return True


def all_nan_guard_probe() -> dict:
    """Run the production selector on a synthetic all-NaN point and report what happens."""
    arr = np.full((len(YEARS), 24, 1), np.nan, dtype=np.float32)
    try:
        _select_representative_year({"temperature_c": arr, "dewpoint_c": arr.copy(),
                                     "surface_pressure_pa": arr.copy()})
        return {"raises": False}
    except Exception as exc:  # documenting behaviour, any type
        return {"raises": True, "type": type(exc).__name__, "message": str(exc)}


# ----------------------------------------------------------------------------
# output helpers
# ----------------------------------------------------------------------------

def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2, default=_json_default) + "\n", encoding="utf-8")


def _json_default(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(type(value))


def git_sha() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=SCRIPTS_DIR, capture_output=True,
                              text=True, check=True, timeout=10).stdout.strip() or None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None  # git unavailable / not a checkout: the manifest records commit_sha null


def write_manifest(out_dir: Path, command: str, args, points, months, files, started, extra=None):
    manifest = {
        "study": "AUTH-003 CEY20", "command": command,
        "commit_sha": git_sha(),
        "started_utc": started.isoformat(), "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "inputs": {"extension_root": str(args.extension_root), "legacy_root": str(args.legacy_root),
                   "points_file": str(args.points_file) if args.points_file else None},
        "parameters": {"months": months, "years": list(YEARS), "tie_tolerance": TIE_TOLERANCE,
                       "feature_weights": FEATURE_WEIGHTS, "feature_scales": FEATURE_SCALES,
                       "ice_coefficients": list(ICE_COEFFICIENTS), "ice_citation": ICE_CITATION_STATUS},
        "points": points, "outputs": sorted(files),
        "numpy_version": np.__version__, "python_version": sys.version.split()[0],
    }
    if extra:
        manifest.update(extra)
    write_json(out_dir / f"manifest_{command}.json", manifest)
    return manifest


def maybe_png(path: Path, labels, values, title, ylabel) -> bool:
    """Bar chart via matplotlib (a repo dependency); skipped if import fails or --no-png."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(range(len(labels)), values)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=60, ha="right", fontsize=7)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return True


# ----------------------------------------------------------------------------
# subcommands
# ----------------------------------------------------------------------------

def _prepare(args):
    months = builder._parse_range(args.months)
    sources = discover_sources(args.extension_root, args.legacy_root, months)
    points = resolve_points(args, sources[(YEARS[0], months[0])].path)
    args.output.mkdir(parents=True, exist_ok=True)
    return months, sources, points


def _iter_months(sources, months, points):
    indices = [p["index"] for p in points]
    for month in months:
        month_data = load_points_month(sources, month, indices)
        yield month, month_data, analyse_month(month_data)


def _finish(args, command, points, months, files, started, extra=None):
    write_manifest(args.output, command, args, points, months, files, started, extra)
    print(f"{command}: wrote {len(files)} files to {args.output}")
    return 0


def cmd_features(args):
    started = dt.datetime.now(dt.timezone.utc)
    months, sources, points = _prepare(args)
    rows = []
    for month, _, res in _iter_months(sources, months, points):
        rows += rows_features(month, points, res)
    write_csv(args.output / "features.csv", rows)
    write_json(args.output / "features.json", rows)
    return _finish(args, "features", points, months, ["features.csv", "features.json"], started)


def cmd_effective_weights(args):
    started = dt.datetime.now(dt.timezone.utc)
    months, sources, points = _prepare(args)
    rows = []
    for month, _, res in _iter_months(sources, months, points):
        rows += rows_effective_weights(month, points, res)
    summary = []
    for k in FEATURES:
        sel = [r for r in rows if r["feature"] == k]
        shares = np.array([r["effective_share"] for r in sel], dtype=float)
        summary.append({"feature": k, "nominal_share": FEATURE_WEIGHTS[k] / sum(FEATURE_WEIGHTS.values()),
                        "mean_effective_share": float(np.nanmean(shares)),
                        "min_effective_share": float(np.nanmin(shares)),
                        "max_effective_share": float(np.nanmax(shares))})
    files = ["effective_weights.csv", "effective_weights_summary.csv", "effective_weights_summary.json"]
    write_csv(args.output / files[0], rows)
    write_csv(args.output / files[1], summary)
    write_json(args.output / files[2], summary)
    if not args.no_png and maybe_png(args.output / "effective_weights.png", [s["feature"] for s in summary],
                                     [s["mean_effective_share"] for s in summary],
                                     "Mean effective weight share (all point-months)", "share"):
        files.append("effective_weights.png")
    return _finish(args, "effective-weights", points, months, files, started)


def cmd_representativeness(args):
    started = dt.datetime.now(dt.timezone.utc)
    months, sources, points = _prepare(args)
    rows, per_month = [], {}
    for month, _, res in _iter_months(sources, months, points):
        rows += rows_representativeness(month, points, res)
        per_month[month] = res
    annual = summarise_annual(per_month, points, months)
    files = ["representativeness.csv", "representativeness.json", "annual_exposure.csv", "annual_exposure.json"]
    write_csv(args.output / files[0], rows)
    write_json(args.output / files[1], rows)
    write_csv(args.output / files[2], annual)
    write_json(args.output / files[3], annual)
    return _finish(args, "representativeness", points, months, files, started,
                   {"annual_note": "annual figures are over the requested months; complete_year marks 12 months"})


def cmd_sensitivity(args):
    started = dt.datetime.now(dt.timezone.utc)
    months, sources, points = _prepare(args)
    sens, per_month = {}, {}
    for month, month_data, res in _iter_months(sources, months, points):
        sens[month] = sensitivity_month(month_data, res)
        per_month[month] = res
    summary, per_point = sensitivity_tables(sens, per_month, points, months)
    files = ["sensitivity_summary.csv", "sensitivity_summary.json", "sensitivity_points.csv"]
    write_csv(args.output / files[0], summary)
    write_json(args.output / files[1], summary)
    write_csv(args.output / files[2], per_point)
    if not args.no_png and maybe_png(args.output / "sensitivity_fraction_changed.png",
                                     [s["variant"] for s in summary], [s["fraction_changed"] if s["fraction_changed"] != UNKNOWN else float("nan") for s in summary],
                                     "Fraction of point-months with changed selected year", "fraction"):
        files.append("sensitivity_fraction_changed.png")
    return _finish(args, "sensitivity", points, months, files, started)


def cmd_checks(args):
    started = dt.datetime.now(dt.timezone.utc)
    months, sources, points = _prepare(args)
    acc = {"nan": [], "ties": [], "dtr": [], "magnus": [], "allnan": []}
    for month, month_data, res in _iter_months(sources, months, points):
        part = checks_month(month, month_data, points, res)
        for key in acc:
            acc[key] += part[key]
    names = {"nan": "checks_nan_completeness", "ties": "checks_ties", "dtr": "checks_dtr_local_day",
             "magnus": "checks_magnus_ice", "allnan": "checks_all_nan_guard"}
    files = []
    for key, stem in names.items():
        write_csv(args.output / f"{stem}.csv", acc[key])
        files.append(f"{stem}.csv")
    ties = acc["ties"]
    summary = {
        "candidates_with_nan": sum(1 for r in acc["nan"] if r["nan_temperature"] or r["nan_dewpoint"]),
        "candidates_total": len(acc["nan"]),
        "point_months_all_nan": sum(1 for r in acc["allnan"] if r["all_nan_scores"]),
        "point_months_tied": sum(1 for r in ties if r["n_tied"] > 1),
        "point_months_total": len(ties),
        "dtr_selection_changed": sum(1 for r in acc["dtr"] if r["selection_changed"]),
        "magnus_selection_changed": sum(1 for r in acc["magnus"] if r["selection_changed"]),
        "all_nan_guard_probe": all_nan_guard_probe(),
        "ice_coefficients": list(ICE_COEFFICIENTS), "ice_citation": ICE_CITATION_STATUS,
        "local_day_approximation": "shift = round(lon/15) h; only full local days inside the UTC month window; "
                                   "no equation of time, no DST, no time zones",
    }
    write_json(args.output / "checks_summary.json", summary)
    files.append("checks_summary.json")
    return _finish(args, "checks", points, months, files, started, {"checks_summary": summary})


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AUTH-003 CEY20 study package (no real data bundled).")
    sub = parser.add_subparsers(dest="command", required=True)
    commands = {"features": cmd_features, "effective-weights": cmd_effective_weights,
                "representativeness": cmd_representativeness, "sensitivity": cmd_sensitivity,
                "checks": cmd_checks}
    for name, func in commands.items():
        p = sub.add_parser(name)
        p.set_defaults(func=func)
        p.add_argument("--extension-root", type=Path, default=builder.DEFAULT_EXTENSION_ROOT)
        p.add_argument("--legacy-root", type=Path, default=builder.DEFAULT_LEGACY_ROOT)
        p.add_argument("--output", type=Path, required=True, help="output directory (created)")
        p.add_argument("--months", default="1-12")
        p.add_argument("--points-file", type=Path, help="CSV with columns name,(lat,lon | index)")
        p.add_argument("--point", action="append", metavar="LAT,LON", help="repeatable; nearest landpoint")
        p.add_argument("--point-index", action="append", type=int, help="repeatable landpoint index")
        p.add_argument("--no-png", action="store_true", help="CSV/JSON only")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

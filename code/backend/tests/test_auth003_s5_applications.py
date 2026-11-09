import datetime as dt
import json
import sys
from pathlib import Path

import netCDF4
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "research"))
import auth003_s5_applications as A  # noqa: E402


def test_context_counts_ties_and_uses_linear_median() -> None:
    c = A.context(2.0, [1.0, 2.0, 2.0, 3.0])
    assert c["percentile"] == 75.0 and c["years_median"] == 2.0 and c["years_min"] == 1.0 and c["n_years"] == 4


def test_tow_levels_use_closed_upper_bounds() -> None:
    assert [A.tow_level(x) for x in (0, 10, 10.5, 250, 251, 2500, 5500, 5501)] == [
        "tau1", "tau1", "tau2", "tau2", "tau3", "tau3", "tau4", "tau5"]


def test_tow_hours_need_rh_strictly_above_80_and_t_strictly_above_0() -> None:
    t = np.array([1.0, 0.0, 5.0, 5.0]); rh = np.array([81.0, 95.0, 80.0, 80.1])
    assert A.tow_hours(t, rh) == 2


def test_zero_crossing_days_are_strict() -> None:
    day_cross = np.r_[np.full(12, -1.0), np.full(12, 1.0)]
    day_zero = np.r_[np.full(12, 0.0), np.full(12, 3.0)]          # exactly 0 only: does not qualify
    day_cold = np.full(24, -5.0)
    assert A.zero_crossing_days(np.r_[day_cross, day_zero, day_cold]) == 1


def test_heat_pump_degree_hours_and_nested_counts() -> None:
    t = np.array([-10.0, -7.0, 2.0, 7.0, 20.0, 30.0])
    h = A.heat_pump(t)
    assert h["hdh_15_c_h"] == 25 + 22 + 13 + 8 and h["cdh_24_c_h"] == 6
    assert (h["hours_t_le_-7c"], h["hours_t_le_2c"], h["hours_t_le_7c"]) == (2, 3, 4)


def test_saturation_hours_use_one_degree_margin() -> None:
    assert A.saturation_hours(np.array([10.0, 10.0, 10.0]), np.array([9.0, 8.99, 10.0])) == 2


def test_duration_distance_is_zero_for_the_pooled_series_and_positive_for_a_shift() -> None:
    rng = np.random.default_rng(0)
    x = rng.normal(size=8760)
    q_pool = A.quantiles(x, A.duration_levels())
    assert A.duration_distance(x, q_pool) == 0.0
    assert A.duration_distance(x + 1.5, q_pool) == pytest.approx(1.5)
    assert A.quantiles(np.array([0.0, 10.0]), [0.5])[0] == 5.0          # linear estimator


def test_box_members_inclusive_bounds_and_longitude_wrap() -> None:
    lat = np.array([63.75, 64.75, 62.75, 64.76, 63.75, 63.75], np.float32)
    lon = np.array([291.5, 292.5, 290.5, 291.5, 289.0, 179.5], np.float32)
    assert A.box_members(lat, lon, 63.75, -68.5).tolist() == [0, 1, 2]
    assert A.box_members(np.array([0.0, 0.0]), np.array([-179.5, 179.75]), 0.0, 179.75).tolist() == [0, 1]


def test_monthly_point_values_compute_rh_hourly_and_reject_gaps() -> None:
    t = np.full((48, 2), 20.0, np.float32); td = np.full((48, 2), 10.0, np.float32)
    td[:10, 1] = 20.0                                              # 10 saturated hours at point 1
    v = A.monthly_point_values(t, td, 48)
    assert v["hours_rh_ge_80"].tolist() == [0.0, 10.0] and v["mean_t_c"].tolist() == [20.0, 20.0]
    assert v["mean_rh_pct"][1] > v["mean_rh_pct"][0]
    td[3, 0] = np.nan
    with pytest.raises(SystemExit):
        A.monthly_point_values(t, td, 48)
    with pytest.raises(SystemExit):
        A.monthly_point_values(t[:47], td[:47], 48)


def test_spatial_summary_reports_frozen_percentiles() -> None:
    s = A.spatial_summary(np.arange(11.0))
    assert (s["n_points"], s["min"], s["p10"], s["p50"], s["p90"], s["max"]) == (11, 0.0, 1.0, 5.0, 9.0, 10.0)


def test_application_rows_cover_every_statistic() -> None:
    rng = np.random.default_rng(2)
    years_t = rng.normal(5.0, 8.0, size=(4, 8760)).astype(np.float32); years_td = years_t - 2.0
    rows = A.application_rows("P", years_t[1], years_td[1], years_t, years_td)
    assert len(rows["a1"]) == 6 and len(rows["a2"]) == 5 and len(rows["a3"]) == 1 and len(rows["a4"]) == 2
    assert rows["a3"][0]["years_same_level"] >= 1                   # the selected year is one of the years


def _product(tmp: Path, lat, lon) -> dict:
    (tmp / "hourly").mkdir()
    (tmp / "hourly_manifest.json").write_text("{}", encoding="utf-8")
    files = {}
    for m in range(1, 13):
        path = tmp / "hourly" / A.PRODUCT_FILE.format(m)
        with netCDF4.Dataset(path, "w") as d:
            d.createDimension("time", A.MONTH_HOURS[m - 1]); d.createDimension("point", len(lat))
            d.createVariable("latitude", "f4", ("point",))[:] = lat
            d.createVariable("longitude", "f4", ("point",))[:] = lon
            for v in ("temperature_c", "dewpoint_c"):
                d.createVariable(v, "f4", ("time", "point"))[:] = 1.0
            d.createVariable("selected_source_year", "i2", ("point",))[:] = 2010
        st = path.stat()
        files[path.name] = {"bytes": st.st_size, "sha256": A.sha256_file(path),
                            "mtime_utc": dt.datetime.fromtimestamp(st.st_mtime, dt.timezone.utc).isoformat(timespec="seconds")}
    return {"hourly_manifest.json": {"sha256": A.sha256_file(tmp / "hourly_manifest.json")}, "month_files": files,
            "variables_used": ["temperature_c", "dewpoint_c", "latitude", "longitude", "selected_source_year"],
            "coordinates_sha256": A.coordinates_sha256(np.asarray(lat, np.float32), np.asarray(lon, np.float32))}


def test_verify_product_accepts_the_pinned_inventory_and_rejects_changes(tmp_path: Path) -> None:
    lat, lon = [63.75, 64.0], [291.5, 291.75]
    inputs = _product(tmp_path, lat, lon)
    la, lo = A.verify_product(tmp_path, inputs)
    assert la.tolist() == lat and lo.tolist() == lon
    for mutate in ("mtime", "coords", "manifest", "variable"):
        bad = json.loads(json.dumps(inputs))
        if mutate == "mtime":
            bad["month_files"]["cey20_landpoints_month05.nc"]["mtime_utc"] = "2000-01-01T00:00:00+00:00"
        elif mutate == "coords":
            bad["coordinates_sha256"] = "0" * 64
        elif mutate == "manifest":
            bad["hourly_manifest.json"]["sha256"] = "0" * 64
        else:
            bad["variables_used"].append("surface_pressure_pa")
        with pytest.raises(SystemExit):
            A.verify_product(tmp_path, bad)


def test_centre_gate_requires_exact_equality_at_the_selected_year_and_column() -> None:
    t = np.zeros((3, 24, 2), np.float32); td = t - 1.0
    t[2, :, 1] = np.arange(24); td[2, :, 1] = np.arange(24) - 2.0
    A.centre_gate("X", t[2, :, 1], td[2, :, 1], t, td, 2, 1)
    with pytest.raises(SystemExit):
        A.centre_gate("X", t[2, :, 1], td[2, :, 1], t, td, 1, 1)          # wrong year
    with pytest.raises(SystemExit):
        A.centre_gate("X", t[2, :, 1] + np.float32(0.01), td[2, :, 1], t, td, 2, 1)


def test_duration_curves_band_contains_every_actual_year() -> None:
    rng = np.random.default_rng(5)
    years = rng.normal(size=(3, 8760)).astype(np.float32)
    rows = A.duration_curves("P", years[0], years)
    assert len(rows) == 8760 and rows[0]["exceedance"] == pytest.approx(1 - 0.5 / 8760)
    assert all(r["years_min_c"] <= r["cey20_c"] <= r["years_max_c"] for r in rows)

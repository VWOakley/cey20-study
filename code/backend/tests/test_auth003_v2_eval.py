import json
import sys
from pathlib import Path

import netCDF4
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "research"))
import auth003_s3 as R  # noqa: E402
import auth003_study as S  # noqa: E402
import auth003_v2_eval as V  # noqa: E402

SM = V.load_smoothing()
HOURS = V.HOURS


def _series(n_points=3, seed=0):
    rng = np.random.default_rng(seed)
    hours = np.arange(HOURS)
    t = (10 + 8 * np.sin(2 * np.pi * hours / 24))[:, None] + rng.normal(0, 0.3, (HOURS, n_points))
    td = t - 3 - rng.uniform(0, 2, (HOURS, n_points))
    p = 100000 + rng.normal(0, 50, (HOURS, n_points))
    return {"temperature_c": t.astype(np.float32), "dewpoint_c": td.astype(np.float32),
            "surface_pressure_pa": p.astype(np.float32)}


def _years_all_different(n_points=3):
    return np.tile(np.arange(2006, 2018, dtype=np.int32)[:, None], (1, n_points))   # 12 different source years


def test_boundary_hours_and_wrap():
    b = V.boundary_hours()
    assert b[0] == 744 and b[1] == 744 + 672 and b[-1] == 0 and len(b) == 12


def test_join_and_local_max_step_are_cyclic():
    s = np.zeros(HOURS, np.float32)
    s[744:] = 5.0                                    # step of 5 at the Jan->Feb join
    assert V.join_step(s, 744) == 5.0 and V.local_max_step(s, 744) == 5.0
    s2 = np.zeros(HOURS, np.float32)
    s2[744 + 6] = 3.0                                # increments touching x[b+6] lie at k=6 (in) and k=7 (out)
    assert V.local_max_step(s2, 744) == 3.0 and V.join_step(s2, 744) == 0.0
    s3 = np.zeros(HOURS, np.float32)
    s3[744 - 8] = 9.0                                # x[b-8] only touches increments k=-8, -7: outside M_b
    assert V.local_max_step(s3, 744) == 0.0
    w = np.zeros(HOURS, np.float32); w[-1] = -2.0     # Dec 31 23 UTC -> Jan 1 00 UTC
    assert V.join_step(w, 0) == 2.0 and V.local_max_step(w, 0) == 2.0


def test_expected_v2_smooths_cross_year_joins_and_respects_mask_bound():
    rec = _series()
    rec["temperature_c"][744:] += 6.0                 # artificial Jan->Feb step
    exp_, mask = V.expected_v2(rec, _years_all_different(), SM)
    for v in V.VARS:
        assert mask[v].sum(axis=0).max() <= V.MAX_MASK
        changed = exp_[v] != rec[v]
        assert not np.any(changed & ~mask[v])         # modifications only inside the mask
    b = 744
    x = exp_["temperature_c"][:, 0].astype(np.float64)
    r = rec["temperature_c"][:, 0].astype(np.float64)
    s = 0.5 * ((r[b - 1] - r[b - 2]) + (r[b + 1] - r[b]))
    assert abs((x[b] - x[b - 1]) - s) < 1e-3          # join step reduced to the mean adjacent step
    assert np.all(exp_["dewpoint_c"][mask["temperature_c"]] <= exp_["temperature_c"][mask["temperature_c"]])


def test_expected_v2_leaves_consecutive_same_year_boundaries_unchanged():
    rec = _series()
    years = np.full((12, 3), 2010, dtype=np.int32)    # same non-leap year everywhere except Dec->Jan
    exp_, mask = V.expected_v2(rec, years, SM)
    inner = np.zeros(HOURS, bool)
    for b in V.boundary_hours()[:-1]:
        inner[b - 6:b + 6] = True
    assert not mask["temperature_c"][inner].any()
    assert np.array_equal(exp_["temperature_c"][inner], rec["temperature_c"][inner])
    assert mask["temperature_c"][:6].all() and mask["temperature_c"][-6:].all()      # Dec->Jan is never consecutive
    leap = np.full((12, 3), 2008, dtype=np.int32)
    _, mask_leap = V.expected_v2(rec, leap, SM)       # leap Feb->Mar is not consecutive (29 Feb removed)
    b = V.boundary_hours()[1]
    assert mask_leap["temperature_c"][b - 6:b + 6].all()


def test_gates_pass_on_exact_reproduction_and_fail_on_tampering():
    rec = _series()
    years = _years_all_different()
    exp_, mask = V.expected_v2(rec, years, SM)
    prod = {v: exp_[v].copy() for v in V.VARS}
    report = V.gate_compare(prod, rec, exp_, mask)
    assert V.gates_pass(report) == []
    outside = {v: prod[v].copy() for v in V.VARS}
    outside["temperature_c"][3000, 1] += 0.01
    assert any("temperature_c" in e for e in V.gates_pass(V.gate_compare(outside, rec, exp_, mask)))
    inside = {v: prod[v].copy() for v in V.VARS}
    inside["surface_pressure_pa"][744, 0] += 1.0
    r = V.gate_compare(inside, rec, exp_, mask)
    assert r["surface_pressure_pa"]["inside_support_mismatches_vs_reproduction"] == 1 and V.gates_pass(r)


def test_td_above_t_outside_mask_is_reported_not_gated():
    rec = _series()
    rec["dewpoint_c"][3000, 2] = rec["temperature_c"][3000, 2] + 0.5     # source-data Td > T, outside any window
    exp_, mask = V.expected_v2(rec, _years_all_different(), SM)
    report = V.gate_compare({v: exp_[v].copy() for v in V.VARS}, rec, exp_, mask)
    assert V.gates_pass(report) == []
    assert report["td_gt_t_outside_support_per_point"] == [0, 0, 1]
    assert report["td_minus_t_outside_support_max"] == pytest.approx(0.5, abs=1e-5)


def test_td_above_t_inside_mask_fails_gate():
    rec = _series()
    exp_, mask = V.expected_v2(rec, _years_all_different(), SM)
    prod = {v: exp_[v].copy() for v in V.VARS}
    prod["dewpoint_c"][744, 0] = prod["temperature_c"][744, 0] + 1.0
    errs = V.gates_pass(V.gate_compare(prod, rec, exp_, mask))
    assert any("Td > T inside" in e for e in errs)


def test_monthly_counts_and_means_match_builder_features():
    s = _series(2, seed=3)
    counts = V.monthly_counts(s["temperature_c"], s["dewpoint_c"])
    starts = np.cumsum([0] + list(V.H.MONTH_HOURS))
    for m in range(12):
        sl = slice(starts[m], starts[m + 1])
        ref = R.counts(s["temperature_c"][None, sl], s["dewpoint_c"][None, sl])
        for k in R.COUNT_KEYS:
            assert np.array_equal(counts[k][m], ref[k][0])
    mt, mrh = V.monthly_means(s["temperature_c"], s["dewpoint_c"])
    f = S.compute_features(s["temperature_c"][None, :744], s["dewpoint_c"][None, :744])
    assert mt[0, 1] == pytest.approx(float(f["temperature_mean_c"][0, 1]))
    assert mrh[0, 1] == pytest.approx(float(f["relative_humidity_mean_pct"][0, 1]))


def test_monthly_target_rows_tolerances():
    pts = [{"name": "A"}]
    mt = np.full((12, 1), 10.5); ref = np.full((12, 1), 10.0)
    rows = V.monthly_target_rows("v2", mt, np.full((12, 1), 52.0), ref, np.full((12, 1), 50.0),
                                 np.full((12, 1), 2010), pts)
    assert all(r["pass_t"] for r in rows) and all(r["pass_rh"] for r in rows)
    rows = V.monthly_target_rows("v2", mt + 0.01, np.full((12, 1), 52.1), ref, np.full((12, 1), 50.0),
                                 np.full((12, 1), 2010), pts)
    assert not any(r["pass_t"] for r in rows) and not any(r["pass_rh"] for r in rows)


def test_verify_manifest_requires_version_commit_and_clean_tree(tmp_path):
    good = {"version": V.EXPECTED_VERSION, "generating_commit": V.EXPECTED_COMMIT, "working_tree_clean_at_start": True}
    (tmp_path / "hourly_manifest.json").write_text(json.dumps(good), encoding="utf-8")
    assert V.verify_manifest(tmp_path)["version"] == V.EXPECTED_VERSION
    for change in ({"generating_commit": "0" * 40}, {"version": "v1"}, {"working_tree_clean_at_start": False}):
        (tmp_path / "hourly_manifest.json").write_text(json.dumps(dict(good, **change)), encoding="utf-8")
        with pytest.raises(SystemExit):
            V.verify_manifest(tmp_path)


def _month_file(path, units="degree_Celsius", step=1, time_units=V.TIME_UNITS, month=1, offset=None, dtype="f4"):
    hours = V.H.MONTH_HOURS[month - 1]
    start = sum(V.H.MONTH_HOURS[:month - 1]) if offset is None else offset
    with netCDF4.Dataset(path, "w") as d:
        d.createDimension("time", hours); d.createDimension("point", 3)
        tv = d.createVariable("time", "i4", ("time",)); tv.units = time_units; tv[:] = start + np.arange(hours) * step
        for name, val in (("latitude", [1.0, 2.0, 3.0]), ("longitude", [10.0, 20.0, 30.0])):
            d.createVariable(name, "f4", ("point",))[:] = val
        for v in V.VARS:
            var = d.createVariable(v, dtype, ("time", "point"))
            var.units = "Pa" if v == "surface_pressure_pa" else units
            var[:] = 0.0


def test_verify_month_file_checks_units_time_and_coordinates(tmp_path):
    f = tmp_path / "m.nc"
    _month_file(f)
    V.verify_month_file(f, 1, [0, 2], [(1.0, 10.0), (3.0, 30.0)])
    with pytest.raises(SystemExit):
        V.verify_month_file(f, 1, [0, 2], [(1.0, 10.0), (2.0, 20.0)])
    for kwargs in ({"units": "K"}, {"step": 2}, {"time_units": "hours since 1970-01-01 00:00:00"}):
        g = tmp_path / f"bad{len(list(tmp_path.iterdir()))}.nc"
        _month_file(g, **kwargs)
        with pytest.raises(SystemExit):
            V.verify_month_file(g, 1, [0], [(1.0, 10.0)])


def test_verify_pin_rejects_changed_inventory(tmp_path):
    inv = tmp_path / "inv.json"; inv.write_text("{}", encoding="utf-8")
    import hashlib
    pin = {name: hashlib.sha256(R._lf(path.read_bytes())).hexdigest() for name, path in V.PINNED_FILES.items()}
    pin[V.INPUTS_KEY] = hashlib.sha256(b"{}").hexdigest()
    V.verify_pin(pin, inv)
    inv.write_text('{"x": 1}', encoding="utf-8")
    with pytest.raises(SystemExit):
        V.verify_pin(pin, inv)


def test_smoothing_constants_match_amendment():
    assert (SM.N, SM.W, SM.B) == (6, 14, 7) and V.MAX_MASK == 144


def test_verify_month_file_requires_absolute_axis_and_float32(tmp_path):
    good = tmp_path / "feb.nc"
    _month_file(good, month=2)
    V.verify_month_file(good, 2, [0], [(1.0, 10.0)])
    for i, kwargs in enumerate(({"month": 2, "offset": 0}, {"dtype": "f8"})):
        bad = tmp_path / f"bad_axis{i}.nc"
        _month_file(bad, **kwargs)
        with pytest.raises(SystemExit):
            V.verify_month_file(bad, kwargs.get("month", 1), [0], [(1.0, 10.0)])


def test_gates_refuse_float64_instead_of_coercing():
    rec = _series()
    exp_, mask = V.expected_v2(rec, _years_all_different(), SM)
    prod = {v: exp_[v].astype(np.float64) for v in V.VARS}
    prod["temperature_c"][3000, 0] += 1e-9            # rounds to the same float32 value
    with pytest.raises(SystemExit):
        V.gate_compare(prod, rec, exp_, mask)


def test_eligibility_masks_follow_source_windows():
    rec = _series()
    b = V.boundary_hours()[0]
    rec["temperature_c"][b + 2, 0] = np.nan          # T/Td ineligible at point 0, pressure still eligible
    rec["surface_pressure_pa"][b - 3, 1] = np.nan    # pressure ineligible at point 1, T/Td eligible
    exp_, mask = V.expected_v2(rec, _years_all_different(), SM)
    sup = slice(b - 6, b + 6)
    assert not mask["temperature_c"][sup, 0].any() and mask["surface_pressure_pa"][sup, 0].all()
    assert mask["temperature_c"][sup, 1].all() and not mask["surface_pressure_pa"][sup, 1].any()
    assert mask["temperature_c"][sup, 2].all() and mask["surface_pressure_pa"][sup, 2].all()
    assert np.array_equal(exp_["surface_pressure_pa"][sup, 1], rec["surface_pressure_pa"][sup, 1], equal_nan=True)


def test_nonpositive_pressure_window_is_skipped():
    rec = _series()
    b = V.boundary_hours()[0]
    rec["surface_pressure_pa"][b:, 0] -= 200000.0     # huge step: the ramp would make values non-positive
    rec["surface_pressure_pa"][b:, 0] = np.maximum(rec["surface_pressure_pa"][b:, 0], 1.0)
    exp_, mask = V.expected_v2(rec, _years_all_different(), SM)
    elig = SM.eligibility({v: rec[v][(b - 7 + np.arange(14)) % HOURS] for v in V.VARS}, 1, np.array([2006] * 3),
                          np.array([2007] * 3))
    assert bool(mask["surface_pressure_pa"][b, 0]) == bool(elig["pressure"][0])


@pytest.mark.parametrize("bi", list(range(12)))
def test_support_edges_and_bitwise_reproduction_per_boundary(bi):
    rec = _series(seed=bi)
    years = _years_all_different()
    exp_, mask = V.expected_v2(rec, years, SM)
    b = V.boundary_hours()[bi]
    rows = (b - 7 + np.arange(14)) % HOURS
    for v in V.VARS:
        assert np.array_equal(exp_[v][rows[[0, 13]]], rec[v][rows[[0, 13]]])       # x[b-7], x[b+6] unchanged
        assert mask[v][rows[1:13]].all() and not mask[v][rows[[0, 13]]].any()
    out, _ = SM.smooth_boundary({v: rec[v][rows].copy() for v in V.VARS}, bi + 1, years[bi], years[(bi + 1) % 12])
    for v in V.VARS:
        assert np.array_equal(exp_[v][rows[1:13]], out[v][1:13])                    # bit-for-bit

from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "research"))
import auth003_s3_hourly as H  # noqa: E402


def test_month_hours_drop_leap_day() -> None:
    assert H.MONTH_HOURS[1] == 28 * 24 and sum(H.MONTH_HOURS) == 8760


def test_runs_spells_and_inner_gaps_only() -> None:
    #       F F T T T F F T F T T F
    mask = [0, 0, 1, 1, 1, 0, 0, 1, 0, 1, 1, 0]
    spells, gaps = H.runs(np.asarray(mask, dtype=bool))
    assert spells == [3, 1, 2]
    assert gaps == [2, 1]                     # leading and trailing dry runs are not gaps


def test_runs_edge_cases() -> None:
    assert H.runs(np.zeros(5, dtype=bool)) == ([], [])
    assert H.runs(np.ones(5, dtype=bool)) == ([5], [])


def test_spell_stats_undefined_values_are_none_not_zero() -> None:
    s = H.spell_stats(np.full(10, 50.0), 80.0)
    assert s["n_spells"] == 0 and s["mean_spell_h"] is None and s["median_gap_h"] is None


def test_joint_hist_normalised_and_clipped() -> None:
    h = H.joint_hist(np.asarray([-80.0, 0.0, 80.0]), np.asarray([100.0, 50.0, 0.0]))
    assert h.sum() == pytest.approx(1.0)
    assert h[0, -1] > 0 and h[-1, 0] > 0      # out-of-range T in edge bins, RH 100 in last bin


def test_distances() -> None:
    p = np.asarray([0.5, 0.5, 0.0]); q = np.asarray([0.0, 0.5, 0.5])
    assert H.total_variation(p, q) == pytest.approx(0.5)
    assert H.hellinger(p, p) == 0.0
    assert H.hellinger(np.asarray([1.0, 0.0]), np.asarray([0.0, 1.0])) == pytest.approx(1.0)


def test_humid_temperature_bands() -> None:
    t = np.asarray([-5.0, 5.0, 15.0, 25.0, 35.0, 99.0])
    rh = np.asarray([90.0, 90.0, 90.0, 90.0, 90.0, 10.0])
    r = H.humid_temperature(t, rh)
    assert r["n_humid_hours"] == 5 and r["mean_t_humid_c"] == pytest.approx(15.0)
    assert r["share_t_lt_0"] == pytest.approx(0.2) and r["share_t_30_inf"] == pytest.approx(0.2)


def test_context_percentile_and_none_handling() -> None:
    c = H.context(2.0, [1.0, 2.0, 3.0, None])
    assert c["percentile"] == pytest.approx(2 / 3) and c["n_years"] == 3 and c["years_median"] == 2.0
    assert H.context(None, [1.0])["percentile"] is None


def test_assemble_takes_selected_year_per_month_and_point() -> None:
    months = []
    for m, hours in enumerate(H.MONTH_HOURS):
        a = np.zeros((3, hours, 2), dtype=np.float32)
        for y in range(3):
            a[y, :, 0] = 100 * m + y
            a[y, :, 1] = 100 * m + 10 + y
        months.append(a)
    idx = np.asarray([[m % 3, (m + 1) % 3] for m in range(12)], dtype=np.int16)
    s = H.assemble(months, idx)
    assert s.shape == (8760, 2)
    assert s[0, 0] == 0 and s[0, 1] == 11                          # Jan: years 0 / 1
    assert s[H.MONTH_HOURS[0], 0] == 101                            # Feb point 0 -> year 1
    assert s[-1, 1] == 1100 + 10 + 0                                # Dec point 1 -> (11+1)%3 = 0


def test_boundary_jump_and_reference_window() -> None:
    series = np.zeros(8760); b = H.MONTH_HOURS[0]
    series[b:] = 5.0
    assert H.boundary_jump(series, 1) == 5.0
    years = np.tile(np.arange(8760, dtype=float), (2, 1))           # slope 1 everywhere
    ref = H.boundary_reference(years, 1)
    assert ref.size == 2 * 2 * H.BOUNDARY_WINDOW_H and np.all(ref == 1.0)
    assert H.percentile_of(5.0, ref) == 1.0 and H.percentile_of(0.5, ref) == 0.0


def test_wrap_reference_uses_consecutive_year_pairs() -> None:
    years = np.stack([np.full(8760, 0.0), np.full(8760, 3.0), np.full(8760, 3.0)])
    ref = H.wrap_reference(years)
    assert ref.size == 2 * 2 * H.BOUNDARY_WINDOW_H
    assert ref.max() == 3.0 and np.count_nonzero(ref) == 1           # only the 0 -> 3 jump of pair (0, 1)


def test_verify_pin_covers_hourly_script(tmp_path, monkeypatch) -> None:
    f = tmp_path / "x.py"; f.write_bytes(b"a\r\n")
    monkeypatch.setattr(H, "PINNED_FILES", {"auth003_s3_hourly.py": f})
    import hashlib
    H.verify_pin({"auth003_s3_hourly.py": hashlib.sha256(b"a\n").hexdigest()})
    with pytest.raises(SystemExit):
        H.verify_pin({})
    assert "auth003_s3_hourly.py" in dict(H.R.PINNED_FILES, **{"auth003_s3_hourly.py": 0})


def test_read_s3_selection_requires_all_point_months(tmp_path) -> None:
    pts = [{"name": "A"}, {"name": "B"}]
    f = tmp_path / "m.csv"
    rows = ["point,month,selected_year"] + [f"{p},{m},2010" for p in "AB" for m in range(1, 13)]
    f.write_text("\n".join(rows), encoding="utf-8")
    idx = H.read_s3_selection(f, pts)
    assert idx.shape == (12, 2) and np.all(idx == H.S.YEARS.index(2010))
    f.write_text("\n".join(rows[:-1]), encoding="utf-8")
    with pytest.raises(SystemExit):
        H.read_s3_selection(f, pts)


def test_verify_s3_selection_file_rejects_substitute(tmp_path) -> None:
    import hashlib
    f = tmp_path / "targets_monthly.csv"; f.write_bytes(b"point,month,selected_year\r\nA,1,2010\r\n")
    pin = {H.S3_SELECTION_KEY: hashlib.sha256(b"point,month,selected_year\nA,1,2010\n").hexdigest()}
    H.verify_s3_selection_file(f, pin)                     # CRLF normalised
    f.write_bytes(b"point,month,selected_year\nA,1,2011\n")
    with pytest.raises(SystemExit):
        H.verify_s3_selection_file(f, pin)

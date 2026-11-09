import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "research"))
import auth003_s4_fs as F  # noqa: E402
import auth003_study as S  # noqa: E402


def test_fs_matches_hand_computed_values() -> None:
    # pool {1,2,3,4}; year 0 = {1,2}: (|.5-.25| + |1-.5|)/2 = .375; year 1 = {3,4}: (|.5-.75| + 0)/2 = .125
    assert np.allclose(F.fs_statistic(np.array([[1.0, 2.0], [3.0, 4.0]])), [0.375, 0.125])


def test_fs_ties_use_right_continuous_cdfs_at_every_value() -> None:
    # pool {1,1,1,2}; year 0 = {1,1}: F_cand(1)=1, F_lt(1)=.75 at both repeats -> .25
    # year 1 = {1,2}: |.5-.75| and |1-1| -> .125
    assert np.allclose(F.fs_statistic(np.array([[1.0, 1.0], [1.0, 2.0]])), [0.25, 0.125])


def test_fs_is_zero_for_constant_series_and_identical_distributions() -> None:
    assert np.all(F.fs_statistic(np.full((5, 31), 7.0)) == 0.0)
    rng = np.random.default_rng(1)
    base = rng.normal(size=30)
    same = np.stack([rng.permutation(base) for _ in range(4)])
    assert np.allclose(F.fs_statistic(same), 0.0)


def test_fs_rejects_non_finite_values() -> None:
    with pytest.raises(SystemExit):
        F.fs_statistic(np.array([[1.0, np.nan], [2.0, 3.0]]))


def test_weights_are_the_frozen_spec_values() -> None:
    a, b = F.WEIGHTS["FS-A"], F.WEIGHTS["FS-B"]
    assert set(a) == set(F.THERMO) and abs(sum(a.values()) - 1) < 1e-12
    assert [a[k] * 8 for k in F.THERMO] == [1, 1, 2, 1, 1, 2]
    assert set(b) == set(F.THERMO + F.EXPOSURE) and abs(sum(b.values()) - 1) < 1e-12
    assert all(abs(b[k] - a[k] / 2) < 1e-12 for k in F.THERMO) and all(b[k] == 1 / 6 for k in F.EXPOSURE)


def test_minimum_ws_takes_the_earliest_year_on_ties() -> None:
    assert F.select_min(np.array([0.3, 0.1, 0.1, 0.2])) == 1


def test_daily_indices_on_utc_and_shifted_days() -> None:
    hours = np.arange(72, dtype=np.float64)
    t = np.stack([hours, hours + 100.0])                   # (years=2, 72 h)
    td = t - 1.0                                          # T - Td = 1 -> every hour counts for h_dpd2
    d = F.daily_indices(t, td)
    assert d["t_max"].shape == (2, 3)
    assert d["t_max"][0].tolist() == [23.0, 47.0, 71.0] and d["t_min"][0].tolist() == [0.0, 24.0, 48.0]
    assert d["td_mean"][1, 0] == pytest.approx(100.0 + 11.5 - 1.0)
    assert d["h_dpd2"][0].tolist() == [24.0, 24.0, 24.0]
    shifted = F.daily_indices(t, td, start=5)              # full days from hour 5: 2 days, edges dropped
    assert shifted["t_min"][0].tolist() == [5.0, 29.0]
    rh = S._relative_humidity_from_dewpoint(t[:, :24], td[:, :24])
    assert d["h_rh80"][0, 0] == np.count_nonzero(rh[0] >= 80.0)


def test_local_starts_match_the_study_shift() -> None:
    assert F.local_starts(np.array([0.0, 103.75, -122.25, -78.5])) == [0, (-7) % 24, 8, 5]


def test_select_fs_prefers_the_year_closest_to_the_long_term_distribution() -> None:
    rng = np.random.default_rng(3)
    years, hours = 6, 24 * 10
    base = rng.normal(15.0, 3.0, size=hours)
    t = np.stack([base + off for off in (3.0, -2.0, 0.0, 1.5, -1.0, 2.5)])[:, :, None]   # (years, hours, 1)
    td = t - 4.0
    idx, ws = F.select_fs(t, td, F.WEIGHTS["FS-A"])
    assert ws.shape == (years, 1) and int(idx[0]) == int(np.argmin(ws[:, 0]))
    assert int(idx[0]) not in (0, 1)                       # the two most shifted years are never chosen
    assert ws[0, 0] == ws[:, 0].max() or ws[1, 0] == ws[:, 0].max()


def test_d5_selection_rows_name_every_changed_point_month() -> None:
    base = np.array([[0, 1], [2, 3]], dtype=np.int16); var = np.array([[0, 4], [2, 3]], dtype=np.int16)
    rows = F.d5_selection_rows("FS-A", "local_solar_day", base, var, [{"name": "P"}, {"name": "Q"}])
    assert len(rows) == 4 and [r for r in rows if r["selection_changed"]] == [
        {"method": "FS-A", "variant": "local_solar_day", "point": "Q", "month": 1,
         "baseline_year": S.YEARS[1], "variant_year": S.YEARS[4], "selection_changed": True}]

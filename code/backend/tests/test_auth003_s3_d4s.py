import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "research"))
import auth003_s3_d4s as D  # noqa: E402
import auth003_s3_hourly as H  # noqa: E402


def _hour_of_day_pattern(n_years: int) -> np.ndarray:
    """Value = hour of day, so every 23->00 change is 23 and every other change is 1."""
    return np.tile((np.arange(8760) % 24).astype(float), (n_years, 1))


def test_midnight_reference_uses_only_23_to_00_transitions() -> None:
    years = _hour_of_day_pattern(3)
    ref = D.midnight_reference(years, 1, (2006, 2007, 2009))
    assert ref.size == 3 * (2 * D.MIDNIGHTS_EACH_SIDE + 1)
    assert np.all(ref == 23.0)                                      # no diurnal 1-unit steps


def test_midnight_reference_is_centred_on_the_boundary() -> None:
    years = np.zeros((1, 8760))
    b = int(np.sum(H.MONTH_HOURS[:3]))
    years[0, b:] = 1.0                                              # step exactly at the Mar->Apr boundary
    ref = D.midnight_reference(years, 3, (2006,))
    assert np.count_nonzero(ref) == 1
    years[0, :] = 0.0
    years[0, b + 24 * D.MIDNIGHTS_EACH_SIDE:] = 1.0                 # last midnight inside the window
    assert np.count_nonzero(D.midnight_reference(years, 3, (2006,))) == 1
    years[0, :] = 0.0
    years[0, b + 24 * (D.MIDNIGHTS_EACH_SIDE + 1):] = 1.0           # first midnight outside
    assert np.count_nonzero(D.midnight_reference(years, 3, (2006,))) == 0


def test_leap_year_feb_mar_join_excluded() -> None:
    years = _hour_of_day_pattern(3)
    ref = D.midnight_reference(years, 2, (2007, 2008, 2009))       # 2008 is a leap year
    assert ref.size == 3 * (2 * D.MIDNIGHTS_EACH_SIDE + 1) - 1
    ref_other = D.midnight_reference(years, 3, (2007, 2008, 2009))  # only Feb->Mar is affected
    assert ref_other.size == 3 * (2 * D.MIDNIGHTS_EACH_SIDE + 1)


def test_non_finite_values_dropped() -> None:
    years = _hour_of_day_pattern(2)
    b = int(np.sum(H.MONTH_HOURS[:1]))
    years[0, b] = np.nan
    ref = D.midnight_reference(years, 1, (2006, 2007))
    assert ref.size == 2 * (2 * D.MIDNIGHTS_EACH_SIDE + 1) - 1 and np.all(np.isfinite(ref))


def test_wrap_reference_consecutive_pairs_and_midnights_only() -> None:
    years = _hour_of_day_pattern(3)
    years[1] += 100.0                                               # year 1 differs by 100 from its neighbours
    ref = D.midnight_wrap_reference(years)
    assert ref.size == 2 * (2 * D.MIDNIGHTS_EACH_SIDE + 1)
    # Each pair contributes one cross-year midnight: |0 - (23+100)| and |100 - 23|; all others are 23.
    assert sorted(set(ref.tolist())) == [23.0, 77.0, 123.0]
    assert np.count_nonzero(ref != 23.0) == 2


def test_verify_pin_covers_d4s_script(tmp_path) -> None:
    with pytest.raises(SystemExit):
        D.verify_pin({})
    assert "auth003_s3_d4s.py" in D.PINNED_FILES and "auth003_s3_hourly.py" in D.PINNED_FILES
